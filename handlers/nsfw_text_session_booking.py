"""NSFW text session booking (public-facing).

Fixes:
- Respects the blocked slots created by nsfw_text_session_availability (same Mongo collection).
- Adds robust back navigation handlers so the "Back to Roni Assistant" button actually responds.

Drop this in: handlers/nsfw_text_session_booking.py
"""

import os
import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.errors import MessageNotModified

try:
    import pytz
except Exception:
    pytz = None

from pymongo import MongoClient

log = logging.getLogger(__name__)

# ──────────────────────────────
# Config
# ──────────────────────────────
LA_TZ = os.getenv("LA_TZ", "America/Los_Angeles")
SLOT_MINUTES = int(os.getenv("NSFW_SLOT_MINUTES", "30"))
OPEN_HOUR = int(os.getenv("NSFW_OPEN_HOUR", "9"))
CLOSE_HOUR = int(os.getenv("NSFW_CLOSE_HOUR", "22"))

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DBNAME", "Succubot")
AVAIL_COLL = os.getenv("NSFW_AVAIL_COLL", "nsfw_availability")

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))

_CB_PREFIX = "nsfw_book"  # our callback namespace


def _tz():
    if pytz is None:
        return None
    try:
        return pytz.timezone(LA_TZ)
    except Exception:
        return pytz.timezone("America/Los_Angeles")


def _now_la() -> datetime:
    tz = _tz()
    if tz is None:
        return datetime.utcnow()
    return datetime.now(tz)


def _fmt_day(d: date) -> str:
    return d.strftime("%a %b %d")


def _day_key(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _slots_for_day(d: date) -> List[str]:
    """Return HH:MM slots in LA time."""
    slots: List[str] = []
    cur = datetime(d.year, d.month, d.day, OPEN_HOUR, 0)
    end = datetime(d.year, d.month, d.day, CLOSE_HOUR, 0)
    while cur < end:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=SLOT_MINUTES)
    return slots


def _mongo_coll():
    if not MONGO_URI:
        return None
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGO_DB]
        coll = db[AVAIL_COLL]
        coll.create_index("day", unique=True)
        return coll
    except Exception:
        log.exception("Mongo init failed for nsfw booking")
        return None


def _get_blocked_for_day(day_key: str) -> List[str]:
    coll = _mongo_coll()
    if coll is None:
        return []
    try:
        doc = coll.find_one({"day": day_key}) or {}
        blocked = doc.get("blocked") or []
        if isinstance(blocked, list):
            return [str(x) for x in blocked]
        return []
    except Exception:
        log.exception("Failed loading blocked slots")
        return []


def _available_slots_for_day(d: date) -> List[str]:
    day = _day_key(d)
    all_slots = _slots_for_day(d)
    blocked = set(_get_blocked_for_day(day))
    # If day is today, remove past slots too
    now = _now_la()
    if d == now.date():
        cutoff = now.strftime("%H:%M")
        all_slots = [s for s in all_slots if s >= cutoff]
    return [s for s in all_slots if s not in blocked]


def _kb_days(start: date, week_index: int) -> InlineKeyboardMarkup:
    btns: List[List[InlineKeyboardButton]] = []
    for i in range(7):
        d = start + timedelta(days=i)
        btns.append([
            InlineKeyboardButton(
                _fmt_day(d),
                callback_data=f"{_CB_PREFIX}:day:{_day_key(d)}:{week_index}",
            )
        ])

    nav_row = []
    if week_index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{_CB_PREFIX}:week:{week_index-1}"))
    nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"{_CB_PREFIX}:week:{week_index+1}"))
    btns.append(nav_row)

    # Back options (support multiple callback ids used elsewhere)
    btns.append([
        InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:open"),
        InlineKeyboardButton("⬅️ Back", callback_data="roni_admin:open"),
    ])

    return InlineKeyboardMarkup(btns)


def _kb_slots(day_key: str, week_index: int, page: int, slots: List[str]) -> InlineKeyboardMarkup:
    per_page = 16  # 8 rows x 2 cols
    start = page * per_page
    chunk = slots[start:start + per_page]

    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(chunk), 2):
        row = []
        for s in chunk[i:i + 2]:
            row.append(InlineKeyboardButton(f"🕒 {datetime.strptime(s, '%H:%M').strftime('%I:%M %p')}", callback_data=f"{_CB_PREFIX}:pick:{day_key}:{s}:{week_index}:{page}"))
        rows.append(row)

    nav: List[InlineKeyboardButton] = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️ More", callback_data=f"{_CB_PREFIX}:slots:{day_key}:{week_index}:{page-1}"))
    if start + per_page < len(slots):
        nav.append(InlineKeyboardButton("More ➡️", callback_data=f"{_CB_PREFIX}:slots:{day_key}:{week_index}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton("⬅️ Back to week", callback_data=f"{_CB_PREFIX}:week:{week_index}"),
    ])
    rows.append([
        InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:open"),
    ])

    return InlineKeyboardMarkup(rows)


async def _safe_edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cb.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except MessageNotModified:
        pass


async def _show_week(cb: CallbackQuery, week_index: int):
    now = _now_la().date()
    start = now + timedelta(days=week_index * 7)

    # For week 0, we want remaining days only (today..today+6)
    if week_index == 0:
        start = now

    text = (
        "💞 <b>Book a private NSFW texting session</b>\n"
        f"Pick a day (LA time):\n"
        f"{start.strftime('%b %d')} — {(start + timedelta(days=6)).strftime('%b %d')}\n"
    )

    await _safe_edit(cb, text, _kb_days(start, week_index))


async def _show_day(cb: CallbackQuery, day_key: str, week_index: int, page: int = 0):
    d = datetime.strptime(day_key, "%Y-%m-%d").date()
    slots = _available_slots_for_day(d)

    # Human readable
    nice = d.strftime("%A, %B %d")

    if not slots:
        text = (
            f"📅 <b>{nice} (LA time)</b>\n\n"
            "No available slots right now. (Either everything is blocked, or the day is over.)\n"
            "Try another day."
        )
        await _safe_edit(cb, text, InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to week", callback_data=f"{_CB_PREFIX}:week:{week_index}")],
            [InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:open")],
        ]))
        return

    text = (
        f"📅 <b>{nice} (LA time)</b>\n"
        f"Open: {OPEN_HOUR:02d}:00  •  Close: {CLOSE_HOUR:02d}:00\n\n"
        f"Available slots: {len(slots)}\n"
        "Pick a start time:" 
    )

    await _safe_edit(cb, text, _kb_slots(day_key, week_index, page, slots))


async def _handle_pick(cb: CallbackQuery, day_key: str, slot: str, week_index: int, page: int):
    """For now: confirm selection and tell them to DM owner.

    (You can wire this into a payment / booking workflow later.)
    """
    d = datetime.strptime(day_key, "%Y-%m-%d").date()

    # Re-check availability (in case it was just blocked)
    if slot not in _available_slots_for_day(d):
        await cb.answer("That slot is no longer available.", show_alert=True)
        await _show_day(cb, day_key, week_index, page)
        return

    nice_day = d.strftime("%a %b %d")
    nice_time = datetime.strptime(slot, "%H:%M").strftime("%I:%M %p")

    text = (
        "✅ <b>Request received!</b>\n\n"
        f"<b>Day:</b> {nice_day} (LA)\n"
        f"<b>Start:</b> {nice_time}\n\n"
        "Please DM @Chaossub283 to confirm + arrange payment. 💕"
    )

    await _safe_edit(cb, text, InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to times", callback_data=f"{_CB_PREFIX}:day:{day_key}:{week_index}")],
        [InlineKeyboardButton("⬅️ Back to week", callback_data=f"{_CB_PREFIX}:week:{week_index}")],
        [InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:open")],
    ]))


# ──────────────────────────────
# Public handlers
# ──────────────────────────────

async def cmd_booknsfw(_: Client, msg: Message):
    # Simple entrypoint for testing in any chat.
    now = _now_la().date()
    text = (
        "💞 <b>Book a private NSFW texting session</b>\n"
        f"Pick a day (LA time):\n"
        f"{now.strftime('%b %d')} — {(now + timedelta(days=6)).strftime('%b %d')}\n"
    )
    await msg.reply_text(text, reply_markup=_kb_days(now, 0), disable_web_page_preview=True)


async def cb_router(_: Client, cb: CallbackQuery):
    data = cb.data or ""

    # Back-to-assistant fallbacks: make sure the button is never dead.
    if data in {"roni_portal:open", "roni_assistant:open", "assistant:open"}:
        # We can't safely call another module's internal UI here, so we show a helpful prompt.
        await cb.answer()
        try:
            await cb.message.edit_text(
                "⬅️ Use /start to return to the main menu.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Open /start", url="https://t.me/" + (os.getenv("BOT_USERNAME", "")) )] if os.getenv("BOT_USERNAME") else []
                ]) if os.getenv("BOT_USERNAME") else None,
            )
        except MessageNotModified:
            pass
        return

    # Entry points used by other panels (we accept several strings)
    if data in {"nsfw_book:open", "nsfw_booking:open", "nsfw_text_session_booking:open", "roni_nsfw_book:open"}:
        await cb.answer()
        await _show_week(cb, 0)
        return

    if not data.startswith(_CB_PREFIX + ":"):
        return

    parts = data.split(":")
    # nsfw_book:week:<idx>
    # nsfw_book:day:<YYYY-MM-DD>:<weekidx>
    # nsfw_book:slots:<YYYY-MM-DD>:<weekidx>:<page>
    # nsfw_book:pick:<YYYY-MM-DD>:<HH:MM>:<weekidx>:<page>

    try:
        kind = parts[1]
        if kind == "week":
            week_idx = int(parts[2])
            await cb.answer()
            await _show_week(cb, week_idx)
            return

        if kind == "day":
            day_key = parts[2]
            week_idx = int(parts[3])
            await cb.answer()
            await _show_day(cb, day_key, week_idx, page=0)
            return

        if kind == "slots":
            day_key = parts[2]
            week_idx = int(parts[3])
            page = int(parts[4])
            await cb.answer()
            await _show_day(cb, day_key, week_idx, page=page)
            return

        if kind == "pick":
            day_key = parts[2]
            slot = parts[3]
            week_idx = int(parts[4])
            page = int(parts[5])
            await cb.answer()
            await _handle_pick(cb, day_key, slot, week_idx, page)
            return

    except Exception:
        log.exception("nsfw booking callback failed: %r", data)
        await cb.answer("Something went wrong. Try again.", show_alert=True)


def register(app: Client):
    app.add_handler(MessageHandler(cmd_booknsfw, filters.command(["booknsfw", "nsfwbook"]) & filters.private))

    # Router handles our callbacks + several back/entrypoint fallbacks.
    app.add_handler(CallbackQueryHandler(cb_router))

    log.info("✅ nsfw_text_session_booking_FIXED registered (blocked-slot aware)")
