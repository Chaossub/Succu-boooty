# handlers/nsfw_text_session_booking.py
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Tuple

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.menu_store import store
from utils.nsfw_store import (
    TZ,
    get_business_hours_for_weekday,
    is_blocked,
    add_booking,
    update_booking,
    find_latest_booking_for_user,
)

# Uses your existing menu key from roni_portal
RONI_MENU_KEY = "RoniPersonalMenu"

# Callback sizes kept tiny (Telegram limit)
# day: YYYYMMDD, time: HHMM, duration: 30/60


def _la_now() -> datetime:
    return datetime.now(pytz.timezone(TZ))


def _fmt_day_label(dt: datetime) -> str:
    return dt.strftime("%a %b %-d") if hasattr(dt, "strftime") else dt.strftime("%a %b %d")


def _dt_to_yyyymmdd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _yyyymmdd_to_date(yyyymmdd: str) -> datetime:
    tz = pytz.timezone(TZ)
    return tz.localize(datetime(int(yyyymmdd[0:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]), 0, 0, 0))


def _hhmm_from_min(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _min_from_hhmm(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _build_booking_intro_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 View Roni’s Menu", callback_data="roni_portal:menu:src=nsfw")],
            [InlineKeyboardButton("➡️ Continue Booking", callback_data="nsfw_book:start")],
            [InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")],
        ]
    )


def _build_duration_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏱ 30 minutes", callback_data="nsfw_book:dur:30")],
            [InlineKeyboardButton("🕰 1 hour", callback_data="nsfw_book:dur:60")],
            [InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:open")],
        ]
    )


def _build_days_kb(duration: int) -> InlineKeyboardMarkup:
    tz = pytz.timezone(TZ)
    now = _la_now()
    days: List[List[InlineKeyboardButton]] = []

    # next 7 days including today
    row: List[InlineKeyboardButton] = []
    for i in range(0, 7):
        d = (now + timedelta(days=i)).astimezone(tz)
        ymd = _dt_to_yyyymmdd(d)
        label = d.strftime("%a")  # Mon, Tue...
        row.append(InlineKeyboardButton(f"{label}", callback_data=f"nsfw_book:day:{duration}:{ymd}"))
        if len(row) == 3:
            days.append(row)
            row = []
    if row:
        days.append(row)

    days.append([InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:start")])
    return InlineKeyboardMarkup(days)


def _generate_slots_for_day(ymd: str, duration: int) -> List[str]:
    """
    Returns list of HH:MM start times (30-minute increments) within business hours,
    excluding blocked overlaps.
    """
    tz = pytz.timezone(TZ)
    day_dt = _yyyymmdd_to_date(ymd).astimezone(tz)
    weekday = day_dt.weekday()

    open_h, close_h = get_business_hours_for_weekday(weekday)
    open_min = _min_from_hhmm(open_h)
    close_min = _min_from_hhmm(close_h)

    latest_start = close_min - duration
    starts: List[str] = []

    m = open_min
    while m <= latest_start:
        start_hhmm = _hhmm_from_min(m)
        end_hhmm = _hhmm_from_min(m + duration)
        if not is_blocked(ymd, start_hhmm, end_hhmm):
            starts.append(start_hhmm)
        m += 30  # ✅ 30-minute increments only

    return starts


def _build_times_kb(duration: int, ymd: str) -> InlineKeyboardMarkup:
    starts = _generate_slots_for_day(ymd, duration)
    if not starts:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Pick a different day", callback_data=f"nsfw_book:pickday:{duration}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")],
            ]
        )

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    # paginate-ish by showing up to 24 options (12 hours * 2)
    for hhmm in starts[:24]:
        cb = f"nsfw_book:time:{duration}:{ymd}:{hhmm.replace(':','')}"
        label = hhmm
        row.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_book:pickday:{duration}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)


def _build_note_kb(booking_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✍️ Add a note", callback_data=f"nsfw_book:note:{booking_id}")],
            [InlineKeyboardButton("⏭ Skip", callback_data=f"nsfw_book:skipnote:{booking_id}")],
        ]
    )


def _final_confirm_text() -> str:
    return (
        "Your session is booked 💞\n"
        "Roni will reach out to you for payment :)\n\n"
        "You can find current prices anytime in 📖 Roni’s Menu."
    )


def register(app: Client) -> None:
    # Step 0: Intro with pricing-first
    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def nsfw_open(_, cq: CallbackQuery):
        text = (
            "💞 <b>Before booking</b>\n"
            "Please review current prices in 📖 <b>Roni’s Menu</b> first.\n\n"
            "Texting only — <b>NO MEET UPS</b>.\n\n"
            "When you’re ready, continue booking below."
        )
        await cq.message.edit_text(text, reply_markup=_build_booking_intro_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Step 1: Duration picker
    @app.on_callback_query(filters.regex(r"^nsfw_book:start$"))
    async def nsfw_start(_, cq: CallbackQuery):
        text = "Choose your session length 💕"
        await cq.message.edit_text(text, reply_markup=_build_duration_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Step 2: Day picker
    @app.on_callback_query(filters.regex(r"^nsfw_book:dur:(30|60)$"))
    async def nsfw_dur(_, cq: CallbackQuery):
        duration = int(cq.data.split(":")[2])
        text = "Pick a day 🗓 (Los Angeles time)"
        await cq.message.edit_text(text, reply_markup=_build_days_kb(duration), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:pickday:(30|60)$"))
    async def nsfw_pickday(_, cq: CallbackQuery):
        duration = int(cq.data.split(":")[2])
        text = "Pick a day 🗓 (Los Angeles time)"
        await cq.message.edit_text(text, reply_markup=_build_days_kb(duration), disable_web_page_preview=True)
        await cq.answer()

    # Step 3: Time picker
    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(30|60):\d{8}$"))
    async def nsfw_day(_, cq: CallbackQuery):
        _, _, _, dur_s, ymd = cq.data.split(":")
        duration = int(dur_s)

        day_dt = _yyyymmdd_to_date(ymd).astimezone(pytz.timezone(TZ))
        day_label = day_dt.strftime("%A, %b %-d") if hasattr(day_dt, "strftime") else day_dt.strftime("%A, %b %d")

        starts = _generate_slots_for_day(ymd, duration)
        if not starts:
            text = f"{day_label}\n\nNo openings inside business hours for that day. Try another day 💕"
            await cq.message.edit_text(text, reply_markup=_build_times_kb(duration, ymd), disable_web_page_preview=True)
            await cq.answer()
            return

        text = f"{day_label}\n\nPick a start time (LA) ⏰"
        await cq.message.edit_text(text, reply_markup=_build_times_kb(duration, ymd), disable_web_page_preview=True)
        await cq.answer()

    # Step 4: Create booking + ask optional note
    @app.on_callback_query(filters.regex(r"^nsfw_book:time:(30|60):\d{8}:\d{4}$"))
    async def nsfw_time(_, cq: CallbackQuery):
        _, _, _, dur_s, ymd, hhmm_compact = cq.data.split(":")
        duration = int(dur_s)
        hhmm = f"{hhmm_compact[0:2]}:{hhmm_compact[2:4]}"

        user = cq.from_user
        user_id = user.id if user else 0
        username = f"@{user.username}" if user and user.username else ""
        display_name = (user.first_name or "").strip() if user else ""

        # Create booking immediately (restart-safe)
        booking_id = uuid.uuid4().hex[:10]
        booking = {
            "booking_id": booking_id,
            "created_ts": time.time(),
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "date": ymd,
            "start_time": hhmm,
            "duration": duration,
            "note": "",
            "status": "awaiting_note",  # will become pending_payment on skip or note
            "tz": TZ,
        }
        add_booking(booking)

        text = (
            "Optional 💬\n"
            "If you’d like, leave a short note about what you’re into or what you’re looking for.\n\n"
            "Or you can skip this."
        )
        await cq.message.edit_text(text, reply_markup=_build_note_kb(booking_id), disable_web_page_preview=True)
        await cq.answer()

    # Step 5a: Add note (one message)
    @app.on_callback_query(filters.regex(r"^nsfw_book:note:[0-9a-f]{10}$"))
    async def nsfw_note_start(_, cq: CallbackQuery):
        booking_id = cq.data.split(":")[2]
        # mark in menu_store so we can capture the next message (restart-safe backup also exists via booking status)
        store.set_menu(f"NSFW_NOTE_PENDING:{cq.from_user.id}", booking_id)

        await cq.message.edit_text(
            "Send your note in <b>one message</b> 💕\n\n"
            "Keep it short and sweet.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Skip", callback_data=f"nsfw_book:skipnote:{booking_id}")]]),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Step 5b: Skip note -> finalize
    @app.on_callback_query(filters.regex(r"^nsfw_book:skipnote:[0-9a-f]{10}$"))
    async def nsfw_skipnote(_, cq: CallbackQuery):
        booking_id = cq.data.split(":")[2]
        store.set_menu(f"NSFW_NOTE_PENDING:{cq.from_user.id}", "")
        update_booking(booking_id, {"status": "pending_payment"})

        await cq.message.edit_text(_final_confirm_text(), disable_web_page_preview=True)
        await cq.answer()

    # Capture the note message (restart-safe: if pending flag missing, we still look for latest awaiting_note)
    @app.on_message(filters.private & filters.text, group=-5)
    async def nsfw_note_capture(_, m: Message):
        if not m.from_user:
            return

        user_id = m.from_user.id
        pending = (store.get_menu(f"NSFW_NOTE_PENDING:{user_id}") or "").strip()

        booking_id = pending
        if not booking_id:
            latest = find_latest_booking_for_user(user_id, statuses=["awaiting_note"])
            if not latest:
                return
            booking_id = latest.get("booking_id") or ""
            if not booking_id:
                return

        note = (m.text or "").strip()
        if not note:
            return

        # limit note length
        if len(note) > 700:
            note = note[:700]

        store.set_menu(f"NSFW_NOTE_PENDING:{user_id}", "")
        update_booking(booking_id, {"note": note, "status": "pending_payment"})

        await m.reply_text(_final_confirm_text(), disable_web_page_preview=True)
