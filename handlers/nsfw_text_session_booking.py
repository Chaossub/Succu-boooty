# handlers/nsfw_text_session_booking.py
import time
import uuid
from datetime import datetime, timedelta
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

def _tz():
    return pytz.timezone(TZ)

def _now():
    return datetime.now(_tz())

def _dt_to_ymd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")

def _ymd_to_dt(ymd: str) -> datetime:
    return _tz().localize(datetime(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:])))

def _pretty_date(dt: datetime) -> str:
    return dt.strftime("%a %b %d").replace(" 0", " ")

def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)

def _hhmm(m: int) -> str:
    return f"{m//60:02d}:{m%60:02d}"

def _intro_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 View Roni’s Menu", callback_data="roni_portal:menu:src=nsfw")],
        [InlineKeyboardButton("➡️ Continue Booking", callback_data="nsfw_book:start")],
        [InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")],
    ])

def _duration_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏱ 30 minutes", callback_data="nsfw_book:dur:30")],
        [InlineKeyboardButton("🕰 1 hour", callback_data="nsfw_book:dur:60")],
        [InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:open")],
    ])

def _date_picker(duration: int, week: int):
    base = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = base + timedelta(days=week * 7)

    rows, row = [], []
    for i in range(7):
        d = start + timedelta(days=i)
        ymd = _dt_to_ymd(d)
        row.append(InlineKeyboardButton(
            _pretty_date(d),
            callback_data=f"nsfw_book:day:{duration}:{ymd}"
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    if week > 0:
        nav.append(InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_book:daypick:{duration}:{week-1}"))
    nav.append(InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_book:daypick:{duration}:{week+1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:start")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)

def _slots(ymd: str, duration: int):
    day = _ymd_to_dt(ymd)
    open_h, close_h = get_business_hours_for_weekday(day.weekday())

    start = _min(open_h)
    end = _min(close_h) - duration

    out = []
    m = start
    while m <= end:
        s = _hhmm(m)
        e = _hhmm(m + duration)
        if not is_blocked(ymd, s, e):
            out.append(s)
        m += 30
    return out

def _times_kb(duration: int, ymd: str):
    starts = _slots(ymd, duration)
    if not starts:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅ Pick another date", callback_data=f"nsfw_book:daypick:{duration}:0")],
            [InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")],
        ])

    rows, row = [], []
    for s in starts:
        row.append(InlineKeyboardButton(
            s,
            callback_data=f"nsfw_book:time:{duration}:{ymd}:{s.replace(':','')}"
        ))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_book:daypick:{duration}:0")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)

def _final():
    return (
        "Your session is booked 💞\n"
        "Roni will reach out to you for payment :)\n\n"
        "You can find current prices in 📖 Roni’s Menu."
    )

def register(app: Client):

    @app.on_callback_query(filters.regex("^nsfw_book:open$"))
    async def open(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "💞 <b>Before booking</b>\n"
            "Please check 📖 Roni’s Menu for pricing.\n\n"
            "<b>Texting only — NO meetups.</b>",
            reply_markup=_intro_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^nsfw_book:start$"))
    async def start(_, cq: CallbackQuery):
        await cq.message.edit_text("Choose session length 💕", reply_markup=_duration_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex("^nsfw_book:dur:(30|60)$"))
    async def dur(_, cq: CallbackQuery):
        duration = int(cq.data.split(":")[2])
        await cq.message.edit_text(
            "Pick a date 📅 (Los Angeles time)",
            reply_markup=_date_picker(duration, 0)
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^nsfw_book:daypick:(30|60):\d+$"))
    async def daypick(_, cq: CallbackQuery):
        _, _, dur_s, week_s = cq.data.split(":")
        await cq.message.edit_text(
            "Pick a date 📅 (Los Angeles time)",
            reply_markup=_date_picker(int(dur_s), int(week_s))
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^nsfw_book:day:(30|60):\d{8}$"))
    async def day(_, cq: CallbackQuery):
        _, _, dur_s, ymd = cq.data.split(":")
        await cq.message.edit_text(
            "Pick a time ⏰",
            reply_markup=_times_kb(int(dur_s), ymd)
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^nsfw_book:time:(30|60):\d{8}:\d{4}$"))
    async def timepick(_, cq: CallbackQuery):
        _, _, dur_s, ymd, hhmm = cq.data.split(":")
        hhmm = f"{hhmm[:2]}:{hhmm[2:]}"
        booking_id = uuid.uuid4().hex[:10]

        add_booking({
            "booking_id": booking_id,
            "user_id": cq.from_user.id,
            "date": ymd,
            "start_time": hhmm,
            "duration": int(dur_s),
            "note": "",
            "status": "pending_payment",
            "tz": TZ,
            "created_ts": time.time(),
        })

        await cq.message.edit_text(_final())
        await cq.answer()
