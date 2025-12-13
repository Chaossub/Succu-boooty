import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

DATA_PATH = "data/nsfw_bookings.json"
ADMIN_ID = int(os.getenv("OWNER_ID", "6964994611"))

LA_TZ = ZoneInfo("America/Los_Angeles")
TZ_LABEL = "LA time"

# Business hours (LA)
# weekday(): Mon=0 ... Sun=6
BUSINESS_HOURS = {
    0: ("09:00", "22:00"),  # Mon
    1: ("09:00", "22:00"),  # Tue
    2: ("09:00", "22:00"),  # Wed
    3: ("09:00", "22:00"),  # Thu
    4: ("09:00", "22:00"),  # Fri
    5: ("09:00", "21:00"),  # Sat
    6: ("09:00", "22:00"),  # Sun
}

DURATIONS = {"30": 30, "60": 60}

# Time-of-day buckets (start hour inclusive, end hour exclusive)
PERIODS = {
    "morning": ("🌤 Morning", 9, 12),     # 9:00–11:59
    "afternoon": ("🌞 Afternoon", 12, 17),# 12:00–4:59
    "evening": ("🌙 Evening", 17, 24),    # 5:00–11:59 (but business hours cap it)
    "all": ("🗓 All times", 0, 24),
}

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
    return d.strftime("%a %b %d").replace(" 0", " ")

def _fmt_full_date(d: datetime) -> str:
    return d.strftime("%A, %B %d").replace(" 0", " ")

def _fmt_booking(date_str: str, tm_label: str, dur_label: str) -> str:
    return f"📅 {date_str}\n⏰ {tm_label} ({TZ_LABEL})\n⏱ {dur_label}"

def _dur_label(dur_key: str) -> str:
    return "30 minutes" if dur_key == "30" else "1 hour"

def _fmt_time_label(hhmm: str) -> str:
    dt = datetime(2000, 1, 1, int(hhmm[:2]), int(hhmm[2:]), tzinfo=LA_TZ)
    return dt.strftime("%-I:%M %p") if os.name != "nt" else dt.strftime("%I:%M %p").lstrip("0")

def _hours_for_date(date_iso: str) -> Tuple[str, str]:
    d = datetime.fromisoformat(date_iso).replace(tzinfo=LA_TZ)
    start, end = BUSINESS_HOURS[d.weekday()]
    return start, end

def _generate_slots(date_iso: str, dur_minutes: int) -> List[str]:
    """
    Return list of HHMM strings for start times every 30 minutes within business hours.
    Last start time = close - duration.
    """
    start_str, end_str = _hours_for_date(date_iso)
    base = datetime.fromisoformat(date_iso).replace(tzinfo=LA_TZ)

    start_dt = base.replace(hour=int(start_str[:2]), minute=int(start_str[3:]), second=0, microsecond=0)
    end_dt = base.replace(hour=int(end_str[:2]), minute=int(end_str[3:]), second=0, microsecond=0)

    last_start = end_dt - timedelta(minutes=dur_minutes)
    slots = []

    cur = start_dt
    while cur <= last_start:
        slots.append(cur.strftime("%H%M"))
        cur += timedelta(minutes=30)

    return slots

def _filter_slots_by_period(slots: List[str], period_key: str) -> List[str]:
    _, start_h, end_h = PERIODS.get(period_key, PERIODS["all"])
    out = []
    for hhmm in slots:
        h = int(hhmm[:2])
        if start_h <= h < end_h:
            out.append(hhmm)
    return out

def _back_to_assistant_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]])

# ────────────── UI Builders ──────────────

def _date_grid_kb(week_offset: int) -> InlineKeyboardMarkup:
    start = _now_la().date() + timedelta(days=week_offset * 7)
    days = [start + timedelta(days=i) for i in range(7)]

    rows = []
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

def _duration_kb(date_iso: str, week_offset: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("30 minutes", callback_data=f"nsfw:book:dur:{date_iso}:{week_offset}:30"),
                InlineKeyboardButton("1 hour", callback_data=f"nsfw:book:dur:{date_iso}:{week_offset}:60"),
            ],
            [InlineKeyboardButton("📅 Pick another date", callback_data=f"nsfw:book:datepage:{week_offset}")],
            [InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:open"), InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")],
        ]
    )

def _period_kb(date_iso: str, week_offset: int, dur_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(PERIODS["morning"][0], callback_data=f"nsfw:book:period:{date_iso}:{week_offset}:{dur_key}:morning"),
                InlineKeyboardButton(PERIODS["afternoon"][0], callback_data=f"nsfw:book:period:{date_iso}:{week_offset}:{dur_key}:afternoon"),
            ],
            [
                InlineKeyboardButton(PERIODS["evening"][0], callback_data=f"nsfw:book:period:{date_iso}:{week_offset}:{dur_key}:evening"),
                InlineKeyboardButton(PERIODS["all"][0], callback_data=f"nsfw:book:period:{date_iso}:{week_offset}:{dur_key}:all"),
            ],
            [InlineKeyboardButton("⏱ Change duration", callback_data=f"nsfw:book:pickdate:{date_iso}:{week_offset}")],
            [InlineKeyboardButton("📅 Pick another date", callback_data=f"nsfw:book:datepage:{week_offset}")],
            [InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:open"), InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")],
        ]
    )

def _time_picker_kb(date_iso: str, week_offset: int, dur_key: str, period_key: str) -> InlineKeyboardMarkup:
    dur_minutes = DURATIONS[dur_key]
    slots = _generate_slots(date_iso, dur_minutes)
    slots = _filter_slots_by_period(slots, period_key)

    # If a bucket ends up empty (rare edge cases), fall back to all
    if not slots and period_key != "all":
        slots = _filter_slots_by_period(_generate_slots(date_iso, dur_minutes), "all")
        period_key = "all"

    rows = []
    for i in range(0, len(slots), 2):
        b1 = InlineKeyboardButton(
            _fmt_time_label(slots[i]),
            callback_data=f"nsfw:book:time:{date_iso}:{week_offset}:{dur_key}:{slots[i]}"
        )
        row = [b1]
        if i + 1 < len(slots):
            b2 = InlineKeyboardButton(
                _fmt_time_label(slots[i+1]),
                callback_data=f"nsfw:book:time:{date_iso}:{week_offset}:{dur_key}:{slots[i+1]}"
            )
            row.append(b2)
        rows.append(row)

    rows.append([InlineKeyboardButton("🕒 Change time of day", callback_data=f"nsfw:book:dur:{date_iso}:{week_offset}:{dur_key}")])
    rows.append([InlineKeyboardButton("⏱ Change duration", callback_data=f"nsfw:book:pickdate:{date_iso}:{week_offset}")])
    rows.append([InlineKeyboardButton("📅 Pick another date", callback_data=f"nsfw:book:datepage:{week_offset}")])
    rows.append([InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:open"), InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)

# ────────────── Register ──────────────

def register(app: Client):

    @app.on_callback_query(filters.regex(r"^(nsfw_book:open|nsfw:book:start)$"))
    async def start_booking(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "📩 <b>Book a private NSFW texting session</b>\n\n"
            "Prices are listed in 📖 Roni’s Menu.\n"
            "🚫 <b>No meetups</b> — this is online/texting only.\n\n"
            f"Tap below to choose a date ({TZ_LABEL}).",
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

    @app.on_callback_query(filters.regex(r"^nsfw:book:pickdate:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def pick_date(_, cq: CallbackQuery):
        date_iso = cq.matches[0].group(1)
        week_offset = int(cq.matches[0].group(2))

        d = datetime.fromisoformat(date_iso).replace(tzinfo=LA_TZ)
        pretty = _fmt_full_date(d)

        start_str, end_str = _hours_for_date(date_iso)
        hours_line = f"Business hours: {start_str}–{end_str} ({TZ_LABEL})"

        await cq.message.edit_text(
            f"🗓 <b>{pretty}</b>\n{hours_line}\n\nChoose a session length:",
            reply_markup=_duration_kb(date_iso, week_offset),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Duration selected -> pick time of day
    @app.on_callback_query(filters.regex(r"^nsfw:book:dur:(\d{4}-\d{2}-\d{2}):(\d+):(30|60)$"))
    async def pick_duration(_, cq: CallbackQuery):
        date_iso = cq.matches[0].group(1)
        week_offset = int(cq.matches[0].group(2))
        dur_key = cq.matches[0].group(3)

        d = datetime.fromisoformat(date_iso).replace(tzinfo=LA_TZ)
        pretty = _fmt_full_date(d)

        await cq.message.edit_text(
            f"🗓 <b>{pretty}</b>\n\n"
            f"Session length: <b>{_dur_label(dur_key)}</b>\n\n"
            "What time of day works best?",
            reply_markup=_period_kb(date_iso, week_offset, dur_key),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Period chosen -> show times in that bucket
    @app.on_callback_query(filters.regex(r"^nsfw:book:period:(\d{4}-\d{2}-\d{2}):(\d+):(30|60):(morning|afternoon|evening|all)$"))
    async def pick_period(_, cq: CallbackQuery):
        date_iso = cq.matches[0].group(1)
        week_offset = int(cq.matches[0].group(2))
        dur_key = cq.matches[0].group(3)
        period_key = cq.matches[0].group(4)

        d = datetime.fromisoformat(date_iso).replace(tzinfo=LA_TZ)
        pretty = _fmt_full_date(d)
        period_label = PERIODS[period_key][0]

        await cq.message.edit_text(
            f"🗓 <b>{pretty}</b>\n\n"
            f"{period_label} • {_dur_label(dur_key)}\n\n"
            f"Choose a start time ({TZ_LABEL}):",
            reply_markup=_time_picker_kb(date_iso, week_offset, dur_key, period_key),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw:book:time:(\d{4}-\d{2}-\d{2}):(\d+):(30|60):(\d{4})$"))
    async def pick_time(_, cq: CallbackQuery):
        date_iso = cq.matches[0].group(1)
        week_offset = int(cq.matches[0].group(2))
        dur_key = cq.matches[0].group(3)
        hhmm = cq.matches[0].group(4)

        d = datetime.fromisoformat(date_iso).replace(tzinfo=LA_TZ)
        date_str = _fmt_full_date(d)
        time_label = _fmt_time_label(hhmm)
        dur_label = _dur_label(dur_key)

        booking_id = str(uuid.uuid4())

        BOOKINGS[booking_id] = {
            "id": booking_id,
            "user_id": cq.from_user.id,
            "username": cq.from_user.username,
            "name": cq.from_user.first_name,
            "date_iso": date_iso,
            "date": date_str,
            "time_hhmm": hhmm,
            "time": time_label,
            "duration_min": DURATIONS[dur_key],
            "duration": dur_label,
            "status": "pending",
            "created": datetime.utcnow().isoformat(),
        }
        _save(BOOKINGS)

        await app.send_message(
            ADMIN_ID,
            (
                "💗 <b>New NSFW texting session request</b>\n\n"
                f"👤 {BOOKINGS[booking_id]['name']} (@{BOOKINGS[booking_id]['username'] or 'no_username'})\n"
                f"{_fmt_booking(date_str, time_label, dur_label)}"
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

        await cq.message.edit_text(
            (
                "💗 <b>Request sent</b>\n\n"
                f"{_fmt_booking(date_str, time_label, dur_label)}\n\n"
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
                f"{_fmt_booking(booking['date'], booking['time'], booking['duration'])}\n\n"
                "Roni will reach out to you for payment :)\n\n"
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
