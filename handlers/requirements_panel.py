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
    # Fallback: single group from SUCCUBUS_SANCTUARY
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

# Simple in-memory state for multi-step flows (manual spend, lookups, etc.)
STATE: Dict[int, Dict[str, Any]] = {}

# ────────────── Helper functions ──────────────

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

def _member_doc(user_id: int) -> Dict[str, Any]:
    doc = members_coll.find_one({"user_id": user_id}) or {}
    return {
        "user_id": user_id,
        "first_name": doc.get("first_name", ""),
        "username": doc.get("username"),
        "manual_spend": float(doc.get("manual_spend", 0.0)),
        "is_exempt": bool(doc.get("is_exempt", False)),
        "reminder_sent": bool(doc.get("reminder_sent", False)),
        "final_warning_sent": bool(doc.get("final_warning_sent", False)),
        "last_updated": doc.get("last_updated"),
    }

def _format_member_status(doc: Dict[str, Any]) -> str:
    total = doc["manual_spend"]
    exempt = doc["is_exempt"]
    status: str
    if exempt:
        status = "✅ Marked exempt from requirements this month."
    elif total >= REQUIRED_MIN_SPEND:
        status = f"✅ Requirements met with ${total:.2f} logged."
    else:
        status = (
            f"⚠️ Currently behind.\n"
            f"Logged so far: ${total:.2f} (minimum ${REQUIRED_MIN_SPEND:.2f})."
        )
    lines = [
        f"<b>Requirement Status</b>",
        "",
        status,
    ]
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
            [InlineKeyboardButton("🧾 Look Up Member", callback_data="reqpanel:lookup")]
        )
        rows.append(
            [InlineKeyboardButton("🛠 Owner / Models Tools", callback_data="reqpanel:admin")]
        )

    rows.append(
        [InlineKeyboardButton("⬅ Back to Sanctuary Menu", callback_data="portal:home")]
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
            ],
            [
                InlineKeyboardButton("💌 Send Reminders (Behind Only)", callback_data="reqpanel:reminders"),
            ],
            [
                InlineKeyboardButton("⚠️ Send Final Warnings", callback_data="reqpanel:final_warnings"),
            ],
            [
                InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home"),
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
                    "• <b>Look Up Member</b> – view another member’s status.",
                    "• <b>Owner / Models Tools</b> – open the full admin tools panel "
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

    # Direct open from somewhere else (optional)
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
            "▪️ Send reminder DMs to members who are behind\n"
            "▪️ Send final-warning DMs to those still not meeting minimums\n\n"
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
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")]]
            ),
        )

    @app.on_message(filters.private & filters.text)
    async def requirements_state_router(client: Client, msg: Message):
        user_id = msg.from_user.id
        state = STATE.get(user_id)
        if not state:
            return

        mode = state.get("mode")

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

        # ADD SPEND FLOW
        if mode == "add_spend":
            try:
                parts = msg.text.strip().split()
                if len(parts) < 2:
                    raise ValueError
                target_id = int(parts[0])
                amount = float(parts[1])
                note = " ".join(parts[2:]) if len(parts) > 2 else ""
            except ValueError:
                await msg.reply_text(
                    "Format should be:\n"
                    "<code>USER_ID amount [note]</code>\n\n"
                    "Example:\n<code>123456789 15 cashapp game night</code>"
                )
                return

            doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}
            new_total = float(doc.get("manual_spend", 0.0)) + amount

            members_coll.update_one(
                {"user_id": target_id},
                {
                    "$set": {
                        "manual_spend": new_total,
                        "last_updated": datetime.now(timezone.utc),
                    },
                    "$setOnInsert": {
                        "first_name": "",
                    },
                },
                upsert=True,
            )

            await msg.reply_text(
                f"Logged ${amount:.2f} for <code>{target_id}</code>.\n"
                f"New manual total: ${new_total:.2f}"
            )
            await _log_event(
                client,
                f"Manual spend +${amount:.2f} for {target_id} by {user_id}. Note: {note or '(none)'}",
            )
            STATE.pop(user_id, None)
            return

        # TOGGLE EXEMPT FLOW
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
                    },
                    "$setOnInsert": {"first_name": ""},
                },
                upsert=True,
            )
            await msg.reply_text(
                f"User <code>{target_id}</code> is now "
                f"{'✅ EXEMPT' if new_val else '❌ NOT exempt'} for this month."
            )
            await _log_event(
                client,
                f"Exempt toggled to {new_val} for {target_id} by {user_id}",
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
                exempt = d.get("is_exempt", False)
                if exempt:
                    status = "EXEMPT"
                elif total >= REQUIRED_MIN_SPEND:
                    status = "MET"
                else:
                    status = "BEHIND"
                lines.append(
                    f"• <code>{uid}</code> – {status} (${total:.2f})"
                )
            text = "\n".join(lines)

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_admin_kb(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex("^reqpanel:add_spend$"))
    async def reqpanel_add_spend_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        STATE[user_id] = {"mode": "add_spend"}
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Add Manual Spend</b>\n\n"
                "Send me a message in this format:\n"
                "<code>USER_ID amount [note]</code>\n\n"
                "Example:\n<code>123456789 15 cashapp game night</code>\n\n"
                "This adds extra credited dollars on top of Stripe / games "
                "for this month only."
            ),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")]]
            ),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex("^reqpanel:toggle_exempt$"))
    async def reqpanel_toggle_exempt_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can change exemptions.", show_alert=True)
            return

        STATE[user_id] = {"mode": "toggle_exempt"}
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Exempt / Un-exempt Member</b>\n\n"
                "Send me the numeric Telegram user ID for the member.\n\n"
                "I’ll flip their exempt status for this month."
            ),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")]]
            ),
            disable_web_page_preview=True,
        )

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

    @app.on_callback_query(filters.regex("^reqpanel:reminders$"))
    async def reqpanel_reminders_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can send reminders.", show_alert=True)
            return

        # behind + not exempt + no reminder yet
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
            name = d.get("first_name") or "there"
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

    @app.on_callback_query(filters.regex("^reqpanel:final_warnings$"))
    async def reqpanel_final_warnings_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can send final warnings.", show_alert=True)
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
            name = d.get("first_name") or "there"
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
