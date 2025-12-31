# handlers/requirements_panel.py
# Restored full panel entry + admin controls + reminder/final-warning picker
# Startup-safe: does not hard-crash the whole bot if Mongo is temporarily unavailable.

import os
import logging
import random
import re
import io
from datetime import datetime, timezone
from typing import List, Set, Dict, Any, Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import MessageNotModified

from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError

log = logging.getLogger(__name__)

# ────────────── ENV ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))

def _parse_id_list(val: Optional[str]) -> Set[int]:
    if not val:
        return set()
    out: Set[int] = set()
    for part in val.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            log.warning("requirements_panel: bad ID in list: %r", part)
    return out

SUPER_ADMINS: Set[int] = _parse_id_list(os.getenv("SUPER_ADMINS"))
MODELS: Set[int] = _parse_id_list(os.getenv("MODELS"))

# Sanctuary group IDs to scan (optional)
_group_ids_str = os.getenv("SANCTUARY_GROUP_IDS")
if not _group_ids_str:
    _single = os.getenv("SUCCUBUS_SANCTUARY")
    SANCTUARY_GROUP_IDS: List[int] = [int(_single)] if _single else []
else:
    SANCTUARY_GROUP_IDS = [int(x) for x in _group_ids_str.replace(" ", "").split(",") if x]

# Log group env keys
LOG_GROUP_ID: Optional[int] = None
for key in ("SANCTU_LOG_GROUP_ID", "SANCTUARY_LOG_CHANNEL", "LOG_GROUP_ID"):
    if os.getenv(key):
        try:
            LOG_GROUP_ID = int(os.getenv(key))
            break
        except ValueError:
            pass

REQUIRED_MIN_SPEND = float(os.getenv("REQUIREMENTS_MIN_SPEND", "20"))

# Model names for attribution (kept for compatibility; not required for reminders)
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME = os.getenv("RIN_NAME", "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

MODEL_NAME_MAP: Dict[str, str] = {
    "roni": RONI_NAME,
    "ruby": RUBY_NAME,
    "rin": RIN_NAME,
    "savy": SAVY_NAME,
}

# ────────────── Mongo (lazy) ──────────────

_mongo: Optional[MongoClient] = None
_db = None
_members_coll = None

def _get_members_coll():
    """
    Lazy-connect to Mongo. Never raises on import; raises only when a Mongo-backed action is invoked.
    """
    global _mongo, _db, _members_coll
    if _members_coll is not None:
        return _members_coll
    if not MONGO_URI:
        raise RuntimeError("MONGODB_URI / MONGO_URI is not set (requirements panel needs Mongo).")

    # short timeout so we don't hang startup
    _mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
    _db = _mongo["Succubot"]
    _members_coll = _db["requirements_members"]

    # Best-effort index creation (ignore failures)
    try:
        _members_coll.create_index([("user_id", ASCENDING)], unique=True)
    except Exception:
        log.exception("requirements_panel: create_index failed (non-fatal)")

    return _members_coll

# ────────────── In-memory state (picker) ──────────────

STATE: Dict[int, Dict[str, Any]] = {}

def _escape(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def _is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS or _is_owner(user_id)

def _is_model(user_id: int) -> bool:
    return user_id in MODELS or _is_owner(user_id)

def _is_admin_or_model(user_id: int) -> bool:
    return _is_super_admin(user_id) or _is_model(user_id)

async def _safe_edit_text(msg: Message, **kwargs):
    try:
        return await msg.edit_text(**kwargs)
    except MessageNotModified:
        return msg

async def _safe_send(app: Client, chat_id: int, text: str):
    try:
        return await app.send_message(chat_id, text)
    except Exception as e:
        log.warning("requirements_panel: failed to send message to %s: %s", chat_id, e)
        return None

async def _log_event(app: Client, text: str):
    if LOG_GROUP_ID is None:
        return
    await _safe_send(app, LOG_GROUP_ID, f"[Requirements] {text}")

def _display_name(first_name: str, username: Optional[str]) -> str:
    first_name = (first_name or "").strip()
    if username:
        username = username.strip()
    if first_name and username:
        return f"{first_name} (@{username})"
    if first_name:
        return first_name
    if username:
        return f"@{username}"
    return "Unknown"

def _member_doc(user_id: int) -> Dict[str, Any]:
    """
    Load a member doc and apply derived fields:
    - Owner & models are always effectively exempt from requirements
    """
    coll = _get_members_coll()
    raw = coll.find_one({"user_id": user_id}) or {}
    is_owner = user_id == OWNER_ID
    is_model = user_id in MODELS or is_owner
    db_exempt = bool(raw.get("is_exempt", False))
    effective_exempt = db_exempt or is_model

    return {
        "user_id": user_id,
        "first_name": raw.get("first_name", "") or "",
        "username": raw.get("username"),
        "manual_spend": float(raw.get("manual_spend", 0.0)),
        "is_exempt": effective_exempt,
        "db_exempt": db_exempt,
        "is_model": is_model,
        "is_owner": is_owner,
        "reminder_sent": bool(raw.get("reminder_sent", False)),
        "final_warning_sent": bool(raw.get("final_warning_sent", False)),
        "last_updated": raw.get("last_updated"),
    }

def _format_member_status(doc: Dict[str, Any]) -> str:
    total = float(doc.get("manual_spend", 0.0))
    exempt = bool(doc.get("is_exempt"))
    is_model = bool(doc.get("is_model"))
    is_owner = bool(doc.get("is_owner"))

    name = _display_name(doc.get("first_name", ""), doc.get("username"))

    header = (
        "<b>Requirement Status</b>\n\n"
        f"<b>Member:</b> {name} (<code>{doc['user_id']}</code>)\n\n"
    )

    if is_owner:
        status = "👑 <b>Sanctuary owner</b> – you’re automatically exempt from requirements."
    elif exempt and is_model:
        status = "✅ <b>Model</b> – you’re automatically exempt from requirements."
    elif exempt:
        status = "✅ Marked exempt from requirements this month."
    elif total >= REQUIRED_MIN_SPEND:
        status = f"✅ Requirements met with ${total:.2f} logged."
    else:
        status = (
            f"⚠️ Currently behind.\n"
            f"Logged so far: ${total:.2f} (minimum ${REQUIRED_MIN_SPEND:.2f})."
        )

    lines = [header, status]
    if doc.get("last_updated"):
        try:
            dt = doc["last_updated"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"\nLast updated: <code>{dt}</code>")
        except Exception:
            pass
    return "\n".join(lines)

# ────────────── DM templates ──────────────

REMINDER_MSGS = [
    "Hi {name}! 💋 Just a sweet reminder that Sanctuary requirements are still open this month. "
    "If you’d like to stay in the Sanctuary, make sure you’ve hit your minimum by the deadline. 💞",
    "Hey {name} ✨ You’re showing as <b>behind</b> on Sanctuary requirements right now. "
    "If that’s a mistake or you’ve already played/spent, please let one of the models know so we can update it.",
    "Psst, {name}… 😈 SuccuBot here. I’m showing that you haven’t hit requirements yet for this month. "
    "Please check the menus or DM a model so we can get you caught up ♥",
]

FINAL_WARNING_MSGS = [
    "Hi {name}. This is your <b>final warning</b> for Sanctuary requirements this month. "
    "If your requirements are not met by the deadline, you’ll be removed from the Sanctuary and will "
    "need to pay the door fee again to come back.",
    "{name}, you are still showing as <b>behind</b> on Sanctuary requirements. This is your last notice. "
    "If this isn’t updated in time, you’ll be removed until requirements are met and the door fee is repaid.",
    "Final notice for this month, {name}: Sanctuary requirements are still not met on your account. "
    "If this isn’t fixed before the sweep, you’ll be removed and will need to re-enter through the door fee.",
]

# ────────────── Keyboards ──────────────

def _root_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:self")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("🛠 Admin / Model Controls", callback_data="reqpanel:admin")])
    rows.append([InlineKeyboardButton("⬅ Back to Sanctuary Menu", callback_data="panels:root")])
    return InlineKeyboardMarkup(rows)

def _admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Member Status List", callback_data="reqpanel:list")],
            [InlineKeyboardButton("📡 Scan Group Members", callback_data="reqpanel:scan")],
            [InlineKeyboardButton("💌 Send Reminders (Behind Only)", callback_data="reqpanel:reminders")],
            [InlineKeyboardButton("⚠️ Send Final Warnings", callback_data="reqpanel:final_warnings")],
            [InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")],
        ]
    )

# ────────────── Reminder picker ──────────────

def _pick_key(action: str, admin_id: int) -> str:
    return f"pick:{action}:{admin_id}"

def _compute_targets() -> List[Dict[str, Any]]:
    coll = _get_members_coll()
    docs = list(coll.find({}))
    targets: List[Dict[str, Any]] = []
    for raw in docs:
        uid = raw.get("user_id")
        if not uid:
            continue
        try:
            md = _member_doc(int(uid))
        except Exception:
            continue
        if md.get("is_exempt"):
            continue
        if float(md.get("manual_spend", 0.0)) >= REQUIRED_MIN_SPEND:
            continue
        targets.append(md)

    targets.sort(key=lambda m: (float(m.get("manual_spend", 0.0)), (m.get("first_name") or "").lower()))
    return targets

def _fmt_user(md: Dict[str, Any]) -> str:
    return f"{_display_name(md.get('first_name',''), md.get('username'))} — <code>{md.get('user_id')}</code>"

def _render_pick(action: str, admin_id: int, page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    st = STATE.get(admin_id, {})
    key = _pick_key(action, admin_id)
    pstate = st.get(key, {})
    targets = pstate.get("targets") or _compute_targets()
    selected = set(pstate.get("selected") or [])

    per_page = 10
    max_page = max(0, (len(targets) - 1) // per_page) if targets else 0
    page = max(0, min(int(page), max_page))

    pstate["targets"] = targets
    pstate["selected"] = list(selected)
    pstate["page"] = page
    st[key] = pstate
    STATE[admin_id] = st

    title = "💌 Send Reminders (Behind Only)" if action == "reminder" else "⚠️ Send Final Warnings (Not Met)"
    lines = [
        f"<b>{title}</b>",
        f"Minimum required: <b>${REQUIRED_MIN_SPEND:.2f}</b>",
        "",
    ]
    if not targets:
        lines.append("✅ Nobody is behind right now.")
    else:
        lines.append(f"Behind members: <b>{len(targets)}</b>")
        lines.append(f"Selected: <b>{len(selected)}</b>")
        lines.append("")
        lines.append("Tap members to toggle selection. Then choose <b>Send Selected</b> or <b>Send All</b>.")

    kb_rows: List[List[InlineKeyboardButton]] = []
    start = page * per_page
    end = start + per_page

    for md in targets[start:end]:
        uid = int(md["user_id"])
        on = "✅" if uid in selected else "⬜️"
        label = f"{on} {_display_name(md.get('first_name',''), md.get('username'))} — ${float(md.get('manual_spend',0.0)):.2f}"
        kb_rows.append([InlineKeyboardButton(label, callback_data=f"reqpick:{action}:toggle:{uid}")])

    if targets and max_page > 0:
        nav: List[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"reqpick:{action}:page:{page-1}"))
        nav.append(InlineKeyboardButton(f"Page {page+1}/{max_page+1}", callback_data="reqpick:noop"))
        if page < max_page:
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"reqpick:{action}:page:{page+1}"))
        kb_rows.append(nav)

    kb_rows.append([
        InlineKeyboardButton("✅ Send Selected", callback_data=f"reqpick:{action}:send_selected"),
        InlineKeyboardButton("📣 Send All", callback_data=f"reqpick:{action}:send_all"),
    ])
    kb_rows.append([InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="reqpanel:admin")])

    return "\n".join(lines), InlineKeyboardMarkup(kb_rows)

async def _try_send_dm(app: Client, user_id: int, tmpl: str) -> Tuple[bool, str]:
    try:
        md = _member_doc(user_id)
        name = (md.get("first_name") or "there").strip() or "there"
        msg = tmpl.format(name=name)
        await app.send_message(user_id, msg, disable_web_page_preview=True)
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

async def _send_dms_for_action(app: Client, cq: CallbackQuery, action: str, only_selected: bool):
    admin_id = cq.from_user.id
    st = STATE.get(admin_id, {})
    key = _pick_key(action, admin_id)
    pstate = st.get(key, {})
    targets = pstate.get("targets") or _compute_targets()
    selected = set(pstate.get("selected") or [])

    if not targets:
        await cq.answer("Nobody is behind right now.", show_alert=True)
        return

    if only_selected:
        send_list = [m for m in targets if int(m["user_id"]) in selected]
        if not send_list:
            await cq.answer("Select at least one member first.", show_alert=True)
            return
    else:
        send_list = targets

    await cq.answer("Sending…", show_alert=False)

    ok: List[Dict[str, Any]] = []
    fail: List[Tuple[Dict[str, Any], str]] = []
    coll = _get_members_coll()

    for md in send_list:
        uid = int(md["user_id"])
        if action == "reminder":
            tmpl = random.choice(REMINDER_MSGS)
            flag_field = "reminder_sent"
        else:
            tmpl = random.choice(FINAL_WARNING_MSGS)
            flag_field = "final_warning_sent"

        sent, reason = await _try_send_dm(app, uid, tmpl)
        if sent:
            ok.append(md)
            try:
                coll.update_one({"user_id": uid}, {"$set": {flag_field: True}}, upsert=True)
            except Exception:
                pass
        else:
            fail.append((md, reason))

    title = "Reminders" if action == "reminder" else "Final Warnings"
    summary_lines = [
        f"<b>{title} sent</b>",
        f"✅ Success: <b>{len(ok)}</b>",
        f"❌ Failed: <b>{len(fail)}</b>",
    ]
    if ok:
        summary_lines.append("")
        summary_lines.append("<b>Sent to:</b>")
        summary_lines += [f"• {_fmt_user(m)}" for m in ok[:50]]
        if len(ok) > 50:
            summary_lines.append(f"…and {len(ok)-50} more")
    if fail:
        summary_lines.append("")
        summary_lines.append("<b>Failed:</b>")
        for m, r in fail[:50]:
            summary_lines.append(f"• {_fmt_user(m)} — <code>{_escape(r)}</code>")
        if len(fail) > 50:
            summary_lines.append(f"…and {len(fail)-50} more")

    await cq.message.reply_text("\n".join(summary_lines), disable_web_page_preview=True)

    # Log group summary
    try:
        await _log_event(app, f"{title} run by {admin_id}. Success={len(ok)} Failed={len(fail)}")
    except Exception:
        pass

    # Keep picker open
    new_text, new_kb = _render_pick(action, admin_id, page=int(pstate.get("page") or 0))
    await _safe_edit_text(cq.message, text=new_text, reply_markup=new_kb, disable_web_page_preview=True)

# ────────────── Register ──────────────

def register(app: Client):
    log.info("✅ handlers.requirements_panel registered (restored panel + picker)")

    @app.on_callback_query(filters.regex("^reqpanel:home$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        is_admin = _is_admin_or_model(user_id)
        text_lines = [
            "<b>Requirements</b>",
            "",
            "Use this panel to check how you’re doing on Sanctuary requirements this month.",
            "",
            "• <b>Check My Status</b> – see if you’re met or behind.",
        ]
        if is_admin:
            text_lines.append("• <b>Admin / Model Controls</b> – open tools (lists, scans, reminders).")
        text_lines.append("")
        text_lines.append("Owner & models get the full tools.")
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text="\n".join(text_lines),
            reply_markup=_root_kb(is_admin),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex("^reqpanel:open$"))
    async def reqpanel_open_cb(_, cq: CallbackQuery):
        await reqpanel_home_cb(_, cq)

    @app.on_callback_query(filters.regex(r"^(requirements:help|requirements_help|requirements:open|requirements:panel)$"))
    async def reqpanel_compat_open_cb(_, cq: CallbackQuery):
        await reqpanel_home_cb(_, cq)

    @app.on_message(filters.private & filters.command(["requirements", "requirementshelp", "reqhelp", "reqs"]))
    async def reqpanel_command_open(_, m: Message):
        await m.reply_text(
            "<b>Requirements</b>\n\nTap below to open the requirements panel.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("📋 Requirements Panel", callback_data="reqpanel:home")]]
            ),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex("^reqpanel:admin$"))
    async def reqpanel_admin_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and approved models can open this.", show_alert=True)
            return

        text = (
            "<b>Admin / Model Controls</b>\n\n"
            "Use these tools to manage Sanctuary requirements for the month.\n\n"
            "From here you can:\n"
            "▪️ View the full member status list\n"
            "▪️ Scan groups into the tracker\n"
            "▪️ Send reminder DMs to members who are behind\n"
            "▪️ Send final-warning DMs to those still not meeting minimums\n\n"
            "<i>Only you and approved model admins see this panel.</i>"
        )
        await cq.answer()
        await _safe_edit_text(cq.message, text=text, reply_markup=_admin_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^reqpanel:self$"))
    async def reqpanel_self_cb(_, cq: CallbackQuery):
        try:
            doc = _member_doc(cq.from_user.id)
            text = _format_member_status(doc)
        except Exception as e:
            await cq.answer("Requirements DB unavailable right now.", show_alert=True)
            return
        await cq.answer()
        await _safe_edit_text(cq.message, text=text, reply_markup=_root_kb(_is_admin_or_model(cq.from_user.id)))

    @app.on_callback_query(filters.regex("^reqpanel:list$"))
    async def reqpanel_list_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Admins only 💜", show_alert=True)
            return
        try:
            coll = _get_members_coll()
            docs = list(coll.find().sort("user_id", ASCENDING).limit(50))
        except Exception:
            await cq.answer("Requirements DB unavailable right now.", show_alert=True)
            return

        if not docs:
            text = "<b>Member Status List</b>\n\nNo tracked members yet. Try running a scan first."
        else:
            lines = ["<b>Member Status List (first 50)</b>\n"]
            for d in docs:
                uid = int(d.get("user_id") or 0)
                total = float(d.get("manual_spend", 0.0))
                db_exempt = bool(d.get("is_exempt", False))
                is_owner = uid == OWNER_ID
                is_model = uid in MODELS or is_owner
                effective_exempt = db_exempt or is_model

                if is_owner:
                    status = "OWNER (EXEMPT)"
                elif is_model:
                    status = "MODEL (EXEMPT)"
                elif effective_exempt:
                    status = "EXEMPT"
                elif total >= REQUIRED_MIN_SPEND:
                    status = "MET"
                else:
                    status = "BEHIND"

                display_name = _display_name(d.get("first_name",""), d.get("username"))
                lines.append(f"• {display_name} (<code>{uid}</code>) – {status} (${total:.2f})")
            text = "\n".join(lines)

        await cq.answer()
        await _safe_edit_text(cq.message, text=text, reply_markup=_admin_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^reqpanel:scan$"))
    async def reqpanel_scan_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Admins only 💜", show_alert=True)
            return
        if not SANCTUARY_GROUP_IDS:
            await cq.answer("No Sanctuary group IDs configured.", show_alert=True)
            return
        try:
            coll = _get_members_coll()
        except Exception:
            await cq.answer("Requirements DB unavailable right now.", show_alert=True)
            return

        total_indexed = 0
        for gid in SANCTUARY_GROUP_IDS:
            try:
                async for member in client.get_chat_members(gid):
                    if member.user.is_bot:
                        continue
                    u = member.user
                    username = (u.username or "").lower() if u.username else None
                    coll.update_one(
                        {"user_id": u.id},
                        {"$set": {"first_name": u.first_name or "", "username": username, "last_updated": datetime.now(timezone.utc)}},
                        upsert=True,
                    )
                    total_indexed += 1
            except Exception as e:
                log.warning("requirements_panel: failed scanning group %s: %s", gid, e)

        await _log_event(client, f"Scan complete by {user_id}: indexed/updated {total_indexed} members.")
        await cq.answer("Scan complete.", show_alert=False)
        await _safe_edit_text(
            cq.message,
            text=(f"✅ Scan complete.\nIndexed or updated {total_indexed} members from Sanctuary group(s)."),
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # Reminders picker
    @app.on_callback_query(filters.regex("^reqpanel:reminders$"))
    async def reqpanel_reminders(app_: Client, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only 💜", show_alert=True)
            return
        try:
            text, kb = _render_pick("reminder", cq.from_user.id, page=0)
        except Exception as e:
            await cq.answer("Requirements DB unavailable right now.", show_alert=True)
            return
        await cq.answer()
        await _safe_edit_text(cq.message, text=text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^reqpanel:final_warnings$"))
    async def reqpanel_final_warnings(app_: Client, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only 💜", show_alert=True)
            return
        try:
            text, kb = _render_pick("final", cq.from_user.id, page=0)
        except Exception:
            await cq.answer("Requirements DB unavailable right now.", show_alert=True)
            return
        await cq.answer()
        await _safe_edit_text(cq.message, text=text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):toggle:(\d+)$"))
    async def reqpick_toggle(app_: Client, cq: CallbackQuery):
        action = cq.data.split(":")[1]
        uid = int(cq.data.split(":")[3])
        admin_id = cq.from_user.id
        st = STATE.get(admin_id, {})
        key = _pick_key(action, admin_id)
        pstate = st.get(key, {})
        selected = set(pstate.get("selected") or [])
        if uid in selected:
            selected.remove(uid)
        else:
            selected.add(uid)
        pstate["selected"] = list(selected)
        st[key] = pstate
        STATE[admin_id] = st

        text2, kb2 = _render_pick(action, admin_id, page=int(pstate.get("page") or 0))
        await cq.answer()
        await _safe_edit_text(cq.message, text=text2, reply_markup=kb2, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):page:(\d+)$"))
    async def reqpick_page(app_: Client, cq: CallbackQuery):
        action = cq.data.split(":")[1]
        page = int(cq.data.split(":")[3])
        admin_id = cq.from_user.id
        text2, kb2 = _render_pick(action, admin_id, page=page)
        await cq.answer()
        await _safe_edit_text(cq.message, text=text2, reply_markup=kb2, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):send_selected$"))
    async def reqpick_send_selected(app_: Client, cq: CallbackQuery):
        action = cq.data.split(":")[1]
        await _send_dms_for_action(app_, cq, action=action, only_selected=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):send_all$"))
    async def reqpick_send_all(app_: Client, cq: CallbackQuery):
        action = cq.data.split(":")[1]
        await _send_dms_for_action(app_, cq, action=action, only_selected=False)

    @app.on_callback_query(filters.regex("^reqpick:noop$"))
    async def reqpick_noop(_, cq: CallbackQuery):
        await cq.answer()
