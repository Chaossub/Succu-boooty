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
    Message,
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

# ────────────── Entry Point ──────────────

def register(app: Client):

    # USER presses “Book Roni”
    @app.on_callback_query(filters.regex("^nsfw:book:start$"))
    async def start_booking(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "📅 <b>Pick a date to request your private texting session</b>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("➡ Continue", callback_data="nsfw:book:date")]]
            ),
        )
        await cq.answer()

    # MOCK DATE (your availability handler feeds real ones)
    @app.on_callback_query(filters.regex("^nsfw:book:date$"))
    async def pick_date(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "🕒 <b>Select a time</b>",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("11:00 AM", callback_data="nsfw:book:time:11:00"),
                        InlineKeyboardButton("1:00 PM", callback_data="nsfw:book:time:13:00"),
                    ]
                ]
            ),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^nsfw:book:time:(.+)$"))
    async def pick_time(_, cq: CallbackQuery):
        time_str = cq.matches[0].group(1)
        booking_id = str(uuid.uuid4())

        BOOKINGS[booking_id] = {
            "id": booking_id,
            "user_id": cq.from_user.id,
            "username": cq.from_user.username,
            "date": "Friday, December 19",
            "time": time_str,
            "duration": "30 minutes",
            "status": "pending",
            "created": datetime.utcnow().isoformat(),
        }
        _save(BOOKINGS)

        # Notify ADMIN
        await app.send_message(
            ADMIN_ID,
            (
                "💗 <b>New NSFW texting session request</b>\n\n"
                f"👤 @{cq.from_user.username or cq.from_user.first_name}\n"
                f"{_fmt('Friday, December 19', time_str)}\n"
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
        )

        # Notify USER
        await cq.message.edit_text(
            (
                "💗 <b>Request sent</b>\n\n"
                f"{_fmt('Friday, December 19', time_str)}\n"
                "⏱ 30 minutes\n\n"
                "Roni will review your request and reach out for payment.\n\n"
                "🚫 <b>NO meetups — online/texting only.</b>"
            ),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]]
            ),
        )
        await cq.answer()

    # ────────────── ADMIN ACTIONS ──────────────

    @app.on_callback_query(filters.regex("^nsfw:admin:accept:(.+)$"))
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

        # Notify USER
        await app.send_message(
            booking["user_id"],
            (
                "✅ <b>Your session request was accepted 💕</b>\n\n"
                f"{_fmt(booking['date'], booking['time'])}\n\n"
                "Roni will reach out to you for payment.\n"
                "Just a reminder: <b>no meetups — this is all over text.</b>"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💕 Book another", callback_data="nsfw:book:start")],
                    [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                ]
            ),
        )

    @app.on_callback_query(filters.regex("^nsfw:admin:cancel:(.+)$"))
    async def admin_cancel(_, cq: CallbackQuery):
        booking_id = cq.matches[0].group(1)
        booking = BOOKINGS.pop(booking_id, None)
        _save(BOOKINGS)

        await cq.message.edit_text("❌ Booking cancelled.")
        await cq.answer()

        if booking:
            await app.send_message(
                booking["user_id"],
                (
                    "❌ <b>All good 💕 Booking cancelled.</b>\n\n"
                    "Just a reminder: <b>no meetups — this is all over text.</b>"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]]
                ),
            )
