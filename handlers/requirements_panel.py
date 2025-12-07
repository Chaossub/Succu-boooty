# handlers/requirements_panel.py

import os
import logging
import random
from datetime import datetime, timezone
from typing import List, Set, Dict, Any, Optional

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
pending_custom_coll = db["requirements_pending_custom_spend"]  # legacy, now unused

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
    """
    Lightweight logger to the Sanctuary records channel.
    Used for: scans, sweeps, kicks, manual spend changes, etc.
    """
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
        dt = doc["last_updated"].astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        lines.append(f"\nLast updated: <code>{dt}</code>")
    return "\n".join(lines)


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
                InlineKeyboardButton(
                    "📋 Member Status List", callback_data="reqpanel:list"
                ),
                InlineKeyboardButton(
                    "➕ Add Manual Spend", callback_data="reqpanel:add_spend"
                ),
            ],
            [
                InlineKeyboardButton(
                    "✅ Exempt / Un-exempt", callback_data="reqpanel:toggle_exempt"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📡 Scan Group Members", callback_data="reqpanel:scan"
                ),
            ],
            [
                InlineKeyboardButton(
                    "💌 Send Reminders (Behind Only)",
                    callback_data="reqpanel:reminders",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚠️ Send Final Warnings",
                    callback_data="reqpanel:final_warnings",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Run Requirements Sweep",
                    callback_data="reqpanel:sweep",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🧹 Clear All Manual Totals",
                    callback_data="reqpanel:clear_all",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅ Back to Requirements Menu", callback_data="reqpanel:home"
                ),
            ],
        ]
    )


def _back_to_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⬅ Back to Requirements Menu", callback_data="reqpanel:home"
                )
            ]
        ]
    )


# ────────────── Core handlers ──────────────


def register(app: Client):
    log.info(
        "✅ handlers.requirements_panel registered (OWNER_ID=%s, super_admins=%s, models=%s, groups=%s)",
        OWNER_ID,
        SUPER_ADMINS,
        MODELS,
        SANCTUARY_GROUP_IDS,
    )

    # Entry point from main menu button
    @app.on_callback_query(filters.regex("^reqpanel:home$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        is_admin = _is_admin_or_model(user_id)
        text_lines = [
            "<b>Requirements Help</b>",
            "",
            "Use this panel to check how you’re doing on Sanctuary requirements this month.",
            "",
            "• <b>Check My Status</b> – see if you’re met or behind.",
        ]
        if is_admin:
            text_lines.extend(
                [
                    "• <b>Admin / Model Controls</b> – open the owner/models tools panel "
                    "(lists, manual credit, exemptions, reminders, sweeps).",
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

    # Owner / models tools panel
    @app.on_callback_query(filters.regex("^reqpanel:admin$"))
    async def reqpanel_admin_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer(
                "Only Roni and approved models can open this.", show_alert=True
            )
            return

        text = (
            "<b>Admin / Model Controls</b>\n\n"
            "Use these tools to manage Sanctuary requirements for the month.\n"
            "Everything you do here updates what SuccuBot uses when checking "
            "member status or running sweeps, so double-check before you confirm changes.\n\n"
            "From here you can:\n"
            "▪️ View the full member status list\n"
            "▪️ Add manual spend credit for offline payments\n"
            "▪️ Exempt / un-exempt members\n"
            "▪️ Scan groups into the tracker\n"
            "▪️ Send reminder DMs to members who are behind\n"
            "▪️ Send final-warning DMs to those still not meeting minimums\n"
            "▪️ Run a full requirements sweep and send a summary to the log channel (owner only)\n"
            "▪️ Clear all manual totals at the start of a new month (owner only)\n\n"
            "All changes here affect this month’s requirement checks and future sweeps/reminders.\n\n"
            "<i>Only you and approved model admins see this panel. Members just see their own status.</i>"
        )

        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ────────────── Self-status & lookup ──────────────

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

    @app.on_callback_query(filters.regex("^reqpanel:lookup$"))
    async def reqpanel_lookup_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer(
                "Only Roni and models can look up other members.", show_alert=True
            )
            return

        STATE[user_id] = {"mode": "lookup"}
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Look Up Member</b>\n\n"
                "Send me either:\n"
                "• A forwarded message from the member\n"
                "• Their @username\n"
                "• Or their numeric Telegram ID\n\n"
                "I’ll show you their current requirement status."
            ),
            reply_markup=_back_to_admin_kb(),
        )

    # ────────────── Text router (lookup / toggle exempt) ──────────────

    @app.on_message(filters.text)
    async def requirements_state_router(client: Client, msg: Message):
        user_id = msg.from_user.id

        # Legacy custom-amount flow (now disabled)
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
            # LOOKUP FLOW
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

            # TOGGLE EXEMPT FLOW
            if mode == "toggle_exempt":
                try:
                    target_id = int(msg.text.strip())
                except ValueError:
                    await msg.reply_text("Please send just the numeric Telegram user ID.")
                    return

                doc = members_coll.find_one({"user_id": target_id}) or {
                    "user_id": target_id
                }
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
            await cq.answer(
                "Only Roni and models can view the full list.", show_alert=True
            )
            return

        docs = list(members_coll.find().sort("user_id", ASCENDING).limit(50))
        if not docs:
            text = (
                "<b>Member Status List</b>\n\n"
                "No tracked members yet. Try running a scan first."
            )
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

                first_name = d.get("first_name") or ""
                username = d.get("username")
                display_name = (
                    first_name.strip()
                    or (f"@{username}" if username else "Unknown")
                )

                if username and first_name:
                    display_name = f"{first_name} (@{username})"

                lines.append(
                    f"• {display_name} (<code>{uid}</code>) – {status} (${total:.2f})"
                )
            text = "\n".join(lines)

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── Add Manual Spend (BUTTONS ONLY) ──────────────

    def _member_select_keyboard() -> InlineKeyboardMarkup:
        docs = list(members_coll.find().sort("first_name", ASCENDING).limit(50))
        rows: List[List[InlineKeyboardButton]] = []

        if not docs:
            return _back_to_admin_kb()

        for d in docs:
            uid = d["user_id"]
            name = d.get("first_name") or "Unknown"
            username = d.get("username")
            label_parts = [name]
            if username:
                label_parts.append(f"@{username}")
            label = " ".join(label_parts)
            rows.append(
                [
                    InlineKeyboardButton(
                        label, callback_data=f"reqpanel:spend_member:{uid}"
                    )
                ]
            )

        rows.append(
            [
                InlineKeyboardButton(
                    "⬅ Back to Requirements Menu", callback_data="reqpanel:home"
                )
            ]
        )
        return InlineKeyboardMarkup(rows)

    def _spend_keyboard(target_id: int) -> InlineKeyboardMarkup:
        """
        Plus/minus buttons, clear, confirm, back. Everything via buttons only.
        """
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "+$5", callback_data=f"reqpanel:spend_delta:{target_id}:5"
                    ),
                    InlineKeyboardButton(
                        "+$10", callback_data=f"reqpanel:spend_delta:{target_id}:10"
                    ),
                    InlineKeyboardButton(
                        "+$20", callback_data=f"reqpanel:spend_delta:{target_id}:20"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "+$25", callback_data=f"reqpanel:spend_delta:{target_id}:25"
                    ),
                    InlineKeyboardButton(
                        "+$50", callback_data=f"reqpanel:spend_delta:{target_id}:50"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "-$5", callback_data=f"reqpanel:spend_delta:{target_id}:-5"
                    ),
                    InlineKeyboardButton(
                        "-$10", callback_data=f"reqpanel:spend_delta:{target_id}:-10"
                    ),
                    InlineKeyboardButton(
                        "-$20", callback_data=f"reqpanel:spend_delta:{target_id}:-20"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "-$25", callback_data=f"reqpanel:spend_delta:{target_id}:-25"
                    ),
                    InlineKeyboardButton(
                        "-$50", callback_data=f"reqpanel:spend_delta:{target_id}:-50"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🧹 Clear Total",
                        callback_data=f"reqpanel:spend_clear:{target_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "✅ Confirm & Pick Model",
                        callback_data=f"reqpanel:spend_confirm:{target_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅ Back to Member List", callback_data="reqpanel:add_spend"
                    )
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

        kb = _member_select_keyboard()
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

        # Start a fresh pending-edit session for this admin
        PENDING_SPEND[user_id] = {
            "target_id": target_id,
            "original_total": current_total,
            "working_total": current_total,
        }

        await cq.answer()
        await _render_spend_panel(cq.message, target_id, current_total)

    @app.on_callback_query(filters.regex(r"^reqpanel:spend_delta:(\d+):(-?\d+)$"))
    async def reqpanel_spend_delta_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        parts = cq.data.split(":")
        target_id = int(parts[2])
        delta = float(parts[3])

        state = PENDING_SPEND.get(user_id)
        if not state or state.get("target_id") != target_id:
            # If somehow state was lost, re-seed from DB
            doc = _member_doc(target_id)
            state = {
                "target_id": target_id,
                "original_total": doc["manual_spend"],
                "working_total": doc["manual_spend"],
            }
            PENDING_SPEND[user_id] = state

        working = state.get("working_total", 0.0) + delta
        if working < 0:
            working = 0.0  # no negative totals

        state["working_total"] = working

        await cq.answer()
        await _render_spend_panel(cq.message, target_id, working)

    @app.on_callback_query(filters.regex(r"^reqpanel:spend_clear:(\d+)$"))
    async def reqpanel_spend_clear_cb(client: Client, cq: CallbackQuery):
        """
        Clear the member's manual total IMMEDIATELY.
        - Sets manual_spend to 0
        - Clears per-model breakdown
        """
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])

        doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}

        members_coll.update_one(
            {"user_id": target_id},
            {
                "$set": {
                    "manual_spend": 0.0,
                    "manual_spend_models": {},
                    "last_updated": datetime.now(timezone.utc),
                    "first_name": doc.get("first_name", ""),
                    "username": doc.get("username"),
                }
            },
            upsert=True,
        )

        # Reset pending state
        PENDING_SPEND[user_id] = {
            "target_id": target_id,
            "original_total": 0.0,
            "working_total": 0.0,
        }
        PENDING_ATTRIB.pop(user_id, None)

        await cq.answer("Manual total cleared and saved.", show_alert=False)
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
            await cq.answer(
                "No pending changes for this member. Use the +/- buttons first.",
                show_alert=True,
            )
            return

        original = float(state.get("original_total", 0.0))
        new_total = float(state.get("working_total", original))
        delta = new_total - original

        if abs(delta) < 0.0001:
            await cq.answer("No changes to save for this member.", show_alert=True)
            return

        # Update main manual_spend total in Mongo
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

        # Store pending attribution (which model got this delta)
        PENDING_ATTRIB[user_id] = {
            "target_id": target_id,
            "delta": delta,
            "new_total": new_total,
        }

        # Build model-name buttons (NO tagging)
        model_buttons: List[List[InlineKeyboardButton]] = []
        row: List[InlineKeyboardButton] = []
        for slug, label in MODEL_NAME_MAP.items():
            if not label:
                continue
            row.append(
                InlineKeyboardButton(
                    label,
                    callback_data=f"reqpanel:spend_model:{target_id}:{slug}",
                )
            )
            if len(row) == 2:
                model_buttons.append(row)
                row = []
        if row:
            model_buttons.append(row)

        # Extra options
        model_buttons.append(
            [
                InlineKeyboardButton(
                    "Split / Other",
                    callback_data=f"reqpanel:spend_model:{target_id}:other",
                )
            ]
        )
        model_buttons.append(
            [
                InlineKeyboardButton(
                    "Skip attribution",
                    callback_data=f"reqpanel:spend_model:{target_id}:skip",
                )
            ]
        )

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
            "If it was split between multiple models, use <b>Split / Other</b>."
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
            await cq.answer(
                "This edit was already finished or expired.", show_alert=True
            )
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

        # Clean up pending state
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
            [
                [
                    InlineKeyboardButton(
                        "⬅ Back to Member List", callback_data="reqpanel:add_spend"
                    )
                ]
            ]
        )

        await cq.answer("Saved.", show_alert=False)
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ────────────── Toggle Exempt ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:toggle_exempt$"))
    async def reqpanel_toggle_exempt_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer(
                "Only Roni and models can change exemptions.", show_alert=True
            )
            return

        STATE[user_id] = {"mode": "toggle_exempt"}
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Exempt / Un-exempt Member</b>\n\n"
                "Send me the numeric Telegram user ID for the member.\n\n"
                "I’ll flip their exempt status for this month.\n\n"
                "<i>Owner and models stay effectively exempt even if you uncheck them here.</i>"
            ),
            reply_markup=_back_to_admin_kb(),
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
                        },
                        upsert=True,
                    )
                    total_indexed += 1
            except Exception as e:
                log.warning(
                    "requirements_panel: failed scanning group %s: %s", gid, e
                )

        await _log_event(
            client,
            f"Scan complete by {user_id}: indexed or updated {total_indexed} members.",
        )

        await cq.answer("Scan complete.", show_alert=False)
        await _safe_edit_text(
            cq.message,
            text=(
                f"✅ Scan complete.\n"
                f"Indexed or updated {total_indexed} members from Sanctuary group(s)."
            ),
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── Reminder sweeps ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:reminders$"))
    async def reqpanel_reminders_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can send reminders.", show_alert=True)
            return

        docs = members_coll.find(
            {
                "is_exempt": {"$ne": True},
                "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
                "reminder_sent": {"$ne": True},
            }
        )

        count = 0
        for d in docs:
            uid = d["user_id"]
            if uid == OWNER_ID or uid in MODELS:
                continue

            name = d.get("first_name") or "there"
            msg = random.choice(REMINDER_MSGS).format(name=name)
            sent = await _safe_send(client, uid, msg)
            if not sent:
                continue
            members_coll.update_one(
                {"user_id": uid},
                {
                    "$set": {
                        "reminder_sent": True,
                        "last_updated": datetime.now(timezone.utc),
                    }
                },
            )
            count += 1

        await cq.answer(f"Sent reminders to {count} member(s).", show_alert=True)
        await _safe_edit_text(
            cq.message,
            text=f"💌 Reminder sweep complete.\nSent to {count} member(s) who are behind.",
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex("^reqpanel:final_warnings$"))
    async def reqpanel_final_warnings_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer(
                "Only Roni and models can send final warnings.", show_alert=True
            )
            return

        docs = members_coll.find(
            {
                "is_exempt": {"$ne": True},
                "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
                "final_warning_sent": {"$ne": True},
            }
        )

        count = 0
        for d in docs:
            uid = d["user_id"]
            if uid == OWNER_ID or uid in MODELS:
                continue

            name = d.get("first_name") or "there"
            msg = random.choice(FINAL_WARNING_MSGS).format(name=name)
            sent = await _safe_send(client, uid, msg)
            if not sent:
                continue
            members_coll.update_one(
                {"user_id": uid},
                {
                    "$set": {
                        "final_warning_sent": True,
                        "last_updated": datetime.now(timezone.utc),
                    }
                },
            )
            count += 1

        await cq.answer(f"Sent final warnings to {count} member(s).", show_alert=True)
        await _safe_edit_text(
            cq.message,
            text=f"⚠️ Final-warning sweep complete.\nSent to {count} member(s) still behind.",
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── Owner-only Requirements Sweep (two messages) ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:sweep$"))
    async def reqpanel_sweep_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id

        # Only OWNER can actually run this
        if not _is_owner(user_id):
            await cq.answer(
                "Only Roni (owner) can run the full requirements sweep.",
                show_alert=True,
            )
            return

        if LOG_GROUP_ID is None:
            await cq.answer(
                "No log group configured. Set SANCTU_LOG_GROUP_ID or SANCTUARY_LOG_CHANNEL in env.",
                show_alert=True,
            )
            return

        docs = list(members_coll.find().sort("user_id", ASCENDING))
        total_members = len(docs)

        total_manual_spend = 0.0
        totals_by_model: Dict[str, float] = {slug: 0.0 for slug in MODEL_NAME_MAP.keys()}
        totals_by_model["other"] = 0.0
        totals_by_model["untracked"] = 0.0

        member_lines: List[str] = []

        for d in docs:
            uid = d["user_id"]
            md = _member_doc(uid)
            total = md["manual_spend"]
            total_manual_spend += total

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

            first_name = d.get("first_name") or ""
            username = d.get("username")
            display_name = (
                first_name.strip()
                or (f"@{username}" if username else "Unknown")
            )
            if username and first_name:
                display_name = f"{first_name} (@{username})"

            # Only count attribution if this member actually has a positive manual total
            attrib_parts: List[str] = []
            breakdown: Dict[str, float] = {}

            if total > 0.0001:
                breakdown = md.get("manual_spend_models", {}) or {}

                # Update model totals
                for slug in MODEL_NAME_MAP.keys():
                    amt = float(breakdown.get(slug, 0.0))
                    totals_by_model[slug] = totals_by_model.get(slug, 0.0) + amt
                totals_by_model["other"] += float(breakdown.get("other", 0.0))
                totals_by_model["untracked"] += float(
                    breakdown.get("untracked", 0.0)
                )

                for slug, label in MODEL_NAME_MAP.items():
                    amt = float(breakdown.get(slug, 0.0))
                    if abs(amt) > 0.0001:
                        attrib_parts.append(f"{label}: ${amt:.2f}")
                other_amt = float(breakdown.get("other", 0.0))
                if abs(other_amt) > 0.0001:
                    attrib_parts.append(f"Other/Split: ${other_amt:.2f}")
                untracked_amt = float(breakdown.get("untracked", 0.0))
                if abs(untracked_amt) > 0.0001:
                    attrib_parts.append(f"Untracked: ${untracked_amt:.2f}")

            attrib_str = ""
            if attrib_parts:
                attrib_str = " [ " + ", ".join(attrib_parts) + " ]"

            member_lines.append(
                f"• {display_name} (<code>{uid}</code>) – {status} (${total:.2f}){attrib_str}"
            )

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Message 1: original style report
        report_lines = [
            "<b>Requirements Sweep Report</b>",
            "",
            f"Generated: {now_str}",
            f"Minimum required: ${REQUIRED_MIN_SPEND:.2f}",
            f"Tracked members: {total_members}",
            "",
        ]
        report_lines.extend(member_lines)
        report_text = "\n".join(report_lines)

        # Message 2: totals + by-model attribution
        summary_lines = [
            f"Requirements sweep run by {user_id} at {now_str}.",
            f"Tracked members: {total_members}",
            f"Total manual spend logged this month: ${total_manual_spend:.2f}",
            "",
            "By model attribution:",
        ]
        for slug, label in MODEL_NAME_MAP.items():
            amt = totals_by_model.get(slug, 0.0)
            summary_lines.append(f"• {label}: ${amt:.2f}")
        summary_lines.append(
            f"• Other / Split: ${totals_by_model.get('other', 0.0):.2f}"
        )
        summary_lines.append(
            f"• Untracked: ${totals_by_model.get('untracked', 0.0):.2f}"
        )
        summary_text = "\n".join(summary_lines)

        # Send both big messages directly to log group
        await _safe_send(client, LOG_GROUP_ID, report_text)
        await _safe_send(client, LOG_GROUP_ID, summary_text)

        # Short log line like before
        await _log_event(
            client,
            f"Full requirements sweep report generated by {user_id} and sent to log channel.",
        )

        await cq.answer("Requirements sweep sent to log channel.", show_alert=True)

    # ────────────── Owner-only CLEAR ALL ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:clear_all$"))
    async def reqpanel_clear_all_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id

        if not _is_owner(user_id):
            await cq.answer(
                "Only Roni (owner) can clear ALL manual totals.",
                show_alert=True,
            )
            return

        # Nuke all manual totals + per-model breakdown + reminder flags
        now = datetime.now(timezone.utc)
        res = members_coll.update_many(
            {},
            {
                "$set": {
                    "manual_spend": 0.0,
                    "manual_spend_models": {},
                    "last_updated": now,
                    "reminder_sent": False,
                    "final_warning_sent": False,
                }
            },
        )

        await _log_event(
            client,
            f"All manual totals cleared by {user_id} for new requirements cycle "
            f"(affected {res.modified_count} member docs).",
        )

        await cq.answer(
            f"Cleared manual totals for {res.modified_count} member(s).",
            show_alert=True,
        )
        await _safe_edit_text(
            cq.message,
            text=(
                f"🧹 <b>All Manual Totals Cleared</b>\n\n"
                f"Manual spend, per-model breakdowns, and reminder flags have been reset "
                f"for <b>{res.modified_count}</b> member(s).\n\n"
                "Use this at the start of a new month after you’ve finished your kick sweep."
            ),
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )
