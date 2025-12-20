# handlers/nsfw_text_session_availability.py
import json
import logging
from datetime import datetime, timedelta, date, time
from typing import Dict, List, Optional, Tuple

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

from utils.menu_store import store

log = logging.getLogger(__name__)
TZ_LA = pytz.timezone("America/Los_Angeles")

# Defaults (you can change these if you want)
DEFAULT_OPEN = "09:00"
DEFAULT_CLOSE = "22:00"
SLOT_MINUTES = 30
SLOTS_PER_PAGE = 12  # for the "More ➡" paging


def _today_la() -> date:
    return datetime.now(TZ_LA).date()


def _date_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _avail_key(dstr: str) -> str:
    return f"NSFW_AVAIL:{dstr}"


def _range_key(user_id: int) -> str:
    return f"NSFW_AVAIL_RANGE:{user_id}"


def _jloads(raw: Optional[str], default):
    try:
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default


def _jdump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _get_day(dstr: str) -> Dict:
    obj = _jloads(store.get_menu(_avail_key(dstr)), {})
    if not isinstance(obj, dict):
        obj = {}
    obj.setdefault("open", DEFAULT_OPEN)
    obj.setdefault("close", DEFAULT_CLOSE)
    obj.setdefault("slot", SLOT_MINUTES)
    obj.setdefault("blocked", [])
    obj.setdefault("booked", [])  # optional; booking handler also checks its own store key
    # normalize blocked list
    if not isinstance(obj.get("blocked"), list):
        obj["blocked"] = []
    return obj


def _set_day(dstr: str, obj: Dict):
    store.set_menu(_avail_key(dstr), _jdump(obj))


def _parse_hm(hm: str) -> time:
    hh, mm = hm.split(":")
    return time(int(hh), int(mm))


def _slots_for_day(open_hm: str, close_hm: str, slot_minutes: int) -> List[str]:
    """Return list of slot start times in HH:MM, open inclusive, close exclusive."""
    o = _parse_hm(open_hm)
    c = _parse_hm(close_hm)
    start_dt = datetime(2000, 1, 1, o.hour, o.minute)
    end_dt = datetime(2000, 1, 1, c.hour, c.minute)
    slots = []
    cur = start_dt
    while cur < end_dt:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=slot_minutes)
    return slots


def _safe_edit(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    async def _do():
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except MessageNotModified:
            pass
    return _do()


def _week_days(start: date) -> List[date]:
    return [start + timedelta(days=i) for i in range(7)]


def _week_keyboard(week_start: date, today: date) -> InlineKeyboardMarkup:
    days = _week_days(week_start)
    rows = []

    # 2-column day grid
    for i in range(0, 6, 2):
        d1, d2 = days[i], days[i + 1]
        rows.append([
            InlineKeyboardButton(d1.strftime("%a %b %d"), callback_data=f"nsfw_av:day:{_date_str(d1)}:p0"),
            InlineKeyboardButton(d2.strftime("%a %b %d"), callback_data=f"nsfw_av:day:{_date_str(d2)}:p0"),
        ])
    rows.append([InlineKeyboardButton(days[6].strftime("%a %b %d"), callback_data=f"nsfw_av:day:{_date_str(days[6])}:p0")])

    # Nav: rolling pages of 7 days
    prev_start = week_start - timedelta(days=7)
    next_start = week_start + timedelta(days=7)

    prev_btn = InlineKeyboardButton("⬅ Prev", callback_data=f"nsfw_av:week:{_date_str(prev_start)}") if prev_start >= today else InlineKeyboardButton(" ", callback_data="noop")
    next_btn = InlineKeyboardButton("Next ➡", callback_data=f"nsfw_av:week:{_date_str(next_start)}")

    rows.append([prev_btn, next_btn])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")])
    return InlineKeyboardMarkup(rows)


def _day_keyboard(d: date, page: int, blocked: set, picking: Optional[Dict]) -> InlineKeyboardMarkup:
    dstr = _date_str(d)
    day_obj = _get_day(dstr)
    slots = _slots_for_day(day_obj["open"], day_obj["close"], int(day_obj["slot"]))

    # paging
    start_i = page * SLOTS_PER_PAGE
    end_i = min(len(slots), start_i + SLOTS_PER_PAGE)
    view = slots[start_i:end_i]

    rows = []
    # 2-column grid of time slots
    for i in range(0, len(view), 2):
        left = view[i]
        right = view[i + 1] if i + 1 < len(view) else None

        def _btn_label(hm: str) -> str:
            # ✅ available, ⛔ blocked
            return ("⛔ " if hm in blocked else "✅ ") + datetime.strptime(hm, "%H:%M").strftime("%-I:%M %p")

        row = [
            InlineKeyboardButton(_btn_label(left), callback_data=f"nsfw_av:slot:{dstr}:{left}:p{page}")
        ]
        if right:
            row.append(InlineKeyboardButton(_btn_label(right), callback_data=f"nsfw_av:slot:{dstr}:{right}:p{page}"))
        rows.append(row)

    # paging controls
    nav = []
    if start_i > 0:
        nav.append(InlineKeyboardButton("⬅ More", callback_data=f"nsfw_av:day:{dstr}:p{page-1}"))
    if end_i < len(slots):
        nav.append(InlineKeyboardButton("More ➡", callback_data=f"nsfw_av:day:{dstr}:p{page+1}"))
    if nav:
        rows.append(nav)

    # range / bulk controls
    if picking and picking.get("date") == dstr and picking.get("mode") == "pick_end":
        rows.append([InlineKeyboardButton("❌ Cancel range", callback_data="nsfw_av:range_cancel")])
    else:
        rows.append([InlineKeyboardButton("📌 Block a range (pick start→end)", callback_data=f"nsfw_av:range_start:{dstr}")])

    rows.append([
        InlineKeyboardButton("⛔ Block all day", callback_data=f"nsfw_av:allday:{dstr}"),
        InlineKeyboardButton("✅ Clear blocks", callback_data=f"nsfw_av:clear:{dstr}"),
    ])

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_av:week:{dstr}")])
    return InlineKeyboardMarkup(rows)


async def _render_week(cq: CallbackQuery, week_start: date):
    today = _today_la()
    if week_start < today:
        week_start = today
    text = (
        "📅 <b>NSFW Availability (LA time)</b>\n"
        f"<b>{week_start.strftime('%b %d')}</b> → <b>{(week_start + timedelta(days=6)).strftime('%b %d')}</b>\n\n"
        "Tap a day to edit blocks.\n"
        "✅ = available · ⛔ = blocked\n"
    )
    kb = _week_keyboard(week_start, today)
    await _safe_edit(cq, text, kb)
    await cq.answer()


async def _render_day(cq: CallbackQuery, d: date, page: int = 0):
    dstr = _date_str(d)
    obj = _get_day(dstr)
    blocked = set(obj.get("blocked", []))

    picking = _jloads(store.get_menu(_range_key(cq.from_user.id)), None)
    hint = ""
    if isinstance(picking, dict) and picking.get("date") == dstr and picking.get("mode") == "pick_end":
        start_hm = picking.get("start")
        if start_hm:
            hint = f"\n\n📌 <i>Range mode:</i> now pick an <b>end</b> time (start = {start_hm})."

    text = (
        f"🗓️ <b>{d.strftime('%A, %B %d')}</b> (LA time)\n"
        f"Open: <b>{obj['open']}</b> · Close: <b>{obj['close']}</b> · Slot: <b>{obj['slot']}m</b>\n"
        f"Blocked slots: <b>{len(blocked)}</b>\n\n"
        "Tap time slots to toggle, or use <b>Block a range</b> for windows like 9–12 then 1–5."
        f"{hint}"
    )
    kb = _day_keyboard(d, page, blocked, picking if isinstance(picking, dict) else None)
    await _safe_edit(cq, text, kb)
    await cq.answer()


def register(app: Client):
    log.info("✅ nsfw_text_session_availability registered (rolling 7-day + slot toggle + range blocking)")

    @app.on_callback_query(filters.regex(r"^noop$"))
    async def _noop(_, cq: CallbackQuery):
        await cq.answer()

    # Open from Roni Admin panel button (whatever callback you use there)
    @app.on_callback_query(filters.regex(r"^(nsfw_av:open|nsfw_text_session_availability:open|nsfw_text_session:availability|nsfw_text_session_availability_open)$"))
    async def open_av(_, cq: CallbackQuery):
        await _render_week(cq, _today_la())

    # Week view (week_start is any date; we clamp to today if needed)
    @app.on_callback_query(filters.regex(r"^nsfw_av:week:(\d{4}-\d{2}-\d{2})$"))
    async def week(_, cq: CallbackQuery):
        dstr = (cq.data or "").split(":")[-1]
        ws = datetime.strptime(dstr, "%Y-%m-%d").date()
        # If they pass a "day" date, still treat it as the week_start anchor
        await _render_week(cq, ws)

    # Day view + paging
    @app.on_callback_query(filters.regex(r"^nsfw_av:day:(\d{4}-\d{2}-\d{2}):p(\d+)$"))
    async def day(_, cq: CallbackQuery):
        parts = (cq.data or "").split(":")
        dstr = parts[2]
        p = int(parts[3][1:])  # "p0"
        d = datetime.strptime(dstr, "%Y-%m-%d").date()
        await _render_day(cq, d, p)

    # Toggle slot (or range-select)
    @app.on_callback_query(filters.regex(r"^nsfw_av:slot:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):p(\d+)$"))
    async def slot(_, cq: CallbackQuery):
        parts = (cq.data or "").split(":")
        dstr = parts[2]
        hm = parts[3]
        page = int(parts[4][1:])

        obj = _get_day(dstr)
        blocked = set(obj.get("blocked", []))

        picking = _jloads(store.get_menu(_range_key(cq.from_user.id)), None)
        if isinstance(picking, dict) and picking.get("date") == dstr and picking.get("mode") == "pick_end":
            # apply range
            start_hm = picking.get("start")
            if start_hm:
                slots = _slots_for_day(obj["open"], obj["close"], int(obj["slot"]))
                try:
                    a = slots.index(start_hm)
                    b = slots.index(hm)
                except ValueError:
                    # if mismatch, just cancel range safely
                    store.delete_menu(_range_key(cq.from_user.id))
                    await cq.answer("Range canceled (invalid selection).", show_alert=True)
                    await _render_day(cq, datetime.strptime(dstr, "%Y-%m-%d").date(), page)
                    return

                lo, hi = (a, b) if a <= b else (b, a)
                for t in slots[lo:hi + 1]:
                    blocked.add(t)

                obj["blocked"] = sorted(blocked)
                _set_day(dstr, obj)
                store.delete_menu(_range_key(cq.from_user.id))
                await cq.answer("✅ Range blocked.")
                await _render_day(cq, datetime.strptime(dstr, "%Y-%m-%d").date(), page)
                return

        # normal toggle
        if hm in blocked:
            blocked.remove(hm)
            await cq.answer("✅ Unblocked")
        else:
            blocked.add(hm)
            await cq.answer("⛔ Blocked")

        obj["blocked"] = sorted(blocked)
        _set_day(dstr, obj)

        await _render_day(cq, datetime.strptime(dstr, "%Y-%m-%d").date(), page)

    # Start range mode
    @app.on_callback_query(filters.regex(r"^nsfw_av:range_start:(\d{4}-\d{2}-\d{2})$"))
    async def range_start(_, cq: CallbackQuery):
        dstr = (cq.data or "").split(":")[-1]
        store.set_menu(_range_key(cq.from_user.id), _jdump({"date": dstr, "mode": "pick_start"}))
        await cq.answer("Tap a START time slot.")

    # Cancel range mode
    @app.on_callback_query(filters.regex(r"^nsfw_av:range_cancel$"))
    async def range_cancel(_, cq: CallbackQuery):
        store.delete_menu(_range_key(cq.from_user.id))
        await cq.answer("Range canceled.")

    # If in pick_start mode, first slot tap should set start and switch to pick_end.
    @app.on_callback_query(filters.regex(r"^nsfw_av:slot:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):p(\d+)$"))
    async def slot_pickstart_override(_, cq: CallbackQuery):
        # NOTE: this handler runs too, but we only act if mode == pick_start
        parts = (cq.data or "").split(":")
        dstr = parts[2]
        hm = parts[3]
        page = int(parts[4][1:])

        picking = _jloads(store.get_menu(_range_key(cq.from_user.id)), None)
        if isinstance(picking, dict) and picking.get("date") == dstr and picking.get("mode") == "pick_start":
            store.set_menu(_range_key(cq.from_user.id), _jdump({"date": dstr, "mode": "pick_end", "start": hm}))
            await cq.answer("Now tap an END time slot.")
            await _render_day(cq, datetime.strptime(dstr, "%Y-%m-%d").date(), page)
            return
        # otherwise do nothing here (normal slot() handler already handled toggle)

    # Block all day
    @app.on_callback_query(filters.regex(r"^nsfw_av:allday:(\d{4}-\d{2}-\d{2})$"))
    async def allday(_, cq: CallbackQuery):
        dstr = (cq.data or "").split(":")[-1]
        obj = _get_day(dstr)
        slots = _slots_for_day(obj["open"], obj["close"], int(obj["slot"]))
        obj["blocked"] = slots
        _set_day(dstr, obj)
        await cq.answer("⛔ Blocked all day.")
        await _render_day(cq, datetime.strptime(dstr, "%Y-%m-%d").date(), 0)

    # Clear blocks
    @app.on_callback_query(filters.regex(r"^nsfw_av:clear:(\d{4}-\d{2}-\d{2})$"))
    async def clear(_, cq: CallbackQuery):
        dstr = (cq.data or "").split(":")[-1]
        obj = _get_day(dstr)
        obj["blocked"] = []
        _set_day(dstr, obj)
        await cq.answer("✅ Cleared.")
        await _render_day(cq, datetime.strptime(dstr, "%Y-%m-%d").date(), 0)
