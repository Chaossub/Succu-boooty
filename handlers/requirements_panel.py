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
pending_custom_coll = db["requirements_pending_custom_spend"]

members_coll.create_index([("user_id", ASCENDING)], unique=True)
pending_custom_coll.create_index([("owner_id", ASCENDING)], unique=True)

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))


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

# Simple in-memory state for some flows (DM lookup / exempt)
STATE: Dict[int, Dict[str, Any]] = {}

# ────────────── Helper functions ──────────────


def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def _is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS or _is_owner(user_id)


def _is_model(user_id: int) -> bool:
    # Owner is considered a model but has special privileges
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
    - Owner & models are always effectively exempt from requirements.
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
        "is_exempt": effective_exempt,
        "db_exempt": db_exempt,
        "is_model": is_model,
        "is_owner": is_owner,
        "reminder_sent": bool(doc.get("reminder_sent", False)),
        "final_warning_sent": bool(doc.get("final_warning_sent", False)),
        "last_updated": doc.get("last_updated"),
    }


def _format_member_status(doc: Dict[str, Any], viewer_id: int) -> str:
    """
    Format requirement status for a given member, but cap visible amounts
    for model admins so only the owner sees true totals.

    Rules:
    - OWNER_ID sees full real amounts for everyone.
    - Models (non-owner) see totals capped at REQUIRED_MIN_SPEND.
    - Regular members see real amounts for themselves.
    """
    total = doc["manual_spend"]
    target_id = doc["user_id"]

    viewer_is_owner = viewer_id == OWNER_ID
    viewer_is_model = _is_model(viewer_id) and not viewer_is_owner

    # Clamp visible total for any model viewer (owner sees full)
    if viewer_is_model:
        display_total = min(total, REQUIRED_MIN_SPEND)
    else:
        display_total = total

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
        f"<b>Member:</b> {name} (<code>{target_id}</code>)\n\n"
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
        status = "✅ Marked exempt from requirements for this cycle."
    elif display_total >= REQUIRED_MIN_SPEND:
        status = f"✅ Requirements met with ${display_total:.2f} logged."
    else:
        status = (
            f"⚠️ Currently behind.\n"
            f"Logged so far: ${display_total:.2f} (minimum ${REQUIRED_MIN_SPEND:.2f})."
        )

    lines = [header, status]
    if doc.get("last_updated"):
        dt = doc["last_updated"].astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        lines.append(f"\nLast updated: <code>{dt}</code>")
    return "\n".join(lines)


async def _log_monthly_totals(app: Client, label: Optional[str] = None):
    """
    Dump ALL member totals (real, uncapped) into the log group.
    Called automatically right before the 'New Month – Clear All Totals' reset.
    """
    if LOG_GROUP_ID is None:
        return

    docs = list(members_coll.find().sort("user_id", ASCENDING))
    if not docs:
        await _safe_send(
            app,
            LOG_GROUP_ID,
            "[Requirements] No member totals to report for this cycle.",
        )
        return

    now = datetime.now(timezone.utc)
    if not label:
        label = now.strftime("%B %Y")

    header_base = f"📊 Sanctuary Requirement Totals – {label}"
    chunk_lines: List[str] = [header_base]
    max_len = 3500  # keep safely under Telegram 4096 limit

    async def flush_chunk():
        nonlocal chunk_lines
        if len(chunk_lines) <= 1:
            return
        text = "\n".join(chunk_lines)
        await _safe_send(app, LOG_GROUP_ID, text)
        chunk_lines = [header_base + " (cont.)"]

    for d in docs:
        uid = d["user_id"]
        total = float(d.get("manual_spend", 0.0) or 0.0)
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

        line = f"• {display_name} (<code>{uid}</code>) – {status}, total ${total:.2f}"

        # If adding this line would overflow, flush current chunk first
        if len("\n".join(chunk_lines + [line])) > max_len:
            await flush_chunk()
        chunk_lines.append(line)

    await flush_chunk()

    await _safe_send(
        app,
        LOG_GROUP_ID,
        "[Requirements] Monthly totals snapshot complete – safe to run sweep / reset.",
    )


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
                    "🛠 Requirements Panel", callback_data="reqpanel:admin"
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("⬅ Back to Sanctuary Menu", callback_data="panels:root")]
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
                    "🧹 New Month – Clear All Totals",
                    callback_data="reqpanel:clear_all_totals",
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
        [[InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")]]
    )


def _custom_amount_kb(target_id: int) -> InlineKeyboardMarkup:
    """
    Inline keypad for adjusting a custom amount (integer dollars).
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "−10", callback_data=f"reqpanel:custom_delta:{target_id}:-10"
                ),
                InlineKeyboardButton(
                    "−5", callback_data=f"reqpanel:custom_delta:{target_id}:-5"
                ),
                InlineKeyboardButton(
                    "−1", callback_data=f"reqpanel:custom_delta:{target_id}:-1"
                ),
            ],
            [
                InlineKeyboardButton(
                    "+1", callback_data=f"reqpanel:custom_delta:{target_id}:+1"
                ),
                InlineKeyboardButton(
                    "+5", callback_data=f"reqpanel:custom_delta:{target_id}:+5"
                ),
                InlineKeyboardButton(
                    "+10", callback_data=f"reqpanel:custom_delta:{target_id}:+10"
                ),
            ],
            [
                InlineKeyboardButton(
                    "✅ Confirm", callback_data=f"reqpanel:custom_confirm:{target_id}"
                ),
                InlineKeyboardButton(
                    "❌ Cancel", callback_data=f"reqpanel:custom_cancel:{target_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅ Back to Member List", callback_data="reqpanel:add_spend"
                )
            ],
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

    # Home

    @app.on_callback_query(filters.regex("^reqpanel:home$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        is_admin = _is_admin_or_model(user_id)
        text_lines = [
            "<b>Requirements Help</b>",
            "",
            "Use this panel to check how you’re doing on Sanctuary requirements for the current cycle.",
            "",
            "• <b>Check My Status</b> – see if you’re met or behind.",
        ]
        if is_admin:
            text_lines.append(
                "• <b>Requirements Panel</b> – owner/model tools for lists, manual credit, "
                "exemptions, reminders, and monthly resets."
            )
        text_lines.append("")
        text_lines.append(
            "Regular members only see their own status. Owner & models get the full tools."
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

    # Admin panel

    @app.on_callback_query(filters.regex("^reqpanel:admin$"))
    async def reqpanel_admin_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer(
                "Only Roni and approved models can open this.", show_alert=True
            )
            return

        text = (
            "<b>Requirements Panel – Owner / Models</b>\n\n"
            "Use these tools to manage Sanctuary requirements for the month/cycle.\n"
            "Everything you do here updates what SuccuBot uses when checking "
            "member status or running sweeps, so double-check before you confirm changes.\n\n"
            "From here you can:\n"
            "▪️ View the full member status list\n"
            "▪️ Add manual spend credit for offline payments\n"
            "▪️ Exempt / un-exempt members\n"
            "▪️ Scan groups into the tracker\n"
            "▪️ Send reminder DMs to members who are behind\n"
            "▪️ Send final-warning DMs\n"
            "▪️ Clear all manual totals when you start a new month after your sweep\n\n"
            "<i>Only you and approved model admins see this panel. Members just see their own status.</i>"
        )

        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Self status

    @app.on_callback_query(filters.regex("^reqpanel:self$"))
    async def reqpanel_self_cb(_, cq: CallbackQuery):
        user = cq.from_user
        doc = _member_doc(user.id)
        text = _format_member_status(doc, viewer_id=user.id)
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_root_kb(_is_admin_or_model(user.id)),
            disable_web_page_preview=True,
        )

    # Lookup / exempt text flow (DM only)

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
                "Send me either in DM:\n"
                "• A forwarded message from the member\n"
                "• Their @username\n"
                "• Or their numeric Telegram ID\n\n"
                "I’ll show you their current requirement status."
            ),
            reply_markup=_back_to_admin_kb(),
        )

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
                "Send me the numeric Telegram user ID for the member in DM.\n\n"
                "I’ll flip their exempt status for this cycle.\n\n"
                "<i>Owner and models stay effectively exempt even if you uncheck them here.</i>"
            ),
            reply_markup=_back_to_admin_kb(),
            disable_web_page_preview=True,
        )

    @app.on_message(filters.text & filters.private)
    async def requirements_state_router(client: Client, msg: Message):
        if not msg.from_user:
            return
        user_id = msg.from_user.id
        text = (msg.text or "").strip()
        state = STATE.get(user_id)
        if not state:
            return

        mode = state.get("mode")
        try:
            if mode == "lookup":
                target_id: Optional[int] = None
                if msg.forward_from:
                    target_id = msg.forward_from.id
                elif text.startswith("@"):
                    username = text[1:].strip().lower()
                    doc = members_coll.find_one({"username": username})
                    if doc:
                        target_id = doc["user_id"]
                else:
                    try:
                        target_id = int(text)
                    except ValueError:
                        pass

                if not target_id:
                    await msg.reply_text(
                        "I couldn’t figure out who you meant. Try again with a forwarded message, "
                        "@username, or numeric ID."
                    )
                    return

                doc = _member_doc(target_id)
                await msg.reply_text(_format_member_status(doc, viewer_id=user_id))
                STATE.pop(user_id, None)
                return

            if mode == "toggle_exempt":
                try:
                    target_id = int(text)
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
                    f"{'✅ EXEMPT' if new_val else '❌ NOT exempt'} for this cycle.{model_note}"
                )
                await _log_event(
                    client,
                    f"Exempt toggled to {new_val} for {target_id} by {user_id}",
                )
                STATE.pop(user_id, None)
        except Exception as e:
            log.exception("requirements_panel: state router failed: %s", e)
            STATE.pop(user_id, None)
            await msg.reply_text(
                "Sorry, something went wrong saving that. Please tap the buttons again and retry."
            )

    # ────────────── Member list ──────────────

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
            viewer_id = cq.from_user.id
            viewer_is_owner = viewer_id == OWNER_ID
            viewer_is_model = _is_model(viewer_id) and not viewer_is_owner

            lines = ["<b>Member Status List (first 50)</b>\n"]
            for d in docs:
                uid = d["user_id"]
                total = float(d.get("manual_spend", 0.0) or 0.0)
                db_exempt = d.get("is_exempt", False)
                is_owner = uid == OWNER_ID
                is_model = uid in MODELS or is_owner
                effective_exempt = db_exempt or is_model

                # Clamp visible total for model viewers
                if viewer_is_model:
                    display_total = min(total, REQUIRED_MIN_SPEND)
                else:
                    display_total = total

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
                    f"• {display_name} (<code>{uid}</code>) – {status} (${display_total:.2f})"
                )
            text = "\n".join(lines)

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── Add Manual Spend ──────────────

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
                [InlineKeyboardButton(label, callback_data=f"reqpanel:spend_member:{uid}")]
            )

        rows.append(
            [InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")]
        )
        return InlineKeyboardMarkup(rows)

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
                "Tap a member below to credit offline payments for this cycle.\n"
                "This adds extra credited dollars on top of Stripe / games."
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

        viewer_is_owner = user_id == OWNER_ID
        viewer_is_model = _is_model(user_id) and not viewer_is_owner

        total = doc["manual_spend"]
        # Clamp for model viewers
        if viewer_is_model:
            display_total = min(total, REQUIRED_MIN_SPEND)
        else:
            display_total = total

        name_parts = []
        if doc.get("first_name"):
            name_parts.append(doc["first_name"])
        if doc.get("username"):
            name_parts.append(f"(@{doc['username']})")
        name = " ".join(name_parts) or "Unknown"

        text = (
            "<b>Add Manual Spend</b>\n\n"
            f"Member: {name} (<code>{target_id}</code>)\n"
            f"Current manual total: ${display_total:.2f}\n\n"
            "Pick an amount to credit for this cycle:"
        )

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "$5", callback_data=f"reqpanel:spend_amount:{target_id}:5"
                    ),
                    InlineKeyboardButton(
                        "$10", callback_data=f"reqpanel:spend_amount:{target_id}:10"
                    ),
                    InlineKeyboardButton(
                        "$20", callback_data=f"reqpanel:spend_amount:{target_id}:20"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "$25", callback_data=f"reqpanel:spend_amount:{target_id}:25"
                    ),
                    InlineKeyboardButton(
                        "$50", callback_data=f"reqpanel:spend_amount:{target_id}:50"
                    ),
                    InlineKeyboardButton(
                        "Custom amount",
                        callback_data=f"reqpanel:spend_custom:{target_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🧹 Clear Manual Total",
                        callback_data=f"reqpanel:clear_total:{target_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⬅ Back to Member List", callback_data="reqpanel:add_spend"
                    )
                ],
            ]
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:spend_amount:(\d+):(\d+)$"))
    async def reqpanel_spend_amount_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        parts = cq.data.split(":")
        target_id = int(parts[2])
        amount = float(parts[3])

        doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}
        new_total = float(doc.get("manual_spend", 0.0) or 0.0) + amount

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
            f"Manual spend +${amount:.2f} for {target_id} by {user_id}.",
        )

        viewer_is_owner = user_id == OWNER_ID
        viewer_is_model = _is_model(user_id) and not viewer_is_owner
        if viewer_is_model:
            display_new_total = min(new_total, REQUIRED_MIN_SPEND)
        else:
            display_new_total = new_total

        await cq.answer(
            f"Added ${amount:.2f}. New total: ${display_new_total:.2f}", show_alert=True
        )
        await reqpanel_spend_member_cb(client, cq)

    # ────────────── Per-member clear total ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:clear_total:(\d+)$"))
    async def reqpanel_clear_total_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can clear totals.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])
        doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}

        members_coll.update_one(
            {"user_id": target_id},
            {
                "$set": {
                    "manual_spend": 0.0,
                    "last_updated": datetime.now(timezone.utc),
                    "first_name": doc.get("first_name", ""),
                    "username": doc.get("username"),
                }
            },
            upsert=True,
        )

        await _log_event(
            client,
            f"Manual spend CLEARED to $0.00 for {target_id} by {user_id}.",
        )

        await cq.answer("Manual total cleared to $0 for this member.", show_alert=True)
        await reqpanel_spend_member_cb(client, cq)

    # ────────────── Global clear-all (with monthly log) ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:clear_all_totals$"))
    async def reqpanel_clear_all_totals_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can clear all totals.", show_alert=True)
            return

        # 1) Log all real totals to the log group before reset
        await _log_monthly_totals(client)

        # 2) Reset manual totals + reminder flags for fresh month
        result = members_coll.update_many(
            {},
            {
                "$set": {
                    "manual_spend": 0.0,
                    "reminder_sent": False,
                    "final_warning_sent": False,
                    "last_updated": datetime.now(timezone.utc),
                }
            },
        )

        modified = result.modified_count if result else 0
        await _log_event(
            client,
            f"GLOBAL reset: manual_totals cleared for {modified} member docs by {user_id}.",
        )

        await cq.answer(
            f"Logged this month’s totals and cleared manual totals for {modified} member(s).",
            show_alert=True,
        )
        await _safe_edit_text(
            cq.message,
            text=(
                f"🧹 New month reset complete.\n"
                f"All member totals were logged to the requirements log group, then "
                f"manual totals were cleared for {modified} member(s).\n\n"
                "You can now start logging this month’s requirements fresh."
            ),
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── Custom amount keypad (ALL BUTTONS, NO TEXT INPUT) ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:spend_custom:(\d+)$"))
    async def reqpanel_spend_custom_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])

        pending_custom_coll.replace_one(
            {"owner_id": user_id},
            {
                "owner_id": user_id,
                "target_id": target_id,
                "amount": 0,
                "created_at": datetime.utcnow(),
            },
            upsert=True,
        )

        text = (
            "<b>Add Manual Spend – Custom Amount</b>\n\n"
            f"Target member ID: <code>{target_id}</code>\n\n"
            "Use the buttons below to adjust the custom amount for this cycle.\n"
            "When you’re happy with the number, tap <b>✅ Confirm</b> to apply it.\n\n"
            "Current pending amount: <b>$0</b>"
        )

        kb = _custom_amount_kb(target_id)
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:custom_delta:(\d+):([+-]?\d+)$"))
    async def reqpanel_custom_delta_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        parts = cq.data.split(":")
        target_id = int(parts[2])
        delta = int(parts[3])

        doc = pending_custom_coll.find_one(
            {"owner_id": user_id, "target_id": target_id}
        ) or {"owner_id": user_id, "target_id": target_id, "amount": 0}

        amount = int(doc.get("amount", 0)) + delta
        if amount < 0:
            amount = 0

        pending_custom_coll.update_one(
            {"owner_id": user_id},
            {
                "$set": {
                    "owner_id": user_id,
                    "target_id": target_id,
                    "amount": amount,
                    "created_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

        text = (
            "<b>Add Manual Spend – Custom Amount</b>\n\n"
            f"Target member ID: <code>{target_id}</code>\n\n"
            "Use the buttons below to adjust the custom amount for this cycle.\n"
            "When you’re happy with the number, tap <b>✅ Confirm</b> to apply it.\n\n"
            f"Current pending amount: <b>${amount}</b>"
        )

        kb = _custom_amount_kb(target_id)
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:custom_confirm:(\d+)$"))
    async def reqpanel_custom_confirm_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])
        doc = pending_custom_coll.find_one(
            {"owner_id": user_id, "target_id": target_id}
        )
        if not doc:
            await cq.answer("No pending custom amount found.", show_alert=True)
            return

        amount = int(doc.get("amount", 0))
        pending_custom_coll.delete_one({"owner_id": user_id})

        if amount <= 0:
            await cq.answer("Amount is $0 – nothing to add.", show_alert=True)
            return

        member_doc = members_coll.find_one({"user_id": target_id}) or {
            "user_id": target_id
        }
        base = float(member_doc.get("manual_spend", 0.0) or 0.0)
        new_total = base + float(amount)

        members_coll.update_one(
            {"user_id": target_id},
            {
                "$set": {
                    "manual_spend": new_total,
                    "last_updated": datetime.now(timezone.utc),
                    "first_name": member_doc.get("first_name", ""),
                    "username": member_doc.get("username"),
                }
            },
            upsert=True,
        )

        await _log_event(
            client,
            f"Manual spend +${amount:.2f} (custom keypad) for {target_id} by {user_id}.",
        )

        viewer_is_owner = user_id == OWNER_ID
        viewer_is_model = _is_model(user_id) and not viewer_is_owner
        if viewer_is_model:
            display_new_total = min(new_total, REQUIRED_MIN_SPEND)
        else:
            display_new_total = new_total

        await cq.answer(
            f"Added ${amount:.2f}. New total: ${display_new_total:.2f}", show_alert=True
        )
        await reqpanel_spend_member_cb(client, cq)

    @app.on_callback_query(filters.regex(r"^reqpanel:custom_cancel:(\d+)$"))
    async def reqpanel_custom_cancel_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        pending_custom_coll.delete_one({"owner_id": user_id})
        await cq.answer("Custom amount cancelled.", show_alert=False)
        await reqpanel_add_spend_cb(_, cq)

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

        await _log_event(client, f"Reminder sweep sent to {count} members by {user_id}")
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

        await _log_event(
            client, f"Final warnings sent to {count} members by {user_id}"
        )
        await cq.answer(f"Sent final warnings to {count} member(s).", show_alert=True)
        await _safe_edit_text(
            cq.message,
            text=f"⚠️ Final-warning sweep complete.\nSent to {count} member(s) still behind.",
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )
