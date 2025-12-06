# handlers/requirements_panel.py

import os
import re
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

PAGE_SIZE = 10  # members per page on list

# Simple in-memory state for multi-step flows
STATE: Dict[int, Dict[str, Any]] = {}

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
    doc = members_coll.find_one({"user_id": user_id}) or {"user_id": user_id}
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


def _display_name(doc: Dict[str, Any]) -> str:
    first_name = (doc.get("first_name") or "").strip()
    username = doc.get("username")
    if first_name and username:
        return f"{first_name} (@{username})"
    if first_name:
        return first_name
    if username:
        return f"@{username}"
    return "Unknown"


def _status_label(doc: Dict[str, Any]) -> str:
    uid = doc["user_id"]
    total = float(doc.get("manual_spend", 0.0))
    db_exempt = bool(doc.get("is_exempt", False))
    is_owner = uid == OWNER_ID
    is_model = uid in MODELS or is_owner

    if is_owner:
        return "OWNER (EXEMPT)"
    if is_model:
        return "MODEL (EXEMPT)"
    if db_exempt:
        return "EXEMPT"
    if total >= REQUIRED_MIN_SPEND:
        return "MET"
    return "BEHIND"


def _format_member_status(doc: Dict[str, Any]) -> str:
    total = doc["manual_spend"]
    exempt = doc["is_exempt"]
    is_model = doc.get("is_model", False)
    is_owner = doc.get("is_owner", False)

    lines = [f"<b>Requirement Status</b>", ""]

    # header with name + id
    name = _display_name(doc)
    lines.append(f"<b>Member:</b> {name} (<code>{doc['user_id']}</code>)")
    lines.append("")

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

    lines.append(status)

    if doc.get("last_updated"):
        dt = doc["last_updated"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
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
            [InlineKeyboardButton("🛠 Admin / Model Controls", callback_data="reqpanel:admin")]
        )

    # Instead of portal:home, we trigger /start (so Requirements Help always shows)
    rows.append(
        [InlineKeyboardButton("⬅ Back to Sanctuary Menu", callback_data="reqpanel:back_start")]
    )
    return InlineKeyboardMarkup(rows)


def _admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📋 Member Status List", callback_data="reqpanel:list:0"
                ),
                InlineKeyboardButton(
                    "➕ Add Manual Spend", callback_data="reqpanel:add_select"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📡 Scan Group Members", callback_data="reqpanel:scan"
                ),
            ],
            [
                InlineKeyboardButton(
                    "💌 Send Reminders (Behind Only)", callback_data="reqpanel:reminders"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚠️ Send Final Warnings", callback_data="reqpanel:final_warnings"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅ Back to Requirements Help", callback_data="reqpanel:help"
                )
            ],
        ]
    )


def _member_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Add Manual Spend", callback_data=f"reqpanel:add:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ Toggle Exempt", callback_data=f"reqpanel:ex_toggle:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "💌 Send Reminder", callback_data=f"reqpanel:rem_one:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚠️ Send Final Warning", callback_data=f"reqpanel:final_one:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅ Back to Member List", callback_data="reqpanel:list:0"
                )
            ],
        ]
    )


def _amount_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "$5", callback_data=f"reqpanel:addamt:{user_id}:5"
                ),
                InlineKeyboardButton(
                    "$10", callback_data=f"reqpanel:addamt:{user_id}:10"
                ),
                InlineKeyboardButton(
                    "$20", callback_data=f"reqpanel:addamt:{user_id}:20"
                ),
            ],
            [
                InlineKeyboardButton(
                    "$25", callback_data=f"reqpanel:addamt:{user_id}:25"
                ),
                InlineKeyboardButton(
                    "$50", callback_data=f"reqpanel:addamt:{user_id}:50"
                ),
                InlineKeyboardButton(
                    "Custom amount", callback_data=f"reqpanel:addamt:{user_id}:custom"
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅ Back to Member Menu", callback_data=f"reqpanel:member:{user_id}"
                )
            ],
        ]
    )


def _who_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Roni", callback_data=f"reqpanel:addwho:{user_id}:Roni"
                ),
                InlineKeyboardButton(
                    "Ruby", callback_data=f"reqpanel:addwho:{user_id}:Ruby"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Peachy", callback_data=f"reqpanel:addwho:{user_id}:Peachy"
                ),
                InlineKeyboardButton(
                    "Savy", callback_data=f"reqpanel:addwho:{user_id}:Savy"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Other / mixed", callback_data=f"reqpanel:addwho:{user_id}:Other"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅ Cancel", callback_data=f"reqpanel:member:{user_id}"
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

    # ENTRY from main menu "Requirements Help" button
    @app.on_callback_query(filters.regex(r"^reqpanel:help$"))
    async def reqpanel_help_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        is_admin = _is_admin_or_model(user_id)

        text = (
            "<b>Requirements Help</b>\n\n"
            "Use this panel to check how you’re doing on Sanctuary requirements this month.\n\n"
            "• <b>Check My Status</b> – see if you’re met or behind.\n"
            "• <b>Admin / Model Controls</b> – open the owner/models tools "
            "(lists, manual credit, exemptions, reminders).\n\n"
            "Regular members only see their own status.\n"
            "Owner & models get the full tools."
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_root_kb(is_admin),
            disable_web_page_preview=True,
        )

    # aliases
    @app.on_callback_query(filters.regex(r"^reqpanel:(home|open)$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        await reqpanel_help_cb(_, cq)

    # Back to sanctuary menu → simulate /start so Requirements Help always shows
    @app.on_callback_query(filters.regex(r"^reqpanel:back_start$"))
    async def reqpanel_back_start_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        # fire /start so your normal start handler runs
        await client.send_message(user_id, "/start")
        await cq.answer()
        # optional: keep current panel text or delete; we'll just leave it

    # Admin / model tools panel
    @app.on_callback_query(filters.regex(r"^reqpanel:admin$"))
    async def reqpanel_admin_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and approved models can open this.", show_alert=True)
            return

        text = (
            "<b>Requirements Panel – Admin / Model Controls</b>\n\n"
            "These tools manage Sanctuary requirements for the month.\n"
            "Everything here updates what SuccuBot uses when checking member status "
            "or running sweeps, so double-check before confirming changes.\n\n"
            "From here you can:\n"
            "▪️ Open the full member list\n"
            "▪️ Add manual spend credit\n"
            "▪️ Scan groups into the tracker\n"
            "▪️ Send reminder DMs\n"
            "▪️ Send final-warning DMs\n\n"
            "<i>Regular members never see this panel.</i>"
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── Self-status ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:self$"))
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

    # ────────────── Member list + per-member menu ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:list(?::\d+)?$"))
    async def reqpanel_list_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can view the list.", show_alert=True)
            return

        m = re.match(r"^reqpanel:list(?::(\d+))?$", cq.data)
        page = int(m.group(1)) if m and m.group(1) is not None else 0
        if page < 0:
            page = 0

        skip = page * PAGE_SIZE
        cursor = members_coll.find().sort("first_name", ASCENDING).skip(skip).limit(PAGE_SIZE)
        docs = list(cursor)

        if not docs:
            text = (
                "<b>Member Status List</b>\n\n"
                "No tracked members yet. Try running a scan first."
            )
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📡 Scan Group Members", callback_data="reqpanel:scan"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅ Back to Admin / Model Controls", callback_data="reqpanel:admin"
                        )
                    ],
                ]
            )
        else:
            lines = [f"<b>Member Status List – Page {page + 1}</b>\n"]
            buttons: List[List[InlineKeyboardButton]] = []

            for d in docs:
                uid = d["user_id"]
                doc_full = _member_doc(uid)
                name = _display_name(doc_full)
                status = _status_label(doc_full)
                total = doc_full["manual_spend"]
                lines.append(
                    f"• {name} (<code>{uid}</code>) – {status} (${total:.2f})"
                )
                label = f"{name} – {status} (${total:.2f})"
                buttons.append(
                    [
                        InlineKeyboardButton(
                            label, callback_data=f"reqpanel:member:{uid}"
                        )
                    ]
                )

            nav_row: List[InlineKeyboardButton] = []
            if page > 0:
                nav_row.append(
                    InlineKeyboardButton("⬅ Prev", callback_data=f"reqpanel:list:{page-1}")
                )
            if len(docs) == PAGE_SIZE:
                nav_row.append(
                    InlineKeyboardButton("Next ➡", callback_data=f"reqpanel:list:{page+1}")
                )
            if nav_row:
                buttons.append(nav_row)
            buttons.append(
                [
                    InlineKeyboardButton(
                        "⬅ Back to Admin / Model Controls", callback_data="reqpanel:admin"
                    )
                ]
            )

            text = "\n".join(lines)
            kb = InlineKeyboardMarkup(buttons)

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:member:(\d+)$"))
    async def reqpanel_member_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can open member controls.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[2])
        doc = _member_doc(target_id)
        text = _format_member_status(doc)

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_member_menu_kb(target_id),
            disable_web_page_preview=True,
        )

    # ────────────── Add Manual Spend (select member from button list) ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:add_select$"))
    async def reqpanel_add_select_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        docs = list(members_coll.find().sort("first_name", ASCENDING).limit(50))
        if not docs:
            text = (
                "<b>Add Manual Spend</b>\n\n"
                "No tracked members yet. Try running a scan first."
            )
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📡 Scan Group Members", callback_data="reqpanel:scan"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅ Back to Admin / Model Controls", callback_data="reqpanel:admin"
                        )
                    ],
                ]
            )
        else:
            lines = [
                "<b>Add Manual Spend</b>\n\n"
                "Tap a member below to credit manual spend for this month:\n"
            ]
            buttons: List[List[InlineKeyboardButton]] = []
            for d in docs:
                uid = d["user_id"]
                doc_full = _member_doc(uid)
                name = _display_name(doc_full)
                status = _status_label(doc_full)
                total = doc_full["manual_spend"]
                lines.append(
                    f"• {name} (<code>{uid}</code>) – {status} (${total:.2f})"
                )
                buttons.append(
                    [
                        InlineKeyboardButton(
                            f"{name} – ${total:.2f}",
                            callback_data=f"reqpanel:add:{uid}",
                        )
                    ]
                )
            buttons.append(
                [
                    InlineKeyboardButton(
                        "⬅ Back to Admin / Model Controls", callback_data="reqpanel:admin"
                    )
                ]
            )
            text = "\n".join(lines)
            kb = InlineKeyboardMarkup(buttons)

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ────────────── Add Manual Spend (per-member flow) ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:add:(\d+)$"))
    async def reqpanel_add_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[2])
        STATE[user_id] = {"mode": "add_amount", "target_id": target_id}

        doc = _member_doc(target_id)
        text = (
            "<b>Add Manual Spend</b>\n\n"
            f"Member: {_display_name(doc)} (<code>{target_id}</code>)\n\n"
            "Pick an amount to credit for this month:"
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_amount_kb(target_id),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:addamt:(\d+):(.+)$"))
    async def reqpanel_addamt_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        state = STATE.get(user_id)
        if not state or state.get("mode") not in {"add_amount", "add_amount_custom"}:
            await cq.answer("This flow expired, start again from Add Manual Spend.")
            return

        _, _, target_str, amt_str = cq.data.split(":", 3)
        target_id = int(target_str)
        STATE[user_id]["target_id"] = target_id

        if amt_str == "custom":
            STATE[user_id]["mode"] = "add_amount_custom"
            await cq.answer()
            await _safe_edit_text(
                cq.message,
                text=(
                    "<b>Add Manual Spend – Custom Amount</b>\n\n"
                    "Send me just the number for how many dollars to credit.\n\n"
                    "Example: <code>17.50</code>"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⬅ Cancel", callback_data=f"reqpanel:member:{target_id}"
                            )
                        ]
                    ]
                ),
                disable_web_page_preview=True,
            )
            return

        amount = float(amt_str)
        STATE[user_id]["amount"] = amount
        STATE[user_id]["mode"] = "add_who"

        doc = _member_doc(target_id)
        text = (
            "<b>Add Manual Spend</b>\n\n"
            f"Member: {_display_name(doc)} (<code>{target_id}</code>)\n"
            f"Amount: ${amount:.2f}\n\n"
            "Who was this payment for?"
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_who_kb(target_id),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:addwho:(\d+):(.+)$"))
    async def reqpanel_addwho_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        state = STATE.get(user_id)
        if not state or state.get("mode") != "add_who":
            await cq.answer("This flow expired, start again from Add Manual Spend.")
            return

        _, _, target_str, who = cq.data.split(":", 3)
        target_id = int(target_str)
        amount = float(state["amount"])

        doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}
        new_total = float(doc.get("manual_spend", 0.0)) + amount

        members_coll.update_one(
            {"user_id": target_id},
            {
                "$set": {
                    "manual_spend": new_total,
                    "last_updated": datetime.now(timezone.utc),
                },
                "$setOnInsert": {"first_name": ""},
            },
            upsert=True,
        )

        STATE.pop(user_id, None)

        await _log_event(
            client,
            f"Manual spend +${amount:.2f} for {target_id} (for {who}) by {user_id}.",
        )

        member_doc = _member_doc(target_id)
        text = (
            "<b>Manual Spend Saved</b>\n\n"
            f"Member: {_display_name(member_doc)} (<code>{target_id}</code>)\n"
            f"Credited: ${amount:.2f} for {who}\n"
            f"New manual total: ${new_total:.2f}"
        )

        await cq.answer("Saved.")
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_member_menu_kb(target_id),
            disable_web_page_preview=True,
        )

    # ────────────── Text-based step ONLY for custom amount value ──────────────

    @app.on_message(filters.private & filters.text)
    async def requirements_state_router(client: Client, msg: Message):
        user_id = msg.from_user.id
        state = STATE.get(user_id)
        if not state:
            return

        mode = state.get("mode")

        if mode == "add_amount_custom":
            try:
                amount = float(msg.text.strip())
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await msg.reply_text(
                    "Please send just a positive number for the dollar amount.\n\n"
                    "Example: <code>17.50</code>"
                )
                return

            STATE[user_id]["amount"] = amount
            STATE[user_id]["mode"] = "add_who"
            target_id = int(state["target_id"])

            doc = _member_doc(target_id)
            text = (
                "<b>Add Manual Spend</b>\n\n"
                f"Member: {_display_name(doc)} (<code>{target_id}</code>)\n"
                f"Amount: ${amount:.2f}\n\n"
                "Who was this payment for?"
            )

            await msg.reply_text(
                text,
                reply_markup=_who_kb(target_id),
                disable_web_page_preview=True,
            )
            return

    # ────────────── Toggle Exempt (button-based) ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:ex_toggle:(\d+)$"))
    async def reqpanel_toggle_exempt_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can change exemptions.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[2])
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

        await _log_event(
            client,
            f"Exempt toggled to {new_val} for {target_id} by {user_id}",
        )

        member_doc = _member_doc(target_id)
        text = _format_member_status(member_doc)

        await cq.answer(
            f"{'Now EXEMPT' if new_val else 'No longer marked exempt'}{model_note}",
            show_alert=False,
        )
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_member_menu_kb(target_id),
            disable_web_page_preview=True,
        )

    # ────────────── Scan group members ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:scan$"))
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

    # ────────────── Reminder + Final warning sweeps (OWNER ONLY) ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:reminders$"))
    async def reqpanel_reminders_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if user_id != OWNER_ID:
            await cq.answer("Only Roni can send batch reminders.", show_alert=True)
            return

        docs = members_coll.find(
            {
                "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
                "reminder_sent": {"$ne": True},
            }
        )

        count = 0
        for d in docs:
            uid = d["user_id"]
            # Owner & models are always treated as exempt for sweeps
            if uid == OWNER_ID or uid in MODELS:
                continue
            member = _member_doc(uid)
            if member["is_exempt"]:
                continue

            name = member.get("first_name") or "there"
            msg = random.choice(REMINDER_MSGS).format(name=name)
            sent = await _safe_send(client, uid, msg)
            if not sent:
                continue
            members_coll.update_one(
                {"user_id": uid},
                {"$set": {"reminder_sent": True, "last_updated": datetime.now(timezone.utc)}},
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

    @app.on_callback_query(filters.regex(r"^reqpanel:final_warnings$"))
    async def reqpanel_final_warnings_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if user_id != OWNER_ID:
            await cq.answer("Only Roni can send batch final warnings.", show_alert=True)
            return

        docs = members_coll.find(
            {
                "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
                "final_warning_sent": {"$ne": True},
            }
        )

        count = 0
        for d in docs:
            uid = d["user_id"]
            if uid == OWNER_ID or uid in MODELS:
                continue
            member = _member_doc(uid)
            if member["is_exempt"]:
                continue

            name = member.get("first_name") or "there"
            msg = random.choice(FINAL_WARNING_MSGS).format(name=name)
            sent = await _safe_send(client, uid, msg)
            if not sent:
                continue
            members_coll.update_one(
                {"user_id": uid},
                {"$set": {"final_warning_sent": True, "last_updated": datetime.now(timezone.utc)}},
            )
            count += 1

        await _log_event(client, f"Final warnings sent to {count} members by {user_id}")
        await cq.answer(f"Sent final warnings to {count} member(s).", show_alert=True)
        await _safe_edit_text(
            cq.message,
            text=f"⚠️ Final-warning sweep complete.\nSent to {count} member(s) still behind.",
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    # ────────────── Single-member reminders (push-button) ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:rem_one:(\d+)$"))
    async def reqpanel_rem_one_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if user_id != OWNER_ID:
            await cq.answer("Only Roni can send reminder DMs.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[2])
        member = _member_doc(target_id)

        if member["is_exempt"] or member["manual_spend"] >= REQUIRED_MIN_SPEND:
            await cq.answer("This member is exempt or already met requirements.", show_alert=True)
            return

        name = member.get("first_name") or "there"
        msg = random.choice(REMINDER_MSGS).format(name=name)
        sent = await _safe_send(client, target_id, msg)
        if sent:
            members_coll.update_one(
                {"user_id": target_id},
                {"$set": {"reminder_sent": True, "last_updated": datetime.now(timezone.utc)}},
            )
            await _log_event(
                client, f"Single reminder sent to {target_id} by {user_id}"
            )
            await cq.answer("Reminder sent.", show_alert=False)
        else:
            await cq.answer("Could not send reminder DM.", show_alert=True)

        member = _member_doc(target_id)
        text = _format_member_status(member)
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_member_menu_kb(target_id),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:final_one:(\d+)$"))
    async def reqpanel_final_one_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if user_id != OWNER_ID:
            await cq.answer("Only Roni can send final-warning DMs.", show_alert=True)
            return

        target_id = int(cq.data.split(":")[2])
        member = _member_doc(target_id)

        if member["is_exempt"] or member["manual_spend"] >= REQUIRED_MIN_SPEND:
            await cq.answer("This member is exempt or already met requirements.", show_alert=True)
            return

        name = member.get("first_name") or "there"
        msg = random.choice(FINAL_WARNING_MSGS).format(name=name)
        sent = await _safe_send(client, target_id, msg)
        if sent:
            members_coll.update_one(
                {"user_id": target_id},
                {"$set": {"final_warning_sent": True, "last_updated": datetime.now(timezone.utc)}},
            )
            await _log_event(
                client, f"Single final warning sent to {target_id} by {user_id}"
            )
            await cq.answer("Final warning sent.", show_alert=False)
        else:
            await cq.answer("Could not send final warning DM.", show_alert=True)

        member = _member_doc(target_id)
        text = _format_member_status(member)
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_member_menu_kb(target_id),
            disable_web_page_preview=True,
        )
