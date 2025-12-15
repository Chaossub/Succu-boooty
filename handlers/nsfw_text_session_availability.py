# handlers/nsfw_availability.py
import json
import logging
from datetime import datetime, timedelta, date

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.menu_store import store

log = logging.getLogger(__name__)

RONI_OWNER_ID = 6964994611
TZ_LA = pytz.timezone("America/Los_Angeles")

# --- Storage schema (single source of truth) ---
# For each day, we store a dict:
# {
#   "date": "YYYY-MM-DD",
#   "slot_minutes": 30,
#   "start": "09:00",
#   "end": "21:30",
#   "blocked": ["09:00","09:30",...],   # start-times blocked
#   "note": optional
# }
def _key(d: str) -> str:
    return f"NSFW_AVAIL:{d}"

DEFAULT_DAY = {
    "slot_minutes": 30,
    "start": "09:00",
    "end": "21:30",
    "blocked": [],
}

def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default

def _get_day(d: str) -> dict:
    raw = store.get_menu(_key(d))
    if not raw:
        obj = dict(DEFAULT_DAY)
        obj["date"] = d
        return obj
    obj = _jloads(raw, None)
    if not isinstance(obj, dict):
        obj = dict(DEFAULT_DAY)
        obj["date"] = d
    obj.setdefault("date", d)
    obj.setdefault("slot_minutes", 30)
    obj.setdefault("start", "09:00")
    obj.setdefault("end", "21:30")
    obj.setdefault("blocked", [])
    if not isinstance(obj["blocked"], list):
        obj["blocked"] = []
    # Normalize blocked entries to HH:MM strings
    norm = []
    for x in obj["blocked"]:
        try:
            s = str(x).strip()
            if len(s) == 5 and s[2] == ":":
                norm.append(s)
        except Exception:
            pass
    obj["blocked"] = sorted(list(set(norm)))
    return obj

def _set_day(d: str, obj: dict) -> None:
    store.set_menu(_key(d), json.dumps(obj, ensure_ascii=False))

def _parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)

def _fmt_hhmm(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"

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

def _calendar_header(d: str) -> str:
    dt = datetime.strptime(d, "%Y-%m-%d").date()
    return dt.strftime("%A, %b %d")

def _date_str(dt: date) -> str:
    return dt.strftime("%Y-%m-%d")

def _admin_day_kb(d: str, page: int = 0) -> InlineKeyboardMarkup:
    obj = _get_day(d)
    slots = _slots_for_day(obj)
    blocked = set(obj.get("blocked", []))

    # Build buttons (10 per page: 2 columns x 5 rows)
    per_page = 10
    max_page = max(0, (len(slots) - 1) // per_page) if slots else 0
    page = max(0, min(page, max_page))
    chunk = slots[page * per_page : (page + 1) * per_page]

    rows = []
    # 2 columns
    for i in range(0, len(chunk), 2):
        row = []
        for t in chunk[i:i+2]:
            is_blocked = t in blocked
            label = f"🚫 {t}" if is_blocked else f"✅ {t}"
            row.append(InlineKeyboardButton(label, callback_data=f"nsfw_avail:toggle:{d}:{t}:{page}"))
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"nsfw_avail:day:{d}:{page-1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"nsfw_avail:day:{d}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🧹 Clear ALL blocks for this day", callback_data=f"nsfw_avail:clear:{d}")])
    rows.append([InlineKeyboardButton("📅 Pick another day", callback_data="nsfw_avail:open")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")])
    return InlineKeyboardMarkup(rows)

def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_availability registered")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:open$"))
    async def open_avail(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        today = datetime.now(TZ_LA).date()
        rows = []
        # show 14 days
        for i in range(0, 14, 2):
            d1 = today + timedelta(days=i)
            d2 = today + timedelta(days=i+1)
            rows.append([
                InlineKeyboardButton(d1.strftime("%b %d"), callback_data=f"nsfw_avail:day:{_date_str(d1)}:0"),
                InlineKeyboardButton(d2.strftime("%b %d"), callback_data=f"nsfw_avail:day:{_date_str(d2)}:0"),
            ])
        rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")])
        await cq.message.edit_text(
            "🗓 <b>NSFW Availability (LA time)</b>\n\nPick a day to block/unblock time slots:",
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:day:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def day_view(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        _, _, d, p = (cq.data or "").split(":")
        page = int(p)
        obj = _get_day(d)
        blocked = obj.get("blocked", [])
        await cq.message.edit_text(
            f"<b>{_calendar_header(d)}</b>\n\nTap times to toggle block.\n"
            f"🚫 blocked: <b>{len(blocked)}</b>",
            reply_markup=_admin_day_kb(d, page),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:toggle:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):(\d+)$"))
    async def toggle_slot(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        _, _, d, t, p = (cq.data or "").split(":")
        page = int(p)
        obj = _get_day(d)
        blocked = set(obj.get("blocked", []))
        if t in blocked:
            blocked.remove(t)
        else:
            blocked.add(t)
        obj["blocked"] = sorted(blocked)
        _set_day(d, obj)
        # refresh same view
        await day_view(app, cq)  # uses cq.data, but we changed it; rebuild edit:
        try:
            await cq.message.edit_text(
                f"<b>{_calendar_header(d)}</b>\n\nTap times to toggle block.\n"
                f"🚫 blocked: <b>{len(obj['blocked'])}</b>",
                reply_markup=_admin_day_kb(d, page),
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clear:(\d{4}-\d{2}-\d{2})$"))
    async def clear_day(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        d = (cq.data or "").split(":")[-1]
        obj = _get_day(d)
        obj["blocked"] = []
        _set_day(d, obj)
        await cq.answer("Cleared ✅", show_alert=True)
        await cq.message.edit_text(
            f"<b>{_calendar_header(d)}</b>\n\nTap times to toggle block.\n🚫 blocked: <b>0</b>",
            reply_markup=_admin_day_kb(d, 0),
            disable_web_page_preview=True,
        )

    # (Optional) quick command to inspect a day
    @app.on_message(filters.private & filters.user(RONI_OWNER_ID) & filters.command(["nsfw_day"]))
    async def cmd_nsfw_day(_, m: Message):
        parts = (m.text or "").split()
        if len(parts) < 2:
            await m.reply_text("Usage: /nsfw_day YYYY-MM-DD")
            return
        d = parts[1].strip()
        obj = _get_day(d)
        await m.reply_text(f"{d}\nBlocked: {obj.get('blocked',[])}")
