# handlers/nsfw_text_session_booking.py
import json
import logging
from datetime import datetime, timedelta

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.menu_store import store
from handlers.roni_portal_age import is_age_verified

log = logging.getLogger(__name__)

RONI_OWNER_ID = 6964994611
TZ_LA = pytz.timezone("America/Los_Angeles")

# SINGLE SOURCE OF TRUTH:
# NSFW_AVAIL:YYYY-MM-DD => {"date": "...", "slot_minutes":30, "start":"09:00", "end":"21:30", "blocked":["HH:MM",...]}
def _avail_key(d: str) -> str:
    return f"NSFW_AVAIL:{d}"

def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default

def _parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)

def _fmt_hhmm(minutes: int) -> str:
    return f"{minutes//60:02d}:{minutes%60:02d}"

def _get_day(d: str) -> dict:
    raw = store.get_menu(_avail_key(d))
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
    # normalize blocked
    b = set()
    for x in obj["blocked"]:
        s = str(x).strip()
        if len(s) == 5 and s[2] == ":":
            b.add(s)
    obj["blocked"] = sorted(b)
    return obj

def _slots_for_day(obj: dict) -> list[str]:
    step = int(obj.get("slot_minutes", 30))
    start = _parse_hhmm(obj.get("start", "09:00"))
    end = _parse_hhmm(obj.get("end", "21:30"))
    out = []
    t = start
    while t <= end:
        out.append(_fmt_hhmm(t))
        t += step
    return out

def _date_str(dt) -> str:
    return dt.strftime("%Y-%m-%d")

def _pretty_date(dt) -> str:
    return dt.strftime("%A, %b %d")

def _days_kb() -> InlineKeyboardMarkup:
    today = datetime.now(TZ_LA).date()
    rows = []
    for i in range(0, 14, 2):
        d1 = today + timedelta(days=i)
        d2 = today + timedelta(days=i+1)
        rows.append([
            InlineKeyboardButton(d1.strftime("%b %d"), callback_data=f"nsfw_book:day:{_date_str(d1)}"),
            InlineKeyboardButton(d2.strftime("%b %d"), callback_data=f"nsfw_book:day:{_date_str(d2)}"),
        ])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)

def _times_kb(d: str, page: int = 0) -> InlineKeyboardMarkup:
    obj = _get_day(d)
    blocked = set(obj.get("blocked", []))
    slots = [t for t in _slots_for_day(obj) if t not in blocked]

    per_page = 18
    max_page = max(0, (len(slots) - 1) // per_page) if slots else 0
    page = max(0, min(page, max_page))
    chunk = slots[page * per_page : (page + 1) * per_page]

    rows = []
    for i in range(0, len(chunk), 3):
        rows.append([InlineKeyboardButton(t, callback_data=f"nsfw_book:time:{d}:{t}:{page}") for t in chunk[i:i+3]])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"nsfw_book:times:{d}:{page-1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"nsfw_book:times:{d}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:open")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)

def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_text_session_booking registered (blocked slots respected + shows date/time)")

    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def book_open(_, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        if uid != RONI_OWNER_ID and not is_age_verified(uid):
            await cq.answer("Photo age verification required 💕", show_alert=True)
            return
        await cq.message.edit_text(
            "💞 <b>Book a private NSFW texting session</b>\n\nPick a day (LA time):",
            reply_markup=_days_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(\d{4}-\d{2}-\d{2})$"))
    async def pick_day(_, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        if uid != RONI_OWNER_ID and not is_age_verified(uid):
            await cq.answer("Photo age verification required 💕", show_alert=True)
            return
        d = (cq.data or "").split(":")[-1]
        obj = _get_day(d)
        blocked = set(obj.get("blocked", []))
        avail = [t for t in _slots_for_day(obj) if t not in blocked]
        dt = datetime.strptime(d, "%Y-%m-%d").date()

        if not avail:
            await cq.message.edit_text(
                f"<b>{_pretty_date(dt)}</b>\n\n"
                "No available times left for this day.\n\nPick another day:",
                reply_markup=_days_kb(),
                disable_web_page_preview=True,
            )
            await cq.answer()
            return

        await cq.message.edit_text(
            f"<b>{_pretty_date(dt)}</b>\nPick a start time (LA) ⏰",
            reply_markup=_times_kb(d, 0),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:times:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def times_page(_, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        if uid != RONI_OWNER_ID and not is_age_verified(uid):
            await cq.answer("Photo age verification required 💕", show_alert=True)
            return
        _, _, d, p = (cq.data or "").split(":")
        page = int(p)
        dt = datetime.strptime(d, "%Y-%m-%d").date()
        await cq.message.edit_text(
            f"<b>{_pretty_date(dt)}</b>\nPick a start time (LA) ⏰",
            reply_markup=_times_kb(d, page),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:time:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):(\d+)$"))
    async def pick_time(_, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        if uid != RONI_OWNER_ID and not is_age_verified(uid):
            await cq.answer("Photo age verification required 💕", show_alert=True)
            return

        _, _, d, t, _page = (cq.data or "").split(":")
        obj = _get_day(d)
        if t in set(obj.get("blocked", [])):
            await cq.answer("That time is blocked.", show_alert=True)
            # refresh
            dt = datetime.strptime(d, "%Y-%m-%d").date()
            await cq.message.edit_text(
                f"<b>{_pretty_date(dt)}</b>\nPick a start time (LA) ⏰",
                reply_markup=_times_kb(d, 0),
                disable_web_page_preview=True,
            )
            return

        # Send request to Roni with date+time
        buyer = cq.from_user
        who = f"{buyer.first_name}" + (f" (@{buyer.username})" if buyer and buyer.username else "")
        req = (
            "💞 <b>NSFW Session Booking Request</b>\n\n"
            f"Buyer: {who}\n"
            f"ID: <code>{buyer.id}</code>\n"
            f"Requested: <b>{d}</b> at <b>{t}</b> (LA)\n\n"
            "Reply to this message to follow up."
        )
        try:
            await app.send_message(RONI_OWNER_ID, req, disable_web_page_preview=True)
        except Exception:
            pass

        dt = datetime.strptime(d, "%Y-%m-%d").date()
        await cq.message.edit_text(
            "✅ Request sent!\n\n"
            f"You requested: <b>{_pretty_date(dt)}</b> at <b>{t} LA</b>\n\n"
            "Roni will confirm with you shortly 💕\n\n"
            "🚫 NO meetups — online/texting only.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]]),
            disable_web_page_preview=True,
        )
        await cq.answer()
