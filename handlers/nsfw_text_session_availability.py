# handlers/nsfw_text_session_availability.py
"""
NSFW Text Session Availability (Roni) — rolling 7-day view + slot toggle blocking.

Fixes:
- Prevents "button does nothing" caused by Telegram MESSAGE_NOT_MODIFIED when editing the same text/markup.
- Always answers callback queries (so Telegram UI stops spinning).
- Shows ONLY future days: today .. today+6 (then Next week / Prev week).
- Persists blocked time slots per-day in MongoDB if available, otherwise falls back to in-memory.
- Works with roni_portal button callback_data: "nsfw_avail:open"

Notes:
- This module only handles AVAILABILITY UI + storage.
- Booking module should read the same storage (blocked slots) to hide/deny times.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, date, time
from typing import Dict, List, Set, Optional, Tuple

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None  # type: ignore

log = logging.getLogger(__name__)

TZ_NAME = os.getenv("LA_TZ", "America/Los_Angeles")
TZ = pytz.timezone(TZ_NAME)

RONI_OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))

# Slot grid settings (30-minute slots)
SLOT_MINUTES = 30

# Default working hours for the grid (9:00 AM – 5:30 PM shown on first page; "More" for later)
DAY_START_HOUR = int(os.getenv("NSFW_DAY_START_HOUR", "9"))   # inclusive
DAY_END_HOUR = int(os.getenv("NSFW_DAY_END_HOUR", "18"))      # exclusive (18 = 6PM)
# How many slots to show per page in the "toggle grid"
SLOTS_PER_PAGE = 16  # 8 rows of 2 buttons = 16 slots

# Mongo (optional)
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DBNAME", "Succubot")
MONGO_COLL = os.getenv("NSFW_AVAIL_COLL", "nsfw_availability")

_mongo_coll = None
_mem_store: Dict[str, Set[str]] = {}  # fallback: {"YYYY-MM-DD": {"09:00", "09:30", ...}}

def _is_owner(user_id: int) -> bool:
    return user_id == RONI_OWNER_ID

def _now_la() -> datetime:
    return datetime.now(TZ)

def _today_la() -> date:
    return _now_la().date()

def _date_key(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def _fmt_day(d: date) -> str:
    return d.strftime("%a %b %d")

def _fmt_time_label(hhmm: str) -> str:
    # "09:00" -> "9:00 AM"
    hh, mm = hhmm.split(":")
    t = time(int(hh), int(mm))
    return datetime.combine(date.today(), t).strftime("%-I:%M %p")

def _all_slots_for_day() -> List[str]:
    slots: List[str] = []
    start = time(DAY_START_HOUR, 0)
    end = time(DAY_END_HOUR, 0)
    cur = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    while cur < end_dt:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=SLOT_MINUTES)
    return slots

ALL_SLOTS = _all_slots_for_day()

def _mongo_init():
    global _mongo_coll
    if _mongo_coll is not None:
        return
    if not (MongoClient and MONGO_URI):
        _mongo_coll = None
        return
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3500)
        db = client[MONGO_DB]
        _mongo_coll = db[MONGO_COLL]
        _mongo_coll.create_index("day", unique=True)
        log.info("NSFW availability: Mongo enabled db=%s coll=%s", MONGO_DB, MONGO_COLL)
    except Exception:
        log.exception("NSFW availability: Mongo init failed, falling back to memory")
        _mongo_coll = None

def _load_blocked(day_key: str) -> Set[str]:
    _mongo_init()
    if _mongo_coll is None:
        return set(_mem_store.get(day_key, set()))
    try:
        doc = _mongo_coll.find_one({"day": day_key}) or {}
        blocked = set(doc.get("blocked", []) or [])
        return blocked
    except Exception:
        log.exception("NSFW availability: Mongo read failed, using memory")
        return set(_mem_store.get(day_key, set()))

def _save_blocked(day_key: str, blocked: Set[str]) -> None:
    _mongo_init()
    blocked_list = sorted(blocked)
    if _mongo_coll is None:
        _mem_store[day_key] = set(blocked_list)
        return
    try:
        _mongo_coll.update_one(
            {"day": day_key},
            {"$set": {"day": day_key, "blocked": blocked_list, "updated_at": datetime.utcnow()}},
            upsert=True,
        )
    except Exception:
        log.exception("NSFW availability: Mongo write failed, storing in memory")
        _mem_store[day_key] = set(blocked_list)

async def _safe_edit(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    """
    Telegram throws MESSAGE_NOT_MODIFIED if you edit with identical content.
    That looks like "button does nothing" in chat — so we just ignore it.
    """
    try:
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except MessageNotModified:
        pass

def _overview_text(page: int) -> str:
    start = _today_la() + timedelta(days=page * 7)
    end = start + timedelta(days=6)
    return (
        f"🗓️ <b>NSFW Availability (LA time)</b>\n"
        f"Window: <b>{start.strftime('%b %d')}</b> — <b>{end.strftime('%b %d')}</b>\n\n"
        f"Tap a day to toggle blocked time slots.\n"
        f"✅ = available   ⛔ = blocked"
    )

def _kb_week(page: int) -> InlineKeyboardMarkup:
    start = _today_la() + timedelta(days=page * 7)
    rows: List[List[InlineKeyboardButton]] = []
    for i in range(7):
        d = start + timedelta(days=i)
        day_key = _date_key(d)
        blocked = _load_blocked(day_key)
        badge = "⛔" if blocked else "✅"
        rows.append([InlineKeyboardButton(f"{badge} {_fmt_day(d)}", callback_data=f"nsfw_avail:day:{day_key}:p0:w{page}")])

    nav_row: List[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev week", callback_data=f"nsfw_avail:week:{page-1}"))
    nav_row.append(InlineKeyboardButton("Next week ➡️", callback_data=f"nsfw_avail:week:{page+1}"))
    rows.append(nav_row)
    rows.append([InlineKeyboardButton("⬅️ Back to Roni Admin", callback_data="roni_portal:admin")])
    return InlineKeyboardMarkup(rows)

def _day_text(day_key: str, page: int, week_page: int) -> str:
    d = datetime.strptime(day_key, "%Y-%m-%d").date()
    blocked = _load_blocked(day_key)
    return (
        f"🧩 <b>Block time slots</b>\n"
        f"Day: <b>{d.strftime('%A, %B %d')} (LA time)</b>\n"
        f"Blocked: <b>{len(blocked)}</b>\n\n"
        f"Tap a slot to toggle:\n"
        f"✅ = available   ⛔ = blocked"
    )

def _kb_day(day_key: str, slot_page: int, week_page: int) -> InlineKeyboardMarkup:
    blocked = _load_blocked(day_key)

    start_idx = slot_page * SLOTS_PER_PAGE
    end_idx = min(len(ALL_SLOTS), start_idx + SLOTS_PER_PAGE)
    slice_slots = ALL_SLOTS[start_idx:end_idx]

    rows: List[List[InlineKeyboardButton]] = []
    # two columns
    for i in range(0, len(slice_slots), 2):
        row: List[InlineKeyboardButton] = []
        for s in slice_slots[i:i+2]:
            is_blocked = s in blocked
            emoji = "⛔" if is_blocked else "✅"
            row.append(InlineKeyboardButton(f"{emoji} {_fmt_time_label(s)}", callback_data=f"nsfw_avail:toggle:{day_key}:{s}:p{slot_page}:w{week_page}"))
        rows.append(row)

    # paging for more times
    nav: List[InlineKeyboardButton] = []
    if start_idx > 0:
        nav.append(InlineKeyboardButton("⬅️ Earlier", callback_data=f"nsfw_avail:day:{day_key}:p{slot_page-1}:w{week_page}"))
    if end_idx < len(ALL_SLOTS):
        nav.append(InlineKeyboardButton("More ➡️", callback_data=f"nsfw_avail:day:{day_key}:p{slot_page+1}:w{week_page}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton("⛔ Block all day", callback_data=f"nsfw_avail:blockall:{day_key}:w{week_page}"),
        InlineKeyboardButton("🧹 Clear blocks", callback_data=f"nsfw_avail:clear:{day_key}:w{week_page}"),
    ])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"nsfw_avail:week:{week_page}")])

    return InlineKeyboardMarkup(rows)

def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_text_session_availability registered (rolling 7-day + slot toggles)")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:open$"))
    async def nsfw_avail_open(_, cq: CallbackQuery):
        await cq.answer()
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return
        text = _overview_text(page=0)
        kb = _kb_week(page=0)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_avail:week:\d+$"))
    async def nsfw_avail_week(_, cq: CallbackQuery):
        await cq.answer()
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return
        try:
            page = int(cq.data.split(":")[-1])
        except Exception:
            page = 0
        text = _overview_text(page=page)
        kb = _kb_week(page=page)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_avail:day:\d{4}-\d{2}-\d{2}:p\d+:w\d+$"))
    async def nsfw_avail_day(_, cq: CallbackQuery):
        await cq.answer()
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return
        # nsfw_avail:day:YYYY-MM-DD:p0:w0
        parts = cq.data.split(":")
        day_key = parts[2]
        slot_page = int(parts[3][1:])
        week_page = int(parts[4][1:])
        text = _day_text(day_key, slot_page, week_page)
        kb = _kb_day(day_key, slot_page, week_page)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_avail:toggle:\d{4}-\d{2}-\d{2}:\d{2}:\d{2}:p\d+:w\d+$"))
    async def nsfw_avail_toggle(_, cq: CallbackQuery):
        await cq.answer()
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return
        # nsfw_avail:toggle:YYYY-MM-DD:HH:MM:p0:w0
        parts = cq.data.split(":")
        day_key = parts[2]
        hhmm = f"{parts[3]}:{parts[4]}"
        slot_page = int(parts[5][1:])
        week_page = int(parts[6][1:])

        blocked = _load_blocked(day_key)
        if hhmm in blocked:
            blocked.remove(hhmm)
        else:
            blocked.add(hhmm)
        _save_blocked(day_key, blocked)

        text = _day_text(day_key, slot_page, week_page)
        kb = _kb_day(day_key, slot_page, week_page)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_avail:blockall:\d{4}-\d{2}-\d{2}:w\d+$"))
    async def nsfw_avail_blockall(_, cq: CallbackQuery):
        await cq.answer()
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return
        parts = cq.data.split(":")
        day_key = parts[2]
        week_page = int(parts[3][1:])
        blocked = set(ALL_SLOTS)
        _save_blocked(day_key, blocked)
        text = _day_text(day_key, 0, week_page)
        kb = _kb_day(day_key, 0, week_page)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clear:\d{4}-\d{2}-\d{2}:w\d+$"))
    async def nsfw_avail_clear(_, cq: CallbackQuery):
        await cq.answer()
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return
        parts = cq.data.split(":")
        day_key = parts[2]
        week_page = int(parts[3][1:])
        _save_blocked(day_key, set())
        text = _day_text(day_key, 0, week_page)
        kb = _kb_day(day_key, 0, week_page)
        await _safe_edit(cq, text, kb)
