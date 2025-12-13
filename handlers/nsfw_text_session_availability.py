# handlers/nsfw_text_session_availability.py
"""
Owner-only: set availability for NSFW texting sessions (LA time).

Data per date (YYYYMMDD) stored in menu_store as JSON:
  NSFW_AVAIL:<YYYYMMDD> = {
    "on": true,
    "windows": [["09:00","12:00"], ["15:00","18:00"]],  # optional; if empty -> business hours default
    "blocks": [["13:00","13:30"], ["19:00","20:00"]]    # optional
  }

Business hours default:
  Mon–Fri: 09:00–22:00
  Sat:     09:00–21:00
  Sun:     09:00–22:00
"""

import json
import logging
from datetime import datetime, timedelta, time as dtime

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.menu_store import store

log = logging.getLogger(__name__)

TZ = pytz.timezone("America/Los_Angeles")
RONI_OWNER_ID = 6964994611


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


def _k_avail(yyyymmdd: str) -> str:
    return f"NSFW_AVAIL:{yyyymmdd}"


def _k_ctx(user_id: int) -> str:
    return f"NSFW_AVAIL_CTX:{user_id}"


def _parse_date(yyyymmdd: str) -> datetime:
    return datetime.strptime(yyyymmdd, "%Y%m%d")


def _fmt_day(yyyymmdd: str) -> str:
    return _parse_date(yyyymmdd).strftime("%A, %b %d")


def _weekday_default_hours(yyyymmdd: str) -> tuple[str, str]:
    # Monday=0 ... Sunday=6
    wd = _parse_date(yyyymmdd).weekday()
    if wd == 5:  # Saturday
        return "09:00", "21:00"
    # Mon–Fri + Sun
    return "09:00", "22:00"


def _norm_hhmm(s: str) -> str:
    # accepts "9:00" etc (best effort)
    try:
        dt = datetime.strptime(s.strip(), "%H:%M")
        return dt.strftime("%H:%M")
    except Exception:
        # fallback: "0900" style
        s = s.strip().replace(":", "")
        if len(s) == 4 and s.isdigit():
            return f"{s[:2]}:{s[2:]}"
        return "09:00"


def _overlaps(a0: str, a1: str, b0: str, b1: str) -> bool:
    # string times "HH:MM"
    def m(x): return int(x[:2]) * 60 + int(x[3:5])
    return m(a0) < m(b1) and m(b0) < m(a1)


def _load(yyyymmdd: str) -> dict:
    d = _jget(_k_avail(yyyymmdd), {})
    if not isinstance(d, dict):
        d = {}
    d.setdefault("on", True)
    d.setdefault("windows", [])
    d.setdefault("blocks", [])
    return d


def _save(yyyymmdd: str, data: dict) -> None:
    data.setdefault("on", True)
    data.setdefault("windows", [])
    data.setdefault("blocks", [])
    _jset(_k_avail(yyyymmdd), data)


def _describe_day(yyyymmdd: str) -> str:
    d = _load(yyyymmdd)
    bh0, bh1 = _weekday_default_hours(yyyymmdd)

    # windows
    windows = d.get("windows") or []
    if windows:
        win_txt = "\n".join([f"• {w[0]}–{w[1]}" for w in windows if isinstance(w, list) and len(w) == 2])
        windows_line = f"✅ <b>Availability windows</b>:\n{win_txt}"
    else:
        windows_line = f"✅ <b>Availability windows</b>: none set (using business hours)"

    # blocks
    blocks = d.get("blocks") or []
    if blocks:
        blk_txt = "\n".join([f"• {b[0]}–{b[1]}" for b in blocks if isinstance(b, list) and len(b) == 2])
        blocks_line = f"⛔ <b>Blocked</b>:\n{blk_txt}"
    else:
        blocks_line = "⛔ <b>Blocked</b>: none"

    on_line = "🟢 <b>Day is ON</b> (bookable)" if d.get("on") else "🔴 <b>Day is OFF</b> (not bookable)"

    return (
        f"📅 <b>{_fmt_day(yyyymmdd)}</b>\n"
        f"{on_line}\n\n"
        f"🕘 <b>Business hours</b>: {bh0}–{bh1} (default)\n\n"
        f"{windows_line}\n\n"
        f"{blocks_line}\n\n"
        "Choose what to do:"
    )


def _week_start_local(dt: datetime) -> datetime:
    # start on Monday
    d = dt.date()
    start = d - timedelta(days=d.weekday())
    return datetime.combine(start, dtime(0, 0))


def _build_week_kb(week_start: datetime) -> InlineKeyboardMarkup:
    # 7 days buttons, with explicit dates like your screenshot
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i in range(7):
        day = week_start.date() + timedelta(days=i)
        yyyymmdd = day.strftime("%Y%m%d")
        label = datetime.combine(day, dtime(0, 0)).strftime("%a %b %d")
        row.append(InlineKeyboardButton(f"{label}", callback_data=f"nsfw_avail:day:{yyyymmdd}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    prev_w = (week_start - timedelta(days=7)).strftime("%Y%m%d")
    next_w = (week_start + timedelta(days=7)).strftime("%Y%m%d")

    rows.append([
        InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_avail:week:{prev_w}"),
        InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_avail:week:{next_w}"),
    ])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")])
    return InlineKeyboardMarkup(rows)


def _time_picker(yyyymmdd: str, mode: str, page: int = 0) -> InlineKeyboardMarkup:
    """
    mode:
      win_start / win_end
      blk_start / blk_end
    page: 0.. (shows 12 options per page)
    """
    bh0, bh1 = _weekday_default_hours(yyyymmdd)

    start_m = int(bh0[:2]) * 60 + int(bh0[3:5])
    end_m = int(bh1[:2]) * 60 + int(bh1[3:5])

    # 30-minute increments
    times: list[str] = []
    m = start_m
    while m <= end_m:
        hh = m // 60
        mm = m % 60
        times.append(f"{hh:02d}:{mm:02d}")
        m += 30

    per_page = 12
    total_pages = max(1, (len(times) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    chunk = times[page * per_page: (page + 1) * per_page]

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for t in chunk:
        row.append(InlineKeyboardButton(t, callback_data=f"nsfw_avail:pick:{yyyymmdd}:{mode}:{t}:{page}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅ Earlier", callback_data=f"nsfw_avail:tp:{yyyymmdd}:{mode}:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Later ➡", callback_data=f"nsfw_avail:tp:{yyyymmdd}:{mode}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_avail:day:{yyyymmdd}")])
    return InlineKeyboardMarkup(rows)


def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_text_session_availability registered")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:open$"))
    async def open_panel(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can use this 💕", show_alert=True)
            return

        now = datetime.now(TZ)
        ws = _week_start_local(now)
        text = (
            "🗓 <b>NSFW Availability (Roni)</b>\n\n"
            "Business hours are the default (LA time).\n"
            "You can add availability windows (multiple), block ranges, or turn a day off.\n\n"
            "Pick a date:"
        )
        await cq.message.edit_text(text, reply_markup=_build_week_kb(ws), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:week:(\d{8})$"))
    async def week_nav(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        ws = _week_start_local(_parse_date(yyyymmdd))
        text = (
            "🗓 <b>NSFW Availability (Roni)</b>\n\n"
            "Pick a date:"
        )
        await cq.message.edit_text(text, reply_markup=_build_week_kb(ws), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:day:(\d{8})$"))
    async def day_detail(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        text = _describe_day(yyyymmdd)

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("➕ Add availability window", callback_data=f"nsfw_avail:win_start:{yyyymmdd}")],
                [InlineKeyboardButton("🚫 Block a time range", callback_data=f"nsfw_avail:blk_start:{yyyymmdd}")],
                [InlineKeyboardButton("🔴 Block entire day", callback_data=f"nsfw_avail:off:{yyyymmdd}")],
                [InlineKeyboardButton("🧹 Clear blocks (this date)", callback_data=f"nsfw_avail:clear_blocks:{yyyymmdd}")],
                [InlineKeyboardButton("✅ Clear availability windows (use business hours)", callback_data=f"nsfw_avail:clear_windows:{yyyymmdd}")],
                [InlineKeyboardButton("🧨 Clear EVERYTHING (this date)", callback_data=f"nsfw_avail:clear_all:{yyyymmdd}")],
                [InlineKeyboardButton("📅 Pick another date", callback_data=f"nsfw_avail:week:{yyyymmdd}")],
                [InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")],
            ]
        )

        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ---- Turn day OFF (entire day blocked) ----
    @app.on_callback_query(filters.regex(r"^nsfw_avail:off:(\d{8})$"))
    async def day_off(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        d = _load(yyyymmdd)
        d["on"] = False
        _save(yyyymmdd, d)
        await cq.answer("Day turned OFF ✅")
        await day_detail(_, cq)

    # ---- Clear blocks ----
    @app.on_callback_query(filters.regex(r"^nsfw_avail:clear_blocks:(\d{8})$"))
    async def clear_blocks(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        d = _load(yyyymmdd)
        d["blocks"] = []
        d["on"] = True
        _save(yyyymmdd, d)
        await cq.answer("Blocks cleared ✅")
        await day_detail(_, cq)

    # ---- Clear windows ----
    @app.on_callback_query(filters.regex(r"^nsfw_avail:clear_windows:(\d{8})$"))
    async def clear_windows(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        d = _load(yyyymmdd)
        d["windows"] = []
        d["on"] = True
        _save(yyyymmdd, d)
        await cq.answer("Availability windows cleared ✅")
        await day_detail(_, cq)

    # ---- Clear everything ----
    @app.on_callback_query(filters.regex(r"^nsfw_avail:clear_all:(\d{8})$"))
    async def clear_all(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        _save(yyyymmdd, {"on": True, "windows": [], "blocks": []})
        await cq.answer("Cleared ✅")
        await day_detail(_, cq)

    # ---- Add window flow ----
    @app.on_callback_query(filters.regex(r"^nsfw_avail:win_start:(\d{8})$"))
    async def win_start(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        _jset(_k_ctx(cq.from_user.id), {"date": yyyymmdd, "mode": "win_start"})
        await cq.message.edit_text(
            f"🪟 <b>Add availability window</b>\n\nPick the <b>start</b> time for {_fmt_day(yyyymmdd)} (LA time):",
            reply_markup=_time_picker(yyyymmdd, "win_start", 0),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:blk_start:(\d{8})$"))
    async def blk_start(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        yyyymmdd = cq.data.split(":")[-1]
        _jset(_k_ctx(cq.from_user.id), {"date": yyyymmdd, "mode": "blk_start"})
        await cq.message.edit_text(
            f"🚫 <b>Block a time range</b>\n\nPick the <b>start</b> time for {_fmt_day(yyyymmdd)} (LA time):",
            reply_markup=_time_picker(yyyymmdd, "blk_start", 0),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:tp:(\d{8}):(win_start|win_end|blk_start|blk_end):(\d+)$"))
    async def time_page(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return
        _, _, yyyymmdd, mode, page = cq.data.split(":")
        await cq.message.edit_text(
            "Pick a time (LA time):",
            reply_markup=_time_picker(yyyymmdd, mode, int(page)),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:pick:(\d{8}):(win_start|win_end|blk_start|blk_end):(\d{2}:\d{2}):(\d+)$"))
    async def time_pick(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return

        _, _, yyyymmdd, mode, hhmm, page = cq.data.split(":")
        hhmm = _norm_hhmm(hhmm)

        ctx = _jget(_k_ctx(cq.from_user.id), {}) or {}
        ctx["date"] = yyyymmdd
        ctx["last_pick"] = hhmm

        if mode == "win_start":
            ctx["mode"] = "win_end"
            ctx["win_start"] = hhmm
            _jset(_k_ctx(cq.from_user.id), ctx)
            await cq.message.edit_text(
                f"🪟 Add availability window\n\nStart: <b>{hhmm}</b>\nNow pick the <b>end</b> time:",
                reply_markup=_time_picker(yyyymmdd, "win_end", int(page)),
                disable_web_page_preview=True,
            )
            await cq.answer()
            return

        if mode == "blk_start":
            ctx["mode"] = "blk_end"
            ctx["blk_start"] = hhmm
            _jset(_k_ctx(cq.from_user.id), ctx)
            await cq.message.edit_text(
                f"🚫 Block a time range\n\nStart: <b>{hhmm}</b>\nNow pick the <b>end</b> time:",
                reply_markup=_time_picker(yyyymmdd, "blk_end", int(page)),
                disable_web_page_preview=True,
            )
            await cq.answer()
            return

        # win_end / blk_end -> finalize
        d = _load(yyyymmdd)
        d["on"] = True

        if mode == "win_end":
            start = _norm_hhmm(str(ctx.get("win_start", "09:00")))
            end = hhmm
            if start == end:
                await cq.answer("Start and end can’t be the same 💕", show_alert=True)
                return
            # keep windows clean / non-overlapping (best effort)
            windows = d.get("windows") or []
            windows.append([start, end])
            # remove any totally invalid overlaps? (simple)
            cleaned: list[list[str]] = []
            for w in windows:
                if not (isinstance(w, list) and len(w) == 2):
                    continue
                a0, a1 = _norm_hhmm(w[0]), _norm_hhmm(w[1])
                if a0 == a1:
                    continue
                cleaned.append([a0, a1])
            d["windows"] = cleaned
            _save(yyyymmdd, d)
            _jset(_k_ctx(cq.from_user.id), {})
            await cq.answer("Window added ✅")
            await day_detail(_, cq)
            return

        if mode == "blk_end":
            start = _norm_hhmm(str(ctx.get("blk_start", "09:00")))
            end = hhmm
            if start == end:
                await cq.answer("Start and end can’t be the same 💕", show_alert=True)
                return
            blocks = d.get("blocks") or []
            blocks.append([start, end])
            cleaned: list[list[str]] = []
            for b in blocks:
                if not (isinstance(b, list) and len(b) == 2):
                    continue
                b0, b1 = _norm_hhmm(b[0]), _norm_hhmm(b[1])
                if b0 == b1:
                    continue
                cleaned.append([b0, b1])
            d["blocks"] = cleaned
            _save(yyyymmdd, d)
            _jset(_k_ctx(cq.from_user.id), {})
            await cq.answer("Blocked ✅")
            await day_detail(_, cq)
            return

        await cq.answer()
