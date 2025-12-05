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

members_coll.create_index([("user_id", ASCENDING)], unique=True)

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
    SANCTUARY_GROUP_IDS = [int(x) for x in _group_ids_str.replace(" ", "").split(",") if x]

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

# Simple in-memory state for multi-step flows (only tiny bits like “custom note”)
STATE: Dict[int, Dict[str, Any]] = {}

# Preset amounts for add-spend buttons
AMOUNT_PRESETS: List[float] = [5, 10, 15, 20, 25, 50, 100]

# Preset “who/what was this payment for” choices
NOTE_CHOICES: Dict[str, str] = {
    "roni": "Roni",
    "ruby": "Ruby",
    "rin": "Rin",
    "savy": "Savy",
    "games": "Games",
    "door": "Door fee",
    "tip": "Tip",
    "other": "Other (custom note)",
}

# ────────────── Helper functions ──────────────


def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def _is_model(user_id: int) -> bool:
    # Owner always counts as model+exempt for requirements
    return user_id in MODELS or _is_owner(user_id)


def _is_admin_or_model(user_id: int) -> bool:
    """
    For the requirements panel, only OWNER + MODELS see admin tools.
    SUPER_ADMINS can exist for other systems, but here it's just you & models.
    """
    return _is_owner(user_id) or user_id in MODELS


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
    uid = doc["user_id"]
    username = doc.get("username")
    fn = doc.get("first_name") or ""

    if is_owner:
        status = (
            "👑 <b>Sanctuary owner</b> – you’re automatically exempt from monthly "
            "requirements. SuccuBot will never mark you behind or kick you for this."
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

    header = "<b>Requirement Status</b>"
    if fn or username:
        name_bits = []
        if fn:
            name_bits.append(fn)
        if username:
            name_bits.append(f"@{username}")
        header += " – " + " ".join(name_bits)
    header += f"\n<code>ID: {uid}</code>"

    lines = [
        header,
        "",
        status,
    ]
    if doc.get("last_updated"):
        dt = doc["last_updated"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"\nLast updated: <code>{dt}</code>")
    return "\n".join(lines)


def _format_display_name(d: Dict[str, Any]) -> str:
    uid = d["user_id"]
    fn = (d.get("first_name") or "").strip()
    username = d.get("username")
    if fn and username:
        return f"{fn} (@{username}) – {uid}"
    if fn:
        return f"{fn} – {uid}"
    if username:
        return f"@{username} – {uid}"
    return f"User {uid}"


def _query_members_for_list(limit: int = 50) -> List[Dict[str, Any]]:
    return list(
        members_coll.find().sort(
            [("first_name", ASCENDING), ("username", ASCENDING), ("user_id", ASCENDING)]
        ).limit(limit)
    )


def _query_members_for_reminders() -> List[Dict[str, Any]]:
    docs = list(
        members_coll.find(
            {
                "is_exempt": {"$ne": True},
                "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
                "reminder_sent": {"$ne": True},
            }
        )
    )
    # filter out owner + models just in case
    return [d for d in docs if d["user_id"] != OWNER_ID and d["user_id"] not in MODELS]


def _query_members_for_final_warnings() -> List[Dict[str, Any]]:
    docs = list(
        members_coll.find(
            {
                "is_exempt": {"$ne": True},
                "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
                "final_warning_sent": {"$ne": True},
            }
        )
    )
    return [d for d in docs if d["user_id"] != OWNER_ID and d["user_id"] not in MODELS]


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
            [InlineKeyboardButton("🧾 Look Up Member", callback_data="reqpanel:lookup")]
        )
        rows.append(
            [InlineKeyboardButton("🛠 Owner / Models Tools", callback_data="reqpanel:admin")]
        )

    # No back-to-portal here so the portal menu button doesn’t vanish randomly.
    return InlineKeyboardMarkup(rows)


def _admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Member Status List", callback_data="reqpanel:list"),
            ],
            [
                InlineKeyboardButton("➕ Add Manual Spend", callback_data="reqpanel:add_spend"),
            ],
            [
                InlineKeyboardButton("✅ Exempt / Un-exempt", callback_data="reqpanel:toggle_exempt"),
            ],
            [
                InlineKeyboardButton("📡 Scan Group Members", callback_data="reqpanel:scan"),
            ],
            [
                InlineKeyboardButton("💌 Send Reminder (Pick Member)", callback_data="reqpanel:reminders"),
            ],
            [
                InlineKeyboardButton("⚠️ Send Final Warning (Pick Member)", callback_data="reqpanel:final_warnings"),
            ],
            [
                InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home"),
            ],
        ]
    )


def _member_pick_kb(
    docs: List[Dict[str, Any]],
    action_prefix: str,
    back_cb: str,
) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for d in docs:
        label = _format_display_name(d)
        uid = d["user_id"]
        rows.append([InlineKeyboardButton(label, callback_data=f"{action_prefix}{uid}")])
    rows.append([InlineKeyboardButton("⬅ Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def _amount_pick_kb(target_id: int, back_cb: str) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for amt in AMOUNT_PRESETS:
        text = f"${int(amt) if amt.is_integer() else amt}"
        cb = f"reqpanel:add_spend_amt:{target_id}:{amt}"
        row.append(InlineKeyboardButton(text, callback_data=cb))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    # Custom amount → optional, uses DM if needed
    rows.append([InlineKeyboardButton("✏️ Custom amount", callback_data=f"reqpanel:add_spend_custom_amt:{target_id}")])
    rows.append([InlineKeyboardButton("⬅ Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def _note_pick_kb(target_id: int, amount: float, back_cb: str) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for key, label in NOTE_CHOICES.items():
        cb = f"reqpanel:add_spend_note:{target_id}:{amount}:{key}"
        row.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"reqpanel:add_spend_user:{target_id}")])
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

    # Entry point from main menu button
    @app.on_callback_query(filters.regex("^reqpanel:home$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        is_admin = _is_admin_or_model(user_id)
        text_lines = [
            "<b>Requirements Panel – Sanctuary</b>",
            "",
            "Use this panel to check how you’re doing on Sanctuary requirements this month.",
            "",
            "• <b>Check My Status</b> – see if you’re met or behind.",
        ]
        if is_admin:
            text_lines.extend(
                [
                    "• <b>Look Up Member</b> – tap a name to view another member’s status.",
                    "• <b>Owner / Models Tools</b> – open the full tools panel "
                    "(scans, manual credits, exemptions, reminders).",
                ]
            )
        text_lines.append("")
        text_lines.append(
            "Only you and approved model admins see the admin tools. "
            "Regular members just see their own status."
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
            await cq.answer("Only Roni and approved models can open this.", show_alert=True)
            return

        text = (
            "<b>Requirements Panel – Owner / Models</b>\n\n"
            "Use these tools to manage Sanctuary requirements for the month.\n"
            "Everything you do here updates what SuccuBot uses when checking "
            "member status or running sweeps, so double-check before you confirm changes.\n\n"
            "From here you can:\n"
            "▪️ View the full member status list\n"
            "▪️ Add manual spend credit for offline payments\n"
            "▪️ Exempt / un-exempt members\n"
            "▪️ Scan groups into the tracker\n"
            "▪️ Send reminder DMs to selected members\n"
            "▪️ Send final-warning DMs to selected members\n\n"
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
            await cq.answer("Only Roni and models can look up other members.", show_alert=True)
            return

        docs = _query_members_for_list()
        if not docs:
            await cq.answer("No tracked members yet. Run a scan first.", show_alert=True)
            return

        kb = _member_pick_kb(
            docs,
            action_prefix="reqpanel:view:",
            back_cb="reqpanel:home",
        )
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text="<b>Look Up Member</b>\n\nTap a member below to see their current requirement status.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:view:\d+$"))
    async def reqpanel_view_member_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can view other members.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])
        doc = _member_doc(target_id)
        text = _format_member_status(doc)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Back to Member List", callback_data="reqpanel:lookup")],
                [InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")],
            ]
        )
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ────────────── DM state router (only for custom notes / custom amount) ──────────────

    @app.on_message(filters.private & filters.text)
    async def requirements_state_router(client: Client, msg: Message):
        user_id = msg.from_user.id
        state = STATE.get(user_id)
        if not state:
            return

        mode = state.get("mode")

        # CUSTOM NOTE after buttons picked amount + “other”
        if mode == "add_spend_custom_note":
            target_id = state.get("target_id")
            amount = state.get("amount")
            if not target_id or amount is None:
                await msg.reply_text("Something went wrong – no member/amount set. Try again from the panel.")
                STATE.pop(user_id, None)
                return

            note = msg.text.strip()
            doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}
            new_total = float(doc.get("manual_spend", 0.0)) + float(amount)

            update_set: Dict[str, Any] = {
                "manual_spend": new_total,
                "last_updated": datetime.now(timezone.utc),
                "last_note": note,
            }
            update_ops: Dict[str, Any] = {
                "$set": update_set,
                "$setOnInsert": {"first_name": ""},
            }
            if note:
                update_ops["$push"] = {"notes": note}

            members_coll.update_one(
                {"user_id": target_id},
                update_ops,
                upsert=True,
            )

            await msg.reply_text(
                f"Logged ${float(amount):.2f} for <code>{target_id}</code>.\n"
                f"New manual total: ${new_total:.2f}\n\n"
                f"Note: {note or '(none)'}"
            )
            await _log_event(
                client,
                f"Manual spend +${float(amount):.2f} for {target_id} by {user_id}. Note: {note or '(none)'}",
            )
            STATE.pop(user_id, None)
            return

        # OPTIONAL: custom amount typed in DM (still button-picked member)
        if mode == "add_spend_custom_amount":
            target_id = state.get("target_id")
            if not target_id:
                await msg.reply_text("Something went wrong – no member set. Try again from the panel.")
                STATE.pop(user_id, None)
                return

            try:
                parts = msg.text.strip().split()
                if len(parts) < 1:
                    raise ValueError
                amount = float(parts[0])
                note = " ".join(parts[1:]) if len(parts) > 1 else ""
            except ValueError:
                await msg.reply_text(
                    "Format should be:\n"
                    "<code>amount [note]</code>\n\n"
                    "Example:\n<code>15 Ruby cashapp game night</code>"
                )
                return

            doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}
            new_total = float(doc.get("manual_spend", 0.0)) + amount

            update_set: Dict[str, Any] = {
                "manual_spend": new_total,
                "last_updated": datetime.now(timezone.utc),
                "last_note": note,
            }
            update_ops: Dict[str, Any] = {
                "$set": update_set,
                "$setOnInsert": {"first_name": ""},
            }
            if note:
                update_ops["$push"] = {"notes": note}

            members_coll.update_one(
                {"user_id": target_id},
                update_ops,
                upsert=True,
            )

            await msg.reply_text(
                f"Logged ${amount:.2f} for <code>{target_id}</code>.\n"
                f"New manual total: ${new_total:.2f}\n\n"
                f"Note: {note or '(none)'}"
            )
            await _log_event(
                client,
                f"Manual spend +${amount:.2f} for {target_id} by {user_id}. Note: {note or '(none)'}",
            )
            STATE.pop(user_id, None)
            return

    # ────────────── Admin-panel buttons ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:list$"))
    async def reqpanel_list_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can view the full list.", show_alert=True)
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
                display_name = first_name.strip() or (f"@{username}" if username else "Unknown")

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

    # ────────────── Add manual spend: all button-based ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:add_spend$"))
    async def reqpanel_add_spend_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        docs = _query_members_for_list()
        if not docs:
            await cq.answer("No tracked members yet. Run a scan first.", show_alert=True)
            return

        kb = _member_pick_kb(
            docs,
            action_prefix="reqpanel:add_spend_user:",
            back_cb="reqpanel:admin",
        )
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Add Manual Spend</b>\n\n"
                "First, pick which member you’re crediting."
            ),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:add_spend_user:\d+$"))
    async def reqpanel_add_spend_user_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])
        kb = _amount_pick_kb(target_id, back_cb="reqpanel:add_spend")
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Add Manual Spend</b>\n\n"
                f"Member: <code>{target_id}</code>\n\n"
                "Now tap an amount to credit."
            ),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:add_spend_amt:\d+:[0-9.]+$"))
    async def reqpanel_add_spend_amt_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        parts = cq.data.split(":")
        target_id = int(parts[2])
        amount = float(parts[3])

        kb = _note_pick_kb(target_id, amount, back_cb="reqpanel:add_spend")
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Add Manual Spend</b>\n\n"
                f"Member: <code>{target_id}</code>\n"
                f"Amount: ${amount:.2f}\n\n"
                "What was this payment for? Tap one below."
            ),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:add_spend_custom_amt:\d+$"))
    async def reqpanel_add_spend_custom_amt_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])
        STATE[user_id] = {"mode": "add_spend_custom_amount", "target_id": target_id}
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Add Manual Spend – Custom Amount</b>\n\n"
                f"Member: <code>{target_id}</code>\n\n"
                "Now send me a DM message (here in our chat) with:\n"
                "<code>amount [note]</code>\n\n"
                "Example:\n"
                "<code>37 Ruby custom bundle</code>"
            ),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back to Admin Tools", callback_data="reqpanel:admin")]]
            ),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:add_spend_note:\d+:[0-9.]+:[a-z_]+$"))
    async def reqpanel_add_spend_note_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        parts = cq.data.split(":")
        target_id = int(parts[2])
        amount = float(parts[3])
        note_key = parts[4]
        note_text = NOTE_CHOICES.get(note_key, "")

        # If they picked "other", we go to DM for custom note
        if note_key == "other":
            STATE[user_id] = {
                "mode": "add_spend_custom_note",
                "target_id": target_id,
                "amount": amount,
            }
            await cq.answer("Now send the custom note in DM ♥", show_alert=False)
            await _safe_edit_text(
                cq.message,
                text=(
                    "<b>Add Manual Spend – Custom Note</b>\n\n"
                    f"Member: <code>{target_id}</code>\n"
                    f"Amount: ${amount:.2f}\n\n"
                    "Now send me a DM message (here in our chat) with what this was for.\n"
                    "Example:\n"
                    "<code>Private bundle + extra pics</code>"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅ Back to Admin Tools", callback_data="reqpanel:admin")]]
                ),
                disable_web_page_preview=True,
            )
            return

        # Otherwise fully button-based: apply update now
        doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}
        new_total = float(doc.get("manual_spend", 0.0)) + amount

        update_set: Dict[str, Any] = {
            "manual_spend": new_total,
            "last_updated": datetime.now(timezone.utc),
            "last_note": note_text,
        }
        update_ops: Dict[str, Any] = {
            "$set": update_set,
            "$setOnInsert": {"first_name": ""},
        }
        if note_text:
            update_ops["$push"] = {"notes": note_text}

        members_coll.update_one(
            {"user_id": target_id},
            update_ops,
            upsert=True,
        )

        await _log_event(
            client,
            f"Manual spend +${amount:.2f} for {target_id} by {user_id}. Note: {note_text or '(none)'}",
        )
        await cq.answer("Manual spend logged.", show_alert=True)
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Add Manual Spend</b>\n\n"
                f"Member: <code>{target_id}</code>\n"
                f"Amount: ${amount:.2f}\n"
                f"Note: {note_text or '(none)'}\n\n"
                "You can use the admin tools below for more actions."
            ),
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── Exempt toggle via buttons ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:toggle_exempt$"))
    async def reqpanel_toggle_exempt_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can change exemptions.", show_alert=True)
            return

        docs = _query_members_for_list()
        if not docs:
            await cq.answer("No tracked members yet. Run a scan first.", show_alert=True)
            return

        kb = _member_pick_kb(
            docs,
            action_prefix="reqpanel:toggle_exempt_user:",
            back_cb="reqpanel:admin",
        )
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Exempt / Un-exempt Member</b>\n\n"
                "Tap a member below to flip their exempt status for this month.\n\n"
                "<i>Owner and models stay effectively exempt even if you uncheck them here.</i>"
            ),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:toggle_exempt_user:\d+$"))
    async def reqpanel_toggle_exempt_user_cb(_, cq: CallbackQuery):
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
                },
                "$setOnInsert": {"first_name": ""},
            },
            upsert=True,
        )
        model_note = ""
        if target_id == OWNER_ID:
            model_note = " (OWNER – still exempt overall)"
        elif target_id in MODELS:
            model_note = " (MODEL – still exempt overall)"

        await cq.answer("Updated.", show_alert=False)
        await _safe_edit_text(
            cq.message,
            text=(
                f"User <code>{target_id}</code> is now "
                f"{'✅ EXEMPT' if new_val else '❌ NOT exempt'} for this month.{model_note}"
            ),
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── Scan groups ──────────────

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
                log.warning("requirements_panel: failed scanning group %s: %s", gid, e)

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

    # ────────────── Reminder / final-warning: pick member from list ──────────────

    @app.on_callback_query(filters.regex("^reqpanel:reminders$"))
    async def reqpanel_reminders_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        # Only you can send DMs so members don't get spammed
        if not _is_owner(user_id):
            await cq.answer("Only Roni can send reminder messages.", show_alert=True)
            return

        docs = _query_members_for_reminders()
        if not docs:
            await cq.answer("No members currently behind that need reminders.", show_alert=True)
            return

        kb = _member_pick_kb(
            docs,
            action_prefix="reqpanel:send_reminder_user:",
            back_cb="reqpanel:admin",
        )
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Send Reminder – Pick Member</b>\n\n"
                "Tap a member below to send them a reminder DM.\n"
                "Only people who are behind & not exempt will show here."
            ),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:send_reminder_user:\d+$"))
    async def reqpanel_send_reminder_user_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_owner(user_id):
            await cq.answer("Only Roni can send reminder messages.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])
        d = members_coll.find_one({"user_id": target_id})
        if not d:
            await cq.answer("Member not found in tracker.", show_alert=True)
            return

        # respect owner/models exempt
        if target_id == OWNER_ID or target_id in MODELS:
            await cq.answer("Models and owner are always exempt.", show_alert=True)
            return

        name = d.get("first_name") or "there"
        msg = random.choice(REMINDER_MSGS).format(name=name)
        sent = await _safe_send(client, target_id, msg)
        if not sent:
            await cq.answer("Couldn’t DM that member.", show_alert=True)
            return

        members_coll.update_one(
            {"user_id": target_id},
            {"$set": {"reminder_sent": True, "last_updated": datetime.now(timezone.utc)}},
        )

        await _log_event(client, f"Reminder sent to {target_id} by {user_id}")
        await cq.answer("Reminder sent.", show_alert=True)

        # Refresh list after sending so they drop out
        docs = _query_members_for_reminders()
        if not docs:
            await _safe_edit_text(
                cq.message,
                text="💌 Reminder list is now empty – everyone behind has been pinged.",
                reply_markup=_admin_kb(),
                disable_web_page_preview=True,
            )
        else:
            kb = _member_pick_kb(
                docs,
                action_prefix="reqpanel:send_reminder_user:",
                back_cb="reqpanel:admin",
            )
            await _safe_edit_text(
                cq.message,
                text=(
                    "<b>Send Reminder – Pick Member</b>\n\n"
                    "Tap another member below to send a reminder DM.\n"
                    "Only people who are behind & not exempt will show here."
                ),
                reply_markup=kb,
                disable_web_page_preview=True,
            )

    @app.on_callback_query(filters.regex("^reqpanel:final_warnings$"))
    async def reqpanel_final_warnings_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_owner(user_id):
            await cq.answer("Only Roni can send final warnings.", show_alert=True)
            return

        docs = _query_members_for_final_warnings()
        if not docs:
            await cq.answer("No members currently behind that need final warnings.", show_alert=True)
            return

        kb = _member_pick_kb(
            docs,
            action_prefix="reqpanel:send_final_user:",
            back_cb="reqpanel:admin",
        )
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Send Final Warning – Pick Member</b>\n\n"
                "Tap a member below to send them a final-warning DM.\n"
                "Only people who are behind & not exempt will show here."
            ),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:send_final_user:\d+$"))
    async def reqpanel_send_final_user_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_owner(user_id):
            await cq.answer("Only Roni can send final warnings.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[-1])
        d = members_coll.find_one({"user_id": target_id})
        if not d:
            await cq.answer("Member not found in tracker.", show_alert=True)
            return

        if target_id == OWNER_ID or target_id in MODELS:
            await cq.answer("Models and owner are always exempt.", show_alert=True)
            return

        name = d.get("first_name") or "there"
        msg = random.choice(FINAL_WARNING_MSGS).format(name=name)
        sent = await _safe_send(client, target_id, msg)
        if not sent:
            await cq.answer("Couldn’t DM that member.", show_alert=True)
            return

        members_coll.update_one(
            {"user_id": target_id},
            {"$set": {"final_warning_sent": True, "last_updated": datetime.now(timezone.utc)}},
        )

        await _log_event(client, f"Final warning sent to {target_id} by {user_id}")
        await cq.answer("Final warning sent.", show_alert=True)

        docs = _query_members_for_final_warnings()
        if not docs:
            await _safe_edit_text(
                cq.message,
                text="⚠️ Final-warning list is now empty – everyone behind has been warned.",
                reply_markup=_admin_kb(),
                disable_web_page_preview=True,
            )
        else:
            kb = _member_pick_kb(
                docs,
                action_prefix="reqpanel:send_final_user:",
                back_cb="reqpanel:admin",
            )
            await _safe_edit_text(
                cq.message,
                text=(
                    "<b>Send Final Warning – Pick Member</b>\n\n"
                    "Tap another member below to send a final-warning DM.\n"
                    "Only people who are behind & not exempt will show here."
                ),
                reply_markup=kb,
                disable_web_page_preview=True,
            )
