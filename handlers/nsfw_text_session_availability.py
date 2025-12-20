# handlers/nsfw_text_session_availability.py
"""
NSFW Text Session Availability (Roni)

- Rolling 7-day view (LA time) starting TODAY (no past days).
- Admin-only (owner) can manage availability.
- Supports blocking time slots (30-min grid) + quick "block range" builder.
- Shared storage format used by nsfw_text_session_booking.py in this project.

Storage (MenuStore key => JSON):
  NSFW_AVAIL:<owner_id>:<YYYY-MM-DD> =>
    {
      "open": "09:00",
      "close": "22:00",
      "blocked": ["09:00","09:30", ...]   # slot start times (HH:MM) blocked
    }

If a day key doesn't exist yet, it falls back to defaults OPEN=09:00 CLOSE=22:00 and blocked=[]
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta, time
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
SLOTS_PER_PAGE = 24  # 12 hours at 30m


def _today_la() -> date:
    return datetime.now(LA_TZ).date()


def _dstr(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _pretty_day(d: date) -> str:
    return d.strftime("%A, %B %d")


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


def _jset(key: str, obj) -> None:
    store.set_menu(key, json.dumps(obj, ensure_ascii=False))


def _parse_hhmm(s: str) -> time:
    hh, mm = s.split(":")
    return time(int(hh), int(mm))


def _hhmm(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _iter_slots(open_hhmm: str, close_hhmm: str) -> List[str]:
    """Return slot start times between open (inclusive) and close (exclusive)."""
    o = _parse_hhmm(open_hhmm)
    c = _parse_hhmm(close_hhmm)
    dt = datetime(2000, 1, 1, o.hour, o.minute)
    end = datetime(2000, 1, 1, c.hour, c.minute)
    out = []
    while dt < end:
        out.append(dt.strftime("%H:%M"))
        dt += timedelta(minutes=SLOT_MINUTES)
    return out


def _load_day(owner_id: int, d: date) -> Dict:
    key = _avail_key(owner_id, d)
    obj = _jget(key, None)
    if not isinstance(obj, dict):
        obj = {"open": DEFAULT_OPEN, "close": DEFAULT_CLOSE, "blocked": []}
        _jset(key, obj)
    obj.setdefault("open", DEFAULT_OPEN)
    obj.setdefault("close", DEFAULT_CLOSE)
    obj.setdefault("blocked", [])
    # normalize
    if not isinstance(obj["blocked"], list):
        obj["blocked"] = []
    obj["blocked"] = sorted({str(x) for x in obj["blocked"]})
    return obj


def _save_day(owner_id: int, d: date, obj: Dict) -> None:
    key = _avail_key(owner_id, d)
    obj.setdefault("open", DEFAULT_OPEN)
    obj.setdefault("close", DEFAULT_CLOSE)
    obj.setdefault("blocked", [])
    obj["blocked"] = sorted({str(x) for x in obj["blocked"]})
    _jset(key, obj)


def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


# ───────────── UI Builders ─────────────

def _week_bounds(start: date) -> Tuple[date, date]:
    """Start is inclusive; end is inclusive (7 days)."""
    return start, start + timedelta(days=6)


def _week_panel(start: date) -> Tuple[str, InlineKeyboardMarkup]:
    today = _today_la()
    if start < today:
        start = today

    s, e = _week_bounds(start)
    title = f"🗓️ <b>NSFW Availability (LA time)</b>\nWeek: <b>{s.strftime('%b %d')}</b> — <b>{e.strftime('%b %d')}</b>\n\nTap a day to edit time slots and blocks."

    rows: List[List[InlineKeyboardButton]] = []
    cur = s
    while cur <= e:
        label = cur.strftime("%a %b %d")
        rows.append([InlineKeyboardButton(f"✅ {label}", callback_data=f"nsfw_av:day:{_dstr(cur)}")])
        cur += timedelta(days=1)

    nav = [
        InlineKeyboardButton("⬅️ Prev week", callback_data=f"nsfw_av:week:{_dstr(s - timedelta(days=7))}"),
        InlineKeyboardButton("Next week ➡️", callback_data=f"nsfw_av:week:{_dstr(s + timedelta(days=7))}"),
    ]
    rows.append(nav)
    rows.append([InlineKeyboardButton("⬅️ Back to Roni Admin", callback_data="roni_admin:home")])
    return title, InlineKeyboardMarkup(rows)


def _day_panel(d: date, page: int = 0, range_start: Optional[str] = None) -> Tuple[str, InlineKeyboardMarkup]:
    obj = _load_day(OWNER_ID, d)
    open_hhmm = obj["open"]
    close_hhmm = obj["close"]
    blocked = set(obj["blocked"])

    all_slots = _iter_slots(open_hhmm, close_hhmm)
    total = len(all_slots)
    page = max(0, page)
    start_i = page * SLOTS_PER_PAGE
    end_i = min(total, start_i + SLOTS_PER_PAGE)
    slots = all_slots[start_i:end_i]

    blocked_count = len([s for s in all_slots if s in blocked])

    subtitle = f"🧩 <b>Block time slots</b>\nDay: <b>{_pretty_day(d)}</b> (LA time)\nOpen: <b>{open_hhmm}</b> · Close: <b>{close_hhmm}</b>\nBlocked slots: <b>{blocked_count}</b> of <b>{total}</b>\n\nTap a slot to toggle it:\n✅ = available · ⛔ = blocked"

    # Grid: 2 columns
    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(slots), 2):
        row = []
        for s in slots[i:i+2]:
            is_blocked = s in blocked
            emoji = "⛔" if is_blocked else "✅"
            human = datetime.strptime(s, "%H:%M").strftime("%-I:%M %p") if hasattr(datetime, "strptime") else s
            row.append(InlineKeyboardButton(f"{emoji} {human}", callback_data=f"nsfw_av:slot:{_dstr(d)}:{s}:{page}"))
        rows.append(row)

    # Range builder status
    if range_start:
        rs_h = datetime.strptime(range_start, "%H:%M").strftime("%-I:%M %p")
        subtitle += f"\n\n🧷 <b>Range mode:</b> start = <b>{rs_h}</b>\nNow tap an <b>end</b> slot to block that whole range."
        # In range mode, slot clicks are interpreted as END. We'll still reuse slot callback, but handler will check session state.

    # Pager row
    pager: List[InlineKeyboardButton] = []
    if start_i > 0:
        pager.append(InlineKeyboardButton("⬅️ More", callback_data=f"nsfw_av:day:{_dstr(d)}:{page-1}"))
    if end_i < total:
        pager.append(InlineKeyboardButton("More ➡️", callback_data=f"nsfw_av:day:{_dstr(d)}:{page+1}"))
    if pager:
        rows.append(pager)

    # Tools
    rows.append([
        InlineKeyboardButton("🧷 Block a range", callback_data=f"nsfw_av:range_start:{_dstr(d)}"),
        InlineKeyboardButton("✅ Clear blocks", callback_data=f"nsfw_av:clear:{_dstr(d)}:{page}"),
    ])
    rows.append([
        InlineKeyboardButton("⛔ Block all day", callback_data=f"nsfw_av:block_all:{_dstr(d)}:{page}"),
        InlineKeyboardButton("⬅️ Back", callback_data=f"nsfw_av:week:{_dstr(_today_la())}"),
    ])

    return subtitle, InlineKeyboardMarkup(rows)


# ───────────── Handlers ─────────────

# Simple in-memory per-user range mode state:
#   (user_id) -> (date_str, start_hhmm, page)
_RANGE_STATE: Dict[int, Tuple[str, str, int]] = {}


@Client.on_message(filters.command("nsfw_availability") & filters.private)
async def _cmd_private(app: Client, msg: Message):
    if not _is_owner(msg.from_user.id):
        return await msg.reply_text("Sorry — this panel is for the owner/admin only.")
    start = _today_la()
    text, kb = _week_panel(start)
    await msg.reply_text(text, reply_markup=kb, disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"^nsfw_av:week:"))
async def _cb_week(app: Client, cq: CallbackQuery):
    if not _is_owner(cq.from_user.id):
        return await cq.answer("Admin only.", show_alert=True)
    _, _, dstr = cq.data.split(":", 2)
    try:
        start = datetime.strptime(dstr, "%Y-%m-%d").date()
    except Exception:
        start = _today_la()
    text, kb = _week_panel(start)
    await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    await cq.answer()


@Client.on_callback_query(filters.regex(r"^nsfw_av:day:"))
async def _cb_day(app: Client, cq: CallbackQuery):
    if not _is_owner(cq.from_user.id):
        return await cq.answer("Admin only.", show_alert=True)

    parts = cq.data.split(":")
    # nsfw_av:day:YYYY-MM-DD or nsfw_av:day:YYYY-MM-DD:page
    dstr = parts[2]
    page = int(parts[3]) if len(parts) >= 4 else 0

    try:
        d = datetime.strptime(dstr, "%Y-%m-%d").date()
    except Exception:
        d = _today_la()

    range_state = _RANGE_STATE.get(cq.from_user.id)
    range_start = None
    if range_state and range_state[0] == dstr:
        range_start = range_state[1]

    text, kb = _day_panel(d, page=page, range_start=range_start)
    await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    await cq.answer()


@Client.on_callback_query(filters.regex(r"^nsfw_av:range_start:"))
async def _cb_range_start(app: Client, cq: CallbackQuery):
    if not _is_owner(cq.from_user.id):
        return await cq.answer("Admin only.", show_alert=True)
    dstr = cq.data.split(":")[2]
    # We set state to require selecting start first: next slot tap sets START.
    # We'll just set a sentinel start="__pick__" and interpret next slot as start.
    _RANGE_STATE[cq.from_user.id] = (dstr, "__pick__", 0)
    await cq.answer("Tap the START time slot.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^nsfw_av:slot:"))
async def _cb_slot(app: Client, cq: CallbackQuery):
    if not _is_owner(cq.from_user.id):
        return await cq.answer("Admin only.", show_alert=True)

    # nsfw_av:slot:YYYY-MM-DD:HH:MM:page
    _, _, dstr, hhmm, page_s = cq.data.split(":")
    page = int(page_s)

    try:
        d = datetime.strptime(dstr, "%Y-%m-%d").date()
    except Exception:
        d = _today_la()

    obj = _load_day(OWNER_ID, d)
    blocked = set(obj["blocked"])

    # Range mode handling
    state = _RANGE_STATE.get(cq.from_user.id)
    if state and state[0] == dstr:
        start_hhmm = state[1]
        if start_hhmm == "__pick__":
            # this click becomes START
            _RANGE_STATE[cq.from_user.id] = (dstr, hhmm, page)
            await cq.answer("Now tap the END time slot.", show_alert=True)
            text, kb = _day_panel(d, page=page, range_start=hhmm)
            return await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

        # this click becomes END -> block whole range inclusive of start, exclusive of end+slot
        slots = _iter_slots(obj["open"], obj["close"])
        try:
            si = slots.index(start_hhmm)
            ei = slots.index(hhmm)
        except ValueError:
            _RANGE_STATE.pop(cq.from_user.id, None)
            await cq.answer("That slot isn't valid for this day.", show_alert=True)
        else:
            if ei < si:
                si, ei = ei, si
            for s in slots[si:ei+1]:
                blocked.add(s)
            obj["blocked"] = sorted(blocked)
            _save_day(OWNER_ID, d, obj)
            _RANGE_STATE.pop(cq.from_user.id, None)
            await cq.answer("Blocked that range ✅")
            text, kb = _day_panel(d, page=page)
            return await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    # Normal toggle
    if hhmm in blocked:
        blocked.remove(hhmm)
    else:
        blocked.add(hhmm)

    obj["blocked"] = sorted(blocked)
    _save_day(OWNER_ID, d, obj)

    await cq.answer("Updated ✅")
    text, kb = _day_panel(d, page=page)
    await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"^nsfw_av:clear:"))
async def _cb_clear(app: Client, cq: CallbackQuery):
    if not _is_owner(cq.from_user.id):
        return await cq.answer("Admin only.", show_alert=True)
    _, _, dstr, page_s = cq.data.split(":")
    page = int(page_s)
    d = datetime.strptime(dstr, "%Y-%m-%d").date()
    obj = _load_day(OWNER_ID, d)
    obj["blocked"] = []
    _save_day(OWNER_ID, d, obj)
    _RANGE_STATE.pop(cq.from_user.id, None)
    await cq.answer("Cleared ✅")
    text, kb = _day_panel(d, page=page)
    await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"^nsfw_av:block_all:"))
async def _cb_block_all(app: Client, cq: CallbackQuery):
    if not _is_owner(cq.from_user.id):
        return await cq.answer("Admin only.", show_alert=True)
    _, _, dstr, page_s = cq.data.split(":")
    page = int(page_s)
    d = datetime.strptime(dstr, "%Y-%m-%d").date()
    obj = _load_day(OWNER_ID, d)
    obj["blocked"] = _iter_slots(obj["open"], obj["close"])
    _save_day(OWNER_ID, d, obj)
    _RANGE_STATE.pop(cq.from_user.id, None)
    await cq.answer("Blocked all day ⛔")
    text, kb = _day_panel(d, page=page)
    await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)


def register(app: Client):
    log.info("✅ nsfw_text_session_availability registered (rolling 7-day + range/block slots)")
