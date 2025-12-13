import json
import os
import uuid
from datetime import datetime
from typing import Dict

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

DATA_PATH = "data/nsfw_bookings.json"
ADMIN_ID = int(os.getenv("OWNER_ID", "6964994611"))
TZ_LABEL = "LA time"

# ────────────── Storage ──────────────

def _load():
    if not os.path.exists(DATA_PATH):
        return {}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

BOOKINGS: Dict[str, dict] = _load()

# ────────────── Helpers ──────────────

def _fmt(dt: str, tm: str):
    return f"📅 {dt}\n⏰ {tm} ({TZ_LABEL})"

def _back_to_assistant_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]]
    )

# ────────────── Register ──────────────

def register(app: Client):

    # ✅ Entry point (supports both callback styles)
    @app.on_callback_query(filters.regex(r"^(nsfw_book:open|nsfw:book:start)$"))
    async def start_booking(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "📅 <b>Pick a date to request your private texting session</b>\n\n"
            "Prices are listed in 📖 Roni’s Menu.\n"
            "🚫 <b>No meetups</b> — this is online/texting only.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📅 Pick a date", callback_data="nsfw:book:date:0")],
                    [InlineKeyboardButton("📖 View prices (Roni’s Menu)", callback_data="roni_portal:menu")],
                    [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Date picker (simple “week offset” pager)
    @app.on_callback_query(filters.regex(r"^nsfw:book:date:(\d+)$"))
    async def pick_date(_, cq: CallbackQuery):
        week = int(cq.matches[0].group(1))

        # For now: just demo dates (you can wire this to your availability system later)
        # Keeping the callback format stable so "next week" actually works.
        base_dates = [
            "Friday, December 19",
            "Saturday, December 20",
            "Sunday, December 21",
            "Monday, December 22",
        ]
        date_label = base_dates[week % len(base_dates)]

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("11:00 AM", callback_data=f"nsfw:book:time:{week}:11:00 AM"),
                    InlineKeyboardButton("1:00 PM", callback_data=f"nsfw:book:time:{week}:1:00 PM"),
                ],
                [
                    InlineKeyboardButton("➡ Next week", callback_data=f"nsfw:book:date:{week+1}")
                ],
                [
                    InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:open"),
                    InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home"),
                ],
            ]
        )

        await cq.message.edit_text(
            f"🗓 <b>{date_label}</b>\n\nChoose a time:",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Time select
    @app.on_callback_query(filters.regex(r"^nsfw:book:time:(\d+):(.+)$"))
    async def pick_time(_, cq: CallbackQuery):
        week = int(cq.matches[0].group(1))
        time_str = cq.matches[0].group(2)

        base_dates = [
            "Friday, December 19",
            "Saturday, December 20",
            "Sunday, December 21",
            "Monday, December 22",
        ]
        date_str = base_dates[week % len(base_dates)]

        booking_id = str(uuid.uuid4())

        BOOKINGS[booking_id] = {
            "id": booking_id,
            "user_id": cq.from_user.id,
            "username": cq.from_user.username,
            "name": cq.from_user.first_name,
            "date": date_str,
            "time": time_str,
            "duration": "30 minutes",
            "status": "pending",
            "created": datetime.utcnow().isoformat(),
        }
        _save(BOOKINGS)

        # Notify ADMIN with Accept/Cancel
        await app.send_message(
            ADMIN_ID,
            (
                "💗 <b>New NSFW texting session request</b>\n\n"
                f"👤 {BOOKINGS[booking_id]['name']} (@{BOOKINGS[booking_id]['username'] or 'no_username'})\n"
                f"{_fmt(date_str, time_str)}\n"
                "⏱ 30 minutes"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ Accept", callback_data=f"nsfw:admin:accept:{booking_id}"),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"nsfw:admin:cancel:{booking_id}"),
                    ]
                ]
            ),
            disable_web_page_preview=True,
        )

        # Notify USER (request sent)
        await cq.message.edit_text(
            (
                "💗 <b>Request sent</b>\n\n"
                f"{_fmt(date_str, time_str)}\n"
                "⏱ 30 minutes\n\n"
                "Roni will review your request and reach out to you for payment :)\n"
                "You can find current prices in 📖 Roni’s Menu.\n\n"
                "Just a reminder: <b>no meetups — this is all over text.</b>"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📖 View prices (Roni’s Menu)", callback_data="roni_portal:menu")],
                    [InlineKeyboardButton("💕 Book another", callback_data="nsfw_book:open")],
                    [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ────────────── ADMIN ACTIONS ──────────────

    @app.on_callback_query(filters.regex(r"^nsfw:admin:accept:(.+)$"))
    async def admin_accept(_, cq: CallbackQuery):
        booking_id = cq.matches[0].group(1)
        booking = BOOKINGS.get(booking_id)
        if not booking:
            await cq.answer("Booking not found", show_alert=True)
            return

        booking["status"] = "accepted"
        _save(BOOKINGS)

        await cq.message.edit_text("✅ Accepted. User was notified 💕")
        await cq.answer()

        # USER accepted message (NO menu button)
        user_kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💕 Book another", callback_data="nsfw_book:open")],
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
            ]
        )

        await app.send_message(
            chat_id=booking["user_id"],
            text=(
                "✅ <b>Your session request was accepted 💕</b>\n\n"
                f"{_fmt(booking['date'], booking['time'])}\n\n"
                "Roni will reach out to you for payment :)\n"
                "Just a reminder: <b>no meetups — this is all over text.</b>"
            ),
            reply_markup=user_kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^nsfw:admin:cancel:(.+)$"))
    async def admin_cancel(_, cq: CallbackQuery):
        booking_id = cq.matches[0].group(1)
        booking = BOOKINGS.pop(booking_id, None)
        _save(BOOKINGS)

        await cq.message.edit_text("❌ Booking cancelled.")
        await cq.answer()

        if booking:
            await app.send_message(
                chat_id=booking["user_id"],
                text=(
                    "❌ <b>All good 💕 Booking cancelled.</b>\n\n"
                    "Just a reminder: <b>no meetups — this is all over text.</b>"
                ),
                reply_markup=_back_to_assistant_kb(),
                disable_web_page_preview=True,
            )

