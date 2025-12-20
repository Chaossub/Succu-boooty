
# handlers/nsfw_text_session_booking.py
"""
NSFW Text Session Booking (User-facing)

- Shows rolling 7-day date picker (LA time) starting TODAY.
- For chosen day, shows available start times as 30-min buttons
  and REMOVES blocked slots from availability.
- "Back to Roni Assistant" always returns to Roni assistant home panel.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.menu_store import store

log = logging.getLogger(__name__)

OWNER_ID = int(__import__("os").environ.get("OWNER_ID", __import__("os").environ.get("BOT_OWNER_ID", "6964994611")))
LA_TZ = pytz.timezone("America/Los_Angeles")

DEFAULT_OPEN = "09:00"
DEFAULT_CLOSE = "22:00"
SLOT_MINUTES = 30
SLOTS_PER_PAGE = 24


def _today_la() -> date:
    return datetime.now(LA_TZ).date()


def _dstr(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _avail_key(owner_id: int, d: date) -> str:
    return f"NSFW_AVAIL:{owner_id}:{_dstr(d)}"


def _jget(key: str, default):
    try:
        raw = store.get_menu(key)
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default


def _parse_hhmm(s: str) -> datetime:
    return datetime.strptime(s, "%H:%M")


def _iter_slots(open_hhmm: str, close_hhmm: str) -> List[str]:
    o = _parse_hhmm(open_hhmm)
    c = _parse_hhmm(close_hhmm)
    dt = datetime(2000, 1, 1, o.hour, o.minute)
    end = datetime(2000, 1, 1, c.hour, c.minute)
    out = []
    while dt < end:
        out.append(dt.strftime("%H:%M"))
        dt += timedelta(minutes=SLOT_MINUTES)
    return out


def _load_day(d: date) -> Dict:
    key = _avail_key(OWNER_ID, d)
    obj = _jget(key, None)
    if not isinstance(obj, dict):
        obj = {"open": DEFAULT_OPEN, "close": DEFAULT_CLOSE, "blocked": []}
    obj.setdefault("open", DEFAULT_OPEN)
    obj.setdefault("close", DEFAULT_CLOSE)
    obj.setdefault("blocked", [])
    if not isinstance(obj["blocked"], list):
        obj["blocked"] = []
    obj["blocked"] = sorted({str(x) for x in obj["blocked"]})
    return obj


def _render_roni_assistant_home(cq_or_msg):
    """
    Return user to Roni assistant home panel.
    We try to call handlers.roni_portal.render_home if it exists.
    Otherwise we fall back to telling them to /start.
    """
    try:
        from handlers import roni_portal as rp  # type: ignore
        if hasattr(rp, "send_portal_home"):
            return rp.send_portal_home(cq_or_msg)
        if hasattr(rp, "show_portal"):
            return rp.show_portal(cq_or_msg)
        if hasattr(rp, "render_home"):
            # expect (app, message/callback)
            return rp.render_home  # caller will use
    except Exception:
        pass
    return None


def _week_panel(start: date) -> Tuple[str, InlineKeyboardMarkup]:
    today = _today_la()
    if start < today:
        start = today
    end = start + timedelta(days=6)

    text = (
        f"💗 <b>Book a private NSFW texting session</b>\n"
        f"Pick a day (LA time):\n"
        f"<b>{start.strftime('%b %d')}</b> — <b>{end.strftime('%b %d')}</b>"
    )

    rows: List[List[InlineKeyboardButton]] = []
    cur = start
    while cur <= end:
        rows.append([InlineKeyboardButton(cur.strftime("%a %b %d"), callback_data=f"nsfw_bk:day:{_dstr(cur)}:0")])
        cur += timedelta(days=1)

    rows.append([
        InlineKeyboardButton("Next ➡️", callback_data=f"nsfw_bk:week:{_dstr(start + timedelta(days=7))}"),
    ])
    rows.append([InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:home")])
    return text, InlineKeyboardMarkup(rows)


def _day_panel(d: date, page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    obj = _load_day(d)
    blocked = set(obj["blocked"])
    all_slots = _iter_slots(obj["open"], obj["close"])
    avail = [s for s in all_slots if s not in blocked]

    text = (
        f"🗓️ <b>{d.strftime('%A, %B %d')} (LA time)</b>\n"
        f"Open: <b>{obj['open']}</b> · Close: <b>{obj['close']}</b>\n\n"
        f"Available slots: <b>{len(avail)}</b>\n"
        f"Pick a start time:"
    )

    page = max(0, page)
    start_i = page * SLOTS_PER_PAGE
    end_i = min(len(avail), start_i + SLOTS_PER_PAGE)
    view = avail[start_i:end_i]

    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(view), 2):
        row = []
        for s in view[i:i+2]:
            human = datetime.strptime(s, "%H:%M").strftime("%-I:%M %p")
            row.append(InlineKeyboardButton(f"🕒 {human}", callback_data=f"nsfw_bk:slot:{_dstr(d)}:{s}"))
        rows.append(row)

    pager: List[InlineKeyboardButton] = []
    if start_i > 0:
        pager.append(InlineKeyboardButton("⬅️ More", callback_data=f"nsfw_bk:day:{_dstr(d)}:{page-1}"))
    if end_i < len(avail):
        pager.append(InlineKeyboardButton("More ➡️", callback_data=f"nsfw_bk:day:{_dstr(d)}:{page+1}"))
    if pager:
        rows.append(pager)

    rows.append([InlineKeyboardButton("⬅️ Back to week", callback_data=f"nsfw_bk:week:{_dstr(_today_la())}")])
    rows.append([InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:home")])

    return text, InlineKeyboardMarkup(rows)


@Client.on_message(filters.command("book_nsfw") & filters.private)
async def _cmd(app: Client, msg: Message):
    text, kb = _week_panel(_today_la())
    await msg.reply_text(text, reply_markup=kb, disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"^nsfw_bk:week:"))
async def _cb_week(app: Client, cq: CallbackQuery):
    _, _, dstr = cq.data.split(":", 2)
    try:
        start = datetime.strptime(dstr, "%Y-%m-%d").date()
    except Exception:
        start = _today_la()
    text, kb = _week_panel(start)
    await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    await cq.answer()


@Client.on_callback_query(filters.regex(r"^nsfw_bk:day:"))
async def _cb_day(app: Client, cq: CallbackQuery):
    parts = cq.data.split(":")
    dstr = parts[2]
    page = int(parts[3]) if len(parts) >= 4 else 0
    d = datetime.strptime(dstr, "%Y-%m-%d").date()
    text, kb = _day_panel(d, page=page)
    await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    await cq.answer()


@Client.on_callback_query(filters.regex(r"^nsfw_bk:slot:"))
async def _cb_slot(app: Client, cq: CallbackQuery):
    # nsfw_bk:slot:YYYY-MM-DD:HH:MM
    _, _, dstr, hhmm = cq.data.split(":")
    d = datetime.strptime(dstr, "%Y-%m-%d").date()
    obj = _load_day(d)
    blocked = set(obj["blocked"])
    if hhmm in blocked:
        return await cq.answer("That time is blocked.", show_alert=True)

    # Here you'd normally proceed to booking confirmation / collecting duration/payment.
    # For now we simply acknowledge and tell the user to DM.
    human = datetime.strptime(hhmm, "%H:%M").strftime("%-I:%M %p")
    await cq.answer()
    await cq.message.edit_text(
        f"✅ <b>Requested:</b> {d.strftime('%A, %B %d')} at <b>{human}</b> (LA time)\n\n"
        f"Please DM Roni to confirm & complete booking. 💕",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to times", callback_data=f"nsfw_bk:day:{dstr}:0")],
            [InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:home")],
        ]),
        disable_web_page_preview=True,
    )


# Back to Roni Assistant (works from anywhere)
@Client.on_callback_query(filters.regex(r"^roni_portal:home$"))
async def _cb_back_to_portal(app: Client, cq: CallbackQuery):
    # Try to call into roni_portal to render home; otherwise fallback
    try:
        from handlers import roni_portal as rp  # type: ignore
        if hasattr(rp, "send_portal_home"):
            await rp.send_portal_home(app, cq.message, cq.from_user.id)
            return await cq.answer()
    except Exception:
        pass
    await cq.answer()
    await cq.message.edit_text("⬅️ Use /start to return to the main menu.")


def register(app: Client):
    log.info("✅ nsfw_text_session_booking registered (respects blocked slots + back to portal)")
