# handlers/nsfw_text_session_booking.py
import json
import logging
from datetime import datetime, timedelta, date

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

from utils.menu_store import store

log = logging.getLogger(__name__)
TZ_LA = pytz.timezone("America/Los_Angeles")

DEFAULT_OPEN_HOUR = 9
DEFAULT_CLOSE_HOUR = 22
SLOT_MINUTES = 30


def _avail_key(d: str) -> str:
    return f"NSFW_AVAIL:{d}"


def _bookings_key(d: str) -> str:
    return f"NSFW_BOOKINGS:{d}"


def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default


def _jdumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _today_la() -> date:
    return datetime.now(TZ_LA).date()


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _safe_hm(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _slot_id(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _load_day_obj(d: str) -> dict:
    raw = store.get_menu(_avail_key(d))
    obj = _jloads(raw, {}) if raw else {}
    if not isinstance(obj, dict):
        obj = {}
    obj.setdefault("open_hour", DEFAULT_OPEN_HOUR)
    obj.setdefault("close_hour", DEFAULT_CLOSE_HOUR)
    obj.setdefault("blocked", [])
    return obj


def _load_bookings(d: str) -> list:
    raw = store.get_menu(_bookings_key(d))
    arr = _jloads(raw, []) if raw else []
    return arr if isinstance(arr, list) else []


def _save_bookings(d: str, arr: list) -> None:
    store.save_menu(_bookings_key(d), _jdumps(arr))


def _week_kb(week_start: date) -> InlineKeyboardMarkup:
    days = [week_start + timedelta(days=i) for i in range(7)]
    rows = []
    for i in range(0, 6, 2):
        rows.append([
            InlineKeyboardButton(days[i].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[i]:%Y-%m-%d}"),
            InlineKeyboardButton(days[i+1].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[i+1]:%Y-%m-%d}"),
        ])
    rows.append([InlineKeyboardButton(days[6].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[6]:%Y-%m-%d}")])
    rows.append([
        InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_book:week:{(week_start - timedelta(days=7)):%Y-%m-%d}"),
        InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_book:week:{(week_start + timedelta(days=7)):%Y-%m-%d}"),
    ])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)


async def _safe_edit(msg, **kwargs):
    try:
        return await msg.edit_text(**kwargs)
    except MessageNotModified:
        return msg


async def _render_week(cq: CallbackQuery, any_day: date):
    ws = _monday(any_day)
    await _safe_edit(
        cq.message,
        text=(
            "💞 <b>Book a private NSFW texting session</b>\n\n"
            "Pick a day (LA time):\n"
            f"Week of <b>{ws.strftime('%B %d')}</b> → <b>{(ws + timedelta(days=6)).strftime('%B %d')}</b>"
        ),
        reply_markup=_week_kb(ws),
        disable_web_page_preview=True,
    )
    await cq.answer()


def _slots_for_day(d_str: str) -> list[tuple[str, str]]:
    """
    Returns list of (slot_id, label) within open/close.
    Slot id is 'HH:MM' in 24h.
    """
    obj = _load_day_obj(d_str)
    open_h = int(obj.get("open_hour", DEFAULT_OPEN_HOUR))
    close_h = int(obj.get("close_hour", DEFAULT_CLOSE_HOUR))

    base = datetime.strptime(d_str, "%Y-%m-%d").replace(tzinfo=TZ_LA)
    start = base.replace(hour=open_h, minute=0)
    end = base.replace(hour=close_h, minute=0)

    out = []
    cur = start
    while cur < end:
        out.append((_slot_id(cur), _safe_hm(cur)))
        cur += timedelta(minutes=SLOT_MINUTES)
    return out


def _time_kb(d_str: str, page: int = 0) -> InlineKeyboardMarkup:
    obj = _load_day_obj(d_str)
    blocked = set(obj.get("blocked", []) or [])
    bookings = _load_bookings(d_str)
    booked = set([b.get("slot") for b in bookings if isinstance(b, dict)])

    slots = _slots_for_day(d_str)

    # Pagination (Telegram keyboards get huge fast)
    per_page = 18  # 9 rows x 2 cols
    start = page * per_page
    end = start + per_page
    page_slots = slots[start:end]

    rows = []
    for i in range(0, len(page_slots), 2):
        row = []
        for j in range(2):
            if i + j >= len(page_slots):
                break
            sid, label = page_slots[i + j]
            if sid in blocked:
                txt = f"⛔ {label}"
                cb = "nsfw_book:nope"
            elif sid in booked:
                txt = f"🔒 {label}"
                cb = "nsfw_book:nope"
            else:
                txt = f"✅ {label}"
                cb = f"nsfw_book:pick:{d_str}:{sid}"
            row.append(InlineKeyboardButton(txt, callback_data=cb))
        rows.append(row)

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅ More", callback_data=f"nsfw_book:times:{d_str}:{page-1}"))
    if end < len(slots):
        nav.append(InlineKeyboardButton("More ➡", callback_data=f"nsfw_book:times:{d_str}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back to week", callback_data=f"nsfw_book:week:{d_str}")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)


def register(app: Client):
    log.info("✅ nsfw_text_session_booking registered (time picker + blocked-window respect)")

    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def open_new(_, cq: CallbackQuery):
        await _render_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^(nsfw_text_session_booking:open|nsfw_text_session:open|book_nsfw:open|booking_nsfw:open)$"))
    async def open_legacy(_, cq: CallbackQuery):
        await _render_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^nsfw_book:week:(\d{4}-\d{2}-\d{2})$"))
    async def week(_, cq: CallbackQuery):
        d = (cq.data or "").split(":")[-1]
        await _render_week(cq, datetime.strptime(d, "%Y-%m-%d").date())

    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(\d{4}-\d{2}-\d{2})$"))
    async def day(_, cq: CallbackQuery):
        d = (cq.data or "").split(":")[-1]
        dt = datetime.strptime(d, "%Y-%m-%d").date()

        obj = _load_day_obj(d)
        blocked = obj.get("blocked", []) or []
        bookings = _load_bookings(d)

        await _safe_edit(
            cq.message,
            text=(
                f"🗓️ <b>{dt.strftime('%A, %B %d')}</b> (LA time)\n\n"
                f"Blocked slots: <b>{len(blocked)}</b>\n"
                f"Booked slots: <b>{len(bookings)}</b>\n\n"
                "Pick an available time:"
            ),
            reply_markup=_time_kb(d, page=0),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:times:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def times(_, cq: CallbackQuery):
        parts = (cq.data or "").split(":")
        d = parts[2]
        page = int(parts[3])
        dt = datetime.strptime(d, "%Y-%m-%d").date()
        await _safe_edit(
            cq.message,
            text=(f"🗓️ <b>{dt.strftime('%A, %B %d')}</b> (LA time)\n\nPick an available time:"),
            reply_markup=_time_kb(d, page=page),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:pick:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2})$"))
    async def pick(_, cq: CallbackQuery):
        d, sid = (cq.data or "").split(":")[2], (cq.data or "").split(":")[3]
        u = cq.from_user
        if not u:
            await cq.answer("Try again.", show_alert=True)
            return

        # Re-check blocked/booked at click-time
        obj = _load_day_obj(d)
        blocked = set(obj.get("blocked", []) or [])
        if sid in blocked:
            await cq.answer("That time is blocked.", show_alert=True)
            return

        bookings = _load_bookings(d)
        if any(isinstance(b, dict) and b.get("slot") == sid for b in bookings):
            await cq.answer("That time was just booked.", show_alert=True)
            return

        # Save booking
        bookings.append({
            "user_id": u.id,
            "username": u.username or "",
            "name": (u.first_name or "").strip(),
            "slot": sid,
            "created_iso": datetime.utcnow().isoformat(),
        })
        _save_bookings(d, bookings)

        await _safe_edit(
            cq.message,
            text=(
                "✅ <b>Booked!</b>\n\n"
                f"Day: <code>{d}</code>\n"
                f"Time: <b>{sid}</b> (LA)\n\n"
                "Roni will reach out to confirm details. 💗"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]
            ]),
            disable_web_page_preview=True,
        )
        await cq.answer("Booked!")

    @app.on_callback_query(filters.regex(r"^nsfw_book:nope$"))
    async def nope(_, cq: CallbackQuery):
        await cq.answer("That slot isn’t available.", show_alert=True)
