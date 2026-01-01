# handlers/requirements_messages.py
"""
Requirements: Send Reminders / Final Warnings (Behind Only)
This module was split out of requirements_panel.py to keep files manageable.

Callbacks handled:
- reqpanel:reminders
- reqpanel:final_warnings
- reqpick:(reminder|final):toggle:<user_id>
- reqpick:(reminder|final):send_selected
- reqpick:(reminder|final):send_all
- reqpick:(reminder|final):page:<n>
- reqpick:noop
"""

import os
import json
import logging
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple, Set

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

try:
    from pymongo import MongoClient, ASCENDING
except Exception:  # pragma: no cover
    MongoClient = None  # type: ignore
    ASCENDING = 1

log = logging.getLogger(__name__)

# ────────────── ENV / CONFIG ──────────────

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "0")) or "0")

def _parse_id_list(raw: str) -> Set[int]:
    out: Set[int] = set()
    for part in (raw or "").replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.add(int(part))
        except Exception:
            continue
    return out

SUPER_ADMINS = _parse_id_list(os.getenv("SUPER_ADMINS", ""))
MODELS = _parse_id_list(os.getenv("MODELS", ""))

REQUIRED_MIN_SPEND = float(os.getenv("REQUIREMENTS_MIN_SPEND", "20") or "20")

# Log group (optional)
LOG_GROUP_ID: Optional[int] = None
for key in ("SANCTU_LOG_GROUP_ID", "SANCTUARY_LOG_CHANNEL"):
    v = os.getenv(key)
    if v:
        try:
            LOG_GROUP_ID = int(v)
            break
        except Exception:
            pass

# Mongo
_MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or ""
_MONGO_DB = os.getenv("MONGO_DB", "succubot")

# Collection names (match requirements_panel)
COLL_MEMBERS = os.getenv("REQ_MEMBERS_COLLECTION", "requirements_members")
COLL_REQSTATE = os.getenv("REQ_STATE_COLLECTION", "requirements_state")  # used for picker UI state

# ────────────── PERMISSIONS ──────────────

def _is_owner(user_id: int) -> bool:
    return bool(OWNER_ID and user_id == OWNER_ID)

def _is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS

def _is_model(user_id: int) -> bool:
    return user_id in MODELS

def _is_admin_or_model(user_id: int) -> bool:
    return _is_owner(user_id) or _is_super_admin(user_id) or _is_model(user_id)

async def _must_be_owner_or_model_admin(app: Client, cq: CallbackQuery) -> bool:
    uid = cq.from_user.id if cq.from_user else 0
    if _is_admin_or_model(uid):
        return True
    try:
        await cq.answer("Not allowed.", show_alert=True)
    except Exception:
        pass
    return False

# ────────────── MONGO HELPERS ──────────────

_client: Optional[MongoClient] = None
_db = None

def _get_db():
    global _client, _db
    if _db is not None:
        return _db
    if not _MONGO_URI or MongoClient is None:
        _db = None
        return None

    # Keep timeouts short so button callbacks don't "do nothing" forever.
    _client = MongoClient(
        _MONGO_URI,
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=3000,
        socketTimeoutMS=5000,
        retryWrites=True,
    )
    _db = _client[_MONGO_DB]
    # Best-effort indexes (won't crash if Mongo is unavailable)
    try:
        _db[COLL_MEMBERS].create_index([("chat_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
        _db[COLL_REQSTATE].create_index([("admin_id", ASCENDING), ("key", ASCENDING)], unique=True)
    except Exception:
        pass
    return _db

def _members_coll():
    db = _get_db()
    return db[COLL_MEMBERS] if db is not None else None

def _state_coll():
    db = _get_db()
    return db[COLL_REQSTATE] if db is not None else None

# ────────────── UTILS ──────────────

def _escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

async def _safe_send(app: Client, chat_id: int, text: str):
    try:
        await app.send_message(chat_id, text, disable_web_page_preview=True)
    except Exception as e:
        log.warning("Failed to send to %s: %s", chat_id, e)

async def _log_to_group(app: Client, text: str):
    if not LOG_GROUP_ID:
        return
    await _safe_send(app, LOG_GROUP_ID, f"[Requirements] {text}")

def _fmt_user(doc: Dict[str, Any]) -> str:
    name = doc.get("name") or doc.get("username") or str(doc.get("user_id") or "")
    uid = doc.get("user_id")
    if uid:
        return f"{_escape(str(name))} (<code>{uid}</code>)"
    return _escape(str(name))

def _display_name_for_doc(doc: Dict[str, Any]) -> str:
    return (doc.get("name") or doc.get("username") or f"User {doc.get('user_id')}").strip()

# ────────────── PICKER STATE ──────────────

def _pick_key(action: str) -> str:
    return f"pick:{action}"

def _load_state(admin_id: int) -> Dict[str, Any]:
    coll = _state_coll()
    if coll is None:
        return {}
    try:
        row = coll.find_one({"admin_id": admin_id, "key": "picker"}) or {}
        blob = row.get("state") or {}
        return blob if isinstance(blob, dict) else {}
    except Exception:
        return {}

def _save_state(admin_id: int, state: Dict[str, Any]) -> None:
    coll = _state_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"admin_id": admin_id, "key": "picker"},
            {"$set": {"state": state, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
    except Exception:
        pass

# ────────────── TARGET SELECTION ──────────────

def _compute_targets(chat_id: int) -> List[Dict[str, Any]]:
    """
    Returns members that are NOT exempt and are below REQUIRED_MIN_SPEND.
    """
    coll = _members_coll()
    if coll is None:
        return []
    try:
        docs = list(coll.find({"chat_id": chat_id, f"in_group.{chat_id}": True}))
    except Exception as e:
        log.warning("Mongo find failed (targets): %s", e)
        return []

    out: List[Dict[str, Any]] = []
    for d in docs:
        if d.get("exempt"):
            continue
        spend = float(d.get("manual_spend") or 0)
        if spend >= REQUIRED_MIN_SPEND:
            continue
        out.append({
            "chat_id": chat_id,
            "user_id": int(d.get("user_id") or 0),
            "name": d.get("name") or d.get("username") or "",
            "username": d.get("username") or "",
            "manual_spend": spend,
            "required": REQUIRED_MIN_SPEND,
        })

    out.sort(key=lambda m: (m.get("manual_spend", 0), _display_name_for_doc(m).lower()))
    return out

def _member_select_keyboard(action: str, admin_id: int, targets: List[Dict[str, Any]], selected: Set[int], page: int) -> InlineKeyboardMarkup:
    per_page = 10
    max_page = max(0, (len(targets) - 1) // per_page) if targets else 0
    page = max(0, min(page, max_page))
    start = page * per_page
    end = start + per_page
    chunk = targets[start:end]

    rows: List[List[InlineKeyboardButton]] = []
    for m in chunk:
        uid = int(m.get("user_id") or 0)
        mark = "✅ " if uid in selected else ""
        label = f"{mark}{_display_name_for_doc(m)} — ${m.get('manual_spend', 0):.2f}/${REQUIRED_MIN_SPEND:.2f}"
        rows.append([InlineKeyboardButton(label[:64], callback_data=f"reqpick:{action}:toggle:{uid}")])

    nav: List[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"reqpick:{action}:page:{page-1}"))
    nav.append(InlineKeyboardButton(f"Page {page+1}/{max_page+1 if targets else 1}", callback_data="reqpick:noop"))
    if page < max_page:
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"reqpick:{action}:page:{page+1}"))
    rows.append(nav)

    rows.append([
        InlineKeyboardButton("📨 Send Selected", callback_data=f"reqpick:{action}:send_selected"),
        InlineKeyboardButton("📣 Send All", callback_data=f"reqpick:{action}:send_all"),
    ])
    rows.append([InlineKeyboardButton("⬅ Back", callback_data="reqpanel:admin")])
    return InlineKeyboardMarkup(rows)

def _render_pick(action: str, admin_id: int, chat_id: int, page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    state = _load_state(admin_id)
    key = _pick_key(action)
    p = state.get(key) or {}
    targets = p.get("targets")
    if not isinstance(targets, list):
        targets = _compute_targets(chat_id)
    selected = set(p.get("selected") or [])

    # keep selection only for still-present targets
    current_ids = {int(t.get("user_id") or 0) for t in targets}
    selected = {uid for uid in selected if uid in current_ids}

    p["targets"] = targets
    p["selected"] = list(selected)
    p["page"] = int(page)
    state[key] = p
    _save_state(admin_id, state)

    title = "💌 Send Reminders (Behind Only)" if action == "reminder" else "⚠️ Send Final Warnings"
    msg = [f"<b>{title}</b>"]
    msg.append(f"Required spend: <b>${REQUIRED_MIN_SPEND:.2f}</b>")
    msg.append(f"Behind members found: <b>{len(targets)}</b>")
    msg.append("")
    msg.append("Tap names to select. Then choose <b>Send Selected</b> or <b>Send All</b>.")
    kb = _member_select_keyboard(action, admin_id, targets, selected, page=int(page))
    return "\n".join(msg), kb

# ────────────── DM SENDING ──────────────

def _build_dm(action: str, member: Dict[str, Any]) -> str:
    name = member.get("name") or "there"
    needed = max(0.0, REQUIRED_MIN_SPEND - float(member.get("manual_spend") or 0))
    if action == "reminder":
        return (
            f"Hey {name} 💕\n\n"
            f"Just a quick reminder — you’re currently <b>${needed:.2f}</b> behind the required spend for this cycle.\n"
            f"If you’ve already handled it, you can ignore this. If not, please check in ASAP.\n\n"
            f"Thank you 🖤"
        )
    # final
    return (
        f"Hi {name} ⚠️\n\n"
        f"This is your <b>final warning</b> — you’re still <b>${needed:.2f}</b> behind the required spend requirement.\n"
        f"If you don’t catch up by the deadline, you may lose access.\n\n"
        f"Please message an admin if you need help."
    )

async def _try_send_dm(app: Client, user_id: int, text: str) -> Tuple[bool, str]:
    try:
        await app.send_message(user_id, text, disable_web_page_preview=True)
        return True, "sent"
    except Exception as e:
        return False, str(e)

async def _send_dms_for_action(app: Client, cq: CallbackQuery, action: str, only_selected: bool):
    chat_id = cq.message.chat.id if cq.message and cq.message.chat else 0
    admin_id = cq.from_user.id if cq.from_user else 0

    state = _load_state(admin_id)
    key = _pick_key(action)
    p = state.get(key) or {}
    targets: List[Dict[str, Any]] = p.get("targets") if isinstance(p.get("targets"), list) else _compute_targets(chat_id)
    selected = set(p.get("selected") or [])

    send_list = targets if not only_selected else [t for t in targets if int(t.get("user_id") or 0) in selected]

    if not send_list:
        try:
            await cq.answer("No members selected.", show_alert=True)
        except Exception:
            pass
        return

    ok: List[Dict[str, Any]] = []
    fail: List[Tuple[Dict[str, Any], str]] = []

    # send sequentially to be gentle on rate limits
    for m in send_list:
        uid = int(m.get("user_id") or 0)
        if not uid:
            continue
        dm_text = _build_dm(action, m)
        success, reason = await _try_send_dm(app, uid, dm_text)
        if success:
            ok.append(m)
        else:
            fail.append((m, reason))
        await asyncio.sleep(0.5)

    # Update Mongo flags
    coll = _members_coll()
    if coll is not None:
        for m in ok:
            uid = int(m.get("user_id") or 0)
            field = "last_reminder_at" if action == "reminder" else "last_final_warning_at"
            try:
                coll.update_one(
                    {"chat_id": chat_id, "user_id": uid},
                    {"$set": {field: datetime.now(timezone.utc)}},
                    upsert=True,
                )
            except Exception:
                pass

    # Report back in chat
    summary_lines = []
    summary_lines.append(f"<b>Done.</b> {len(ok)} sent, {len(fail)} failed.")
    if ok:
        summary_lines.append("")
        summary_lines.append("<b>Sent:</b>")
        for m in ok[:50]:
            summary_lines.append(f"• {_fmt_user(m)}")
        if len(ok) > 50:
            summary_lines.append(f"…and {len(ok)-50} more")
    if fail:
        summary_lines.append("")
        summary_lines.append("<b>Failed:</b>")
        for m, r in fail[:25]:
            summary_lines.append(f"• {_fmt_user(m)} — <code>{_escape(r)[:120]}</code>")
        if len(fail) > 25:
            summary_lines.append(f"…and {len(fail)-25} more")

    try:
        await cq.message.reply_text("\n".join(summary_lines), disable_web_page_preview=True)
    except Exception:
        pass

    # Log to group
    try:
        await _log_to_group(app, re.sub(r"<.*?>", "", "\n".join(summary_lines)))
    except Exception:
        pass

    # Refresh picker UI
    text2, kb2 = _render_pick(action, admin_id, chat_id, page=int(p.get("page") or 0))
    try:
        await cq.message.edit_text(text2, reply_markup=kb2, disable_web_page_preview=True)
    except Exception:
        pass

# ────────────── REGISTER ──────────────

def register(app: Client):
    @app.on_callback_query(filters.regex(r"^reqpanel:reminders$"))
    async def _open_reminders(client: Client, cq: CallbackQuery):
        try:
            await cq.answer()
        except Exception:
            pass
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        admin_id = cq.from_user.id
        chat_id = cq.message.chat.id
        text, kb = _render_pick("reminder", admin_id, chat_id, page=0)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpanel:final_warnings$"))
    async def _open_final(client: Client, cq: CallbackQuery):
        try:
            await cq.answer()
        except Exception:
            pass
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        admin_id = cq.from_user.id
        chat_id = cq.message.chat.id
        text, kb = _render_pick("final", admin_id, chat_id, page=0)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):page:(\d+)$"))
    async def _page(client: Client, cq: CallbackQuery):
        try:
            await cq.answer()
        except Exception:
            pass
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        action, page_s = cq.data.split(":")[1], cq.data.split(":")[3]
        page = int(page_s)
        admin_id = cq.from_user.id
        chat_id = cq.message.chat.id
        text, kb = _render_pick(action, admin_id, chat_id, page=page)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):toggle:(\d+)$"))
    async def _toggle(client: Client, cq: CallbackQuery):
        try:
            await cq.answer()
        except Exception:
            pass
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        parts = cq.data.split(":")
        action = parts[1]
        uid = int(parts[3])
        admin_id = cq.from_user.id
        chat_id = cq.message.chat.id

        state = _load_state(admin_id)
        key = _pick_key(action)
        p = state.get(key) or {}
        selected = set(p.get("selected") or [])
        if uid in selected:
            selected.remove(uid)
        else:
            selected.add(uid)
        p["selected"] = list(selected)
        state[key] = p
        _save_state(admin_id, state)

        text, kb = _render_pick(action, admin_id, chat_id, page=int(p.get("page") or 0))
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):send_selected$"))
    async def _send_sel(client: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        action = cq.data.split(":")[1]
        await _send_dms_for_action(client, cq, action=action, only_selected=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):send_all$"))
    async def _send_all(client: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(client, cq):
            return
        action = cq.data.split(":")[1]
        await _send_dms_for_action(client, cq, action=action, only_selected=False)

    @app.on_callback_query(filters.regex(r"^reqpick:noop$"))
    async def _noop(client: Client, cq: CallbackQuery):
        try:
            await cq.answer()
        except Exception:
            pass
