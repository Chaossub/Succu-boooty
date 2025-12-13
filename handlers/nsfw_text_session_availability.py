# handlers/nsfw_text_session_availability.py
import os
from datetime import datetime, timedelta
from typing import List, Tuple

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.nsfw_store import (
    TZ,
    clear_blocks_for_date,
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
        row.append(InlineKeyboardButton(_pretty_date_label(d), callback_data=f"nsfw_avail:date:{ymd}"))
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


def _date_actions_kb(ymd: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Block 30 minutes", callback_data=f"nsfw_avail:add:{ymd}:30")],
            [InlineKeyboardButton("➕ Block 60 minutes", callback_data=f"nsfw_avail:add:{ymd}:60")],
            [InlineKeyboardButton("🧼 Clear ALL blocks (this date)", callback_data=f"nsfw_avail:clear:{ymd}")],
            [InlineKeyboardButton("⬅ Pick another date", callback_data="nsfw_avail:pickdate:0")],
            [InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")],
        ]
    )


def _generate_all_start_times_for_date(ymd: str, duration: int) -> List[str]:
    """
    For blocking: show every possible start time in business hours (30-min increments),
    regardless of current time (so you can manage weeks ahead).
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


def _pick_block_time_kb(ymd: str, duration: int) -> InlineKeyboardMarkup:
    starts = _generate_all_start_times_for_date(ymd, duration)

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for hhmm in starts[:36]:
        compact = hhmm.replace(":", "")
        row.append(InlineKeyboardButton(hhmm, callback_data=f"nsfw_avail:time:{ymd}:{duration}:{compact}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_avail:date:{ymd}")])
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
            f"Pick a date to add/remove blocks.\n\n"
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

    @app.on_callback_query(filters.regex(r"^nsfw_avail:date:\d{8}$"))
    async def avail_date(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        ymd = cq.data.split(":")[2]
        day_dt = _yyyymmdd_to_local_day(ymd).astimezone(_tz())
        label = day_dt.strftime("%A, %b %d").replace(" 0", " ")

        blocks = get_blocks_for_date(ymd)
        if blocks:
            bl = "\n".join([f"• {s}–{e}" for (s, e) in blocks])
            block_text = f"<b>Current blocks:</b>\n{bl}"
        else:
            block_text = "<b>Current blocks:</b>\nNone ✅"

        await cq.message.edit_text(
            f"🗓 <b>{label}</b>\n\n{block_text}\n\nChoose what to do:",
            reply_markup=_date_actions_kb(ymd),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clear:\d{8}$"))
    async def avail_clear(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        ymd = cq.data.split(":")[2]
        clear_blocks_for_date(ymd)
        await cq.answer("Cleared ✅", show_alert=True)
        # refresh the date screen
        cq.data = f"nsfw_avail:date:{ymd}"
        await avail_date(_, cq)

    @app.on_callback_query(filters.regex(r"^nsfw_avail:add:\d{8}:(30|60)$"))
    async def avail_add(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        _, _, _, ymd, dur_s = cq.data.split(":")
        duration = int(dur_s)

        day_dt = _yyyymmdd_to_local_day(ymd).astimezone(_tz())
        label = day_dt.strftime("%A, %b %d").replace(" 0", " ")

        await cq.message.edit_text(
            f"➕ Block a <b>{duration}-minute</b> slot\n"
            f"🗓 <b>{label}</b>\n\nPick a start time (LA):",
            reply_markup=_pick_block_time_kb(ymd, duration),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:time:\d{8}:(30|60):\d{4}$"))
    async def avail_time(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        _, _, _, ymd, dur_s, hhmm_compact = cq.data.split(":")
        duration = int(dur_s)
        start = f"{hhmm_compact[0:2]}:{hhmm_compact[2:4]}"

        # compute end
        start_min = _min_from_hhmm(start)
        end = _hhmm_from_min(start_min + duration)

        blocks = get_blocks_for_date(ymd)
        blocks.append((start, end))
        set_blocks_for_date(ymd, blocks)

        await cq.answer(f"Blocked {start}–{end} ✅", show_alert=True)

        # back to date view
        cq.data = f"nsfw_avail:date:{ymd}"
        await avail_date(_, cq)
