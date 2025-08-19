# handlers/enforce_requirements.py
# Requirement enforcement:
# - Reminders: spicy/flirty DMs to DM-ready users who didn't meet (either $20 OR 4 games)
# - Monthly sweep (1st of month): remove non-compliant members, clear DM-ready, and post a report
# - Audit logs: success/fail & summaries to REQ_AUDIT_CHAT_ID
# - Manual commands: /reqstatus, /reqremind [test|run], /reqsweep, /reqreport
#
# ENV:
#   SANCTUARY_CHAT_ID      = -100XXXXXXXX (main group)
#   OWNER_ID               = 6964994611   (you)
#   REQ_AUDIT_CHAT_ID      = -4702726782  (logs group)  (optional; falls back to OWNER_ID)
#   REQ_AUDIT_VERBOSE      = 0/1          (per-user lines during batches)
#   REQ_REQUIRE_DOLLARS    = 20           (default 20)
#   REQ_REQUIRE_GAMES      = 4            (default 4)
#   TZ                     = America/Los_Angeles (optional; else system tz)
#
# Notes:
# - We only DM users who are DM-ready (per ReqStore).
# - Exemptions are respected (global or per group) via ReqStore.
# - Kick = ban + quick unban to force leave; then DM-ready is cleared.
# - Data source for spend/games is ReqStore's current month bucket.

import os
import asyncio
import math
from datetime import datetime
from typing import Optional, Tuple, Dict, List

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserIsBlocked, PeerIdInvalid, RPCError, BadRequest

try:
    import pytz
    TZ = os.getenv("TZ", "America/Los_Angeles")
    _TZ = pytz.timezone(TZ)
except Exception:
    _TZ = None

# ---- ReqStore ----
try:
    from req_store import ReqStore, _month_key  # your provided store helper
except Exception:
    ReqStore = None
    def _month_key(ts: Optional[float] = None) -> str:
        now = datetime.utcnow()
        return f"{now.year:04d}-{now.month:02d}"

_store = ReqStore() if ReqStore else None

# ---- ENV / Config ----
def _to_int(s: Optional[str]) -> Optional[int]:
    try:
        return int(str(s))
    except Exception:
        return None

SANCTUARY_CHAT_ID = _to_int(os.getenv("SANCTUARY_CHAT_ID"))   # main group
OWNER_ID          = _to_int(os.getenv("OWNER_ID"))
REQ_AUDIT_CHAT_ID = _to_int(os.getenv("REQ_AUDIT_CHAT_ID") or (str(OWNER_ID) if OWNER_ID else "0"))
REQ_AUDIT_VERBOSE = (os.getenv("REQ_AUDIT_VERBOSE", "0").lower() in ("1","true","yes","on"))

REQ_REQUIRE_DOLLARS = float(os.getenv("REQ_REQUIRE_DOLLARS", "20"))
REQ_REQUIRE_GAMES   = int(os.getenv("REQ_REQUIRE_GAMES", "4"))

# ---------------- Utilities ----------------

async def _audit(app: Client, text: str):
    """Send an audit log line (if configured)."""
    if not REQ_AUDIT_CHAT_ID:
        return
    try:
        await app.send_message(REQ_AUDIT_CHAT_ID, text, disable_web_page_preview=True)
    except Exception:
        pass

async def _send_dm_safe(app: Client, user_id: int, text: str) -> bool:
    try:
        msg = await app.send_message(user_id, text, disable_web_page_preview=True)
        if REQ_AUDIT_VERBOSE:
            await _audit(app, f"✅ Reminder sent to <code>{user_id}</code> (msg {msg.id})")
        return True
    except FloodWait as e:
        await asyncio.sleep(int(getattr(e, "value", 1)) or 1)
        try:
            msg = await app.send_message(user_id, text, disable_web_page_preview=True)
            if REQ_AUDIT_VERBOSE:
                await _audit(app, f"✅ Reminder sent after wait to <code>{user_id}</code> (msg {msg.id})")
            return True
        except Exception as e2:
            await _audit(app, f"❌ Flood/Retry failed for <code>{user_id}</code>: {type(e2).__name__}")
            return False
    except UserIsBlocked:
        await _audit(app, f"❌ Blocked by user <code>{user_id}</code>")
        return False
    except PeerIdInvalid:
        await _audit(app, f"❌ Cannot DM (privacy) <code>{user_id}</code>")
        return False
    except RPCError as e:
        await _audit(app, f"❌ RPCError for <code>{user_id}</code>: {type(e).__name__}")
        return False
    except Exception as e:
        await _audit(app, f"❌ Unknown error for <code>{user_id}</code>: {type(e).__name__}")
        return False

def _now_str() -> str:
    dt = datetime.now(_TZ) if _TZ else datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M")

def _qualifies(purchases: float, games: int) -> bool:
    # Qualify if EITHER condition is met
    return (purchases >= REQ_REQUIRE_DOLLARS) or (games >= REQ_REQUIRE_GAMES)

def _progress_line(purchases: float, games: int) -> str:
    # e.g. "You’re at $12.00 and 1 game."
    return f"You’re at <b>${purchases:.2f}</b> and <b>{games}</b> game{'s' if games != 1 else ''}."

def _spicy_dm(name: str, purchases: float, games: int) -> str:
    # Succubus Sanctuary themed, flirty, and clear
    need_cash = max(0.0, REQ_REQUIRE_DOLLARS - purchases)
    need_games = max(0, REQ_REQUIRE_GAMES - games)

    # A few variants randomized lightly by totals to avoid repetition
    variants = []

    variants.append(
        f"Hey {name}… 😈\n\n"
        f"Your favorite succubi have been watching. This month’s doorway stays open if you’ve done "
        f"<b>${REQ_REQUIRE_DOLLARS:.0f}+ in support</b> <i>or</i> <b>{REQ_REQUIRE_GAMES}+ games</b>.\n"
        f"{_progress_line(purchases, games)}\n\n"
        f"Just a little more and we’ll drag you deeper. "
        f"{'Another <b>${:.2f}</b> will do it.'.format(need_cash) if purchases < REQ_REQUIRE_DOLLARS else ''}"
        f"{' Or just <b>{}</b> more game{}…'.format(need_games, 's' if need_games != 1 else '') if games < REQ_REQUIRE_GAMES else ''}\n\n"
        f"Be a good plaything and finish your tribute… we’ll make it worth your while. 💋"
    )

    variants.append(
        f"Psst {name}… you’re almost ours. 💌\n\n"
        f"To stay wrapped in the Sanctuary’s tail, you need <b>${REQ_REQUIRE_DOLLARS:.0f}</b> "
        f"or <b>{REQ_REQUIRE_GAMES}</b> games each month. "
        f"{_progress_line(purchases, games)}\n\n"
        f"Come tip, join a game, tease a model—just don’t keep us waiting. We bite when ignored. 😘"
    )

    variants.append(
        f"{name}, the circle is hungry. 🔥\n\n"
        f"Meet your monthly tribute: <b>${REQ_REQUIRE_DOLLARS:.0f}</b> <i>or</i> <b>{REQ_REQUIRE_GAMES}</b> games.\n"
        f"{_progress_line(purchases, games)}\n\n"
        f"Finish your offering and we’ll open the fun vault again. "
        f"Don’t make us come looking… unless you want us to. 😏"
    )

    # pick a line by simple hash of counts (deterministic)
    idx = (int(purchases * 100) + games) % len(variants)
    return variants[idx]

def _get_month_user(user_id: int):
    """Return (mk, UserReq) for current month."""
    if not _store:
        return _month_key(), None
    mk, u = _store.get_status(user_id, None)
    # u is a dataclass UserReq (per your store)
    return mk, u

def _is_exempt(user_id: int) -> bool:
    # global or group exemption counts
    if not _store:
        return False
    if SANCTUARY_CHAT_ID:
        if _store.is_exempt(user_id, SANCTUARY_CHAT_ID):
            return True
    return _store.is_exempt(user_id, None)

async def _kick_member(app: Client, user_id: int) -> bool:
    """Kick member from the sanctuary group; clear DM-ready."""
    if not SANCTUARY_CHAT_ID:
        return False
    ok = True
    try:
        await app.ban_chat_member(SANCTUARY_CHAT_ID, user_id)
        # quick unban lets them rejoin if they pay later
        await app.unban_chat_member(SANCTUARY_CHAT_ID, user_id)
    except BadRequest:
        ok = False
    except RPCError:
        ok = False

    # Clear DM-ready flag
    try:
        if _store:
            _store.set_dm_ready_global(user_id, False, by_admin=False)
    except Exception:
        pass
    return ok

# --------------- Commands / Batches ----------------

async def _batch_remind(app: Client) -> Tuple[int, int, int]:
    """
    DM-ready non-exempt users who are not qualified this month.
    Returns (checked, sent, failed)
    """
    checked = sent = failed = 0
    if not _store:
        await _audit(app, "❌ ReqStore unavailable; cannot run reminders.")
        return checked, sent, failed

    dm_ready_map: Dict[str, dict] = _store.list_dm_ready_global()  # {uid_str: {...}}
    for s_uid in list(dm_ready_map.keys()):
        try:
            uid = int(s_uid)
        except Exception:
            continue

        checked += 1
        if _is_exempt(uid):
            continue

        mk, u = _get_month_user(uid)
        if not u:
            continue

        # skip if qualified (either condition)
        if _qualifies(u.purchases, u.games):
            continue

        # Build text & send
        name = f"darling"
        try:
            user = await app.get_users(uid)
            if user and user.first_name:
                name = user.first_name
        except Exception:
            pass

        text = _spicy_dm(name, u.purchases, u.games)
        ok = await _send_dm_safe(app, uid, text)
        if ok:
            sent += 1
        else:
            failed += 1

    await _audit(app, f"📣 Reminder batch summary @ {_now_str()}: checked={checked}, ✅ sent={sent}, ❌ failed={failed}.")
    return checked, sent, failed

async def _monthly_report(app: Client, title: str = "Monthly Requirement Report"):
    """Post totals for the current month: spend by user & group; games by user & group."""
    if not _store:
        return

    mk = _month_key()
    # months[mk]["users"] -> dict of uid -> UserReq
    raw = _store.state.months.get(mk, {}).get("users", {})
    if not raw:
        await _audit(app, f"🗒 {title}: No data for {mk}.")
        return

    # Build per-user lines and totals
    lines: List[str] = []
    total_spend = 0.0
    total_games = 0
    kept = 0
    removed = 0

    for s_uid, rec in raw.items():
        # rec may be dict or UserReq
        try:
            uid = int(s_uid)
        except Exception:
            continue
        try:
            # normalize
            purchases = float(getattr(rec, "purchases", rec.get("purchases", 0.0)))
            games = int(getattr(rec, "games", rec.get("games", 0)))
        except Exception:
            continue

        total_spend += purchases
        total_games += games
        status = "✅" if _qualifies(purchases, games) else "❌"
        if status == "✅":
            kept += 1
        else:
            removed += 1
        lines.append(f"{status} <code>{uid}</code> — ${purchases:.2f}, {games} game{'s' if games!=1 else ''}")

    header = (
        f"📊 <b>{title}</b> ({mk})\n"
        f"• Group spend: <b>${total_spend:.2f}</b>\n"
        f"• Group games: <b>{total_games}</b>\n"
        f"• Qualified (kept): <b>{kept}</b>\n"
        f"• Not qualified (at risk/removed): <b>{removed}</b>\n\n"
        f"<b>Per-user:</b>"
    )
    body = header + "\n" + "\n".join(lines[:300])  # avoid huge messages
    await _audit(app, body)

async def _monthly_sweep(app: Client):
    """
    Remove non-compliant, non-exempt members from the sanctuary group on the 1st.
    Sends audit lines and a summary; also emits a fresh monthly report.
    """
    if not SANCTUARY_CHAT_ID:
        await _audit(app, "❌ No SANCTUARY_CHAT_ID set; cannot sweep.")
        return
    if not _store:
        await _audit(app, "❌ ReqStore unavailable; cannot sweep.")
        return

    kept = 0
    removed = 0
    failures = 0

    # Iterate current members (best effort — Telegram API may limit visibility)
    try:
        async for member in app.get_chat_members(SANCTUARY_CHAT_ID):
            user = member.user
            if not user or user.is_bot:
                continue

            uid = user.id
            if _is_exempt(uid):
                kept += 1
                continue

            _, u = _get_month_user(uid)
            purchases = float(getattr(u, "purchases", 0.0)) if u else 0.0
            games = int(getattr(u, "games", 0)) if u else 0

            if _qualifies(purchases, games):
                kept += 1
                continue

            # Not qualified -> remove
            ok = await _kick_member(app, uid)
            if ok:
                removed += 1
                await _audit(app, f"🛑 Removed <code>{uid}</code> — ${purchases:.2f}, {games} game(s).")
            else:
                failures += 1
                await _audit(app, f"⚠️ Could not remove <code>{uid}</code> (insufficient rights?).")

    except RPCError:
        await _audit(app, "❌ Failed to iterate members for sweep (bot may lack rights).")
        return

    await _audit(app, f"🧹 <b>Monthly Sweep Summary</b>: kept={kept}, removed={removed}, failures={failures}.")
    await _monthly_report(app, "Post-Sweep Monthly Report")

# ----------------- Registration ------------------

def register(app: Client):

    # ---- Commands ----

    @app.on_message(filters.command("reqstatus"))
    async def reqstatus(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else None
        if not uid:
            return
        _, u = _get_month_user(uid)
        if not u:
            return await m.reply_text("No activity recorded yet for you this month.")
        txt = (
            f"📋 <b>Your Status</b>\n"
            f"• Spent: <b>${u.purchases:.2f}</b>\n"
            f"• Games: <b>{u.games}</b>\n"
            f"• Requirement: <b>${REQ_REQUIRE_DOLLARS:.0f}</b> or <b>{REQ_REQUIRE_GAMES}</b> games\n"
            f"• Status: {'✅ Qualified' if _qualifies(u.purchases, u.games) else '❌ Not yet'}"
        )
        await m.reply_text(txt, disable_web_page_preview=True)

    @app.on_message(filters.command("reqremind"))
    async def reqremind(client: Client, m: Message):
        """
        /reqremind test  → Preview a single user's reminder (reply to user or use in DM)
        /reqremind run   → Run batch reminders to DM-ready, non-exempt, non-qualified
        """
        if m.chat and m.chat.type != ChatType.PRIVATE:
            # limit to admins in groups
            try:
                member = await client.get_chat_member(m.chat.id, m.from_user.id)
                if member.status not in ("administrator", "creator"):
                    return await m.reply_text("Admins only.")
            except Exception:
                return await m.reply_text("Admins only.")
        args = (m.text or "").split()
        mode = args[1].lower() if len(args) > 1 else "help"

        if mode == "test":
            # pick target: reply-to user, or self if in DM
            target_id = None
            if m.reply_to_message and m.reply_to_message.from_user:
                target_id = m.reply_to_message.from_user.id
            elif m.chat and m.chat.type == ChatType.PRIVATE and m.from_user:
                target_id = m.from_user.id
            if not target_id:
                return await m.reply_text("Reply to a user or DM me directly to preview.")

            _, u = _get_month_user(target_id)
            if not u:
                return await m.reply_text("No data for that user yet this month.")
            if _qualifies(u.purchases, u.games):
                return await m.reply_text("They already qualify. No reminder needed.")
            name = "darling"
            try:
                uobj = await client.get_users(target_id)
                if uobj and uobj.first_name:
                    name = uobj.first_name
            except Exception:
                pass
            await m.reply_text(_spicy_dm(name, u.purchases, u.games), disable_web_page_preview=True)
            return

        if mode == "run":
            await _audit(client, "▶️ Starting reminder batch...")
            checked, sent, failed = await _batch_remind(client)
            return await m.reply_text(f"Done. checked={checked}, sent={sent}, failed={failed}.")

        # help
        return await m.reply_text(
            "<b>/reqremind</b> usage:\n"
            "• <code>/reqremind test</code> — preview for a user (reply or DM)\n"
            "• <code>/reqremind run</code>  — DM-ready batch to non-exempt, non-qualified",
            disable_web_page_preview=True
        )

    @app.on_message(filters.command("reqreport"))
    async def reqreport(client: Client, m: Message):
        if m.chat and m.chat.type != ChatType.PRIVATE:
            try:
                member = await client.get_chat_member(m.chat.id, m.from_user.id)
                if member.status not in ("administrator", "creator"):
                    return await m.reply_text("Admins only.")
            except Exception:
                return await m.reply_text("Admins only.")
        await _monthly_report(client, "Manual Monthly Report")
        await m.reply_text("Report dispatched to audit channel.")

    @app.on_message(filters.command("reqsweep"))
    async def reqsweep(client: Client, m: Message):
        if m.chat and m.chat.type != ChatType.PRIVATE:
            try:
                member = await client.get_chat_member(m.chat.id, m.from_user.id)
                if member.status not in ("administrator", "creator"):
                    return await m.reply_text("Admins only.")
            except Exception:
                return await m.reply_text("Admins only.")
        await _audit(client, "▶️ Manual sweep triggered.")
        await _monthly_sweep(client)
        await m.reply_text("Sweep complete (see audit).")

    # ---- Scheduler (1st of month @ 00:10 local) ----
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        _scheduler = AsyncIOScheduler(timezone=TZ if _TZ else None)
        # Reminders on the last day @ 18:00, and sweep on the 1st @ 00:10 (adjust if you prefer)
        _scheduler.add_job(_batch_remind, CronTrigger(day="last", hour=18, minute=0), args=[app])
        _scheduler.add_job(_monthly_sweep, CronTrigger(day=1, hour=0, minute=10), args=[app])
        _scheduler.add_job(_monthly_report, CronTrigger(day=1, hour=0, minute=12), args=[app])
        _scheduler.start()
    except Exception:
        # If APScheduler is not available or fails, we just skip scheduling; manual commands still work.
        pass
