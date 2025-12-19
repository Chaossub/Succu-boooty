# handlers/nsfw_text_session_availability.py
import json
import logging
from datetime import datetime, timedelta, date

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import MessageNotModified

from utils.menu_store import store

log = logging.getLogger(__name__)
TZ_LA = pytz.timezone("America/Los_Angeles")

OWNER_ID = 6964994611  # you already use env in other files; leaving static here is ok

DEFAULT_OPEN_HOUR = 9
DEFAULT_CLOSE_HOUR = 22
SLOT_MINUTES = 30


# ────────────── storage ──────────────
def _avail_key(d: str) -> str:
    return f"NSFW_AVAIL:{d}"


def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default


def _jdumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _today_la() -> date:
    return datetime.now(TZ_LA).date()


def _load_day_obj(d_str: str) -> dict:
    raw = store.get_menu(_avail_key(d_str))
    obj = _jloads(raw, {}) if raw else {}
    if not isinstance(obj, dict):
        obj = {}
    obj.setdefault("open_hour", DEFAULT_OPEN_HOUR)
    obj.setdefault("close_hour", DEFAULT_CLOSE_HOUR)
    obj.setdefault("blocked", [])  # list of "HH:MM" slot ids
    return obj


def _save_day_obj(d_str: str, obj: dict) -> None:
    store.save_menu(_avail_key(d_str), _jdumps(obj))


# ────────────── helpers ──────────────
def _is_owner_or_admin(user_id: int) -> bool:
    # match your existing pattern: owner can edit.
    # if you have a SUPER_ADMINS set elsewhere, you can expand this later.
    return user_id == OWNER_ID


def _slot_id(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _label(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _slots_for_day(d_str: str) -> list[tuple[str, str]]:
    obj = _load_day_obj(d_str)
    open_h = int(obj.get("open_hour", DEFAULT_OPEN_HOUR))
    close_h = int(obj.get("close_hour", DEFAULT_CLOSE_HOUR))

    base = TZ_LA.localize(datetime.strptime(d_str, "%Y-%m-%d"))
    cur = base.replace(hour=open_h, minute=0)
    end = base.replace(hour=close_h, minute=0)

    out = []
    while cur < end:
        out.append((_slot_id(cur), _label(cur)))
        cur += timedelta(minutes=SLOT_MINUTES)
    return out


async def _safe_edit(msg, **kwargs):
    try:
        return await msg.edit_text(**kwargs)
    except MessageNotModified:
        return msg


# ────────────── UI: rolling 7-day window ──────────────
def _week_kb(start_day: date) -> InlineKeyboardMarkup:
    """
    7 days at a time starting from start_day (LA). Never shows days < today.
    """
    today = _today_la()
    if start_day < today:
        start_day = today

    days = [start_day + timedelta(days=i) for i in range(7)]
    rows = []

    # 2-column layout (3 rows + last single)
    for i in range(0, 6, 2):
        rows.append([
            InlineKeyboardButton(days[i].strftime("%a %b %d"), callback_data=f"nsfw_av:day:{days[i]:%Y-%m-%d}"),
            InlineKeyboardButton(days[i + 1].strftime("%a %b %d"), callback_data=f"nsfw_av:day:{days[i+1]:%Y-%m-%d}"),
        ])
    rows.append([InlineKeyboardButton(days[6].strftime("%a %b %d"), callback_data=f"nsfw_av:day:{days[6]:%Y-%m-%d}")])

    nav = []
    prev_start = start_day - timedelta(days=7)
    next_start = start_day + timedelta(days=7)

    # Only show Prev if it would not go into the past
    if prev_start >= today:
        nav.append(InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_av:week:{prev_start:%Y-%m-%d}"))
    nav.append(InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_av:week:{next_start:%Y-%m-%d}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")])
    return InlineKeyboardMarkup(rows)


async def _open_week(cq: CallbackQuery, start_day: date):
    today = _today_la()
    if start_day < today:
        start_day = today

    end_day = start_day + timedelta(days=6)
    await _safe_edit(
        cq.message,
        text=(
            "📅 <b>NSFW Availability</b> (LA time)\n"
            f"7-day window: <b>{start_day.strftime('%b %d')}</b> → <b>{end_day.strftime('%b %d')}</b>\n\n"
            "Tap a day to edit hours + block times.\n"
            "Tip: Tap time slots to block/unblock multiple windows (ex: 9–12 and 1–5)."
        ),
        reply_markup=_week_kb(start_day),
        disable_web_page_preview=True,
    )
    await cq.answer()


# ────────────── UI: day editor ──────────────
def _day_kb(d_str: str) -> InlineKeyboardMarkup:
    obj = _load_day_obj(d_str)
    open_h = int(obj.get("open_hour", DEFAULT_OPEN_HOUR))
    close_h = int(obj.get("close_hour", DEFAULT_CLOSE_HOUR))
    blocked = obj.get("blocked", []) or []

    rows = [
        [
            InlineKeyboardButton("🕘 Open -1h", callback_data=f"nsfw_av:open:{d_str}:-1"),
            InlineKeyboardButton(f"Open: {open_h:02d}:00", callback_data="nsfw_av:noop"),
            InlineKeyboardButton("🕘 Open +1h", callback_data=f"nsfw_av:open:{d_str}:1"),
        ],
        [
            InlineKeyboardButton("🕙 Close -1h", callback_data=f"nsfw_av:close:{d_str}:-1"),
            InlineKeyboardButton(f"Close: {close_h:02d}:00", callback_data="nsfw_av:noop"),
            InlineKeyboardButton("🕙 Close +1h", callback_data=f"nsfw_av:close:{d_str}:1"),
        ],
        [
            InlineKeyboardButton(f"⛔ Block times ({len(blocked)})", callback_data=f"nsfw_av:blockgrid:{d_str}:0")
        ],
        [
            InlineKeyboardButton("⬅ Back to 7-day view", callback_data=f"nsfw_av:week:{_today_la():%Y-%m-%d}")
        ],
    ]
    return InlineKeyboardMarkup(rows)


def _block_grid_kb(d_str: str, page: int) -> InlineKeyboardMarkup:
    """
    Toggle block/unblock by tapping slots.
    """
    obj = _load_day_obj(d_str)
    blocked = set(obj.get("blocked", []) or [])
    slots = _slots_for_day(d_str)

    per_page = 18  # 9 rows x 2 columns
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
            is_blocked = sid in blocked
            txt = f"⛔ {label}" if is_blocked else f"✅ {label}"
            cb = f"nsfw_av:toggle:{d_str}:{sid}:{page}"
            row.append(InlineKeyboardButton(txt, callback_data=cb))
        rows.append(row)

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅ More", callback_data=f"nsfw_av:blockgrid:{d_str}:{page-1}"))
    if end < len(slots):
        nav.append(InlineKeyboardButton("More ➡", callback_data=f"nsfw_av:blockgrid:{d_str}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton("🚫 Block all day", callback_data=f"nsfw_av:block_all:{d_str}:{page}"),
        InlineKeyboardButton("✅ Clear blocks", callback_data=f"nsfw_av:clear_blocks:{d_str}:{page}"),
    ])

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_av:day:{d_str}")])
    return InlineKeyboardMarkup(rows)


async def _render_day(cq: CallbackQuery, d_str: str):
    dt = datetime.strptime(d_str, "%Y-%m-%d").date()
    obj = _load_day_obj(d_str)

    await _safe_edit(
        cq.message,
        text=(
            f"🗓️ <b>{dt.strftime('%A, %B %d')}</b> (LA time)\n\n"
            f"Open: <b>{int(obj.get('open_hour', DEFAULT_OPEN_HOUR)):02d}:00</b>\n"
            f"Close: <b>{int(obj.get('close_hour', DEFAULT_CLOSE_HOUR)):02d}:00</b>\n"
            f"Blocked slots: <b>{len(obj.get('blocked', []) or [])}</b>\n\n"
            "Tap <b>Block times</b> to toggle time slots on/off.\n"
            "You can block multiple windows (ex: 9–12 and 1–5)."
        ),
        reply_markup=_day_kb(d_str),
        disable_web_page_preview=True,
    )
    await cq.answer()


async def _render_block_grid(cq: CallbackQuery, d_str: str, page: int):
    dt = datetime.strptime(d_str, "%Y-%m-%d").date()
    obj = _load_day_obj(d_str)
    blocked = obj.get("blocked", []) or []

    await _safe_edit(
        cq.message,
        text=(
            f"🧩 <b>Block time slots</b>\n"
            f"Day: <b>{dt.strftime('%A, %B %d')}</b> (LA time)\n"
            f"Blocked: <b>{len(blocked)}</b>\n\n"
            "Tap a slot to toggle it:\n"
            "✅ = available, ⛔ = blocked"
        ),
        reply_markup=_block_grid_kb(d_str, page),
        disable_web_page_preview=True,
    )
    await cq.answer()


# ────────────── register ──────────────
def register(app: Client):
    log.info("✅ nsfw_text_session_availability registered (rolling 7-day + slot toggle blocking)")

    # Open availability UI (new + legacy aliases)
    @app.on_callback_query(filters.regex(r"^nsfw_av:open$"))
    async def av_open(_, cq: CallbackQuery):
        if not _is_owner_or_admin(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        await _open_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^(nsfw_availability:open|nsfw_text_session_availability:open|nsfw_text_session:availability|nsfw_avail:open)$"))
    async def av_open_alias(_, cq: CallbackQuery):
        if not _is_owner_or_admin(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        await _open_week(cq, _today_la())

    # Week navigation (rolling start day)
    @app.on_callback_query(filters.regex(r"^nsfw_av:week:(\d{4}-\d{2}-\d{2})$"))
    async def av_week(_, cq: CallbackQuery):
        if not _is_owner_or_admin(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        d = (cq.data or "").split(":")[-1]
        start_day = datetime.strptime(d, "%Y-%m-%d").date()
        await _open_week(cq, start_day)

    # Day editor
    @app.on_callback_query(filters.regex(r"^nsfw_av:day:(\d{4}-\d{2}-\d{2})$"))
    async def av_day(_, cq: CallbackQuery):
        if not _is_owner_or_admin(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        d_str = (cq.data or "").split(":")[-1]

        # don’t allow editing past days
        if datetime.strptime(d_str, "%Y-%m-%d").date() < _today_la():
            await cq.answer("That day already passed.", show_alert=True)
            return

        await _render_day(cq, d_str)

    # Open/close hour adjust
    @app.on_callback_query(filters.regex(r"^nsfw_av:(open|close):(\d{4}-\d{2}-\d{2}):(-?1)$"))
    async def av_hours(_, cq: CallbackQuery):
        if not _is_owner_or_admin(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return

        _, kind, d_str, delta = (cq.data or "").split(":")
        delta = int(delta)

        obj = _load_day_obj(d_str)
        open_h = int(obj.get("open_hour", DEFAULT_OPEN_HOUR))
        close_h = int(obj.get("close_hour", DEFAULT_CLOSE_HOUR))

        if kind == "open":
            open_h = max(0, min(23, open_h + delta))
        else:
            close_h = max(0, min(23, close_h + delta))

        # keep sane ordering
        if close_h <= open_h:
            close_h = min(23, open_h + 1)

        obj["open_hour"] = open_h
        obj["close_hour"] = close_h

        # If hours changed, remove blocked slots outside new range
        slots = {sid for sid, _ in _slots_for_day(d_str)}
        obj["blocked"] = [sid for sid in (obj.get("blocked", []) or []) if sid in slots]

        _save_day_obj(d_str, obj)
        await _render_day(cq, d_str)

    # Block grid view (paged)
    @app.on_callback_query(filters.regex(r"^nsfw_av:blockgrid:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def av_blockgrid(_, cq: CallbackQuery):
        if not _is_owner_or_admin(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        parts = (cq.data or "").split(":")
        d_str = parts[2]
        page = int(parts[3])
        await _render_block_grid(cq, d_str, page)

    # Toggle a slot
    @app.on_callback_query(filters.regex(r"^nsfw_av:toggle:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):(\d+)$"))
    async def av_toggle(_, cq: CallbackQuery):
        if not _is_owner_or_admin(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return

        parts = (cq.data or "").split(":")
        d_str = parts[2]
        sid = parts[3]
        page = int(parts[4])

        obj = _load_day_obj(d_str)
        blocked = set(obj.get("blocked", []) or [])

        if sid in blocked:
            blocked.remove(sid)
        else:
            blocked.add(sid)

        # keep order stable by day slots order
        order = [s for s, _ in _slots_for_day(d_str)]
        obj["blocked"] = [s for s in order if s in blocked]

        _save_day_obj(d_str, obj)
        await _render_block_grid(cq, d_str, page)

    # Block all day (within open/close range)
    @app.on_callback_query(filters.regex(r"^nsfw_av:block_all:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def av_block_all(_, cq: CallbackQuery):
        if not _is_owner_or_admin(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        parts = (cq.data or "").split(":")
        d_str = parts[2]
        page = int(parts[3])

        obj = _load_day_obj(d_str)
        obj["blocked"] = [sid for sid, _ in _slots_for_day(d_str)]
        _save_day_obj(d_str, obj)

        await _render_block_grid(cq, d_str, page)

    # Clear blocks
    @app.on_callback_query(filters.regex(r"^nsfw_av:clear_blocks:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def av_clear(_, cq: CallbackQuery):
        if not _is_owner_or_admin(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        parts = (cq.data or "").split(":")
        d_str = parts[2]
        page = int(parts[3])

        obj = _load_day_obj(d_str)
        obj["blocked"] = []
        _save_day_obj(d_str, obj)

        await _render_block_grid(cq, d_str, page)

    @app.on_callback_query(filters.regex(r"^nsfw_av:noop$"))
    async def av_noop(_, cq: CallbackQuery):
        await cq.answer()
