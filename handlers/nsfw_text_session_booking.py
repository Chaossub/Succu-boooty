import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict
from zoneinfo import ZoneInfo

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

DATA_PATH = "data/nsfw_bookings.json"
ADMIN_ID = int(os.getenv("OWNER_ID", "6964994611"))

LA_TZ = ZoneInfo("America/Los_Angeles")
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

def _now_la() -> datetime:
    return datetime.now(tz=LA_TZ)

def _fmt_date_label(d: datetime) -> str:
    # "Fri Dec 19"
    return d.strftime("%a %b %d").replace(" 0", " ")

def _fmt_full_date(d: datetime) -> str:
    # "Friday, December 19"
    return d.strftime("%A, %B %d").replace(" 0", " ")

def _fmt(dt_label: str, tm: str) -> str:
    return f"📅 {dt_label}\n⏰ {tm} ({TZ_LABEL})"

def _back_to_assistant_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]]
    )

def _menu_or_back_kb(back_cb: str):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 View prices (Roni’s Menu)", callback_data="roni_portal:menu")],
            [InlineKeyboardButton("⬅ Back", callback_data=back_cb)],
        ]
    )

# ────────────── UI Builders ──────────────

def _date_grid_kb(week_offset: int) -> InlineKeyboardMarkup:
    """
    Show 7 dates starting from 'today + week_offset*7' in LA time.
    """
    start = _now_la().date() + timedelta(days=week_offset * 7)
    days = [start + timedelta(days=i) for i in range(7)]

    rows = []
    # 2 columns for first 6, last row single
    for i in range(0, 6, 2):
        d1 = datetime(days[i].year, days[i].month, days[i].day, tzinfo=LA_TZ)
        d2 = datetime(days[i+1].year, days[i+1].month, days[i+1].day, tzinfo=LA_TZ)
        rows.append([
            InlineKeyboardButton(_fmt_date_label(d1), callback_data=f"nsfw:book:pickdate:{d1.date().isoformat()}:{week_offset}"),
            InlineKeyboardButton(_fmt_date_label(d2), callback_data=f"nsfw:book:pickdate:{d2.date().isoformat()}:{week_offset}"),
        ])

    d7 = datetime(days[6].year, days[6].month, days[6].day, tzinfo=LA_TZ)
    rows.append([InlineKeyboardButton(_fmt_date_label(d7), callback_data=f"nsfw:book:pickdate:{d7.date().isoformat()}:{week_offset}")])

    nav = []
    if week_offset > 0:
        nav.append(InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw:book:datepage:{week_offset-1}"))
    nav.append(InlineKeyboardButton("➡ Next week", callback_data=f"nsfw:book:datepage:{week_offset+1}"))
    rows.append(nav)

    rows.append([
        InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:open"),
        InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home"),
    ])

    return InlineKeyboardMarkup(rows)

def _time_picker_kb(date_iso: str, week_offset: int) -> InlineKeyboardMarkup:
    """
    Preset times (LA). You can expand/replace this later with your availability windows.
    """
    # Keeping this sane: start times that fit 30–60 min inside business hours (09:00–22:00)
    times = ["9:00 AM", "11:00 AM", "1:00 PM", "3:00 PM", "5:00 PM", "7:00 PM", "9:00 PM"]

    rows = []
    for i in range(0, len(times), 2):
        row = [InlineKeyboardButton(times[i], callback_data=f"nsfw:book:time:{date_iso}:{times[i]}")]
        if i + 1 < len(times):
            row.append(InlineKeyboardButton(times[i+1], callback_data=f"nsfw:book:time:{date_iso}:{times[i+1]}"))
        rows.append(row)

    rows.append([
        InlineKeyboardButton("📅 Pick another date", callback_data=f"nsfw:book:datepage:{week_offset}"),
    ])
    rows.append([
        InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:open"),
        InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home"),
    ])
    return InlineKeyboardMarkup(rows)

# ────────────── Register ──────────────

def register(app: Client):

    # ✅ Entry point (supports BOTH callback styles)
    @app.on_callback_query(filters.regex(r"^(nsfw_book:open|nsfw:book:start)$"))
    async def start_booking(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "📩 <b>Book a private NSFW texting session</b>\n\n"
            "Prices are listed in 📖 Roni’s Menu.\n"
            "🚫 <b>No meetups</b> — this is online/texting only.\n\n"
            "Tap below to choose a date (LA time).",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📅 Pick a date", callback_data="nsfw:book:datepage:0")],
                    [InlineKeyboardButton("📖 View prices (Roni’s Menu)", callback_data="roni_portal:menu")],
                    [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ✅ Date page (7-day grid + next/prev week)
    @app.on_callback_query(filters.regex(r"^nsfw:book:datepage:(\d+)$"))
    async def date_page(_, cq: CallbackQuery):
        week_offset = int(cq.matches[0].group(1))
        kb = _date_grid_kb(week_offset)

        start = _now_la().date() + timedelta(days=week_offset * 7)
        end = start + timedelta(days=6)

        await cq.message.edit_text(
            f"📅 <b>Pick a date</b> ({TZ_LABEL})\n"
            f"{start.strftime('%b %d').replace(' 0',' ')} – {end.strftime('%b %d').replace(' 0',' ')}",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ✅ Pick a specific date
    @app.on_callback_query(filters.regex(r"^nsfw:book:pickdate:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def pick_date(_, cq: CallbackQuery):
        date_iso = cq.matches[0].group(1)
        week_offset = int(cq.matches[0].group(2))

        d = datetime.fromisoformat(date_iso).replace(tzinfo=LA_TZ)
        pretty = _fmt_full_date(d)

        await cq.message.edit_text(
            f"🗓 <b>{pretty}</b>\n\nChoose a time:",
            reply_markup=_time_picker_kb(date_iso, week_offset),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ✅ Pick time -> create booking request -> notify admin with Accept/Cancel
    @app.on_callback_query(filters.regex(r"^nsfw:book:time:(\d{4}-\d{2}-\d{2}):(.+)$"))
    async def pick_time(_, cq: CallbackQuery):
        date_iso = cq.matches[0].group(1)
        time_str = cq.matches[0].group(2)

        d = datetime.fromisoformat(date_iso).replace(tzinfo=LA_TZ)
        date_str = _fmt_full_date(d)

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

        # ADMIN message with Accept/Cancel
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

        # USER confirmation (request sent)
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

        # USER accepted (NO menu button)
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
