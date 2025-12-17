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

def _avail_key(d: str) -> str:
    return f"NSFW_AVAIL:{d}"

def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default

def _today_la() -> date:
    return datetime.now(TZ_LA).date()

def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def _week_kb(week_start: date) -> InlineKeyboardMarkup:
    days=[week_start+timedelta(days=i) for i in range(7)]
    rows=[]
    for i in range(0, 6, 2):
        rows.append([
            InlineKeyboardButton(days[i].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[i]:%Y-%m-%d}"),
            InlineKeyboardButton(days[i+1].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[i+1]:%Y-%m-%d}"),
        ])
    rows.append([InlineKeyboardButton(days[6].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[6]:%Y-%m-%d}")])
    rows.append([
        InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_book:week:{(week_start-timedelta(days=7)):%Y-%m-%d}"),
        InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_book:week:{(week_start+timedelta(days=7)):%Y-%m-%d}"),
    ])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:open")])
    return InlineKeyboardMarkup(rows)

async def _render_week(cq: CallbackQuery, any_day: date):
    ws=_monday(any_day)
    await cq.message.edit_text(
        "💞 <b>Book a private NSFW texting session</b>\n\nPick a day (LA time):\n"
        f"Week of <b>{ws.strftime('%B %d')}</b> → <b>{(ws+timedelta(days=6)).strftime('%B %d')}</b>",
        reply_markup=_week_kb(ws),
        disable_web_page_preview=True,
    )
    await cq.answer()

def register(app: Client):
    log.info("✅ nsfw_text_session_booking registered (Mon–Sun + aliases)")

    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def open_new(_, cq: CallbackQuery):
        await _render_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^(nsfw_text_session_booking:open|nsfw_text_session:open|book_nsfw:open|booking_nsfw:open)$"))
    async def open_legacy(_, cq: CallbackQuery):
        await _render_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^nsfw_book:week:(\d{4}-\d{2}-\d{2})$"))
    async def week(_, cq: CallbackQuery):
        d=(cq.data or "").split(":")[-1]
        await _render_week(cq, datetime.strptime(d, "%Y-%m-%d").date())

    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(\d{4}-\d{2}-\d{2})$"))
    async def day(_, cq: CallbackQuery):
        d=(cq.data or "").split(":")[-1]
        dt=datetime.strptime(d, "%Y-%m-%d").date()
        raw=store.get_menu(_avail_key(d))
        obj=_jloads(raw, {}) if raw else {}
        blocked=obj.get("blocked", []) if isinstance(obj, dict) else []
        await cq.message.edit_text(
            f"🗓️ <b>{dt.strftime('%A, %B %d')}</b> (LA time)\n\n"
            f"Blocked slots: <b>{len(blocked)}</b>\n"
            "Next step: pick a time (wire your time grid here).",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅ Back to week", callback_data=f"nsfw_book:week:{d}")],
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:open")],
            ]),
            disable_web_page_preview=True,
        )
        await cq.answer()
