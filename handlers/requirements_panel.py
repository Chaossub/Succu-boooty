# handlers/requirements_panel.py
# SAFE STARTUP VERSION (prevents Render crash loops) + working Reminder/Final Warning picker

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

# ────────────── ENV & CONSTANTS ──────────────

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

_group_ids_str = os.getenv("SANCTUARY_GROUP_IDS")
if not _group_ids_str:
    _single = os.getenv("SUCCUBUS_SANCTUARY")
    SANCTUARY_GROUP_IDS: List[int] = [int(_single)] if _single else []
else:
    SANCTUARY_GROUP_IDS = [int(x) for x in _group_ids_str.replace(" ", "").split(",") if x]

LOG_GROUP_ID: Optional[int] = None
for key in ("SANCTU_LOG_GROUP_ID", "SANCTUARY_LOG_CHANNEL", "LOG_GROUP_ID"):
    if os.getenv(key):
        try:
            LOG_GROUP_ID = int(os.getenv(key))
            break
        except ValueError:
            pass

REQUIRED_MIN_SPEND = float(os.getenv("REQUIREMENTS_MIN_SPEND", "20"))

# In-memory per-admin state
STATE: Dict[int, Dict[str, Any]] = {}

# ────────────── Mongo lazy init (prevents crash loops) ──────────────

_mongo_client: Optional[MongoClient] = None
_db = None
_members_coll = None

def _get_members_coll():
    global _mongo_client, _db, _members_coll
    if _members_coll is not None:
        return _members_coll

    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
    if not uri:
        # Do NOT crash the whole bot on import; show an alert when used.
        log.error("MONGODB_URI / MONGO_URI is not set; requirements_panel disabled.")
        return None

    try:
        _mongo_client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _db = _mongo_client["Succubot"]
        _members_coll = _db["requirements_members"]
        # Index creation can fail if duplicates exist—don't crash startup.
        try:
            _members_coll.create_index([("user_id", ASCENDING)], unique=True)
        except Exception as e:
            log.warning("requirements_panel: create_index failed (non-fatal): %s", e)
        return _members_coll
    except Exception as e:
        log.exception("requirements_panel: Mongo init failed: %s", e)
        return None

# ────────────── Helpers ──────────────

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

def _escape(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _load_state(admin_id: int) -> Dict[str, Any]:
    return STATE.get(admin_id, {})

def _save_state(admin_id: int, data: Dict[str, Any]) -> None:
    STATE[admin_id] = data

async def _must_be_owner_or_model_admin(_: Client, cq: CallbackQuery) -> bool:
    if not _is_admin_or_model(cq.from_user.id):
        await cq.answer("Admins only 💜", show_alert=True)
        return False
    return True

def _display_name(d: Dict[str, Any]) -> str:
    name = (d.get("first_name") or "").strip()
    username = (d.get("username") or "").strip()
    if username and name:
        return f"{name} (@{username})"
    if name:
        return name
    if username:
        return f"@{username}"
    return "Unknown"

def _member_doc(user_id: int) -> Dict[str, Any]:
    coll = _get_members_coll()
    raw = coll.find_one({"user_id": user_id}) if coll else {}
    raw = raw or {}
    is_owner = user_id == OWNER_ID
    is_model = user_id in MODELS or is_owner
    db_exempt = bool(raw.get("is_exempt", False))
    effective_exempt = db_exempt or is_model
    return {
        "user_id": user_id,
        "first_name": raw.get("first_name", ""),
        "username": raw.get("username"),
        "manual_spend": float(raw.get("manual_spend", 0.0)),
        "is_exempt": effective_exempt,
        "db_exempt": db_exempt,
        "is_model": is_model,
        "is_owner": is_owner,
    }

def _fmt_user(d: Dict[str, Any]) -> str:
    return f"{_display_name(d)} — <code>{d.get('user_id')}</code>"

REMINDER_MSGS = [
    "Hi {name}! 💋 Just a sweet reminder that Sanctuary requirements are still open this month. If you’d like to stay in the Sanctuary, make sure you’ve hit your minimum by the deadline. 💞",
    "Hey {name} ✨ You’re showing as <b>behind</b> on Sanctuary requirements right now. If that’s a mistake or you’ve already played/spent, please let one of the models know so we can update it.",
    "Psst, {name}… 😈 SuccuBot here. I’m showing that you haven’t hit requirements yet for this month. Please check the menus or DM a model so we can get you caught up ♥",
]

FINAL_WARNING_MSGS = [
    "Hi {name}. This is your <b>final warning</b> for Sanctuary requirements this month. If your requirements are not met by the deadline, you’ll be removed from the Sanctuary and will need to pay the door fee again to come back.",
    "{name}, you are still showing as <b>behind</b> on Sanctuary requirements. This is your last notice. If this isn’t updated in time, you’ll be removed until requirements are met and the door fee is repaid.",
    "Final notice for this month, {name}: Sanctuary requirements are still not met on your account. If this isn’t fixed before the sweep, you’ll be removed and will need to re-enter through the door fee.",
]

# ────────────── Reminder picker logic ──────────────

def _pick_key(action: str, admin_id: int) -> str:
    return f"pick:{action}:{admin_id}"

def _compute_targets() -> List[Dict[str, Any]]:
    coll = _get_members_coll()
    if coll is None:
        return []
    targets: List[Dict[str, Any]] = []
    for raw in coll.find({}):
        uid = raw.get("user_id")
        if not uid:
            continue
        md = _member_doc(int(uid))
        if md.get("is_exempt"):
            continue
        if float(md.get("manual_spend", 0.0)) >= REQUIRED_MIN_SPEND:
            continue
        targets.append(md)
    targets.sort(key=lambda m: (float(m.get("manual_spend", 0.0)), (m.get("first_name") or "").lower()))
    return targets

def _render_pick(action: str, admin_id: int, page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    st = _load_state(admin_id)
    key = _pick_key(action, admin_id)
    pstate = st.get(key) or {}

    targets = pstate.get("targets") or _compute_targets()
    selected = set(pstate.get("selected") or [])
    per_page = 10
    max_page = max(0, (len(targets) - 1) // per_page) if targets else 0
    page = max(0, min(page, max_page))

    pstate["targets"] = targets
    pstate["selected"] = list(selected)
    pstate["page"] = page
    st[key] = pstate
    _save_state(admin_id, st)

    title = "💌 Send Reminders (Behind Only)" if action == "reminder" else "⚠️ Send Final Warnings (Not Met)"
    lines = [f"<b>{title}</b>", f"Minimum required: <b>${REQUIRED_MIN_SPEND:.2f}</b>", ""]
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
        uid = md["user_id"]
        on = "✅" if uid in selected else "⬜️"
        label = f"{on} {_fmt_user(md)} — ${md.get('manual_spend', 0.0):.2f}"
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
        text = tmpl.format(name=name)
        await app.send_message(user_id, text, disable_web_page_preview=True)
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

async def _send_dms_for_action(app: Client, cq: CallbackQuery, action: str, only_selected: bool):
    coll = _get_members_coll()
    if coll is None:
        await cq.answer("Mongo not configured — cannot send.", show_alert=True)
        return

    admin_id = cq.from_user.id
    st = _load_state(admin_id)
    key = _pick_key(action, admin_id)
    pstate = st.get(key) or {}
    targets = pstate.get("targets") or _compute_targets()
    selected = set(pstate.get("selected") or [])

    if not targets:
        await cq.answer("Nobody is behind right now.", show_alert=True)
        return

    if only_selected:
        send_list = [m for m in targets if m["user_id"] in selected]
        if not send_list:
            await cq.answer("Select at least one member first.", show_alert=True)
            return
    else:
        send_list = targets

    await cq.answer("Sending…", show_alert=False)

    ok: List[Dict[str, Any]] = []
    fail: List[Tuple[Dict[str, Any], str]] = []

    for md in send_list:
        uid = int(md["user_id"])
        tmpl = random.choice(REMINDER_MSGS if action == "reminder" else FINAL_WARNING_MSGS)
        sent, reason = await _try_send_dm(app, uid, tmpl)
        if sent:
            ok.append(md)
            flag = "reminder_sent" if action == "reminder" else "final_warning_sent"
            coll.update_one({"user_id": uid}, {"$set": {flag: True}}, upsert=True)
        else:
            fail.append((md, reason))

    title = "Reminders" if action == "reminder" else "Final Warnings"
    summary = [
        f"<b>{title} sent</b>",
        f"✅ Success: <b>{len(ok)}</b>",
        f"❌ Failed: <b>{len(fail)}</b>",
    ]
    if ok:
        summary += ["", "<b>Sent to:</b>"] + [f"• {_fmt_user(m)}" for m in ok[:50]]
        if len(ok) > 50:
            summary.append(f"…and {len(ok)-50} more")
    if fail:
        summary += ["", "<b>Failed:</b>"]
        for m, r in fail[:50]:
            summary.append(f"• {_fmt_user(m)} — <code>{_escape(r)}</code>")
        if len(fail) > 50:
            summary.append(f"…and {len(fail)-50} more")

    await cq.message.reply_text("\n".join(summary), disable_web_page_preview=True)

    # log group
    await _log_event(app, f"{title} run by {admin_id}. Success={len(ok)} Failed={len(fail)}")

    text2, kb2 = _render_pick(action, admin_id, page=int(pstate.get("page") or 0))
    await cq.message.edit_text(text2, reply_markup=kb2, disable_web_page_preview=True)

# ────────────── Minimal UI to reach picker (keeps your existing panel working elsewhere) ──────────────

def _admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💌 Send Reminders (Behind Only)", callback_data="reqpanel:reminders")],
            [InlineKeyboardButton("⚠️ Send Final Warnings", callback_data="reqpanel:final_warnings")],
        ]
    )

def register(app: Client):
    log.info("✅ handlers.requirements_panel registered (SAFE STARTUP)")

    @app.on_callback_query(filters.regex("^reqpanel:admin$"))
    async def reqpanel_admin_cb(_, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only 💜", show_alert=True)
            return
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text="<b>Admin / Model Controls</b>\n\nPick an action:",
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex("^reqpanel:reminders$"))
    async def reqpanel_reminders(client: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        admin_id = cq.from_user.id
        text, kb = _render_pick("reminder", admin_id, page=0)
        await cq.answer()
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^reqpanel:final_warnings$"))
    async def reqpanel_final_warnings(client: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        admin_id = cq.from_user.id
        text, kb = _render_pick("final", admin_id, page=0)
        await cq.answer()
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):toggle:(\d+)$"))
    async def reqpick_toggle(client: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        parts = (cq.data or "").split(":")
        action = parts[1]
        uid = int(parts[3])
        admin_id = cq.from_user.id

        st = _load_state(admin_id)
        key = _pick_key(action, admin_id)
        pstate = st.get(key) or {}
        selected = set(pstate.get("selected") or [])
        if uid in selected:
            selected.remove(uid)
        else:
            selected.add(uid)
        pstate["selected"] = list(selected)
        st[key] = pstate
        _save_state(admin_id, st)

        text2, kb2 = _render_pick(action, admin_id, page=int(pstate.get("page") or 0))
        await cq.answer()
        await cq.message.edit_text(text2, reply_markup=kb2, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):page:(\d+)$"))
    async def reqpick_page(client: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        parts = (cq.data or "").split(":")
        action = parts[1]
        page = int(parts[3])
        admin_id = cq.from_user.id
        text2, kb2 = _render_pick(action, admin_id, page=page)
        await cq.answer()
        await cq.message.edit_text(text2, reply_markup=kb2, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):send_selected$"))
    async def reqpick_send_selected(client: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        action = (cq.data or "").split(":")[1]
        await _send_dms_for_action(client, cq, action, only_selected=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):send_all$"))
    async def reqpick_send_all(client: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        action = (cq.data or "").split(":")[1]
        await _send_dms_for_action(client, cq, action, only_selected=False)

    @app.on_callback_query(filters.regex("^reqpick:noop$"))
    async def reqpick_noop(_, cq: CallbackQuery):
        await cq.answer()
