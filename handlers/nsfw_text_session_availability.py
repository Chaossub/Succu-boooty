# handlers/nsfw_text_session_availability.py
"""
Owner-only availability + blocking panel for NSFW texting sessions (LA time).

Stores per date:
  NSFW_AVAIL:<yyyymmdd> = {
    "on": True/False,
    "windows": [["09:00","12:00"], ...],  # multiple allowed
    "blocks":  [["13:00","14:00"], ...],  # multiple allowed
  }

Also stores bookings under NSFW_BOOKINGS:<yyyymmdd> (created by booking handler).

UI:
- Week picker (Prev/Next week)
- Date detail:
  - Toggle day ON/OFF
  - Add availability window (pick start -> pick end) (multiple)
  - Block 30 / 60 (pick start)
  - Block entire day
  - Clear blocks / Clear windows / Clear all
  - View bookings for date + Cancel booking buttons
"""

import json
import logging
from datetime import datetime, timedelta, time as dtime

import pytz
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.menu_store import store

log = logging.getLogger(__name__)

TZ = pytz.timezone("America/Los_Angeles")
RONI_OWNER_ID = 6964994611


# ---------- storage helpers ----------

def _jget(key: str, default):
    try:
        raw = store.get_menu(key)
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default


def _jset(key: str, obj) -> None:
    store.set_menu(key, json.dumps(obj, ensure_ascii=False))


def _avail_key(yyyymmdd: str) -> str:
    return f"NSFW_AVAIL:{yyyymmdd}"


def _bookings_key(yyyymmdd: str) -> str:
    return f"NSFW_BOOKINGS:{yyyymmdd}"


def _booking_id_key(booking_id: str) -> str:
    return f"NSFW_BOOK_ID:{booking_id}"


def _admin_state_key() -> str:
    return "NSFW_AVAIL_ADMIN_STATE"


def _parse_date(yyyymmdd: str) -> datetime:
    return datetime.strptime(yyyymmdd, "%Y%m%d")


def _today_local() -> datetime:
    return datetime.now(TZ)


def _week_start(dt: datetime) -> datetime:
    d = dt.date()
    start = d - timedelta(days=d.weekday())
    return datetime.combine(start, dtime(0, 0))


def _weekday_default_hours(yyyymmdd: str) -> tuple[str, str]:
    wd = _parse_date(yyyymmdd).weekday()
    if wd == 5:  # Sat
        return "09:00", "21:00"
    return "09:00", "22:00"


def _load_avail(yyyymmdd: str) -> dict:
    d = _jget(_avail_key(yyyymmdd), {})
    if not isinstance(d, dict):
        d = {}
    d.setdefault("on", True)
    d.setdefault("windows", [])
    d.setdefault("blocks", [])
    return d


def _save_avail(yyyymmdd: str, d: dict) -> None:
    _jset(_avail_key(yyyymmdd), d)


def _load_bookings(yyyymmdd: str) -> list[dict]:
    items = _jget(_bookings_key(yyyymmdd), [])
    return items if isinstance(items, list) else []


def _fmt_week_day(dt: datetime) -> str:
    return dt.strftime("%a %b %d")


def _fmt_day(dt: datetime) -> str:
    return dt.strftime("%A, %B %d")


def _fmt_time_12(hhmm: str) -> str:
    return datetime.strptime(hhmm, "%H%M").strftime("%I:%M %p").lstrip("0")


def _to_hhmm_colon(hhmm: str) -> str:
    return f"{hhmm[:2]}:{hhmm[2:]}"


def _time_options_for_day(yyyymmdd: str) -> list[str]:
    # Build 30-minute grid across business hours for that day
    bh0, bh1 = _weekday_default_hours(yyyymmdd)
    day0 = TZ.localize(_parse_date(yyyymmdd))
    start = day0.replace(hour=int(bh0[:2]), minute=int(bh0[3:5]))
    end = day0.replace(hour=int(bh1[:2]), minute=int(bh1[3:5]))
    out: list[str] = []
    cur = start
    step = timedelta(minutes=30)
    while cur <= end:
        out.append(cur.strftime("%H%M"))
        cur += step
    return out


# ---------- UI builders ----------

def _week_kb(week_start: datetime) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for i in range(7):
        day = week_start.date() + timedelta(days=i)
        yyyymmdd = day.strftime("%Y%m%d")
        label = _fmt_week_day(datetime.combine(day, dtime(0, 0)))
        row.append(InlineKeyboardButton(f"📅 {label}", callback_data=f"nsfw_avail:day:{yyyymmdd}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    prev_w = (week_start - timedelta(days=7)).date().strftime("%Y%m%d")
    next_w = (week_start + timedelta(days=7)).date().strftime("%Y%m%d")
    rows.append(
        [
            InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_avail:week:{prev_w}"),
            InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_avail:week:{next_w}"),
        ]
    )
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")])
    return InlineKeyboardMarkup(rows)


def _day_summary_text(yyyymmdd: str) -> str:
    d = _load_avail(yyyymmdd)
    on = d.get("on", True)
    windows = d.get("windows") or []
    blocks = d.get("blocks") or []

    bh0, bh1 = _weekday_default_hours(yyyymmdd)
    header = f"🗓 <b>{_fmt_day(_parse_date(yyyymmdd))}</b>\n\n"
    header += f"Status: <b>{'ON' if on else 'OFF (blocked day)'}</b>\n"
    header += f"Business hours: <b>{bh0}–{bh1}</b> (LA)\n\n"

    def fmt_ranges(ranges):
        if not ranges:
            return "• none"
        lines = []
        for r in ranges:
            if isinstance(r, list) and len(r) == 2:
                lines.append(f"• {r[0]}–{r[1]}")
        return "\n".join(lines) if lines else "• none"

    txt = header
    txt += "<b>Availability windows</b>\n"
    if windows:
        txt += fmt_ranges(windows) + "\n\n"
    else:
        txt += "• <i>none set (defaults to business hours)</i>\n\n"

    txt += "<b>Blocked ranges</b>\n"
    txt += fmt_ranges(blocks) + "\n\n"

    return txt


def _day_kb(yyyymmdd: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    rows.append(
        [
            InlineKeyboardButton("✅ Toggle ON/OFF", callback_data=f"nsfw_avail:toggle:{yyyymmdd}"),
            InlineKeyboardButton("📌 View bookings", callback_data=f"nsfw_avail:bookings:{yyyymmdd}"),
        ]
    )
    rows.append([InlineKeyboardButton("➕ Add availability window", callback_data=f"nsfw_avail:addwin:{yyyymmdd}")])
    rows.append(
        [
            InlineKeyboardButton("⛔ Block 30", callback_data=f"nsfw_avail:blockpick:{yyyymmdd}:30"),
            InlineKeyboardButton("⛔ Block 60", callback_data=f"nsfw_avail:blockpick:{yyyymmdd}:60"),
        ]
    )
    rows.append([InlineKeyboardButton("🚫 Block entire day", callback_data=f"nsfw_avail:blockday:{yyyymmdd}")])

    rows.append(
        [
            InlineKeyboardButton("🧹 Clear blocks", callback_data=f"nsfw_avail:clearblocks:{yyyymmdd}"),
            InlineKeyboardButton("🧹 Clear windows", callback_data=f"nsfw_avail:clearwins:{yyyymmdd}"),
        ]
    )
    rows.append([InlineKeyboardButton("🧹 Clear ALL (windows+blocks)", callback_data=f"nsfw_avail:clearall:{yyyymmdd}")])

    rows.append([InlineKeyboardButton("⬅ Back to week", callback_data=f"nsfw_avail:week:{yyyymmdd}")])
    return InlineKeyboardMarkup(rows)


def _time_grid_kb(prefix_cb: str, yyyymmdd: str, back_cb: str) -> InlineKeyboardMarkup:
    times = _time_options_for_day(yyyymmdd)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    # skip the last time (closing time) as a start time
    for hhmm in times[:-1]:
        row.append(InlineKeyboardButton(_fmt_time_12(hhmm), callback_data=f"{prefix_cb}:{yyyymmdd}:{hhmm}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def _end_grid_kb(yyyymmdd: str, start_hhmm: str) -> InlineKeyboardMarkup:
    times = _time_options_for_day(yyyymmdd)
    # end must be after start by at least 30m
    start_idx = max(0, times.index(start_hhmm))
    possible = times[start_idx + 1:]  # at least 30 min later

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for hhmm in possible:
        row.append(InlineKeyboardButton(_fmt_time_12(hhmm), callback_data=f"nsfw_avail:endwin:{yyyymmdd}:{start_hhmm}:{hhmm}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_avail:addwin:{yyyymmdd}")])
    return InlineKeyboardMarkup(rows)


def _bookings_text(yyyymmdd: str) -> tuple[str, InlineKeyboardMarkup]:
    items = _load_bookings(yyyymmdd)
    if not items:
        txt = f"📌 <b>Bookings for {_fmt_day(_parse_date(yyyymmdd))}</b>\n\n• none"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_avail:day:{yyyymmdd}")]])
        return txt, kb

    lines = [f"📌 <b>Bookings for {_fmt_day(_parse_date(yyyymmdd))}</b>\n"]
    rows: list[list[InlineKeyboardButton]] = []
    for b in items:
        bid = b.get("id", "")
        status = (b.get("status") or "").lower()
        if not bid:
            continue
        try:
            start = datetime.strptime(b["start"], "%Y-%m-%d %H:%M")
            end = datetime.strptime(b["end"], "%Y-%m-%d %H:%M")
            start_str = start.strftime("%I:%M %p").lstrip("0")
            end_str = end.strftime("%I:%M %p").lstrip("0")
        except Exception:
            start_str = b.get("start", "?")
            end_str = b.get("end", "?")

        who = b.get("name") or "User"
        if b.get("username"):
            who += f" (@{b['username']})"

        lines.append(f"• <b>{start_str}–{end_str}</b> — {who} — <i>{status}</i>")
        rows.append([InlineKeyboardButton(f"❌ Cancel {start_str}", callback_data=f"nsfw_avail:cancelbk:{bid}")])

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_avail:day:{yyyymmdd}")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ---------- admin state ----------

def _set_admin_state(d: dict) -> None:
    _jset(_admin_state_key(), d)


def _get_admin_state() -> dict:
    st = _jget(_admin_state_key(), {})
    return st if isinstance(st, dict) else {}


# ---------- handlers ----------

def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_text_session_availability registered")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:open$"))
    async def open_panel(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💕", show_alert=True)
            return
        if cq.message and cq.message.chat and cq.message.chat.type != ChatType.PRIVATE:
            await cq.answer("Open this in DM 💕", show_alert=True)
            return

        ws = _week_start(_today_local())
        txt = (
            "🗓 <b>NSFW Availability (Roni)</b>\n\n"
            "Pick a date to set availability windows and blocks.\n"
            "If no windows are set, it defaults to your business hours.\n\n"
            "Times are Los Angeles time."
        )
        await cq.message.edit_text(txt, reply_markup=_week_kb(ws), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:week:(\d{8})$"))
    async def week_nav(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        ws = _week_start(_parse_date(yyyymmdd))
        txt = (
            "🗓 <b>NSFW Availability (Roni)</b>\n\n"
            "Pick a date to edit.\n"
            "Times are Los Angeles time."
        )
        await cq.message.edit_text(txt, reply_markup=_week_kb(ws), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:day:(\d{8})$"))
    async def day_open(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        txt = _day_summary_text(yyyymmdd)
        await cq.message.edit_text(txt, reply_markup=_day_kb(yyyymmdd), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:toggle:(\d{8})$"))
    async def toggle_day(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        d = _load_avail(yyyymmdd)
        d["on"] = not bool(d.get("on", True))
        _save_avail(yyyymmdd, d)
        txt = _day_summary_text(yyyymmdd)
        await cq.message.edit_text(txt, reply_markup=_day_kb(yyyymmdd), disable_web_page_preview=True)
        await cq.answer("Updated 💕")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:blockday:(\d{8})$"))
    async def block_day(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        d = _load_avail(yyyymmdd)
        d["on"] = False
        _save_avail(yyyymmdd, d)
        txt = _day_summary_text(yyyymmdd)
        await cq.message.edit_text(txt, reply_markup=_day_kb(yyyymmdd), disable_web_page_preview=True)
        await cq.answer("Day blocked 💕")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clearblocks:(\d{8})$"))
    async def clear_blocks(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        d = _load_avail(yyyymmdd)
        d["blocks"] = []
        _save_avail(yyyymmdd, d)
        await cq.message.edit_text(_day_summary_text(yyyymmdd), reply_markup=_day_kb(yyyymmdd), disable_web_page_preview=True)
        await cq.answer("Blocks cleared 💕")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clearwins:(\d{8})$"))
    async def clear_wins(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        d = _load_avail(yyyymmdd)
        d["windows"] = []
        _save_avail(yyyymmdd, d)
        await cq.message.edit_text(_day_summary_text(yyyymmdd), reply_markup=_day_kb(yyyymmdd), disable_web_page_preview=True)
        await cq.answer("Windows cleared 💕")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clearall:(\d{8})$"))
    async def clear_all(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        d = _load_avail(yyyymmdd)
        d["windows"] = []
        d["blocks"] = []
        d["on"] = True
        _save_avail(yyyymmdd, d)
        await cq.message.edit_text(_day_summary_text(yyyymmdd), reply_markup=_day_kb(yyyymmdd), disable_web_page_preview=True)
        await cq.answer("Cleared 💕")

    # ---- add availability window (start -> end) ----

    @app.on_callback_query(filters.regex(r"^nsfw_avail:addwin:(\d{8})$"))
    async def add_win(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        _set_admin_state({"mode": "pick_win_start", "date": yyyymmdd})
        txt = (
            f"➕ <b>Add availability window</b>\n\n"
            f"Date: <b>{_fmt_day(_parse_date(yyyymmdd))}</b>\n\n"
            "Pick a <b>start</b> time (LA)."
        )
        kb = _time_grid_kb("nsfw_avail:winstart", yyyymmdd, f"nsfw_avail:day:{yyyymmdd}")
        await cq.message.edit_text(txt, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:winstart:(\d{8}):(\d{4})$"))
    async def win_start(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        _, _, yyyymmdd, start_hhmm = cq.data.split(":")
        _set_admin_state({"mode": "pick_win_end", "date": yyyymmdd, "start": start_hhmm})

        txt = (
            f"➕ <b>Add availability window</b>\n\n"
            f"Date: <b>{_fmt_day(_parse_date(yyyymmdd))}</b>\n"
            f"Start: <b>{_fmt_time_12(start_hhmm)}</b>\n\n"
            "Pick an <b>end</b> time (LA)."
        )
        await cq.message.edit_text(txt, reply_markup=_end_grid_kb(yyyymmdd, start_hhmm), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:endwin:(\d{8}):(\d{4}):(\d{4})$"))
    async def win_end(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        _, _, yyyymmdd, start_hhmm, end_hhmm = cq.data.split(":")
        start_s = _to_hhmm_colon(start_hhmm)
        end_s = _to_hhmm_colon(end_hhmm)

        d = _load_avail(yyyymmdd)
        d.setdefault("windows", [])
        d["windows"].append([start_s, end_s])
        d["on"] = True
        _save_avail(yyyymmdd, d)
        _set_admin_state({})

        await cq.message.edit_text(_day_summary_text(yyyymmdd), reply_markup=_day_kb(yyyymmdd), disable_web_page_preview=True)
        await cq.answer("Window added 💕")

    # ---- block picker (start -> duration) ----

    @app.on_callback_query(filters.regex(r"^nsfw_avail:blockpick:(\d{8}):(30|60)$"))
    async def block_pick(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        parts = cq.data.split(":")
        yyyymmdd = parts[2]
        mins = int(parts[3])

        _set_admin_state({"mode": "pick_block_start", "date": yyyymmdd, "mins": mins})
        txt = (
            f"⛔ <b>Block {mins} minutes</b>\n\n"
            f"Date: <b>{_fmt_day(_parse_date(yyyymmdd))}</b>\n\n"
            "Pick a start time (LA)."
        )
        kb = _time_grid_kb("nsfw_avail:blockstart", yyyymmdd, f"nsfw_avail:day:{yyyymmdd}")
        await cq.message.edit_text(txt, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:blockstart:(\d{8}):(\d{4})$"))
    async def block_start(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        _, _, yyyymmdd, start_hhmm = cq.data.split(":")
        st = _get_admin_state()
        mins = int(st.get("mins", 30))

        day0 = TZ.localize(_parse_date(yyyymmdd))
        start_dt = day0.replace(hour=int(start_hhmm[:2]), minute=int(start_hhmm[2:]))
        end_dt = start_dt + timedelta(minutes=mins)

        start_s = start_dt.strftime("%H:%M")
        end_s = end_dt.strftime("%H:%M")

        d = _load_avail(yyyymmdd)
        d.setdefault("blocks", [])
        d["blocks"].append([start_s, end_s])
        _save_avail(yyyymmdd, d)
        _set_admin_state({})

        await cq.message.edit_text(_day_summary_text(yyyymmdd), reply_markup=_day_kb(yyyymmdd), disable_web_page_preview=True)
        await cq.answer("Blocked 💕")

    # ---- bookings + cancel booking (owner) ----

    @app.on_callback_query(filters.regex(r"^nsfw_avail:bookings:(\d{8})$"))
    async def view_bookings(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        txt, kb = _bookings_text(yyyymmdd)
        await cq.message.edit_text(txt, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:cancelbk:([a-f0-9]+)$"))
    async def cancel_booking(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💕", show_alert=True)
            return
        booking_id = cq.data.split(":")[-1]
        yyyymmdd = store.get_menu(_booking_id_key(booking_id)) or ""
        if not yyyymmdd:
            await cq.answer("Booking not found.", show_alert=True)
            return

        items = _load_bookings(yyyymmdd)
        target = next((b for b in items if b.get("id") == booking_id), None)
        if not target:
            await cq.answer("Booking not found.", show_alert=True)
            return

        new_items = [b for b in items if b.get("id") != booking_id]
        _jset(_bookings_key(yyyymmdd), new_items)
        store.set_menu(_booking_id_key(booking_id), "")

        # try notify user (best effort)
        try:
            uid = int(target.get("user_id"))
            await cq._client.send_message(
                uid,
                "❌ <b>Your session request was cancelled</b> 💕\n\n"
                "If you want to reschedule, just book again from the assistant.\n\n"
                "🚫 <b>NO meetups</b> — online/texting only.",
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        # refresh bookings view
        txt, kb = _bookings_text(yyyymmdd)
        await cq.message.edit_text(txt, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer("Cancelled 💕")

