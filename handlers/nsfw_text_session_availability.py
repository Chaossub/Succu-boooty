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

# Single source of truth for booking + blocks:
# NSFW_AVAIL:YYYY-MM-DD => {"date":"YYYY-MM-DD","slot_minutes":30,"start":"09:00","end":"21:30","blocked":["HH:MM",...]}
def _key(d: str) -> str:
    return f"NSFW_AVAIL:{d}"

def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default

def _jdumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)

def _parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)

def _fmt_hhmm(minutes: int) -> str:
    return f"{minutes//60:02d}:{minutes%60:02d}"

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
    # normalize
    b=set()
    for x in obj["blocked"]:
        s=str(x).strip()
        if len(s)==5 and s[2]==":":
            b.add(s)
    obj["blocked"]=sorted(b)
    return obj

def _save_day(obj: dict) -> None:
    d = obj.get("date")
    if not d:
        return
    store.set_menu(_key(d), _jdumps(obj))

def _slots(obj: dict) -> list[str]:
    step = int(obj.get("slot_minutes", 30))
    start = _parse_hhmm(obj.get("start", "09:00"))
    end = _parse_hhmm(obj.get("end", "21:30"))
    out=[]
    t=start
    while t<=end:
        out.append(_fmt_hhmm(t))
        t+=step
    return out

def _week_kb(week_start: date) -> InlineKeyboardMarkup:
    # 7 days, shown as: "Mon Dec 15"
    rows=[]
    for i in range(0, 7, 2):
        d1 = week_start + timedelta(days=i)
        d2 = week_start + timedelta(days=i+1)
        rows.append([
            InlineKeyboardButton(d1.strftime("%a %b %d"), callback_data=f"nsfw_av:day:{d1.strftime('%Y-%m-%d')}"),
            InlineKeyboardButton(d2.strftime("%a %b %d"), callback_data=f"nsfw_av:day:{d2.strftime('%Y-%m-%d')}"),
        ])
    nav = [
        InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_av:week:{(week_start - timedelta(days=7)).strftime('%Y-%m-%d')}"),
        InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_av:week:{(week_start + timedelta(days=7)).strftime('%Y-%m-%d')}"),
    ]
    rows.append(nav)
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")])
    return InlineKeyboardMarkup(rows)

def _times_kb(d: str, page: int = 0) -> InlineKeyboardMarkup:
    obj = _ensure_day(d)
    blocked=set(obj.get("blocked", []))
    slots=_slots(obj)

    # paged buttons (18 per page)
    per_page=18
    max_page=max(0, (len(slots)-1)//per_page) if slots else 0
    page=max(0, min(page, max_page))
    chunk=slots[page*per_page:(page+1)*per_page]

    rows=[]
    for i in range(0, len(chunk), 3):
        row=[]
        for t in chunk[i:i+3]:
            is_blocked = t in blocked
            label = f"🚫 {t}" if is_blocked else t
            row.append(InlineKeyboardButton(label, callback_data=f"nsfw_av:toggle:{d}:{t}:{page}"))
        rows.append(row)

    nav=[]
    if page>0:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"nsfw_av:times:{d}:{page-1}"))
    if page<max_page:
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"nsfw_av:times:{d}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back to days", callback_data=f"nsfw_av:week:{datetime.strptime(d,'%Y-%m-%d').date().strftime('%Y-%m-%d')}")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")])
    return InlineKeyboardMarkup(rows)

def _day_header(d: str, obj: dict) -> str:
    dt = datetime.strptime(d, "%Y-%m-%d").date()
    blocked = obj.get("blocked", [])
    return (
        f"🗓️ <b>{dt.strftime('%A, %B %d')}</b> (LA time)\n\n"
        "Tap times to block/unblock.\n"
        f"Blocked: <b>{len(blocked)}</b>"
    )

def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_availability registered (weekly 7-day view + full date header)")

    @app.on_callback_query(filters.regex(r"^nsfw_av:open$"))
    async def open_av(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        today=_today_la()
        week_start=today  # rolling start from today (not Monday)
        await cq.message.edit_text(
            "🗓️ <b>NSFW Availability</b> (LA time)\n\nPick a day to block/unblock time slots:",
            reply_markup=_week_kb(week_start),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_av:week:(\d{4}-\d{2}-\d{2})$"))
    async def open_week(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        d=(cq.data or "").split(":")[-1]
        week_start=datetime.strptime(d, "%Y-%m-%d").date()
        # clamp prev weeks not earlier than today-21d (optional safety)
        await cq.message.edit_text(
            "🗓️ <b>NSFW Availability</b> (LA time)\n\nPick a day to block/unblock time slots:",
            reply_markup=_week_kb(week_start),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_av:day:(\d{4}-\d{2}-\d{2})$"))
    async def open_day(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        d=(cq.data or "").split(":")[-1]
        obj=_ensure_day(d)
        await cq.message.edit_text(
            _day_header(d, obj),
            reply_markup=_times_kb(d, 0),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_av:times:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def times_page(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        _, _, d, p = (cq.data or "").split(":")
        page=int(p)
        obj=_ensure_day(d)
        await cq.message.edit_text(
            _day_header(d, obj),
            reply_markup=_times_kb(d, page),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_av:toggle:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):(\d+)$"))
    async def toggle_time(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        _, _, d, t, p = (cq.data or "").split(":")
        page=int(p)
        obj=_ensure_day(d)
        blocked=set(obj.get("blocked", []))
        if t in blocked:
            blocked.remove(t)
            await cq.answer("Unblocked ✅")
        else:
            blocked.add(t)
            await cq.answer("Blocked 🚫")
        obj["blocked"]=sorted(blocked)
        _save_day(obj)
        await cq.message.edit_text(
            _day_header(d, obj),
            reply_markup=_times_kb(d, page),
            disable_web_page_preview=True,
        )
