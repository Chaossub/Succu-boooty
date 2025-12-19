# handlers/nsfw_text_session_availability.py
import os
import json
import logging
from datetime import datetime, timedelta, date
from typing import List, Tuple, Optional

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

from utils.menu_store import store

log = logging.getLogger(__name__)
TZ_LA = pytz.timezone("America/Los_Angeles")

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "0")) or 0)

OPEN_HOUR = 9
CLOSE_HOUR = 22
SLOT_MINUTES = 30


def _avail_key(d: str) -> str:
    return f"NSFW_AVAIL:{d}"


def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default


def _jdump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _today_la() -> date:
    return datetime.now(TZ_LA).date()


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _min_to_hhmm(m: int) -> str:
    return f"{m//60:02d}:{m%60:02d}"


def _label_hhmm(hhmm: str) -> str:
    t = datetime(2000, 1, 1, int(hhmm[:2]), int(hhmm[3:]))
    try:
        return t.strftime("%-I:%M %p")
    except Exception:
        return t.strftime("%I:%M %p").lstrip("0")


def _normalize_windows(windows: List[List[str]]) -> List[List[str]]:
    parsed: List[Tuple[int, int]] = []
    for w in windows or []:
        if not (isinstance(w, (list, tuple)) and len(w) == 2):
            continue
        s, e = w[0], w[1]
        if not (isinstance(s, str) and isinstance(e, str) and ":" in s and ":" in e):
            continue
        sm, em = _to_minutes(s), _to_minutes(e)
        if em <= sm:
            continue
        parsed.append((sm, em))

    parsed.sort()
    merged: List[List[int]] = []
    for sm, em in parsed:
        if not merged or sm > merged[-1][1]:
            merged.append([sm, em])
        else:
            merged[-1][1] = max(merged[-1][1], em)

    return [[_min_to_hhmm(s), _min_to_hhmm(e)] for s, e in merged]


def _load_day_obj(d: str) -> dict:
    raw = store.get_menu(_avail_key(d))
    obj = _jloads(raw, {}) if raw else {}
    if not isinstance(obj, dict):
        obj = {}
    obj.setdefault("blocked_windows", [])
    if not isinstance(obj["blocked_windows"], list):
        obj["blocked_windows"] = []
    obj["blocked_windows"] = _normalize_windows(obj["blocked_windows"])
    return obj


def _save_day_obj(d: str, obj: dict):
    obj["blocked_windows"] = _normalize_windows(obj.get("blocked_windows", []))
    store.set_menu(_avail_key(d), _jdump(obj))


def _toggle_window(d: str, start: str, end: str):
    obj = _load_day_obj(d)
    wins = obj.get("blocked_windows", [])
    target = [start, end]
    if target in wins:
        wins = [w for w in wins if w != target]
    else:
        wins.append(target)
    obj["blocked_windows"] = wins
    _save_day_obj(d, obj)


def _add_window(d: str, start: str, end: str):
    obj = _load_day_obj(d)
    wins = obj.get("blocked_windows", [])
    wins.append([start, end])
    obj["blocked_windows"] = wins
    _save_day_obj(d, obj)


def _remove_window(d: str, start: str, end: str):
    obj = _load_day_obj(d)
    wins = [w for w in obj.get("blocked_windows", []) if not (w[0] == start and w[1] == end)]
    obj["blocked_windows"] = wins
    _save_day_obj(d, obj)


def _clear_all(d: str):
    obj = _load_day_obj(d)
    obj["blocked_windows"] = []
    _save_day_obj(d, obj)


def _slots_hhmm() -> List[str]:
    out = []
    m = OPEN_HOUR * 60
    end = CLOSE_HOUR * 60
    while m < end:
        out.append(_min_to_hhmm(m))
        m += SLOT_MINUTES
    return out


def _week_kb(ws: date) -> InlineKeyboardMarkup:
    days = [ws + timedelta(days=i) for i in range(7)]
    rows = []
    for i in range(0, 6, 2):
        rows.append([
            InlineKeyboardButton(days[i].strftime("%a %b %d"), callback_data=f"nsfw_av:day:{days[i]:%Y-%m-%d}"),
            InlineKeyboardButton(days[i+1].strftime("%a %b %d"), callback_data=f"nsfw_av:day:{days[i+1]:%Y-%m-%d}"),
        ])
    rows.append([InlineKeyboardButton(days[6].strftime("%a %b %d"), callback_data=f"nsfw_av:day:{days[6]:%Y-%m-%d}")])
    rows.append([
        InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_av:week:{(ws - timedelta(days=7)):%Y-%m-%d}"),
        InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_av:week:{(ws + timedelta(days=7)):%Y-%m-%d}"),
    ])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_portal:admin")])
    return InlineKeyboardMarkup(rows)


def _quick_windows() -> List[Tuple[str, str, str]]:
    # label, start, end
    return [
        ("🌅 Morning", f"{OPEN_HOUR:02d}:00", "12:00"),
        ("☀️ Afternoon", "12:00", "17:00"),
        ("🌙 Evening", "17:00", f"{CLOSE_HOUR:02d}:00"),
        ("🗓 Whole day", f"{OPEN_HOUR:02d}:00", f"{CLOSE_HOUR:02d}:00"),
    ]


def _day_kb(d: str, windows: List[List[str]]) -> InlineKeyboardMarkup:
    rows = []

    # Quick toggles (morning/afternoon/evening/whole-day)
    quick_row = []
    for label, s, e in _quick_windows():
        mark = " ✅" if [s, e] in windows else ""
        quick_row.append(InlineKeyboardButton(label + mark, callback_data=f"nsfw_av:toggle:{d}:{s}:{e}"))
    rows.append(quick_row[:2])
    rows.append(quick_row[2:])

    # Custom add
    rows.append([InlineKeyboardButton("➕ Block a custom time range", callback_data=f"nsfw_av:custom_start:{d}")])

    # Existing windows: removable
    if windows:
        rows.append([InlineKeyboardButton("🧱 Blocked windows (tap to remove):", callback_data="noop")])
        for w in windows:
            s, e = w[0], w[1]
            rows.append([InlineKeyboardButton(f"❌ {_label_hhmm(s)} – {_label_hhmm(e)}", callback_data=f"nsfw_av:rm:{d}:{s}:{e}")])

        rows.append([InlineKeyboardButton("🧽 Clear all blocks", callback_data=f"nsfw_av:clear:{d}")])
    else:
        rows.append([InlineKeyboardButton("No blocks set ✅", callback_data="noop")])

    rows.append([InlineKeyboardButton("⬅ Back to week", callback_data=f"nsfw_av:week:{d}")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_portal:admin")])
    return InlineKeyboardMarkup(rows)


def _start_picker_kb(d: str) -> InlineKeyboardMarkup:
    times = _slots_hhmm()
    rows = []
    row = []
    for i, t in enumerate(times, start=1):
        row.append(InlineKeyboardButton(_label_hhmm(t), callback_data=f"nsfw_av:custom_end:{d}:{t}"))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Cancel", callback_data=f"nsfw_av:day:{d}")])
    return InlineKeyboardMarkup(rows)


def _end_picker_kb(d: str, start: str) -> InlineKeyboardMarkup:
    start_m = _to_minutes(start)
    times = _slots_hhmm()
    # end must be > start
    end_times = [t for t in times if _to_minutes(t) > start_m]
    # allow end exactly at close
    end_times.append(f"{CLOSE_HOUR:02d}:00")

    rows = []
    row = []
    for i, t in enumerate(end_times, start=1):
        row.append(InlineKeyboardButton(_label_hhmm(t), callback_data=f"nsfw_av:add:{d}:{start}:{t}"))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_av:custom_start:{d}")])
    rows.append([InlineKeyboardButton("⬅ Cancel", callback_data=f"nsfw_av:day:{d}")])
    return InlineKeyboardMarkup(rows)


async def _safe_edit(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except MessageNotModified:
        pass


async def _open_week(cq: CallbackQuery, any_day: date):
    ws = _monday(any_day)
    text = "🛠 <b>NSFW Availability</b>\n\nPick a day to block/unblock time ranges (LA time):\n"
    text += f"{ws.strftime('%B %d')} → {(ws + timedelta(days=6)).strftime('%B %d')}"
    await _safe_edit(cq, text, _week_kb(ws))
    await cq.answer()


async def _open_day(cq: CallbackQuery, d: str):
    obj = _load_day_obj(d)
    windows = obj.get("blocked_windows", [])
    title = f"🗓 <b>{datetime.strptime(d, '%Y-%m-%d').strftime('%A, %B %d')}</b> (LA time)\n"
    title += f"Hours: <b>{_label_hhmm(f'{OPEN_HOUR:02d}:00')}</b> – <b>{_label_hhmm(f'{CLOSE_HOUR:02d}:00')}</b>\n\n"
    title += "Toggle quick blocks, add custom ranges, or remove existing windows."
    await _safe_edit(cq, title, _day_kb(d, windows))
    await cq.answer()


def register(app: Client):
    log.info("✅ nsfw_availability registered (multi-window blocks + custom ranges)")

    def _owner_only(cq: CallbackQuery) -> bool:
        return (cq.from_user and cq.from_user.id == OWNER_ID)

    @app.on_callback_query(filters.regex(r"^noop$"))
    async def noop(_, cq: CallbackQuery):
        await cq.answer()

    # Open (new + legacy aliases)
    @app.on_callback_query(filters.regex(r"^nsfw_av:open$"))
    async def av_open(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Admins only.", show_alert=True)
            return
        await _open_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^(nsfw_text_session_availability:open|nsfw_availability:open|availability_nsfw:open)$"))
    async def av_open_alias(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Admins only.", show_alert=True)
            return
        await _open_week(cq, _today_la())

    @app.on_callback_query(filters.regex(r"^nsfw_av:week:(\d{4}-\d{2}-\d{2})$"))
    async def av_week(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Admins only.", show_alert=True)
            return
        d = (cq.data or "").split(":")[-1]
        await _open_week(cq, datetime.strptime(d, "%Y-%m-%d").date())

    @app.on_callback_query(filters.regex(r"^nsfw_av:day:(\d{4}-\d{2}-\d{2})$"))
    async def av_day(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Admins only.", show_alert=True)
            return
        d = (cq.data or "").split(":")[-1]
        await _open_day(cq, d)

    # Toggle a quick window
    @app.on_callback_query(filters.regex(r"^nsfw_av:toggle:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):(\d{2}:\d{2})$"))
    async def av_toggle(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Admins only.", show_alert=True)
            return
        _, _, d, s, e = (cq.data or "").split(":")
        _toggle_window(d, s, e)
        await _open_day(cq, d)

    # Clear all
    @app.on_callback_query(filters.regex(r"^nsfw_av:clear:(\d{4}-\d{2}-\d{2})$"))
    async def av_clear(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Admins only.", show_alert=True)
            return
        d = (cq.data or "").split(":")[-1]
        _clear_all(d)
        await _open_day(cq, d)

    # Remove a specific window
    @app.on_callback_query(filters.regex(r"^nsfw_av:rm:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):(\d{2}:\d{2})$"))
    async def av_rm(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Admins only.", show_alert=True)
            return
        _, _, d, s, e = (cq.data or "").split(":")
        _remove_window(d, s, e)
        await _open_day(cq, d)

    # Custom range: pick start
    @app.on_callback_query(filters.regex(r"^nsfw_av:custom_start:(\d{4}-\d{2}-\d{2})$"))
    async def av_custom_start(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Admins only.", show_alert=True)
            return
        d = (cq.data or "").split(":")[-1]
        text = f"➕ <b>Block custom range</b>\n\nPick a <b>start</b> time for {datetime.strptime(d, '%Y-%m-%d').strftime('%A, %B %d')} (LA time):"
        await _safe_edit(cq, text, _start_picker_kb(d))
        await cq.answer()

    # Custom range: pick end (after start)
    @app.on_callback_query(filters.regex(r"^nsfw_av:custom_end:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2})$"))
    async def av_custom_end(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Admins only.", show_alert=True)
            return
        _, _, d, start = (cq.data or "").split(":")
        text = f"➕ <b>Block custom range</b>\n\nStart: <b>{_label_hhmm(start)}</b>\nPick an <b>end</b> time:"
        await _safe_edit(cq, text, _end_picker_kb(d, start))
        await cq.answer()

    # Custom range: add window
    @app.on_callback_query(filters.regex(r"^nsfw_av:add:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2}):(\d{2}:\d{2})$"))
    async def av_add(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Admins only.", show_alert=True)
            return
        _, _, d, s, e = (cq.data or "").split(":")
        _add_window(d, s, e)
        await _open_day(cq, d)
