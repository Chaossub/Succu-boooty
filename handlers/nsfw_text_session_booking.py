# handlers/nsfw_text_session_booking.py
import time
import uuid
from datetime import datetime, timedelta
from typing import List

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.menu_store import store
from utils.nsfw_store import (
    TZ,
    add_booking,
    find_latest_booking_for_user,
    get_business_hours_for_weekday,
    is_blocked,
    update_booking,
)

RONI_MENU_KEY = "RoniPersonalMenu"


def _tz():
    return pytz.timezone(TZ)


def _la_now() -> datetime:
    return datetime.now(_tz())


def _dt_to_yyyymmdd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _yyyymmdd_to_local_day(yyyymmdd: str) -> datetime:
    tz = _tz()
    return tz.localize(datetime(int(yyyymmdd[0:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]), 0, 0, 0))


def _min_from_hhmm(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm_from_min(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _pretty_date_label(day_dt: datetime) -> str:
    # "Fri Dec 13" (works cross-platform)
    return day_dt.strftime("%a %b %d").replace(" 0", " ")


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


def _build_date_picker_kb(duration: int, week: int) -> InlineKeyboardMarkup:
    """
    Shows 7 actual dates (Fri Dec 13...) so you can go weeks ahead.
    week=0 is current week window starting today.
    """
    tz = _tz()
    base = _la_now().astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    start = base + timedelta(days=week * 7)

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for i in range(7):
        d = (start + timedelta(days=i)).astimezone(tz)
        ymd = _dt_to_yyyymmdd(d)
        label = _pretty_date_label(d)
        row.append(InlineKeyboardButton(label, callback_data=f"nsfw_book:day:{duration}:{ymd}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav: List[InlineKeyboardButton] = []
    if week > 0:
        nav.append(InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_book:daypick:{duration}:{week-1}"))
    nav.append(InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_book:daypick:{duration}:{week+1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:start")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)


def _generate_slots_for_day(ymd: str, duration: int) -> List[str]:
    """
    Returns HH:MM start times (30-min increments) within business hours,
    excluding blocked overlaps.
    """
    tz = _tz()
    day_dt = _yyyymmdd_to_local_day(ymd).astimezone(tz)
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
                [InlineKeyboardButton("⬅ Pick a different date", callback_data=f"nsfw_book:daypick:{duration}:0")],
                [InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")],
            ]
        )

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for hhmm in starts[:30]:  # keep it sane
        cb = f"nsfw_book:time:{duration}:{ymd}:{hhmm.replace(':','')}"
        row.append(InlineKeyboardButton(hhmm, callback_data=cb))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_book:daypick:{duration}:0")])
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

    @app.on_callback_query(filters.regex(r"^nsfw_book:start$"))
    async def nsfw_start(_, cq: CallbackQuery):
        await cq.message.edit_text("Choose your session length 💕", reply_markup=_build_duration_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:dur:(30|60)$"))
    async def nsfw_dur(_, cq: CallbackQuery):
        duration = int(cq.data.split(":")[2])
        text = "Pick a date 📅 (Los Angeles time)"
        await cq.message.edit_text(text, reply_markup=_build_date_picker_kb(duration, week=0), disable_web_page_preview=True)
        await cq.answer()

    # ✅ Date picker with week navigation
    @app.on_callback_query(filters.regex(r"^nsfw_book:daypick:(30|60):\d+$"))
    async def nsfw_daypick(_, cq: CallbackQuery):
        _, _, _, dur_s, week_s = cq.data.split(":")
        duration = int(dur_s)
        week = int(week_s)
        text = "Pick a date 📅 (Los Angeles time)"
        await cq.message.edit_text(text, reply_markup=_build_date_picker_kb(duration, week=week), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(30|60):\d{8}$"))
    async def nsfw_day(_, cq: CallbackQuery):
        _, _, _, dur_s, ymd = cq.data.split(":")
        duration = int(dur_s)

        day_dt = _yyyymmdd_to_local_day(ymd).astimezone(_tz())
        day_label = day_dt.strftime("%A, %b %d").replace(" 0", " ")

        starts = _generate_slots_for_day(ymd, duration)
        if not starts:
            text = f"{day_label}\n\nNo openings inside business hours for that date. Try another date 💕"
            await cq.message.edit_text(text, reply_markup=_build_times_kb(duration, ymd), disable_web_page_preview=True)
            await cq.answer()
            return

        text = f"{day_label}\n\nPick a start time (LA) ⏰"
        await cq.message.edit_text(text, reply_markup=_build_times_kb(duration, ymd), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:time:(30|60):\d{8}:\d{4}$"))
    async def nsfw_time(_, cq: CallbackQuery):
        _, _, _, dur_s, ymd, hhmm_compact = cq.data.split(":")
        duration = int(dur_s)
        hhmm = f"{hhmm_compact[0:2]}:{hhmm_compact[2:4]}"

        user = cq.from_user
        user_id = user.id if user else 0
        username = f"@{user.username}" if user and user.username else ""
        display_name = (user.first_name or "").strip() if user else ""

        booking_id = uuid.uuid4().hex[:10]
        add_booking(
            {
                "booking_id": booking_id,
                "created_ts": time.time(),
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "date": ymd,
                "start_time": hhmm,
                "duration": duration,
                "note": "",
                "status": "awaiting_note",
                "tz": TZ,
            }
        )

        text = (
            "Optional 💬\n"
            "If you’d like, leave a short note about what you’re into or what you’re looking for.\n\n"
            "Or you can skip this."
        )
        await cq.message.edit_text(text, reply_markup=_build_note_kb(booking_id), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:note:[0-9a-f]{10}$"))
    async def nsfw_note_start(_, cq: CallbackQuery):
        booking_id = cq.data.split(":")[2]
        store.set_menu(f"NSFW_NOTE_PENDING:{cq.from_user.id}", booking_id)

        await cq.message.edit_text(
            "Send your note in <b>one message</b> 💕\n\nKeep it short and sweet.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Skip", callback_data=f"nsfw_book:skipnote:{booking_id}")]]),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:skipnote:[0-9a-f]{10}$"))
    async def nsfw_skipnote(_, cq: CallbackQuery):
        booking_id = cq.data.split(":")[2]
        store.set_menu(f"NSFW_NOTE_PENDING:{cq.from_user.id}", "")
        update_booking(booking_id, {"status": "pending_payment"})
        await cq.message.edit_text(_final_confirm_text(), disable_web_page_preview=True)
        await cq.answer()

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
            booking_id = (latest.get("booking_id") or "").strip()
            if not booking_id:
                return

        note = (m.text or "").strip()
        if not note:
            return

        if len(note) > 700:
            note = note[:700]

        store.set_menu(f"NSFW_NOTE_PENDING:{user_id}", "")
        update_booking(booking_id, {"note": note, "status": "pending_payment"})
        await m.reply_text(_final_confirm_text(), disable_web_page_preview=True)
