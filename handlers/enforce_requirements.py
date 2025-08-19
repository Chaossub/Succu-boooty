# handlers/enforce_requirements.py
# Succubus Sanctuary — requirement enforcement + reporting (either/or: $ >= 20 OR games >= 4)

import os, time, asyncio, random
from typing import Optional, Tuple, Dict, List, Set
from contextlib import suppress

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError, FloodWait, UserIsBlocked, PeerIdInvalid, ChatAdminRequired

try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

def _to_int(x: Optional[str]) -> Optional[int]:
    try:
        return int(str(x)) if x not in (None,"","None") else None
    except Exception:
        return None

OWNER_ID       = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID = _to_int(os.getenv("SUPER_ADMIN_ID"))

RONI_ID = _to_int(os.getenv("RONI_ID"))
RUBY_ID = _to_int(os.getenv("RUBY_ID"))
RIN_ID  = _to_int(os.getenv("RIN_ID"))
SAVY_ID = _to_int(os.getenv("SAVY_ID"))
MODELS: Set[int] = set(i for i in (RONI_ID, RUBY_ID, RIN_ID, SAVY_ID) if i)

REQ_EITHER_PURCHASE = float(os.getenv("REQ_EITHER_PURCHASE", "20"))
REQ_EITHER_GAMES    = int(os.getenv("REQ_EITHER_GAMES", "4"))

NUDGE_COOLDOWN_H    = float(os.getenv("REQ_NUDGE_COOLDOWN_H", "24"))
NUDGE_PREFIX        = os.getenv("REQ_NUDGE_PREFIX", "⚠️ Sanctuary Notice")
NUDGE_DMREADY_ONLY  = os.getenv("NUDGE_DMREADY_ONLY", "1") in ("1","true","True","yes","YES")

_ADMIN_EXTRA: Set[int] = set()
if os.getenv("ENFORCE_ADMINS"):
    for tok in os.getenv("ENFORCE_ADMINS").split(","):
        v = _to_int(tok.strip()); 
        if v: _ADMIN_EXTRA.add(v)
ADMIN_IDS: Set[int] = {i for i in (OWNER_ID, SUPER_ADMIN_ID) if i} | _ADMIN_EXTRA | MODELS

def _parse_groups_csv(s: Optional[str]) -> List[int]:
    if not s: return []
    out = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok: continue
        try: out.append(int(tok))
        except Exception: pass
    return out

ENFORCE_GROUP_IDS: List[int] = _parse_groups_csv(os.getenv("ENFORCE_GROUP_IDS"))

ENFORCE_TZ    = os.getenv("ENFORCE_TZ", "America/Los_Angeles")
ENFORCE_HOUR  = int(os.getenv("ENFORCE_HOUR", "0"))
ENFORCE_MIN   = int(os.getenv("ENFORCE_MINUTE", "30"))

LOG_CHANNEL_ID   = _to_int(os.getenv("LOG_CHANNEL_ID"))
REQ_AUTO_REPORT  = os.getenv("REQ_AUTO_REPORT", "1") in ("1","true","True","yes","YES")
REQ_AUTO_RESET   = os.getenv("REQ_AUTO_RESET",  "0") in ("1","true","True","yes","YES")

def _is_admin(uid: Optional[int]) -> bool:
    return bool(uid and uid in ADMIN_IDS)

def _fmt_money(v: float) -> str:
    s = f"{v:.2f}"
    return s[:-3] if s.endswith(".00") else s

def _status(user_id: int) -> Tuple[float, int, bool]:
    if not _store: return (0.0, 0, False)
    mk, rec = _store.get_status(user_id)
    return float(getattr(rec,"purchases",0.0) or 0.0), int(getattr(rec,"games",0) or 0), _store.is_exempt(user_id, None)

def _meets_either(spent: float, games: int) -> bool:
    return (spent >= REQ_EITHER_PURCHASE) or (games >= REQ_EITHER_GAMES)

_last_sent: Dict[int, float] = {}
_TEMPLATES = [
    ("Mmm {nick}… your succubi are waiting.\n"
     "Offer <b>${rem_purchase}</b> or play <b>{rem_games}</b> more game(s). Don’t make us tease it out of you 😈"),
    ("Darling {nick}, you’re slipping…\n"
     "Bring us <b>${rem_purchase}</b> or <b>{rem_games}</b> game(s) and earn your way back into our arms 💋"),
    ("Sweet {nick}, so close…\n"
     "Choose: <b>${rem_purchase}</b> in tribute or <b>{rem_games}</b> game(s) at our table. We’re watching 🔥"),
    ("Naughty {nick}, we see everything…\n"
     "You still owe <b>${rem_purchase}</b> or <b>{rem_games}</b> game(s). Don’t keep the Sanctuary waiting 💦"),
    ("Pssst {nick}… the Sanctuary hungers.\n"
     "Satisfy us with <b>${rem_purchase}</b> or <b>{rem_games}</b> game(s). Be a good plaything 😏"),
]

def _progress_block(spent: float, games: int) -> str:
    return (f"<b>Requirement:</b> ${_fmt_money(REQ_EITHER_PURCHASE)} <i>or</i> {REQ_EITHER_GAMES} game(s)\n"
            f"<b>Progress:</b> ${_fmt_money(spent)} • {games} game(s)")

def _remaining_either(spent: float, games: int):
    return max(0.0, REQ_EITHER_PURCHASE - (spent or 0.0)), max(0, REQ_EITHER_GAMES - (games or 0))

def _cooldown_ok(user_id: int) -> bool:
    ts = _last_sent.get(user_id, 0.0)
    return (time.time() - ts) >= NUDGE_COOLDOWN_H * 3600.0

async def _send_nudge(client: Client, user_id: int, name: str, spent: float, games: int) -> str:
    if _meets_either(spent, games): return "skip"
    if NUDGE_DMREADY_ONLY and _store and not _store.is_dm_ready_global(user_id):
        return "not_ready"
    if not _cooldown_ok(user_id): return "cooldown"
    rem_p, rem_g = _remaining_either(spent, games)
    body = random.choice(_TEMPLATES).format(nick=name or "there", rem_purchase=_fmt_money(rem_p), rem_games=rem_g)
    text = f"{NUDGE_PREFIX}\n\n{body}\n\n{_progress_block(spent, games)}"
    try:
        await client.send_message(user_id, text, disable_web_page_preview=True)
        _last_sent[user_id] = time.time()
        return "sent"
    except UserIsBlocked:
        return "blocked"
    except (PeerIdInvalid, FloodWait, RPCError):
        return "fail"

async def _kick_member(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        await client.ban_chat_member(chat_id, user_id)
        with suppress(Exception):
            await client.unban_chat_member(chat_id, user_id)
        if _store:
            with suppress(Exception):
                _store.set_dm_ready_global(user_id, False)
        return True
    except ChatAdminRequired:
        return False
    except (FloodWait, RPCError):
        return False

def _should_skip_user(uid: int) -> bool:
    return uid in ADMIN_IDS

async def _username_or_id(client: Client, uid: int) -> str:
    try:
        u = await client.get_users(uid)
        if u.username: return f"@{u.username}"
        return f"{u.first_name} (<code>{uid}</code>)"
    except Exception:
        return f"<code>{uid}</code>"

def _month_key(ts: Optional[float] = None) -> str:
    import datetime as _dt
    dt = _dt.datetime.fromtimestamp(ts or time.time())
    return f"{dt.year:04d}-{dt.month:02d}"

def _format_enforcement_report(month_key: str, per_group: Dict[int, Dict], grand: Dict[str, float]) -> str:
    lines: List[str] = []
    lines.append(f"📅 <b>Succubus Sanctuary — {month_key} Enforcement Report</b>")
    lines.append("")
    for gid, rep in per_group.items():
        lines.append(f"<b>Group</b> <code>{gid}</code>")
        lines.append(
            f"• Checked: <b>{rep['checked']}</b> • Kept: <b>{rep['kept']}</b> • Removed: <b>{rep['kicked']}</b> "
            f"• Exempt: <b>{rep['exempt']}</b> • Admins: <b>{rep['admin']}</b> • Errors: <b>{rep['errors']}</b>"
        )
        lines.append(f"• Group spend (scanned): <b>${_fmt_money(rep['sum_spent'])}</b> • Group games: <b>{rep['sum_games']}</b>")
        if rep["kept_list"]:
            lines.append("Members kept:")
            kept_sorted = sorted(rep["kept_list"], key=lambda r: (r["spent"], r["games"]), reverse=True)
            for r in kept_sorted[:100]:
                lines.append(f"  • {r.get('label','') or '<code>'+str(r['user_id'])+'</code>'}: ${_fmt_money(r['spent'])} • {r['games']} game(s)")
        else:
            lines.append("Members kept: (none)")
        if rep["kicked_list"]:
            lines.append("Members removed:")
            kicked_sorted = sorted(rep["kicked_list"], key=lambda r: (r["spent"], r["games"]), reverse=True)
            for r in kicked_sorted[:100]:
                lines.append(f"  • {r.get('label','') or '<code>'+str(r['user_id'])+'</code>'}: ${_fmt_money(r['spent'])} • {r['games']} game(s)")
        else:
            lines.append("Members removed: (none)")
        lines.append("")
    lines.append("—")
    lines.append(
        f"🧮 <b>Totals (all groups scanned)</b>: "
        f"Spend: <b>${_fmt_money(grand['sum_spent'])}</b> • Games: <b>{int(grand['sum_games'])}</b> • "
        f"Kept: <b>{grand['kept']}</b> • Removed: <b>{grand['kicked']}</b>"
    )
    return "\n".join(lines)

async def _post_enforcement_report(client: Client, month_key: str, per_group: Dict[int, Dict], grand: Dict[str, float]):
    dst = LOG_CHANNEL_ID or OWNER_ID
    if not dst: return
    for rep in per_group.values():
        for r in rep["kept_list"]:
            if not r.get("label"): r["label"] = await _username_or_id(client, r["user_id"])
        for r in rep["kicked_list"]:
            if not r.get("label"): r["label"] = await _username_or_id(client, r["user_id"])
    text = _format_enforcement_report(month_key, per_group, grand)
    with suppress(Exception):
        await client.send_message(dst, text, disable_web_page_preview=True)

async def enforce_in_group(client: Client, chat_id: int) -> Dict:
    report = {
        "checked": 0, "kicked": 0, "kept": 0, "skipped": 0, "exempt": 0, "admin": 0, "errors": 0,
        "sum_spent": 0.0, "sum_games": 0,
        "kept_list": [], "kicked_list": [],
    }
    async for member in client.get_chat_members(chat_id):
        user = member.user
        if user.is_bot: continue
        report["checked"] += 1
        uid = user.id

        spent, games, _ex_global = _status(uid)
        report["sum_spent"] += float(spent)
        report["sum_games"] += int(games)

        if _should_skip_user(uid):
            report["admin"] += 1
            report["kept"] += 1
            report["kept_list"].append({"user_id": uid, "spent": float(spent), "games": int(games)})
            continue

        # group or global exemption
        try:
            ex_group = _store.is_exempt(uid, chat_id) if _store else False
        except Exception:
            ex_group = False
        if ex_group or _ex_global:
            report["exempt"] += 1
            report["kept"] += 1
            report["kept_list"].append({"user_id": uid, "spent": float(spent), "games": int(games)})
            continue

        if _meets_either(spent, games):
            report["skipped"] += 1
            report["kept"] += 1
            report["kept_list"].append({"user_id": uid, "spent": float(spent), "games": int(games)})
            continue

        # DM then kick
        with suppress(Exception):
            await client.send_message(
                uid,
                f"{NUDGE_PREFIX}\n\nYou haven’t met this month’s Sanctuary requirement.\n\n"
                f"{_progress_block(spent, games)}\n\n"
                f"You’ll be removed now. Come back when you’re ready to play nicely. 💋",
                disable_web_page_preview=True
            )
        ok = await _kick_member(client, chat_id, uid)
        if ok:
            report["kicked"] += 1
            report["kicked_list"].append({"user_id": uid, "spent": float(spent), "games": int(games)})
        else:
            report["errors"] += 1

        await asyncio.sleep(0.4)
    return report

_scheduler = None
def _ensure_scheduler():
    global _scheduler
    if _scheduler is None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            import pytz
            _scheduler = AsyncIOScheduler(timezone=pytz.timezone(ENFORCE_TZ))
            _scheduler.start()
        except Exception as e:
            print("[ENFORCE] Scheduler unavailable:", e)
            _scheduler = None
    return _scheduler

async def _run_monthly(client: Client):
    if not ENFORCE_GROUP_IDS: return
    per_group: Dict[int, Dict] = {}
    grand = {"sum_spent": 0.0, "sum_games": 0, "kicked": 0, "kept": 0}
    for gid in ENFORCE_GROUP_IDS:
        try:
            rep = await enforce_in_group(client, gid)
            per_group[gid] = rep
            grand["sum_spent"] += rep["sum_spent"]
            grand["sum_games"] += rep["sum_games"]
            grand["kicked"]    += rep["kicked"]
            grand["kept"]      += rep["kept"]
            with suppress(Exception):
                await client.send_message(
                    gid,
                    f"🧹 Enforcement: checked {rep['checked']}, removed {rep['kicked']}, kept {rep['kept']}, "
                    f"exempt {rep['exempt']}, admins {rep['admin']}.",
                )
        except Exception:
            pass
        await asyncio.sleep(1.0)

    mk = _month_key()
    await _post_enforcement_report(client, mk, per_group, grand)

    if REQ_AUTO_REPORT and _store:
        with suppress(Exception):
            mk2, _per_user, totals = _store.month_summary(mk)
            dst = LOG_CHANNEL_ID or OWNER_ID
            if dst:
                await client.send_message(
                    dst,
                    f"📊 <b>Monthly Totals ({mk2})</b>\n"
                    f"• Spend: <b>${_fmt_money(totals['spent'])}</b>\n"
                    f"• Games: <b>{totals['games']}</b>\n"
                    f"• Members recorded: <b>{totals['count']}</b>",
                    disable_web_page_preview=True
                )

    if REQ_AUTO_RESET and _store:
        with suppress(Exception):
            _store.reset_month(None)
            dst = LOG_CHANNEL_ID or OWNER_ID
            if dst:
                await client.send_message(dst, "✅ Requirements reset for the new month.")

def register(app: Client):
    # scheduler job
    sched = _ensure_scheduler()
    if sched:
        from apscheduler.triggers.cron import CronTrigger
        try:
            trigger = CronTrigger(day="1", hour=ENFORCE_HOUR, minute=ENFORCE_MIN)
            async def _job():
                await _run_monthly(app)
            sched.add_job(_job, trigger, name="monthly_enforce")
        except Exception as e:
            print("[ENFORCE] Failed to add monthly job:", e)

    @app.on_message(filters.command("reqcheck"))
    async def reqcheck(client: Client, m: Message):
        target_id = m.from_user.id if m.from_user else None
        if m.reply_to_message and m.reply_to_message.from_user:
            target_id = m.reply_to_message.from_user.id
        elif len(m.command) > 1:
            arg = m.command[1]
            if arg.isdigit(): target_id = int(arg)
            else:
                try: target_id = (await client.get_users(arg)).id
                except Exception: target_id = None
        if not target_id:
            return await m.reply_text("Usage: /reqcheck (reply or pass @username/user_id)")
        spent, games, ex = _status(target_id)
        meet = _meets_either(spent, games)
        txt = (f"<b>Requirement:</b> ${_fmt_money(REQ_EITHER_PURCHASE)} or {REQ_EITHER_GAMES} game(s)\n"
               f"<b>Progress:</b> ${_fmt_money(spent)} • {games} game(s)\n"
               f"<b>Exempt (global):</b> {'Yes' if ex else 'No'}\n"
               f"<b>Status:</b> {'✅ Met' if meet else '❌ Not met'}")
        await m.reply_text(txt, disable_web_page_preview=True)

    @app.on_message(filters.command("reqnudge"))
    async def reqnudge(client: Client, m: Message):
        if not _is_admin(m.from_user.id if m.from_user else None):
            return await m.reply_text("Admins only.")
        if not _store:
            return await m.reply_text("ReqStore missing; can’t check requirements.")
        target_id = None; target_name = "there"
        if m.reply_to_message and m.reply_to_message.from_user:
            target_id = m.reply_to_message.from_user.id
            target_name = m.reply_to_message.from_user.first_name
        elif len(m.command) > 1:
            arg = m.command[1]
            if arg.isdigit():
                target_id = int(arg)
                with suppress(Exception): target_name = (await client.get_users(target_id)).first_name
            else:
                u = await client.get_users(arg); target_id, target_name = u.id, u.first_name
        if not target_id: return await m.reply_text("Reply to someone or pass @username/user_id.")
        spent, games, ex = _status(target_id)
        if ex: return await m.reply_text("User is globally exempt right now.")
        if _meets_either(spent, games): return await m.reply_text("User already meets requirements ✅")
        res = await _send_nudge(client, target_id, target_name, spent, games)
        if   res == "sent":      await m.reply_text("Nudge sent ✅")
        elif res == "cooldown":  await m.reply_text("Nudge recently sent; cooldown in effect.")
        elif res == "blocked":   await m.reply_text("User blocked the bot ❌")
        elif res == "not_ready": await m.reply_text("User hasn’t started the bot yet (not DM-ready).")
        elif res == "skip":      await m.reply_text("User meets requirements now.")
        else:                    await m.reply_text("Could not DM user.")

    @app.on_message(filters.command("reqblast"))
    async def reqblast(client: Client, m: Message):
        if not _is_admin(m.from_user.id if m.from_user else None):
            return await m.reply_text("Admins only.")
        if not _store:
            return await m.reply_text("ReqStore missing; can’t scan users.")
        try:
            mk = max(_store.state.months.keys()) if _store.state.months else None
        except Exception:
            mk = None
        if not mk: return await m.reply_text("No users recorded yet this month.")
        users = list(_store.state.months[mk]["users"].keys())
        sent = cool = skip = blocked = fail = not_ready = 0
        for s_uid in users:
            uid = int(s_uid)
            spent, games, ex = _status(uid)
            if ex or _meets_either(spent, games):
                skip += 1; continue
            try:
                u = await client.get_users(uid)
                res = await _send_nudge(client, uid, u.first_name, spent, games)
            except Exception:
                res = "fail"
            if res == "sent": sent += 1
            elif res == "cooldown": cool += 1
            elif res == "blocked": blocked += 1
            elif res == "not_ready": not_ready += 1
            elif res == "skip": skip += 1
            else: fail += 1
            await asyncio.sleep(0.6)
        await m.reply_text(
            f"<b>Blast complete</b>\n"
            f"• Sent: {sent}\n• Cooldown: {cool}\n• Not DM-ready: {not_ready}\n"
            f"• Blocked: {blocked}\n• Failed: {fail}\n• Skipped (met/exempt): {skip}"
        )

    @app.on_message(filters.command("reqenforce_now"))
    async def reqenforce_now(client: Client, m: Message):
        if not _is_admin(m.from_user.id if m.from_user else None):
            return await m.reply_text("Admins only.")
        if not ENFORCE_GROUP_IDS:
            return await m.reply_text("No ENFORCE_GROUP_IDS configured.")
        per_group: Dict[int, Dict] = {}
        grand = {"sum_spent": 0.0, "sum_games": 0, "kicked": 0, "kept": 0}
        for gid in ENFORCE_GROUP_IDS:
            rep = await enforce_in_group(client, gid)
            per_group[gid] = rep
            grand["sum_spent"] += rep["sum_spent"]
            grand["sum_games"] += rep["sum_games"]
            grand["kicked"]    += rep["kicked"]
            grand["kept"]      += rep["kept"]
            await asyncio.sleep(0.5)
        await _post_enforcement_report(client, _month_key(), per_group, grand)
        await m.reply_text("Manual enforcement complete. Report posted.", disable_web_page_preview=True)
