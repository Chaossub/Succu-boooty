# handlers/requirements_panel.py

import os
import logging
import random
import re
import io
from datetime import datetime, timezone
from typing import List, Set, Dict, Any, Optional, Tuple

from pyrogram import Client, filters
from pyrogram.enums import ChatType
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
        "dm_ready": bool(doc.get("dm_ready", False)),
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
        rows.append(
            [
                InlineKeyboardButton(
                    "🛠 Admin / Model Controls", callback_data="reqpanel:admin"
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "⬅ Back to Sanctuary Menu", callback_data="panels:root"
            )
        ]
    )
    return InlineKeyboardMarkup(rows)

def _admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Member Status List", callback_data="reqpanel:list"),
                InlineKeyboardButton("➕ Add Manual Spend", callback_data="reqpanel:add_spend"),
            ],
            [
                InlineKeyboardButton("✅ Exempt / Un-exempt", callback_data="reqpanel:toggle_exempt"),
            ],
            [
                InlineKeyboardButton("📡 Scan Group Members", callback_data="reqpanel:scan"),
                InlineKeyboardButton("📊 Scan & Log Status", callback_data="reqpanel:scan_log"),
            ],
            [
                InlineKeyboardButton("💬 DM-Ready (This Group)", callback_data="reqpanel:dm_ready_group"),
            ],
            [
                InlineKeyboardButton("💌 Send Reminders (Behind Only)", callback_data="reqpanel:reminders"),
            ],
            [
                InlineKeyboardButton("⚠️ Send Final Warnings", callback_data="reqpanel:final_warnings"),
            ],
            [
                InlineKeyboardButton("🧹 Kick Behind (Manual)", callback_data="kickreq:menu"),
            ],
            [
                InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home"),
            ],
        ]
    )

def _back_to_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")]]
    )

# ────────────── Member selection keyboards ──────────────

def _member_select_keyboard(back_cb: str, title: str) -> InlineKeyboardMarkup:
    """
    Generic member selector (first 50, sorted by first_name).
    """
    docs = list(members_coll.find().sort("first_name", ASCENDING).limit(50))
    rows: List[List[InlineKeyboardButton]] = []

    if not docs:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data=back_cb)]]
        )

    for d in docs:
        uid = d["user_id"]
        label = _display_name_for_doc(d)
        rows.append([InlineKeyboardButton(label, callback_data=f"{title}:{uid}")])

    rows.append([InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")])
    return InlineKeyboardMarkup(rows)

# ────────────── Core handlers ──────────────

def register(app: Client):
    log.info(
        "✅ handlers.requirements_panel registered (OWNER_ID=%s, super_admins=%s, models=%s, groups=%s)",
        OWNER_ID,
        SUPER_ADMINS,
        MODELS,
        SANCTUARY_GROUP_IDS,
    )

    # Cancel any stuck flow (DM only)
    @app.on_message(filters.private & filters.command("cancel"))
    async def reqpanel_cancel_cmd(client: Client, msg: Message):
        uid = msg.from_user.id
        STATE.pop(uid, None)
        PENDING_SPEND.pop(uid, None)
        PENDING_ATTRIB.pop(uid, None)
        pending_custom_coll.delete_one({"owner_id": uid})
        await msg.reply_text("✅ Cancelled. You can use the buttons again.")

    # Entry point from main menu button
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
            text_lines.extend(
                [
                    "• <b>Admin / Model Controls</b> – open the owner/models tools panel "
                    "(lists, manual credit, exemptions, reminders).",
                ]
            )
        text_lines.append("")
        text_lines.append(
            "Regular members only see their own status. "
            "Owner & models get the full tools."
        )

        await _safe_edit_text(
            cq.message,
            text="\n".join(text_lines),
            reply_markup=_root_kb(is_admin),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^reqpanel:open$"))
    async def reqpanel_open_cb(_, cq: CallbackQuery):
        await reqpanel_home_cb(_, cq)

    
    # Compatibility aliases (older buttons / panels)
    @app.on_callback_query(filters.regex(r"^(requirements:help|requirements_help|requirements:open|requirements:panel)$"))
    async def reqpanel_compat_open_cb(_, cq: CallbackQuery):
        await reqpanel_home_cb(_, cq)

    @app.on_message(filters.private & filters.command(["requirements", "requirementshelp", "reqhelp", "reqs"]))
    async def reqpanel_command_open(_, m: Message):
        # Sends/updates a fresh panel message
        try:
            await m.reply_text(
                "<b>Requirements</b>\n\nTap below to open the requirements panel.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 Requirements Panel", callback_data="reqpanel:home")]]),
                disable_web_page_preview=True,
            )
        except Exception:
            pass

# Owner / models tools panel
    @app.on_callback_query(filters.regex("^reqpanel:admin$"))
    async def reqpanel_admin_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and approved models can open this.", show_alert=True)
            return

        text = (
            "<b>Admin / Model Controls</b>\n\n"
            "Use these tools to manage Sanctuary requirements for the month.\n"
            "Everything you do here updates what SuccuBot uses when checking "
            "member status or running sweeps, so double-check before you confirm changes.\n\n"
            "From here you can:\n"
            "▪️ View the full member status list\n"
            "▪️ Add manual spend credit for offline payments\n"
            "▪️ Exempt / un-exempt members (buttons only)\n"
            "▪️ Scan groups into the tracker\n"
            "▪️ Send reminder DMs to members who are behind\n"
            "▪️ Send final-warning DMs to those still not meeting minimums\n\n"
            "<i>Only you and approved model admins see this panel.</i>"
        )

        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ────────────── Self-status ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:self$"))
    async def reqpanel_self_cb(_, cq: CallbackQuery):
        user = cq.from_user
        doc = _member_doc(user.id)
        text = _format_member_status(doc)
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_root_kb(_is_admin_or_model(user.id)),
            disable_web_page_preview=True,
        )

    # ────────────── IMPORTANT FIX ──────────────
    # The state router should NEVER run in groups.
    # This is what was causing your bot to hijack normal chat messages.
    @app.on_message(filters.private & filters.text)
    async def requirements_state_router(client: Client, msg: Message):
        user_id = msg.from_user.id

        # Legacy custom-amount flow in Mongo (no longer used)
        pending = pending_custom_coll.find_one({"owner_id": user_id})
        if pending:
            pending_custom_coll.delete_one({"owner_id": user_id})
            await msg.reply_text(
                "This custom-amount flow has been replaced with buttons. "
                "Please use the Add Manual Spend buttons again."
            )
            return

        state = STATE.get(user_id)
        if not state:
            return

        mode = state.get("mode")

        try:
            # LOOKUP FLOW (if you ever re-enable it)
            if mode == "lookup":
                target_id: Optional[int] = None

                if msg.forward_from:
                    target_id = msg.forward_from.id
                elif msg.text.startswith("@"):
                    username = msg.text[1:].strip().lower()
                    doc = members_coll.find_one({"username": username})
                    if doc:
                        target_id = doc["user_id"]
                else:
                    try:
                        target_id = int(msg.text.strip())
                    except ValueError:
                        pass

                if not target_id:
                    await msg.reply_text(
                        "I couldn’t figure out who you meant. Try again with a forwarded message, "
                        "@username, or numeric ID."
                    )
                    return

                doc = _member_doc(target_id)
                text = _format_member_status(doc)
                await msg.reply_text(text)
                STATE.pop(user_id, None)
                return

            # TOGGLE EXEMPT (legacy typed ID) — kept for safety, DM only
            if mode == "toggle_exempt":
                try:
                    target_id = int(msg.text.strip())
                except ValueError:
                    await msg.reply_text("Please send just the numeric Telegram user ID.")
                    return

                doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}
                new_val = not bool(doc.get("is_exempt", False))

                members_coll.update_one(
                    {"user_id": target_id},
                    {
                        "$set": {
                            "is_exempt": new_val,
                            "last_updated": datetime.now(timezone.utc),
                            "first_name": doc.get("first_name", ""),
                            "username": doc.get("username"),
                        }
                    },
                    upsert=True,
                )

                model_note = ""
                if target_id == OWNER_ID:
                    model_note = " (OWNER – still exempt overall)"
                elif target_id in MODELS:
                    model_note = " (MODEL – still exempt overall)"

                await msg.reply_text(
                    f"User <code>{target_id}</code> is now "
                    f"{'✅ EXEMPT' if new_val else '❌ NOT exempt'} for this month.{model_note}"
                )
                await _log_event(client, f"Exempt toggled to {new_val} for {target_id} by {user_id}")
                STATE.pop(user_id, None)
                return

        except Exception as e:
            log.exception("requirements_panel: state router failed: %s", e)
            STATE.pop(user_id, None)
            await msg.reply_text(
                "Sorry, something went wrong saving that. "
                "Please tap the buttons again and retry."
            )

    # ────────────── Admin-panel buttons ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:list$"))
    async def reqpanel_list_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can view the full list.", show_alert=True)
            return

        docs = list(members_coll.find().sort("user_id", ASCENDING).limit(50))
        if not docs:
            text = "<b>Member Status List</b>\n\nNo tracked members yet. Try running a scan first."
        else:
            lines = ["<b>Member Status List (first 50)</b>\n"]
            for d in docs:
                uid = d["user_id"]
                total = float(d.get("manual_spend", 0.0))
                db_exempt = d.get("is_exempt", False)
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

                display_name = _display_name_for_doc(d)
                lines.append(f"• {display_name} (<code>{uid}</code>) – {status} (${total:.2f})")
            text = "\n".join(lines)

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── Toggle Exempt (BUTTONS ONLY) ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:toggle_exempt$"))
    async def reqpanel_toggle_exempt_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can change exemptions.", show_alert=True)
            return

        kb = _member_select_keyboard(
            back_cb="reqpanel:home",
            title="reqpanel:toggle_exempt_member",
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Exempt / Un-exempt Member</b>\n\n"
                "Tap a member below to flip their exempt status for this month.\n\n"
                "<i>Owner and models stay effectively exempt overall even if you uncheck them here.</i>"
            ),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:toggle_exempt_member:(\d+)$"))
    async def reqpanel_toggle_exempt_member_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can change exemptions.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])
        doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}

        new_val = not bool(doc.get("is_exempt", False))

        members_coll.update_one(
            {"user_id": target_id},
            {
                "$set": {
                    "is_exempt": new_val,
                    "last_updated": datetime.now(timezone.utc),
                    "first_name": doc.get("first_name", ""),
                    "username": doc.get("username"),
                }
            },
            upsert=True,
        )

        model_note = ""
        if target_id == OWNER_ID:
            model_note = " (OWNER – still exempt overall)"
        elif target_id in MODELS:
            model_note = " (MODEL – still exempt overall)"

        await _log_event(client, f"Exempt toggled to {new_val} for {target_id} by {user_id}")

        await cq.answer("Saved.", show_alert=False)
        await _safe_edit_text(
            cq.message,
            text=(
                "✅ <b>Saved</b>\n\n"
                f"User <code>{target_id}</code> is now "
                f"{'✅ EXEMPT' if new_val else '❌ NOT exempt'} for this month.{model_note}\n\n"
                "Tap another member to continue."
            ),
            reply_markup=_member_select_keyboard(
                back_cb="reqpanel:home",
                title="reqpanel:toggle_exempt_member",
            ),
            disable_web_page_preview=True,
        )

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


    
    @app.on_callback_query(filters.regex(r"^reqpanel:spend_clear:(\d+)$"))
    async def reqpanel_spend_clear_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])

        state = PENDING_SPEND.get(user_id)
        if not state or state.get("target_id") != target_id:
            doc = _member_doc(target_id)
            state = {
                "target_id": target_id,
                "original_total": doc["manual_spend"],
                "working_total": 0.0,
            }
            PENDING_SPEND[user_id] = state
        else:
            state["working_total"] = 0.0

        await cq.answer("Cleared (preview). Tap Confirm to save.", show_alert=False)
        await _render_spend_panel(cq.message, target_id, 0.0)

    @app.on_callback_query(filters.regex(r"^reqpanel:spend_confirm:(\d+)$"))
    async def reqpanel_spend_confirm_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])
        state = PENDING_SPEND.get(user_id)
        if not state or state.get("target_id") != target_id:
            await cq.answer("No pending changes for this member. Use the +/- buttons first.", show_alert=True)
            return

        original = float(state.get("original_total", 0.0))
        new_total = float(state.get("working_total", original))
        delta = new_total - original

        if abs(delta) < 0.0001:
            await cq.answer("No changes to save for this member.", show_alert=True)
            return

        doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}
        members_coll.update_one(
            {"user_id": target_id},
            {
                "$set": {
                    "manual_spend": new_total,
                    "last_updated": datetime.now(timezone.utc),
                    "first_name": doc.get("first_name", ""),
                    "username": doc.get("username"),
                }
            },
            upsert=True,
        )

        await _log_event(
            client,
            f"Manual spend change {delta:+.2f} for {target_id} by {user_id}. New total: ${new_total:.2f}",
        )

        PENDING_ATTRIB[user_id] = {
            "target_id": target_id,
            "delta": delta,
            "new_total": new_total,
        }

        model_buttons: List[List[InlineKeyboardButton]] = []
        row: List[InlineKeyboardButton] = []
        for slug, label in MODEL_NAME_MAP.items():
            if not label:
                continue
            row.append(InlineKeyboardButton(label, callback_data=f"reqpanel:spend_model:{target_id}:{slug}"))
            if len(row) == 2:
                model_buttons.append(row)
                row = []
        if row:
            model_buttons.append(row)

        model_buttons.append([InlineKeyboardButton("Split / Other", callback_data=f"reqpanel:spend_model:{target_id}:other")])
        model_buttons.append([InlineKeyboardButton("Skip attribution", callback_data=f"reqpanel:spend_model:{target_id}:skip")])

        kb = InlineKeyboardMarkup(model_buttons)

        doc_view = _member_doc(target_id)
        name_parts = []
        if doc_view.get("first_name"):
            name_parts.append(doc_view["first_name"])
        if doc_view.get("username"):
            name_parts.append(f"(@{doc_view['username']})")
        name = " ".join(name_parts) or "Unknown"

        text = (
            "<b>Confirm Manual Spend</b>\n\n"
            f"Saved change of <b>{delta:+.2f}</b> for {name} (<code>{target_id}</code>).\n"
            f"New manual total for this month: <b>${new_total:.2f}</b>.\n\n"
            "Who received this payment? Choose a model below.\n"
            "If it was split, use <b>Split / Other</b>."
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:spend_model:(\d+):([a-z]+)$"))
    async def reqpanel_spend_model_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        parts = cq.data.split(":")
        target_id = int(parts[2])
        slug = parts[3]

        attrib = PENDING_ATTRIB.get(user_id)
        if not attrib or attrib.get("target_id") != target_id:
            await cq.answer("This edit was already finished or expired.", show_alert=True)
            return

        delta = float(attrib.get("delta", 0.0))
        new_total = float(attrib.get("new_total", 0.0))

        model_label = "Unattributed"
        if slug == "skip":
            model_field = "manual_spend_models.untracked"
            model_label = "Skipped attribution"
        elif slug == "other":
            model_field = "manual_spend_models.other"
            model_label = "Split / Other"
        else:
            model_field = f"manual_spend_models.{slug}"
            model_label = MODEL_NAME_MAP.get(slug, slug.capitalize())

        members_coll.update_one(
            {"user_id": target_id},
            {"$inc": {model_field: delta}},
            upsert=True,
        )

        await _log_event(
            client,
            f"Manual spend attribution {delta:+.2f} for {target_id} marked as {model_label} by {user_id}.",
        )

        PENDING_ATTRIB.pop(user_id, None)
        PENDING_SPEND.pop(user_id, None)

        doc_view = _member_doc(target_id)
        name_parts = []
        if doc_view.get("first_name"):
            name_parts.append(doc_view["first_name"])
        if doc_view.get("username"):
            name_parts.append(f"(@{doc_view['username']})")
        name = " ".join(name_parts) or "Unknown"

        text = (
            "✅ <b>Manual Spend Saved</b>\n\n"
            f"Member: {name} (<code>{target_id}</code>)\n"
            f"Change this edit: <b>{delta:+.2f}</b> credited to <b>{model_label}</b>.\n"
            f"New manual total for this month: <b>${new_total:.2f}</b>.\n\n"
            "You can pick another member from the list to continue."
        )

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back to Member List", callback_data="reqpanel:add_spend")]]
        )

        await cq.answer("Saved.", show_alert=False)
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ────────────── Scan members ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:scan$"))
    async def reqpanel_scan_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can run scans.", show_alert=True)
            return

        if not SANCTUARY_GROUP_IDS:
            await cq.answer("No Sanctuary group IDs configured.", show_alert=True)
            return

        total_indexed = 0
        for gid in SANCTUARY_GROUP_IDS:
            try:
                async for member in client.get_chat_members(gid):
                    if member.user.is_bot:
                        continue
                    u = member.user
                    username = (u.username or "").lower() if u.username else None
                    members_coll.update_one(
                        {"user_id": u.id},
                        {
                            "$set": {
                                "first_name": u.first_name or "",
                                "username": username,
                                "last_updated": datetime.now(timezone.utc),
                            },
                            "$addToSet": {"groups": gid},
                        },
                        upsert=True,
                    )
                    total_indexed += 1
            except Exception as e:
                log.warning("requirements_panel: failed scanning group %s: %s", gid, e)

        await _log_event(client, f"Scan complete by {user_id}: indexed or updated {total_indexed} members.")
        await cq.answer("Scan complete.", show_alert=False)
        await _safe_edit_text(
            cq.message,
            text=(f"✅ Scan complete.\nIndexed or updated {total_indexed} members from Sanctuary group(s)."),
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    
    # ────────────── Scan + log status ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:scan_log$"))
    async def reqpanel_scan_log_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can run scans.", show_alert=True)
            return

        if not SANCTUARY_GROUP_IDS:
            await cq.answer("No Sanctuary group IDs configured.", show_alert=True)
            return

        # Scan members (same as scan button) and also track group membership
        total_indexed = 0
        for gid in SANCTUARY_GROUP_IDS:
            try:
                async for member in client.get_chat_members(gid):
                    if member.user.is_bot:
                        continue
                    u = member.user
                    username = (u.username or "").lower() if u.username else None
                    members_coll.update_one(
                        {"user_id": u.id},
                        {
                            "$set": {
                                "first_name": u.first_name or "",
                                "username": username,
                                "last_updated": datetime.now(timezone.utc),
                            },
                            "$addToSet": {"groups": gid},
                        },
                        upsert=True,
                    )
                    total_indexed += 1
            except Exception as e:
                log.warning("requirements_panel: failed scanning group %s: %s", gid, e)

        # Summarize
        docs = list(members_coll.find())
        total = len(docs)
        met = behind = exempt = 0

        for d in docs:
            uid = d.get("user_id")
            if not uid:
                continue
            md = _member_doc(uid)
            if md["is_exempt"]:
                exempt += 1
            elif md["manual_spend"] >= REQUIRED_MIN_SPEND:
                met += 1
            else:
                behind += 1

        summary = (
            "📊 <b>Sanctuary Requirements Scan</b>\n\n"
            f"👥 Total members tracked: <b>{total}</b>\n"
            f"✅ Requirements met: <b>{met}</b>\n"
            f"⚠️ Behind: <b>{behind}</b>\n"
            f"🟢 Exempt (models/owner/exempt): <b>{exempt}</b>\n\n"
            f"📡 Indexed/updated this run: <b>{total_indexed}</b>\n"
            f"💵 Minimum required: ${REQUIRED_MIN_SPEND:.2f}"
        )

        await _log_event(client, f"Scan+log run by {user_id}: indexed {total_indexed} members. Met={met}, Behind={behind}, Exempt={exempt}.")
        if LOG_GROUP_ID:
            await _safe_send(client, LOG_GROUP_ID, summary)

        await cq.answer("Scan & log complete ✅", show_alert=True)
        await _safe_edit_text(
            cq.message,
            text="✅ Scan & log complete. Summary sent to the log group.",
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── DM-ready list (current group) ──────────────

    
    # ────────────── DM-ready list (pick group) ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:dm_ready_group$"))
    async def reqpanel_dm_ready_group_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Admins only 💜", show_alert=True)
            return

        if not SANCTUARY_GROUP_IDS:
            await cq.answer("No Sanctuary group IDs configured.", show_alert=True)
            return

        # In DM with the bot, we can't infer which group you mean—so pick one.
        rows = []
        for gid in SANCTUARY_GROUP_IDS[:30]:
            rows.append([InlineKeyboardButton(f"📍 Group {gid}", callback_data=f"reqpanel:dm_ready_gid:{gid}")])
        rows.append([InlineKeyboardButton("⬅ Back", callback_data="reqpanel:admin")])
        kb = InlineKeyboardMarkup(rows)

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text="💬 <b>DM-Ready</b>\n\nPick which group you want to filter by:",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

        @app.on_callback_query(filters.regex(r"^reqpanel:dm_ready_gid:(-?\d+)$"))
        async def reqpanel_dm_ready_gid_cb(client: Client, cq: CallbackQuery):
            user_id = cq.from_user.id
            if not _is_admin_or_model(user_id):
                await cq.answer("Admins only 💜", show_alert=True)
                return

            gid = int((cq.data or "").split(":")[-1])

            # Pull everyone we know is in this group (from Scan Group Members),
            # then split into DM-ready vs NOT DM-ready.
            all_docs = list(members_coll.find({"groups": gid}).sort("first_name", ASCENDING))

            ready_docs = [d for d in all_docs if d.get("dm_ready") is True]
            not_ready_docs = [d for d in all_docs if d.get("dm_ready") is not True]

            if not all_docs:
                text = (
                    f"💬 <b>DM Status (This Group)</b>\n"
                    f"Group: <code>{gid}</code>\n\n"
                    "• No members found for this group yet.\n\n"
                    "Note: Run 📡 <b>Scan Group Members</b> first so the panel knows who is in the group."
                )
            else:
                lines: List[str] = [
                    "💬 <b>DM Status (This Group)</b>",
                    f"Group: <code>{gid}</code>",
                    "",
                    f"✅ DM-Ready: <b>{len(ready_docs)}</b>",
                ]

                # Show DM-ready list (cap to avoid Telegram limits)
                for d in ready_docs[:80]:
                    name = _display_name_for_doc(d)
                    uid = d.get("user_id")
                    lines.append(f"• {name} — <code>{uid}</code>")

                if len(ready_docs) > 80:
                    lines.append(f"…and <b>{len(ready_docs) - 80}</b> more DM-ready.")

                lines.extend([
                    "",
                    f"🚫 NOT DM-Ready: <b>{len(not_ready_docs)}</b>",
                ])

                for d in not_ready_docs[:80]:
                    name = _display_name_for_doc(d)
                    uid = d.get("user_id")
                    lines.append(f"• {name} — <code>{uid}</code>")

                if len(not_ready_docs) > 80:
                    lines.append(f"…and <b>{len(not_ready_docs) - 80}</b> more not DM-ready.")

                lines.append("")
                lines.append("Tip: DM-ready comes from <code>dm_ready=true</code> (users who have DM’d the bot).")

                text = "\n".join(lines)

            await cq.answer()
            await _safe_edit_text(
                cq.message,
                text=text,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("⬅ Back", callback_data="reqpanel:dm_ready_group")],
                        [InlineKeyboardButton("🏠 Admin Panel", callback_data="reqpanel:admin")],
                    ]
                ),
                disable_web_page_preview=True,
            )

def _fmt_user(d: Dict[str, Any]) -> str:
    name = (d.get("first_name") or "Unknown").strip()
    username = (d.get("username") or "").strip()
    uid = d.get("user_id")
    if username:
        return f"{name} (@{username}) — <code>{uid}</code>"
    return f"{name} — <code>{uid}</code>"

async def _log_long(app: Client, title: str, lines: List[str]):
    """Send a detailed list to the log group. Falls back to a .txt when too long."""
    if LOG_GROUP_ID is None:
        return
    body = "\n".join(lines) if lines else "(none)"
    text = f"[Requirements] {title}\n{body}"

    # Telegram message limit ~4096; keep margin
    if len(text) <= 3500:
        await _safe_send(app, LOG_GROUP_ID, text)
        return

    plain = re.sub(r"<.*?>", "", text)
    buf = io.BytesIO(plain.encode("utf-8"))
    buf.name = "requirements_sweep.txt"
    try:
        await app.send_document(LOG_GROUP_ID, document=buf, caption=re.sub(r"<.*?>", "", f"[Requirements] {title}"))
    except Exception:
        await _safe_send(app, LOG_GROUP_ID, text[:3400] + "\n…(truncated)")


# ────────────── Reminder sweeps ──────────────

    

    # ────────────── Reminder / Final-warning DM picker (buttons only) ──────────────
    def _pick_key(action: str, admin_id: int) -> str:
        return f"pick:{action}:{admin_id}"

    def _compute_targets(action: str):
        # action: "reminder" or "final"
        docs = list(members_coll.find({}))
        targets = []
        for raw in docs:
            md = _member_doc(raw)
            if md.get("exempt"):
                continue
            if md.get("manual_spend", 0) >= REQUIRED_MIN_SPEND:
                continue
            # for reminders: only "behind" (not met) — same as above
            targets.append(md)
        # sort by spend asc then name
        targets.sort(key=lambda m: (m.get("manual_spend", 0), (m.get("name") or "").lower()))
        return targets

    def _render_pick(action: str, admin_id: int, *, page: int = 0):
        st = _load_state(admin_id)
        key = _pick_key(action, admin_id)
        pstate = st.get(key) or {}
        targets = pstate.get("targets") or _compute_targets(action)
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

        kb_rows = []

        # member buttons
        start = page * per_page
        end = start + per_page
        for md in targets[start:end]:
            uid = md["user_id"]
            on = "✅" if uid in selected else "⬜️"
            label = f"{on} {_fmt_user(md)} — ${md.get('manual_spend', 0):.2f}"
            kb_rows.append([InlineKeyboardButton(label, callback_data=f"reqpick:{action}:toggle:{uid}")])

        # paging
        if targets and max_page > 0:
            nav = []
            if page > 0:
                nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"reqpick:{action}:page:{page-1}"))
            nav.append(InlineKeyboardButton(f"Page {page+1}/{max_page+1}", callback_data="reqpick:noop"))
            if page < max_page:
                nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"reqpick:{action}:page:{page+1}"))
            kb_rows.append(nav)

        # actions
        kb_rows.append([
            InlineKeyboardButton("✅ Send Selected", callback_data=f"reqpick:{action}:send_selected"),
            InlineKeyboardButton("📣 Send All", callback_data=f"reqpick:{action}:send_all"),
        ])
        kb_rows.append([InlineKeyboardButton("⬅️ Back to Requirements Menu", callback_data="reqpanel:admin")])

        return "\n".join(lines), InlineKeyboardMarkup(kb_rows)

    async def _send_dms_for_action(app: Client, cq: CallbackQuery, *, action: str, only_selected: bool):
        admin_id = cq.from_user.id
        st = _load_state(admin_id)
        key = _pick_key(action, admin_id)
        pstate = st.get(key) or {}
        targets = pstate.get("targets") or _compute_targets(action)
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

        # quick progress note
        await cq.answer("Sending…", show_alert=False)

        ok = []
        fail = []
        for md in send_list:
            uid = md["user_id"]
            if action == "reminder":
                msg = random.choice(REMINDER_MSGS)
                flag_field = "reminder_sent"
            else:
                msg = random.choice(FINAL_WARNING_MSGS)
                flag_field = "final_warning_sent"

            sent, reason = await _try_send_dm(app, uid, msg)
            if sent:
                ok.append(md)
                members_coll.update_one({"_id": md["_id"]}, {"$set": {flag_field: True}})
            else:
                fail.append((md, reason))

        # summary to admin chat
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

        # detailed log to log group (if configured)
        try:
            await _log_to_group(app, "\n".join([
                f"[Requirements] {title} run by {admin_id}",
                f"Success={len(ok)} Failed={len(fail)}",
                "Sent: " + ", ".join([str(m['user_id']) for m in ok]) if ok else "Sent: (none)",
                "Failed: " + ", ".join([f"{m['user_id']}({r})" for m, r in fail]) if fail else "Failed: (none)",
            ]))
        except Exception:
            pass

        # keep picker open and refreshed
        new_text, new_kb = _render_pick(action, admin_id, page=int(pstate.get("page") or 0))
        await cq.message.edit_text(new_text, reply_markup=new_kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^reqpanel:reminders$"))
    async def reqpanel_reminders(app: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(app, cq):
            return
        admin_id = cq.from_user.id
        text, kb = _render_pick("reminder", admin_id, page=0)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^reqpanel:final_warnings$"))
    async def reqpanel_final_warnings(app: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(app, cq):
            return
        admin_id = cq.from_user.id
        text, kb = _render_pick("final", admin_id, page=0)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):toggle:(\d+)$"))
    async def reqpick_toggle(app: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(app, cq):
            return
        action, uid_s = cq.data.split(":")[1], cq.data.split(":")[3]
        admin_id = cq.from_user.id
        st = _load_state(admin_id)
        key = _pick_key(action, admin_id)
        pstate = st.get(key) or {}
        selected = set(pstate.get("selected") or [])
        uid = int(uid_s)
        if uid in selected:
            selected.remove(uid)
        else:
            selected.add(uid)
        pstate["selected"] = list(selected)
        st[key] = pstate
        _save_state(admin_id, st)

        text2, kb2 = _render_pick(action, admin_id, page=int(pstate.get("page") or 0))
        await cq.message.edit_text(text2, reply_markup=kb2, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):page:(\d+)$"))
    async def reqpick_page(app: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(app, cq):
            return
        action = cq.data.split(":")[1]
        page = int(cq.data.split(":")[3])
        admin_id = cq.from_user.id
        text2, kb2 = _render_pick(action, admin_id, page=page)
        await cq.message.edit_text(text2, reply_markup=kb2, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):send_selected$"))
    async def reqpick_send_selected(app: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(app, cq):
            return
        action = cq.data.split(":")[1]
        await _send_dms_for_action(app, cq, action=action, only_selected=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):send_all$"))
    async def reqpick_send_all(app: Client, cq: CallbackQuery):
        if not await _must_be_owner_or_model_admin(app, cq):
            return
        action = cq.data.split(":")[1]
        await _send_dms_for_action(app, cq, action=action, only_selected=False)

    @app.on_callback_query(filters.regex("^reqpick:noop$"))
    async def reqpick_noop(app: Client, cq: CallbackQuery):
        await cq.answer()

