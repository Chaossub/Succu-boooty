# handlers/nsfw_text_session_booking.py
import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

from utils.menu_store import store

log = logging.getLogger(__name__)
TZ_LA = pytz.timezone("America/Los_Angeles")

DEFAULT_OPEN = "09:00"
DEFAULT_CLOSE = "22:00"
SLOT_MINUTES = 30
SLOTS_PER_PAGE = 12

OWNER_ID = None  # set at register()


def _today_la() -> date:
    return datetime.now(TZ_LA).date()


def _dstr(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _avail_key(dstr: str) -> str:
    return f"NSFW_AVAIL:{dstr}"


def _book_key(dstr: str) -> str:
    return f"NSFW_BOOKINGS:{dstr}"


def _pick_key(user_id: int) -> str:
    return f"NSFW_BOOK_PICK:{user_id}"


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
    if not isinstance(obj.get("blocked"), list):
        obj["blocked"] = []
    return obj


def _slots_for_day(open_hm: str, close_hm: str, slot_minutes: int) -> List[str]:
    start_dt = datetime(2000, 1, 1, int(open_hm[:2]), int(open_hm[3:]))
    end_dt = datetime(2000, 1, 1, int(close_hm[:2]), int(close_hm[3:]))
    out = []
    cur = start_dt
    while cur < end_dt:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=slot_minutes)
    return out


def _safe_edit(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    async def _do():
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except MessageNotModified:
            pass
    return _do()


def _week_days(start: date) -> List[date]:
    return [start + timedelta(days=i) for i in range(7)]


def _week_kb(week_start: date, today: date) -> InlineKeyboardMarkup:
    days = _week_days(week_start)
    rows = []
    for i in range(0, 6, 2):
        rows.append([
            InlineKeyboardButton(days[i].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{_dstr(days[i])}:p0"),
            InlineKeyboardButton(days[i+1].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{_dstr(days[i+1])}:p0"),
        ])
    rows.append([InlineKeyboardButton(days[6].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{_dstr(days[6])}:p0")])

    prev_start = week_start - timedelta(days=7)
    next_start = week_start + timedelta(days=7)
    prev_btn = InlineKeyboardButton("⬅ Prev", callback_data=f"nsfw_book:week:{_dstr(prev_start)}") if prev_start >= today else InlineKeyboardButton(" ", callback_data="noop")
    next_btn = InlineKeyboardButton("Next ➡", callback_data=f"nsfw_book:week:{_dstr(next_start)}")
    rows.append([prev_btn, next_btn])

    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:open")])
    return InlineKeyboardMarkup(rows)


def _day_kb(d: date, page: int, slots_view: List[str]) -> InlineKeyboardMarkup:
    dstr = _dstr(d)
    rows = []
    for i in range(0, len(slots_view), 2):
        left = slots_view[i]
        right = slots_view[i + 1] if i + 1 < len(slots_view) else None

        def label(hm: str) -> str:
            return datetime.strptime(hm, "%H:%M").strftime("%-I:%M %p")

        row = [InlineKeyboardButton(f"🕒 {label(left)}", callback_data=f"nsfw_book:pick:{dstr}:{left}:p{page}")]
        if right:
            row.append(InlineKeyboardButton(f"🕒 {label(right)}", callback_data=f"nsfw_book:pick:{dstr}:{right}:p{page}"))
        rows.append(row)

    # paging
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅ More", callback_data=f"nsfw_book:day:{dstr}:p{page-1}"))
    if len(slots_view) == SLOTS_PER_PAGE:
        nav.append(InlineKeyboardButton("More ➡", callback_data=f"nsfw_book:day:{dstr}:p{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back to week", callback_data=f"nsfw_book:week:{dstr}")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:open")])
    return InlineKeyboardMarkup(rows)


def _dur_kb(dstr: str, hm: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("30m", callback_data=f"nsfw_book:dur:{dstr}:{hm}:30"),
            InlineKeyboardButton("60m", callback_data=f"nsfw_book:dur:{dstr}:{hm}:60"),
        ],
        [InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_book:day:{dstr}:p0")],
        [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:open")],
    ])


def _confirm_kb(dstr: str, hm: str, mins: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm booking", callback_data=f"nsfw_book:confirm:{dstr}:{hm}:{mins}")],
        [InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_book:dur:{dstr}:{hm}:{mins}")],
        [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:open")],
    ])


def _get_bookings(dstr: str) -> List[Dict]:
    raw = store.get_menu(_book_key(dstr))
    obj = _jloads(raw, [])
    return obj if isinstance(obj, list) else []


def _set_bookings(dstr: str, bookings: List[Dict]):
    store.set_menu(_book_key(dstr), _jdump(bookings))


def _is_taken(bookings: List[Dict], hm: str) -> bool:
    for b in bookings:
        if isinstance(b, dict) and b.get("start") == hm:
            return True
    return False


async def _render_week(cq: CallbackQuery, week_start: date):
    today = _today_la()
    if week_start < today:
        week_start = today

    text = (
        "💞 <b>Book a private NSFW texting session</b>\n\n"
        f"Pick a day (LA time):\n<b>{week_start.strftime('%b %d')}</b> → <b>{(week_start + timedelta(days=6)).strftime('%b %d')}</b>"
    )
    kb = _week_kb(week_start, today)
    await _safe_edit(cq, text, kb)
    await cq.answer()


async def _render_day(cq: CallbackQuery, d: date, page: int):
    dstr = _dstr(d)
    day = _get_day(dstr)
    blocked = set(day.get("blocked", []))
    slots = _slots_for_day(day["open"], day["close"], int(day["slot"]))

    bookings = _get_bookings(dstr)
    available = [s for s in slots if (s not in blocked and not _is_taken(bookings, s))]

    start_i = page * SLOTS_PER_PAGE
    end_i = min(len(available), start_i + SLOTS_PER_PAGE)
    view = available[start_i:end_i]

    text = (
        f"🗓️ <b>{d.strftime('%A, %B %d')}</b> (LA time)\n"
        f"Open: <b>{day['open']}</b> · Close: <b>{day['close']}</b>\n\n"
        f"Available slots: <b>{len(available)}</b>\n"
        "Pick a start time:"
    )

    kb = _day_kb(d, page, view)
    await _safe_edit(cq, text, kb)
    await cq.answer()


def register(app: Client):
    global OWNER_ID
    OWNER_ID = int(__import__("os").environ.get("OWNER_ID", __import__("os").environ.get("BOT_OWNER_ID", "6964994611")))

    log.info("✅ nsfw_text_session_booking registered (rolling 7-day + booking respects blocks)")

    @app.on_callback_query(filters.regex(r"^noop$"))
    async def _noop(_, cq: CallbackQuery):
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def open_new(_, cq: CallbackQuery):
        await _render_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^(nsfw_text_session_booking:open|nsfw_text_session:open|book_nsfw:open|booking_nsfw:open)$"))
    async def open_legacy(_, cq: CallbackQuery):
        await _render_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^nsfw_book:week:(\d{4}-\d{2}-\d{2})$"))
    async def week(_, cq: CallbackQuery):
        dstr = (cq.data or "").split(":")[-1]
        ws = datetime.strptime(dstr, "%Y-%m-%d").date()
        await _render_week(cq, ws)

    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(\d{4}-\d{2}-\d{2}):p(\d+)$"))
    async def day(_, cq: CallbackQuery):
        parts = (cq.data or "").split(":")
        dstr = parts[2]
        page = int(parts[3][1:])
        d = datetime.strptime(dstr, "%Y-%m-%d").date()
        await _render_day(cq, d, page)

    @app.on_callback_query(filters.regex(r"^nsfw_book:pick:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):p(\d+)$"))
    async def pick(_, cq: CallbackQuery):
        parts = (cq.data or "").split(":")
        dstr = parts[2]
        hm = parts[3]
        text = (
            f"🕒 <b>Pick duration</b>\n\n"
            f"Day: <b>{dstr}</b>\nStart: <b>{datetime.strptime(hm, '%H:%M').strftime('%-I:%M %p')}</b> (LA time)"
        )
        await _safe_edit(cq, text, _dur_kb(dstr, hm))
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:dur:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):(\d+)$"))
    async def dur(_, cq: CallbackQuery):
        parts = (cq.data or "").split(":")
        dstr = parts[2]
        hm = parts[3]
        mins = int(parts[4])

        text = (
            f"✅ <b>Confirm booking</b>\n\n"
            f"Day: <b>{dstr}</b>\n"
            f"Start: <b>{datetime.strptime(hm, '%H:%M').strftime('%-I:%M %p')}</b>\n"
            f"Duration: <b>{mins} minutes</b>\n\n"
            "Tap confirm to book this slot."
        )
        await _safe_edit(cq, text, _confirm_kb(dstr, hm, mins))
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:confirm:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):(\d+)$"))
    async def confirm(_, cq: CallbackQuery):
        parts = (cq.data or "").split(":")
        dstr = parts[2]
        hm = parts[3]
        mins = int(parts[4])

        # re-check availability
        day = _get_day(dstr)
        blocked = set(day.get("blocked", []))
        if hm in blocked:
            await cq.answer("That time is blocked. Pick another.", show_alert=True)
            await _render_day(cq, datetime.strptime(dstr, "%Y-%m-%d").date(), 0)
            return

        bookings = _get_bookings(dstr)
        if _is_taken(bookings, hm):
            await cq.answer("That time was just booked. Pick another.", show_alert=True)
            await _render_day(cq, datetime.strptime(dstr, "%Y-%m-%d").date(), 0)
            return

        entry = {
            "user_id": cq.from_user.id,
            "name": (cq.from_user.first_name or ""),
            "username": (cq.from_user.username or ""),
            "start": hm,
            "mins": mins,
            "ts": datetime.now(TZ_LA).isoformat(),
        }
        bookings.append(entry)
        _set_bookings(dstr, bookings)

        # notify owner
        try:
            who = f"{cq.from_user.first_name or ''}".strip()
            if cq.from_user.username:
                who += f" (@{cq.from_user.username})"
            msg = (
                "📩 <b>New NSFW session booking</b>\n\n"
                f"Day: <b>{dstr}</b>\n"
                f"Start: <b>{datetime.strptime(hm, '%H:%M').strftime('%-I:%M %p')}</b> (LA)\n"
                f"Duration: <b>{mins}m</b>\n"
                f"User: <b>{who}</b> · <code>{cq.from_user.id}</code>"
            )
            await app.send_message(OWNER_ID, msg)
        except Exception:
            log.exception("Failed to notify owner of booking")

        text = (
            "✅ <b>Booked!</b>\n\n"
            f"Day: <b>{dstr}</b>\n"
            f"Start: <b>{datetime.strptime(hm, '%H:%M').strftime('%-I:%M %p')}</b>\n"
            f"Duration: <b>{mins} minutes</b>\n\n"
            "Roni will reach out to you if anything changes 💕"
        )
        await _safe_edit(cq, text, InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:open")]
        ]))
        await cq.answer("Booked ✅")
