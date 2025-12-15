# handlers/nsfw_availability.py
import json
import logging
from datetime import datetime, timedelta, date
import pytz

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.menu_store import store

log = logging.getLogger(__name__)
RONI_OWNER_ID = 6964994611
TZ_LA = pytz.timezone("America/Los_Angeles")

def _key(d: str) -> str:
    return f"NSFW_AVAIL:{d}"

def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default

def _jdumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)

def _today_la() -> date:
    return datetime.now(TZ_LA).date()

def _ensure_day(d: str) -> dict:
    raw = store.get_menu(_key(d))
    obj = _jloads(raw, None) if raw else None
    if not isinstance(obj, dict):
        obj = {"date": d, "slot_minutes": 30, "start": "09:00", "end": "21:30", "blocked": []}
    obj.setdefault("date", d)
    obj.setdefault("slot_minutes", 30)
    obj.setdefault("start", "09:00")
    obj.setdefault("end", "21:30")
    obj.setdefault("blocked", [])
    if not isinstance(obj["blocked"], list):
        obj["blocked"] = []
    return obj

def _save_day(obj: dict) -> None:
    store.set_menu(_key(obj["date"]), _jdumps(obj))

def _week_kb(week_start: date) -> InlineKeyboardMarkup:
    rows=[]
    for i in range(0, 7, 2):
        d1 = week_start + timedelta(days=i)
        d2 = week_start + timedelta(days=i+1)
        rows.append([
            InlineKeyboardButton(d1.strftime("%a %b %d"), callback_data=f"nsfw_av:day:{d1:%Y-%m-%d}"),
            InlineKeyboardButton(d2.strftime("%a %b %d"), callback_data=f"nsfw_av:day:{d2:%Y-%m-%d}"),
        ])
    rows.append([
        InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_av:week:{(week_start-timedelta(days=7)):%Y-%m-%d}"),
        InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_av:week:{(week_start+timedelta(days=7)):%Y-%m-%d}"),
    ])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")])
    return InlineKeyboardMarkup(rows)

def register(app: Client):
    log.info("✅ nsfw_availability handler registered")

    @app.on_callback_query(filters.regex(r"^nsfw_av:open$"))
    async def av_open(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        ws = _today_la()
        await cq.message.edit_text(
            "🗓️ <b>NSFW Availability</b> (LA time)\n\nPick a day:",
            reply_markup=_week_kb(ws),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_av:week:(\d{4}-\d{2}-\d{2})$"))
    async def av_week(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        d = (cq.data or "").split(":")[-1]
        ws = datetime.strptime(d, "%Y-%m-%d").date()
        await cq.message.edit_text(
            "🗓️ <b>NSFW Availability</b> (LA time)\n\nPick a day:",
            reply_markup=_week_kb(ws),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_av:day:(\d{4}-\d{2}-\d{2})$"))
    async def av_day(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        d = (cq.data or "").split(":")[-1]
        obj = _ensure_day(d)
        _save_day(obj)  # ensure stored
        dt = datetime.strptime(d, "%Y-%m-%d").date()
        await cq.message.edit_text(
            f"🗓️ <b>{dt.strftime('%A, %B %d')}</b> (LA time)\n\n(Buttons for times are in your existing build; this confirms handler is firing.)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to days", callback_data=f"nsfw_av:week:{d}")]]),
            disable_web_page_preview=True,
        )
        await cq.answer()
