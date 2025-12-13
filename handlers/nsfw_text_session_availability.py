# handlers/nsfw_text_session_availability.py
import os
from typing import List, Tuple

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.nsfw_store import (
    set_blocks_for_date,
    clear_blocks_for_date,
    get_blocks_for_date,
    TZ,
)

RONI_OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))


def _owner_only(cq: CallbackQuery) -> bool:
    return bool(cq.from_user and cq.from_user.id == RONI_OWNER_ID)


def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Clear blocks for a date", callback_data="nsfw_avail:cleardate")],
            [InlineKeyboardButton("➕ Block 30 min", callback_data="nsfw_avail:block30")],
            [InlineKeyboardButton("➕ Block 60 min", callback_data="nsfw_avail:block60")],
            [InlineKeyboardButton("⬅ Back to Roni Admin", callback_data="roni_admin:open")],
        ]
    )


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^nsfw_avail:open$"))
    async def avail_open(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return
        await cq.message.edit_text(
            f"🗓 <b>NSFW Availability (Roni)</b>\n\n"
            f"Business hours are the default.\n"
            f"Use blocks to remove specific times.\n\n"
            f"Timezone: <b>{TZ}</b>",
            reply_markup=_kb_main(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Simple “clear blocks” helper: clears TODAY (quick reset)
    @app.on_callback_query(filters.regex(r"^nsfw_avail:cleardate$"))
    async def clear_today(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        # Clear today's blocks (keeps it button-only and quick)
        from datetime import datetime
        import pytz
        tz = pytz.timezone(TZ)
        ymd = datetime.now(tz).strftime("%Y%m%d")
        clear_blocks_for_date(ymd)
        await cq.answer("Cleared today’s blocks ✅", show_alert=True)

    # Very simple quick blocks: blocks the next 30 or 60 minutes from now (today)
    @app.on_callback_query(filters.regex(r"^nsfw_avail:block(30|60)$"))
    async def block_next(_, cq: CallbackQuery):
        if not _owner_only(cq):
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        minutes = int(cq.data.replace("nsfw_avail:block", ""))
        from datetime import datetime, timedelta
        import pytz

        tz = pytz.timezone(TZ)
        now = datetime.now(tz)

        # round to next 30-min boundary
        minute = now.minute
        add = (30 - (minute % 30)) % 30
        start = (now + timedelta(minutes=add)).replace(second=0, microsecond=0)
        end = start + timedelta(minutes=minutes)

        ymd = start.strftime("%Y%m%d")
        s = start.strftime("%H:%M")
        e = end.strftime("%H:%M")

        blocks: List[Tuple[str, str]] = get_blocks_for_date(ymd)
        blocks.append((s, e))
        set_blocks_for_date(ymd, blocks)

        await cq.answer(f"Blocked {s}–{e} today ✅", show_alert=True)
