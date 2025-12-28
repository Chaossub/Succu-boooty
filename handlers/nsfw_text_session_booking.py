# handlers/nsfw_text_session_booking.py
import os
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional

import pytz
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger(__name__)

LA_TZ = pytz.timezone("America/Los_Angeles")

# Time window (LA time)
OPEN_HOUR = int(os.getenv("NSFW_OPEN_HOUR", "9"))
CLOSE_HOUR = int(os.getenv("NSFW_CLOSE_HOUR", "22"))
SLOT_MINUTES = 30
SLOTS_PER_PAGE = 16

# Mongo
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "Succubot")
NSFW_AVAIL_COLL = os.getenv("NSFW_AVAIL_COLL", "nsfw_availability")
NSFW_BOOKINGS_COLL = os.getenv("NSFW_BOOKINGS_COLL", "nsfw_bookings")

mongo = None
avail_coll = None
bookings_coll = None
if MONGO_URI:
    try:
        mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        db = mongo[MONGO_DBNAME]
        avail_coll = db[NSFW_AVAIL_COLL]
        bookings_coll = db[NSFW_BOOKINGS_COLL]
        # quick ping
        mongo.admin.command("ping")
        log.info("✅ nsfw_text_session_booking: Mongo OK db=%s avail=%s bookings=%s", MONGO_DBNAME, NSFW_AVAIL_COLL, NSFW_BOOKINGS_COLL)
    except Exception:
        log.exception("nsfw_text_session_booking: Mongo init failed (booking will still render UI but won't persist bookings)")
        mongo = None
        avail_coll = None
        bookings_coll = None

# Callback prefixes
CB_OPEN = "nsfw_book:open"
CB_WEEK = "nsfw_book:week"        # nsfw_book:week:YYYY-MM-DD
CB_DAY  = "nsfw_book:day"         # nsfw_book:day:YYYY-MM-DD
CB_PAGE = "nsfw_book:page"        # nsfw_book:page:YYYY-MM-DD:<page>
CB_TIME = "nsfw_book:time"        # nsfw_book:time:YYYY-MM-DD:HH:MM
CB_BACK = "nsfw_book:back"        # nsfw_book:back (to week)
CB_HOME = "roni_portal:home"      # defined in roni_portal.py

def _today_la() -> date:
    return datetime.now(LA_TZ).date()

def _day_key(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def _parse_day_key(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def _format_day_label(d: date) -> str:
    return d.strftime("%a %b %d")

def _format_day_title(d: date) -> str:
    # e.g., Saturday, December 20 (LA time)
    return d.strftime("%A, %B %d")

def _slot_keys_for_day() -> List[str]:
    out = []
    for h in range(OPEN_HOUR, CLOSE_HOUR):
        out.append(f"{h:02d}:00")
        out.append(f"{h:02d}:30")
    return out

def _get_blocked_map(day_key: str) -> Dict[str, bool]:
    """
    Returns blocked dict like {"17:00": True, ...} for the given day.
    """
    if not avail_coll:
        return {}
    doc = avail_coll.find_one({"day": day_key}) or {}
    blocked = doc.get("blocked") or {}
    # normalize to str->bool
    out: Dict[str, bool] = {}
    for k, v in blocked.items():
        if isinstance(k, str):
            out[k] = bool(v)
    return out

def _available_slots(day_key: str) -> List[str]:
    slots = _slot_keys_for_day()
    blocked = _get_blocked_map(day_key)
    return [s for s in slots if not blocked.get(s, False)]

def _week_start(d: date) -> date:
    # 7-day rolling window starting at d (not ISO week)
    return d

def _week_days(start: date) -> List[date]:
    return [start + timedelta(days=i) for i in range(7)]

def _week_keyboard(start: date) -> InlineKeyboardMarkup:
    days = _week_days(start)
    buttons: List[List[InlineKeyboardButton]] = []
    for d in days:
        buttons.append([InlineKeyboardButton(_format_day_label(d), callback_data=f"{CB_DAY}:{_day_key(d)}")])

    nav = [
        InlineKeyboardButton("Next ➡️", callback_data=f"{CB_WEEK}:{_day_key(start + timedelta(days=7))}")
    ]
    # allow going back only if it won't include past days
    prev_start = start - timedelta(days=7)
    if prev_start >= _today_la():
        nav.insert(0, InlineKeyboardButton("⬅️ Earlier", callback_data=f"{CB_WEEK}:{_day_key(prev_start)}"))

    buttons.append(nav)
    buttons.append([InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data=CB_HOME)])
    return InlineKeyboardMarkup(buttons)

def _times_keyboard(day_key: str, page: int = 0) -> InlineKeyboardMarkup:
    slots = _available_slots(day_key)
    total = len(slots)
    start_i = page * SLOTS_PER_PAGE
    end_i = start_i + SLOTS_PER_PAGE
    page_slots = slots[start_i:end_i]

    rows: List[List[InlineKeyboardButton]] = []
    # 2 columns
    for i in range(0, len(page_slots), 2):
        row = []
        for s in page_slots[i:i+2]:
            # pretty label
            dt = datetime.strptime(s, "%H:%M")
            label = dt.strftime("%-I:%M %p") if os.name != "nt" else dt.strftime("%I:%M %p").lstrip("0")
            row.append(InlineKeyboardButton(f"🕒 {label}", callback_data=f"{CB_TIME}:{day_key}:{s}"))
        rows.append(row)

    nav_row: List[InlineKeyboardButton] = []
    if end_i < total:
        nav_row.append(InlineKeyboardButton("More ➡️", callback_data=f"{CB_PAGE}:{day_key}:{page+1}"))
    if page > 0:
        nav_row.insert(0, InlineKeyboardButton("⬅️ Earlier", callback_data=f"{CB_PAGE}:{day_key}:{page-1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton("⬅️ Back to week", callback_data=CB_BACK)])
    rows.append([InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data=CB_HOME)])
    return InlineKeyboardMarkup(rows)

async def _show_week(cq: CallbackQuery, start: date):
    # Never show past days
    if start < _today_la():
        start = _today_la()
    text = (
        "💞 <b>Book a private NSFW texting session</b>\n\n"
        f"Pick a day (LA time):\n"
        f"<b>{_format_day_label(start)}</b> — <b>{_format_day_label(start + timedelta(days=6))}</b>"
    )
    await cq.message.edit_text(text, reply_markup=_week_keyboard(start))

async def _show_day(cq: CallbackQuery, day_key: str, page: int = 0):
    d = _parse_day_key(day_key)
    # safety: don't allow picking past
    if d < _today_la():
        return await _show_week(cq, _today_la())

    slots = _available_slots(day_key)
    open_str = f"{OPEN_HOUR:02d}:00"
    close_str = f"{CLOSE_HOUR:02d}:00"
    text = (
        f"🗓️ <b>{_format_day_title(d)} (LA time)</b>\n"
        f"Open: <b>{open_str}</b> · Close: <b>{close_str}</b>\n\n"
        f"Available start times: <b>{len(slots)}</b>\n"
        f"Pick a start time:"
    )
    await cq.message.edit_text(text, reply_markup=_times_keyboard(day_key, page=page))

async def _confirm_booking(app: Client, cq: CallbackQuery, day_key: str, slot_key: str):
    d = _parse_day_key(day_key)
    dt = datetime.strptime(slot_key, "%H:%M")
    pretty = dt.strftime("%-I:%M %p") if os.name != "nt" else dt.strftime("%I:%M %p").lstrip("0")

    # Persist booking (optional)
    if bookings_coll:
        try:
            bookings_coll.insert_one({
                "user_id": cq.from_user.id,
                "username": cq.from_user.username,
                "name": (cq.from_user.first_name or "") + (" " + cq.from_user.last_name if cq.from_user.last_name else ""),
                "day": day_key,
                "time": slot_key,
                "created_at": datetime.utcnow(),
            })
        except Exception:
            log.exception("Failed to persist booking")

    # Confirm to user
    await cq.answer("Booked! ✅", show_alert=False)
    await cq.message.edit_text(
        f"✅ <b>Request received!</b>\n\n"
        f"Day: <b>{_format_day_title(d)}</b> (LA time)\n"
        f"Start time: <b>{pretty}</b>\n\n"
        f"Roni will confirm in DMs if anything needs adjusting. 💕",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data=CB_HOME)]
        ])
    )

def register(app: Client):
    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def _open(cq: CallbackQuery):
        await _show_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^nsfw_book:week:"))
    async def _week(cq: CallbackQuery):
        try:
            start_key = cq.data.split(":", 2)[2]
            start = _parse_day_key(start_key)
        except Exception:
            start = _today_la()
        await _show_week(cq, start)

    @app.on_callback_query(filters.regex(r"^nsfw_book:day:"))
    async def _day(cq: CallbackQuery):
        day_key = cq.data.split(":", 2)[2]
        await _show_day(cq, day_key, page=0)

    @app.on_callback_query(filters.regex(r"^nsfw_book:page:"))
    async def _page(cq: CallbackQuery):
        # nsfw_book:page:YYYY-MM-DD:<page>
        try:
            _, _, rest = cq.data.split(":", 2)
            day_key, page_s = rest.split(":")
            page = int(page_s)
        except Exception:
            return await cq.answer("Something went wrong.", show_alert=True)
        await _show_day(cq, day_key, page=page)

    @app.on_callback_query(filters.regex(r"^nsfw_book:back$"))
    async def _back(cq: CallbackQuery):
        await _show_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^nsfw_book:time:"))
    async def _time(cq: CallbackQuery):
        # nsfw_book:time:YYYY-MM-DD:HH:MM
        try:
            _, _, rest = cq.data.split(":", 2)
            day_key, slot_key = rest.split(":")
        except Exception:
            return await cq.answer("Bad selection.", show_alert=True)

        # Respect blocks (re-check before accepting)
        if _get_blocked_map(day_key).get(slot_key, False):
            return await cq.answer("That time is blocked. Pick another.", show_alert=True)

        await _confirm_booking(app, cq, day_key, slot_key)

    log.info("✅ handlers.nsfw_text_session_booking registered (callbacks nsfw_book:...)")
