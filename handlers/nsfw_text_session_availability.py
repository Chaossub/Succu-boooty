import os
from datetime import datetime, timedelta
from typing import List, Tuple

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.menu_store import store
from utils.nsfw_store import (
    TZ,
    add_allowed_window,
    clear_allowed_for_date,
    clear_blocks_for_date,
    get_allowed_for_date,
    get_blocks_for_date,
    get_business_hours_for_weekday,
    set_blocks_for_date,
)

RONI_OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))


def _tz():
    return pytz.timezone(TZ)


def _owner_only(cq: CallbackQuery) -> bool:
    return bool(cq.from_user and cq.from_user.id == RONI_OWNER_ID)


def _dt_to_yyyymmdd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _yyyymmdd_to_local_day(yyyymmdd: str) -> datetime:
    tz = _tz()
    return tz.localize(datetime(int(yyyymmdd[0:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]), 0, 0, 0))


def _pretty_date_label(day_dt: datetime) -> str:
    return day_dt.strftime("%a %b %d").replace(" 0", " ")


def _min_from_hhmm(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm_from_min(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _date_picker_kb(week: int) -> InlineKeyboardMarkup:
    tz = _tz()
    base = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    start = base + timedelta(days=week * 7)

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for i in range(7):
        d = (start + timedelta(days=i)).astimezone(tz)
        ymd = _dt_to_yyyymmdd(d)
        row.append(InlineKeyboardButton(_pretty_date_label(d), callback_data=f"nsfw_avail:date:{ymd}:{week}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav: List[InlineKeyboardButton] = []
    if week > 0:
        nav.append(InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_avail:pickdate:{week-1}"))
    nav.append(InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_avail:pickdate:{week+1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data="nsfw_avail:open")])
    return InlineKeyboardMarkup(rows)


def _date_actions_kb(ymd: str, week: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Block 30 minutes", callback_data=f"nsfw_avail:blockpick:{ymd}:{week}:30")],
            [InlineKeyboardButton("➕ Block 60 minutes", callback_data=f"nsfw_avail:blockpick:{ymd}:{week}:60")],

            [InlineKeyboardButton("✅ Add available SLOT (30m)", callback_data=f"nsfw_avail:allowpick:{ymd}:{week}:slot:30")],
            [InlineKeyboardButton("✅ Add available SLOT (60m)", callback_data=f"nsfw_avail:allowpick:{ymd}:{week}:slot:60")],

            [InlineKeyboardButton("✅ Add available WINDOW", callback_data=f"nsfw_avail:allowpick:{ymd}:{week}:win")],

            [InlineKeyboardButton("🧼 Clear ALL blocks (this date)", callback_data=f"nsfw_avail:clearblocks:{ymd}:{week}")],
            [InlineKeyboardButton("🔄 Reset availability to business hours", callback_data=f"nsfw_avail:clearallowed:{ymd}:{week}")],

            [InlineKeyboardButton("⬅ Pick another date", callback_data=f"nsfw_avail:pickdate:{week}")],
            [InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")],
        ]
    )


def _generate_start_times_for_date(ymd: str, duration: int) -> List[str]:
    """
    For picking start times: every possible start in business hours (30-min increments),
    so you can edit weeks/months ahead.
    """
    day_dt = _yyyymmdd_to_local_day(ymd).astimezone(_tz())
    weekday = day_dt.weekday()
    open_h, close_h = get_business_hours_for_weekday(weekday)

    open_min = _min_from_hhmm(open_h)
    close_min = _min_from_hhmm(close_h)
    latest_start = close_min - duration

    starts: List[str] = []
    m = open_min
    while m <= latest_start:
        starts.append(_hhmm_from_min(m))
        m += 30
    return starts


def _pick_time_kb(prefix: str, ymd: str, week: int, duration: int) -> InlineKeyboardMarkup:
    starts = _generate_start_times_for_date(ymd, duration)
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for hhmm in starts[:42]:
        compact = hhmm.replace(":", "")
        row.append(InlineKeyboardButton(hhmm, callback_data=f"{prefix}:{ymd}:{week}:{duration}:{compact}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_avail:date:{ymd}:{week}")])
    return InlineKeyboardMarkup(rows)


def _pick_window_end_kb(ymd: str, week: int, start_hhmm: str) -> InlineKeyboardMarkup:
    day_dt = _yyyymmdd_to_local_day(ymd).astimezone(_tz())
    weekday = day_dt.weekday()
    open_h, close_h = get_business_hours_for_weekday(weekday)

    start_min = _min_from_hhmm(start_hhmm)
    close_min = _min_from_hhmm(close_h)

    # end must be at least +30
    ends: List[str] = []
    m = start_min + 30
    while m <= close_min:
        ends.append(_hhmm_from_min(m))
        m += 30

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for hhmm in ends[:42]:
        compact = hhmm.replace(":", "")
        row.append(InlineKeyboardButton(hhmm, callback_data=f"nsfw_avail:winend:{ymd}:{week}:{start_hhmm.replace(':','')}:{compact}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_avail:date:{ymd}:{week}")])
    return InlineKeyboardMarkup(rows)


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^nsfw_avail:open$"))
    async def avail_open(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        await cq.message.edit_text(
            f"🗓 <b>NSFW Availability (Roni)</b>\n\n"
            f"Business hours are the default.\n"
            f"You can:\n"
            f"• Add <b>blocks</b> (unavailable)\n"
            f"• Add <b>availability</b> slots/windows (overrides)\n\n"
            f"Timezone: <b>{TZ}</b>",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📅 Pick a date", callback_data="nsfw_avail:pickdate:0")],
                    [InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")],
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:pickdate:\d+$"))
    async def avail_pickdate(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        week = int(cq.data.split(":")[2])
        await cq.message.edit_text(
            "Pick a date to edit 🗓 (Los Angeles time)",
            reply_markup=_date_picker_kb(week),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:date:\d{8}:\d+$"))
    async def avail_date(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        _, _, ymd, week_s = cq.data.split(":")
        week = int(week_s)

        day_dt = _yyyymmdd_to_local_day(ymd).astimezone(_tz())
        label = day_dt.strftime("%A, %b %d").replace(" 0", " ")

        blocks = get_blocks_for_date(ymd)
        allowed = get_allowed_for_date(ymd)

        if allowed:
            al = "\n".join([f"• {s}–{e}" for (s, e) in allowed])
            allowed_text = f"<b>Availability overrides:</b>\n{al}\n(Booking will only offer times inside these windows)"
        else:
            allowed_text = "<b>Availability overrides:</b>\nNone (using business hours ✅)"

        if blocks:
            bl = "\n".join([f"• {s}–{e}" for (s, e) in blocks])
            block_text = f"<b>Blocks (unavailable):</b>\n{bl}"
        else:
            block_text = "<b>Blocks (unavailable):</b>\nNone ✅"

        await cq.message.edit_text(
            f"🗓 <b>{label}</b>\n\n{allowed_text}\n\n{block_text}\n\nChoose what to do:",
            reply_markup=_date_actions_kb(ymd, week),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ────────────── CLEAR BUTTONS ──────────────

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clearblocks:\d{8}:\d+$"))
    async def avail_clearblocks(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        _, _, ymd, week_s = cq.data.split(":")
        week = int(week_s)
        clear_blocks_for_date(ymd)
        await cq.answer("Cleared blocks ✅", show_alert=True)
        await cq.message.edit_text("Refreshing…", disable_web_page_preview=True)
        cq.data = f"nsfw_avail:date:{ymd}:{week}"
        await avail_date(_, cq)

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clearallowed:\d{8}:\d+$"))
    async def avail_clearallowed(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        _, _, ymd, week_s = cq.data.split(":")
        week = int(week_s)
        clear_allowed_for_date(ymd)
        await cq.answer("Availability reset ✅", show_alert=True)
        await cq.message.edit_text("Refreshing…", disable_web_page_preview=True)
        cq.data = f"nsfw_avail:date:{ymd}:{week}"
        await avail_date(_, cq)

    # ────────────── BLOCK PICKERS ──────────────

    @app.on_callback_query(filters.regex(r"^nsfw_avail:blockpick:\d{8}:\d+:(30|60)$"))
    async def avail_blockpick(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        _, _, ymd, week_s, dur_s = cq.data.split(":")
        week = int(week_s)
        duration = int(dur_s)

        day_dt = _yyyymmdd_to_local_day(ymd).astimezone(_tz())
        label = day_dt.strftime("%A, %b %d").replace(" 0", " ")

        await cq.message.edit_text(
            f"➕ Block a <b>{duration}-minute</b> slot\n🗓 <b>{label}</b>\n\nPick a start time (LA):",
            reply_markup=_pick_time_kb("nsfw_avail:blocktime", ymd, week, duration),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:blocktime:\d{8}:\d+:(30|60):\d{4}$"))
    async def avail_blocktime(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        _, _, ymd, week_s, dur_s, hhmm_compact = cq.data.split(":")
        week = int(week_s)
        duration = int(dur_s)

        start = f"{hhmm_compact[0:2]}:{hhmm_compact[2:4]}"
        end = _hhmm_from_min(_min_from_hhmm(start) + duration)

        blocks = get_blocks_for_date(ymd)
        blocks.append((start, end))
        set_blocks_for_date(ymd, blocks)

        await cq.answer(f"Blocked {start}–{end} ✅", show_alert=True)
        cq.data = f"nsfw_avail:date:{ymd}:{week}"
        await avail_date(_, cq)

    # ────────────── AVAILABILITY PICKERS (SLOT) ──────────────

    @app.on_callback_query(filters.regex(r"^nsfw_avail:allowpick:\d{8}:\d+:slot:(30|60)$"))
    async def avail_allow_slot_pick(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        _, _, ymd, week_s, _, dur_s = cq.data.split(":")
        week = int(week_s)
        duration = int(dur_s)

        day_dt = _yyyymmdd_to_local_day(ymd).astimezone(_tz())
        label = day_dt.strftime("%A, %b %d").replace(" 0", " ")

        await cq.message.edit_text(
            f"✅ Add available <b>{duration}m</b> SLOT\n🗓 <b>{label}</b>\n\nPick a start time (LA):",
            reply_markup=_pick_time_kb("nsfw_avail:allowtime", ymd, week, duration),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:allowtime:\d{8}:\d+:(30|60):\d{4}$"))
    async def avail_allowtime(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        _, _, ymd, week_s, dur_s, hhmm_compact = cq.data.split(":")
        week = int(week_s)
        duration = int(dur_s)

        start = f"{hhmm_compact[0:2]}:{hhmm_compact[2:4]}"
        end = _hhmm_from_min(_min_from_hhmm(start) + duration)

        add_allowed_window(ymd, start, end)

        await cq.answer(f"Available {start}–{end} ✅", show_alert=True)
        cq.data = f"nsfw_avail:date:{ymd}:{week}"
        await avail_date(_, cq)

    # ────────────── AVAILABILITY PICKERS (WINDOW) ──────────────

    @app.on_callback_query(filters.regex(r"^nsfw_avail:allowpick:\d{8}:\d+:win$"))
    async def avail_allow_window_pick(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        _, _, ymd, week_s, _ = cq.data.split(":")
        week = int(week_s)

        day_dt = _yyyymmdd_to_local_day(ymd).astimezone(_tz())
        label = day_dt.strftime("%A, %b %d").replace(" 0", " ")

        # pick a START first (30-min grid)
        await cq.message.edit_text(
            f"✅ Add available WINDOW\n🗓 <b>{label}</b>\n\nPick a START time (LA):",
            reply_markup=_pick_time_kb("nsfw_avail:winstart", ymd, week, 30),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:winstart:\d{8}:\d+:30:\d{4}$"))
    async def avail_winstart(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        _, _, ymd, week_s, _, hhmm_compact = cq.data.split(":")
        week = int(week_s)
        start = f"{hhmm_compact[0:2]}:{hhmm_compact[2:4]}"

        day_dt = _yyyymmdd_to_local_day(ymd).astimezone(_tz())
        label = day_dt.strftime("%A, %b %d").replace(" 0", " ")

        await cq.message.edit_text(
            f"✅ Add available WINDOW\n🗓 <b>{label}</b>\n\nStart: <b>{start}</b>\nPick an END time (LA):",
            reply_markup=_pick_window_end_kb(ymd, week, start),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:winend:\d{8}:\d+:\d{4}:\d{4}$"))
    async def avail_winend(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        _, _, ymd, week_s, start_compact, end_compact = cq.data.split(":")
        week = int(week_s)
        start = f"{start_compact[0:2]}:{start_compact[2:4]}"
        end = f"{end_compact[0:2]}:{end_compact[2:4]}"

        if _min_from_hhmm(end) <= _min_from_hhmm(start):
            await cq.answer("End must be after start 💕", show_alert=True)
            return

        add_allowed_window(ymd, start, end)

        await cq.answer(f"Available {start}–{end} ✅", show_alert=True)
        cq.data = f"nsfw_avail:date:{ymd}:{week}"
        await avail_date(_, cq)
