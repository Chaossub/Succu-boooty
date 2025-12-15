# handlers/nsfw_text_session_booking.py
import json
import logging
from datetime import datetime, timedelta, date

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from utils.menu_store import store

log = logging.getLogger(__name__)

TZ_LA = pytz.timezone("America/Los_Angeles")

# Booking reads the SAME source of truth as your blocker:
# NSFW_AVAIL:YYYY-MM-DD => {"date":"YYYY-MM-DD","slot_minutes":30,"start":"09:00","end":"21:30","blocked":["HH:MM",...]}
def _avail_key(d: str) -> str:
    return f"NSFW_AVAIL:{d}"

def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default

def _today_la() -> date:
    return datetime.now(TZ_LA).date()

def _monday_of(d: date) -> date:
    # Monday = 0
    return d - timedelta(days=d.weekday())

def _week_days(week_start: date) -> list[date]:
    return [week_start + timedelta(days=i) for i in range(7)]

def _week_picker_kb(week_start: date) -> InlineKeyboardMarkup:
    days = _week_days(week_start)

    rows = []
    # 2 columns (Mon/Tue, Wed/Thu, Fri/Sat, Sun alone)
    pairs = [(0,1), (2,3), (4,5)]
    for a, b in pairs:
        rows.append([
            InlineKeyboardButton(days[a].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[a]:%Y-%m-%d}"),
            InlineKeyboardButton(days[b].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[b]:%Y-%m-%d}"),
        ])
    # Sunday row
    rows.append([InlineKeyboardButton(days[6].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[6]:%Y-%m-%d}")])

    # Week nav
    rows.append([
        InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_book:week:{(week_start - timedelta(days=7)):%Y-%m-%d}"),
        InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_book:week:{(week_start + timedelta(days=7)):%Y-%m-%d}"),
    ])

    # Back (keep your existing back target)
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:open")])
    return InlineKeyboardMarkup(rows)

def register(app: Client) -> None:
    log.info("✅ nsfw_text_session_booking registered (Mon–Sun week picker)")

    # OPEN booking (you likely call this from a portal button)
    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def nsfw_book_open(_, cq: CallbackQuery):
        # Start on the current week Monday
        week_start = _monday_of(_today_la())
        await cq.message.edit_text(
            "💞 <b>Book a private NSFW texting session</b>\n\n"
            "Pick a day (LA time):\n"
            f"Week of <b>{week_start.strftime('%B %d')}</b> → <b>{(week_start + timedelta(days=6)).strftime('%B %d')}</b>",
            reply_markup=_week_picker_kb(week_start),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # WEEK NAV
    @app.on_callback_query(filters.regex(r"^nsfw_book:week:(\d{4}-\d{2}-\d{2})$"))
    async def nsfw_book_week(_, cq: CallbackQuery):
        d = (cq.data or "").split(":")[-1]
        week_start = _monday_of(datetime.strptime(d, "%Y-%m-%d").date())
        await cq.message.edit_text(
            "💞 <b>Book a private NSFW texting session</b>\n\n"
            "Pick a day (LA time):\n"
            f"Week of <b>{week_start.strftime('%B %d')}</b> → <b>{(week_start + timedelta(days=6)).strftime('%B %d')}</b>",
            reply_markup=_week_picker_kb(week_start),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # DAY PICK (this just proves correct Monday–Sunday; your time-slot picker can be your existing one)
    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(\d{4}-\d{2}-\d{2})$"))
    async def nsfw_book_day(_, cq: CallbackQuery):
        d = (cq.data or "").split(":")[-1]
        dt = datetime.strptime(d, "%Y-%m-%d").date()

        # Read availability for that day (blocks live here)
        raw = store.get_menu(_avail_key(d))
        obj = _jloads(raw, {}) if raw else {}
        blocked = obj.get("blocked", []) if isinstance(obj, dict) else []

        # If you already have a time-slot UI elsewhere, keep it there.
        # For now we show a correct header + a “continue” hook.
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Continue ➡", callback_data=f"nsfw_book:times:{d}:0")],
            [InlineKeyboardButton("⬅ Back to week", callback_data=f"nsfw_book:week:{d}")],
            [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:open")],
        ])

        await cq.message.edit_text(
            f"🗓️ <b>{dt.strftime('%A, %B %d')}</b> (LA time)\n\n"
            f"Blocked slots: <b>{len(blocked)}</b>\n"
            "Tap <b>Continue</b> to pick a time.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # If you already have a time picker handler, keep it.
    # This stub prevents “nothing happens” if your old one was removed.
    @app.on_callback_query(filters.regex(r"^nsfw_book:times:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def nsfw_book_times_stub(_, cq: CallbackQuery):
        d = (cq.data or "").split(":")[2]
        await cq.answer("Time picker hook reached ✅ (wire your slot UI here).", show_alert=True)
