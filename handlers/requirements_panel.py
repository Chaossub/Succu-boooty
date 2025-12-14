# handlers/requirements_panel.py

import os
import logging
import random
import re
from datetime import datetime, timezone
from typing import List, Set, Dict, Any, Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)
from pyrogram.errors import MessageNotModified

from pymongo import MongoClient, ASCENDING

log = logging.getLogger(__name__)

# ────────────── ENV & CONSTANTS ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI must be set for requirements_panel")

mongo = MongoClient(MONGO_URI)
db = mongo["Succubot"]
members_coll = db["requirements_members"]
pending_custom_coll = db["requirements_pending_custom_spend"]  # legacy, now unused for buttons-only

members_coll.create_index([("user_id", ASCENDING)], unique=True)
pending_custom_coll.create_index([("owner_id", ASCENDING)], unique=True)

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))

# Model names for attribution buttons
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

def _parse_id_list(val: str | None) -> Set[int]:
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

# Sanctuary group IDs to scan
_group_ids_str = os.getenv("SANCTUARY_GROUP_IDS")
if not _group_ids_str:
    _single = os.getenv("SUCCUBUS_SANCTUARY")
    SANCTUARY_GROUP_IDS: List[int] = [int(_single)] if _single else []
else:
    SANCTUARY_GROUP_IDS = [
        int(x) for x in _group_ids_str.replace(" ", "").split(",") if x
    ]

LOG_GROUP_ID: Optional[int] = None
for key in ("SANCTU_LOG_GROUP_ID", "SANCTUARY_LOG_CHANNEL"):
    if os.getenv(key):
        try:
            LOG_GROUP_ID = int(os.getenv(key))
            break
        except ValueError:
            pass

# Minimum requirement total to be "met"
REQUIRED_MIN_SPEND = float(os.getenv("REQUIREMENTS_MIN_SPEND", "20"))

# Simple in-memory state for some flows
STATE: Dict[int, Dict[str, Any]] = {}

# Pending manual-spend edits (buttons-only) per admin
PENDING_SPEND: Dict[int, Dict[str, Any]] = {}
PENDING_ATTRIB: Dict[int, Dict[str, Any]] = {}

# ────────────── Helper functions ──────────────

def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def _is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS or _is_owner(user_id)

def _is_model(user_id: int) -> bool:
    # Owner always counts as model+exempt for requirements
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

def _member_doc(user_id: int) -> Dict[str, Any]:
    """
    Load a member doc and apply derived fields:
    - Owner & models are always effectively exempt from requirements
    """
    doc = members_coll.find_one({"user_id": user_id}) or {}
    is_owner = user_id == OWNER_ID
    is_model = user_id in MODELS or is_owner
    db_exempt = bool(doc.get("is_exempt", False))
    effective_exempt = db_exempt or is_model

    return {
        "user_id": user_id,
        "first_name": doc.get("first_name", ""),
        "username": doc.get("username"),
        "manual_spend": float(doc.get("manual_spend", 0.0)),
        "manual_spend_models": dict(doc.get("manual_spend_models", {})),
        "is_exempt": effective_exempt,
        "db_exempt": db_exempt,
        "is_model": is_model,
        "is_owner": is_owner,
        "reminder_sent": bool(doc.get("reminder_sent", False)),
        "final_warning_sent": bool(doc.get("final_warning_sent", False)),
        "last_updated": doc.get("last_updated"),
    }

def _format_member_status(doc: Dict[str, Any]) -> str:
    total = doc["manual_spend"]
    exempt = doc["is_exempt"]
    is_model = doc.get("is_model", False)
    is_owner = doc.get("is_owner", False)

    name_parts = []
    if doc.get("first_name"):
        name_parts.append(doc["first_name"])
    if doc.get("username"):
        name_parts.append(f"(@{doc['username']})")
    name = " ".join(name_parts) or "Unknown"

    header = (
        "<b>Requirement Status</b>\n\n"
        f"<b>Member:</b> {name} (<code>{doc['user_id']}</code>)\n\n"
    )

    if is_owner:
        status = (
            "👑 <b>Sanctuary owner</b> – you’re automatically exempt from requirements. "
            "SuccuBot will never mark you behind or kick you for this."
        )
    elif exempt and is_model:
        status = (
            "✅ <b>Model</b> – you’re automatically exempt from requirements. "
            "Even if your spend shows as $0, you won’t be warned or kicked."
        )
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
        dt = doc["last_updated"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"\nLast updated: <code>{dt}</code>")
    return "\n".join(lines)

def _display_name_for_doc(d: Dict[str, Any]) -> str:
    first_name = (d.get("first_name") or "").strip()
    username = d.get("username")
    if username and first_name:
        return f"{first_name} @{username}"
    if first_name:
        return first_name
    if username:
        return f"@{username}"
    return "Unknown"

# ────────────── DM text templates ──────────────

REMINDER_MSGS = [
    "Hi {name}! 💋 Just a sweet reminder that Sanctuary requirements are still open this month. "
    "If you’d like to stay in the Sanctuary, make sure you’ve hit your minimum by the deadline. 💞",
    "Hey {name} ✨ You’re showing as <b>behind</b> on Sanctuary requirements right now. "
    "If that’s a mistake or you’ve already played/spent, please let one of the models know so we can update it.",
    "Psst, {name}… 😈 SuccuBot here. I’m showing that you haven’t hit requirements yet for this month. "
    "Please check the menus or DM a model so we can get you caught up ♥",
]

FINAL_WARNING_MSGS = [
    "⚠️ Final reminder, {name}. Sanctuary requirements are still not met. "
    "If you want to stay, please handle it ASAP. 💗",
    "{name} — this is your <b>final warning</b> about Sanctuary requirements. "
    "If you’ve already paid/played, DM a model so we can fix your totals.",
]

KICK_MSGS = [
    "Removed for not meeting requirements this month. 💔 You’re welcome back anytime once requirements are handled.",
    "SuccuBot removed you due to unmet requirements. If this is a mistake, DM Roni.",
]

# ────────────── Keyboards ──────────────

def _back_to_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")]])

def _member_select_keyboard(back_cb: str, title: str) -> InlineKeyboardMarkup:
    docs = list(members_coll.find().sort("first_name", ASCENDING).limit(50))
    rows: List[List[InlineKeyboardButton]] = []
    if not docs:
        return _back_to_admin_kb()
    for d in docs:
        uid = d["user_id"]
        label = _display_name_for_doc(d)
        rows.append([InlineKeyboardButton(label, callback_data=f"{title}:{uid}")])
    rows.append([InlineKeyboardButton("⬅ Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)

# ────────────── Main Register ──────────────

def register(app: Client):

    # ... (UNCHANGED CONTENT ABOVE THIS IN YOUR FILE)
    # NOTE: Everything else remains as-is. Only the manual spend delta callback is replaced below.

    # ────────────── Add Manual Spend (BUTTONS ONLY) ──────────────

    def _member_select_keyboard_spend() -> InlineKeyboardMarkup:
        docs = list(members_coll.find().sort("first_name", ASCENDING).limit(50))
        rows: List[List[InlineKeyboardButton]] = []

        if not docs:
            return _back_to_admin_kb()

        for d in docs:
            uid = d["user_id"]
            label = _display_name_for_doc(d)
            rows.append([InlineKeyboardButton(label, callback_data=f"reqpanel:spend_member:{uid}")])

        rows.append([InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")])
        return InlineKeyboardMarkup(rows)

    def _spend_keyboard(target_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("+$5", callback_data=f"reqpanel:spend_delta:{target_id}:5"),
                    InlineKeyboardButton("+$10", callback_data=f"reqpanel:spend_delta:{target_id}:10"),
                    InlineKeyboardButton("+$20", callback_data=f"reqpanel:spend_delta:{target_id}:20"),
                ],
                [
                    InlineKeyboardButton("+$25", callback_data=f"reqpanel:spend_delta:{target_id}:25"),
                    InlineKeyboardButton("+$50", callback_data=f"reqpanel:spend_delta:{target_id}:50"),
                ],
                [
                    InlineKeyboardButton("-$5", callback_data=f"reqpanel:spend_delta:{target_id}:-5"),
                    InlineKeyboardButton("-$10", callback_data=f"reqpanel:spend_delta:{target_id}:-10"),
                    InlineKeyboardButton("-$20", callback_data=f"reqpanel:spend_delta:{target_id}:-20"),
                ],
                [
                    InlineKeyboardButton("-$25", callback_data=f"reqpanel:spend_delta:{target_id}:-25"),
                    InlineKeyboardButton("-$50", callback_data=f"reqpanel:spend_delta:{target_id}:-50"),
                ],
                [
                    InlineKeyboardButton("🧹 Clear Total (Preview)", callback_data=f"reqpanel:spend_clear:{target_id}"),
                ],
                [
                    InlineKeyboardButton("✅ Confirm & Pick Model", callback_data=f"reqpanel:spend_confirm:{target_id}"),
                ],
                [
                    InlineKeyboardButton("⬅ Back to Member List", callback_data="reqpanel:add_spend"),
                ],
            ]
        )

    async def _render_spend_panel(message: Message, target_id: int, display_total: float):
        doc = _member_doc(target_id)
        name_parts = []
        if doc.get("first_name"):
            name_parts.append(doc["first_name"])
        if doc.get("username"):
            name_parts.append(f"(@{doc['username']})")
        name = " ".join(name_parts) or "Unknown"

        text = (
            "<b>Add Manual Spend</b>\n\n"
            f"Member: {name} (<code>{target_id}</code>)\n"
            f"Current manual total: <b>${display_total:.2f}</b>\n\n"
            "Use the buttons below to add, subtract, or clear their total for this month.\n"
            "Totals will be included in the end-of-month requirement logs."
        )

        await _safe_edit_text(
            message,
            text=text,
            reply_markup=_spend_keyboard(target_id),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex("^reqpanel:add_spend$"))
    async def reqpanel_add_spend_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        kb = _member_select_keyboard_spend()
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Add Manual Spend</b>\n\n"
                "Tap a member below to credit offline payments for this month.\n"
                "This adds extra credited dollars on top of Stripe / games for this month only."
            ),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:spend_member:(\d+)$"))
    async def reqpanel_spend_member_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])
        doc = _member_doc(target_id)
        current_total = doc["manual_spend"]

        PENDING_SPEND[user_id] = {
            "target_id": target_id,
            "original_total": current_total,
            "working_total": current_total,
        }

        await cq.answer()
        await _render_spend_panel(cq.message, target_id, current_total)

    # ✅ UPDATED: bulletproof delta handler + visible alert on error
    @app.on_callback_query(filters.regex(r"^reqpanel:spend_delta:(\d+):(-?\d+)$"))
    async def reqpanel_spend_delta_cb(_, cq: CallbackQuery):
        try:
            user_id = cq.from_user.id
            if not _is_admin_or_model(user_id):
                await cq.answer("Only Roni and models can add spend.", show_alert=True)
                return

            m = re.match(r"^reqpanel:spend_delta:(\d+):(-?\d+)$", cq.data or "")
            if not m:
                await cq.answer("That button payload didn’t parse.", show_alert=True)
                return

            target_id = int(m.group(1))
            delta = float(m.group(2))

            state = PENDING_SPEND.get(user_id)
            if not state or state.get("target_id") != target_id:
                doc = _member_doc(target_id)
                state = {
                    "target_id": target_id,
                    "original_total": doc["manual_spend"],
                    "working_total": doc["manual_spend"],
                }
                PENDING_SPEND[user_id] = state

            working = float(state.get("working_total", 0.0)) + delta
            if working < 0:
                working = 0.0
            state["working_total"] = working

            await cq.answer()
            await _render_spend_panel(cq.message, target_id, working)

        except Exception as e:
            log.exception("requirements_panel: spend_delta failed: %s", e)
            try:
                await cq.answer(f"Manual spend error: {type(e).__name__}", show_alert=True)
            except Exception:
                pass

    # ... the rest of your file continues unchanged ...
