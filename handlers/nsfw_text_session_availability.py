# handlers/nsfw_text_session_availability.py
import logging
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from utils.nsfw_store import (
    get_day_config,
    set_day_off,
    set_day_hours,
    clear_day_blocks,
    add_day_block,
)

log = logging.getLogger(__name__)

RONI_OWNER_ID = 6964994611

# Callback prefixes:
#   nsfw_avail:open
#   na:week:offset  (offset weeks from current)
#   na:day:YYYYMMDD
#   na:off:YYYYMMDD
#   na:on_preset:YYYYMMDD:PRESET
#   na:hours_start:YYYYMMDD:PAGE
#   na:hours_pickstart:YYYYMMDD:HHMM
#   na:hours_end:YYYYMMDD:HHMM:PAGE
#   na:hours_pickend:YYYYMMDD:START:END
#   na:block_start:YYYYMMDD:PAGE
#   na:block_pickstart:YYYYMMDD:HHMM
#   na:block_end:YYYYMMDD:START:PAGE
#   na:block_pickend:YYYYMMDD:START:END
#   na:clear_blocks:YYYYMMDD
#   na:back_week:offset

_TIME_GRID = [f"{h:02d}{m:02d}" for h in range(10, 24) for m in (0, 30)]  # 10:00–23:30
_PER_PAGE = 10


def _deny_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]])


def _require_roni(cq: CallbackQuery) -> bool:
    if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
        return False
    return True


def _week_dates(week_offset: int):
    today = datetime.now().date()
    # Monday start
    start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    return [start + timedelta(days=i) for i in range(7)]


def _week_kb(week_offset: int):
    days = _week_dates(week_offset)
    rows = []

    for d in days:
        ymd = d.strftime("%Y%m%d")
        cfg = get_day_config(ymd)
        if cfg.get("off"):
            icon = "🌙"
        elif cfg.get("start") and cfg.get("end"):
            icon = "✅" if not cfg.get("blocks") else "⚠️"
        else:
            icon = "❌"
        label = f"{icon} {d.strftime('%a %b %d')}"
        rows.append([InlineKeyboardButton(label, callback_data=f"na:day:{ymd}")])

    rows.append(
        [
            InlineKeyboardButton("⬅ Prev week", callback_data=f"na:week:{week_offset-1}"),
            InlineKeyboardButton("📅 This week", callback_data="na:week:0"),
            InlineKeyboardButton("Next week ➡", callback_data=f"na:week:{week_offset+1}"),
        ]
    )
    rows.append([InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)


def _day_text(ymd: str) -> str:
    d = datetime.strptime(ymd, "%Y%m%d").date()
    cfg = get_day_config(ymd)

    if cfg.get("off"):
        hours = "🌙 Day OFF"
    elif cfg.get("start") and cfg.get("end"):
        st = datetime.strptime(cfg["start"], "%H%M").strftime("%-I:%M %p")
        en = datetime.strptime(cfg["end"], "%H%M").strftime("%-I:%M %p")
        hours = f"🟢 Hours: <b>{st}</b> – <b>{en}</b>"
    else:
        hours = "❌ No hours set"

    blocks = cfg.get("blocks") or []
    if blocks:
        btxt = "\n".join(
            f"🚫 {datetime.strptime(b['start'], '%H%M').strftime('%-I:%M %p')} – {datetime.strptime(b['end'], '%H%M').strftime('%-I:%M %p')}"
            for b in blocks
        )
        block_line = f"\n\n<b>Blocks:</b>\n{btxt}"
    else:
        block_line = "\n\n<b>Blocks:</b>\n—"

    return (
        f"🗓 <b>NSFW availability</b> — {d.strftime('%A, %b %d')}\n\n"
        f"{hours}"
        f"{block_line}\n\n"
        "🚫 <b>NO meetups</b> — this is only for online/text sessions."
    )


def _day_kb(ymd: str, week_offset: int):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌙 Turn day OFF", callback_data=f"na:off:{ymd}")],
            [
                InlineKeyboardButton("⚡ Quick presets", callback_data=f"na:presets:{ymd}:{week_offset}"),
                InlineKeyboardButton("🎯 Custom hours", callback_data=f"na:hours_start:{ymd}:0"),
            ],
            [InlineKeyboardButton("🚫 Block time range", callback_data=f"na:block_start:{ymd}:0")],
            [InlineKeyboardButton("🧹 Clear all blocks", callback_data=f"na:clear_blocks:{ymd}")],
            [InlineKeyboardButton("⬅ Back to week", callback_data=f"na:week:{week_offset}")],
        ]
    )


def _presets_kb(ymd: str, week_offset: int):
    # Presets are just start/end pairs (30-min granularity)
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌤 Afternoon (3–7 PM)", callback_data=f"na:on_preset:{ymd}:AFT")],
            [InlineKeyboardButton("🌆 Evening (7–11 PM)", callback_data=f"na:on_preset:{ymd}:EVE")],
            [InlineKeyboardButton("🌗 Full (3–11 PM)", callback_data=f"na:on_preset:{ymd}:FULL")],
            [InlineKeyboardButton("❌ Clear hours (no sessions)", callback_data=f"na:on_preset:{ymd}:CLEAR")],
            [InlineKeyboardButton("⬅ Back", callback_data=f"na:day:{ymd}")],
            [InlineKeyboardButton("⬅ Back to week", callback_data=f"na:week:{week_offset}")],
        ]
    )


def _time_picker_kb(prefix: str, ymd: str, page: int, back_cb: str):
    start = page * _PER_PAGE
    end = start + _PER_PAGE
    chunk = _TIME_GRID[start:end]

    rows = []
    for hhmm in chunk:
        label = "🕒 " + datetime.strptime(hhmm, "%H%M").strftime("%-I:%M %p")
        rows.append([InlineKeyboardButton(label, callback_data=f"{prefix}:{ymd}:{hhmm}")])

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅ Earlier", callback_data=f"{back_cb}:{page-1}"))
    if end < len(_TIME_GRID):
        nav.append(InlineKeyboardButton("Later ➡", callback_data=f"{back_cb}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"na:day:{ymd}")])
    return InlineKeyboardMarkup(rows)


def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_text_session_availability registered")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:open$"))
    async def open_availability(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer("❌ Roni only.", show_alert=True)
            try:
                await cq.message.edit_text("❌ This panel is for Roni only.", reply_markup=_deny_kb())
            finally:
                return

        await cq.message.edit_text(
            "🗓 <b>NSFW availability (Roni)</b>\n\n"
            "Tap a day to set hours, block times, or turn the day off.\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=_week_kb(0),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^na:week:-?\d+$"))
    async def week_view(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, off_s = cq.data.split(":")
        off = int(off_s)
        await cq.message.edit_text(
            "🗓 <b>NSFW availability (Roni)</b>\n\n"
            "Tap a day to edit.\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=_week_kb(off),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^na:day:\d{8}$"))
    async def day_view(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        ymd = cq.data.split(":")[2]
        # try to infer current week offset from the message? keep simple: back goes to this week
        await cq.message.edit_text(
            _day_text(ymd),
            reply_markup=_day_kb(ymd, 0),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^na:presets:\d{8}:-?\d+$"))
    async def presets(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, ymd, off_s = cq.data.split(":")
        off = int(off_s)
        await cq.message.edit_text(
            f"⚡ <b>Quick presets</b> — {datetime.strptime(ymd, '%Y%m%d').strftime('%A, %b %d')}\n\n"
            "Pick a window for bookings.\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=_presets_kb(ymd, off),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^na:on_preset:\d{8}:(AFT|EVE|FULL|CLEAR)$"))
    async def apply_preset(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, ymd, preset = cq.data.split(":")
        if preset == "AFT":
            set_day_hours(ymd, "1500", "1900")
        elif preset == "EVE":
            set_day_hours(ymd, "1900", "2300")
        elif preset == "FULL":
            set_day_hours(ymd, "1500", "2300")
        elif preset == "CLEAR":
            set_day_hours(ymd, "", "")
        await cq.message.edit_text(
            _day_text(ymd),
            reply_markup=_day_kb(ymd, 0),
            disable_web_page_preview=True,
        )
        await cq.answer("✅ Saved")

    @app.on_callback_query(filters.regex(r"^na:off:\d{8}$"))
    async def day_off(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        ymd = cq.data.split(":")[2]
        set_day_off(ymd, True)
        await cq.message.edit_text(
            _day_text(ymd),
            reply_markup=_day_kb(ymd, 0),
            disable_web_page_preview=True,
        )
        await cq.answer("🌙 Day off")

    # --- Custom hours: pick start then end ---

    @app.on_callback_query(filters.regex(r"^na:hours_start:\d{8}:\d+$"))
    async def hours_start(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, ymd, page_s = cq.data.split(":")
        page = int(page_s)
        await cq.message.edit_text(
            "🎯 <b>Custom hours</b>\n\n"
            "Step 1: pick a <b>start</b> time.",
            reply_markup=_time_picker_kb(
                prefix="na:hours_pickstart",
                ymd=ymd,
                page=page,
                back_cb=f"na:hours_start:{ymd}",
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^na:hours_pickstart:\d{8}:\d{4}$"))
    async def hours_pick_start(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, ymd, start = cq.data.split(":")
        await cq.message.edit_text(
            "🎯 <b>Custom hours</b>\n\n"
            "Step 2: pick an <b>end</b> time.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🕒 Pick end time", callback_data=f"na:hours_end:{ymd}:{start}:0")],
                    [InlineKeyboardButton("⬅ Back", callback_data=f"na:hours_start:{ymd}:0")],
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^na:hours_end:\d{8}:\d{4}:\d+$"))
    async def hours_end(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, ymd, start, page_s = cq.data.split(":")
        page = int(page_s)

        # end picker shows only times after start
        grid = [t for t in _TIME_GRID if t > start]
        start_i = page * _PER_PAGE
        end_i = start_i + _PER_PAGE
        chunk = grid[start_i:end_i]

        rows = []
        for hhmm in chunk:
            label = "🕒 " + datetime.strptime(hhmm, "%H%M").strftime("%-I:%M %p")
            rows.append([InlineKeyboardButton(label, callback_data=f"na:hours_pickend:{ymd}:{start}:{hhmm}")])

        nav = []
        if start_i > 0:
            nav.append(InlineKeyboardButton("⬅ Earlier", callback_data=f"na:hours_end:{ymd}:{start}:{page-1}"))
        if end_i < len(grid):
            nav.append(InlineKeyboardButton("Later ➡", callback_data=f"na:hours_end:{ymd}:{start}:{page+1}"))
        if nav:
            rows.append(nav)

        rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"na:day:{ymd}")])

        await cq.message.edit_text(
            "🎯 <b>Custom hours</b>\n\nStep 2: pick an <b>end</b> time.",
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^na:hours_pickend:\d{8}:\d{4}:\d{4}$"))
    async def hours_pick_end(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, ymd, start, end = cq.data.split(":")
        set_day_off(ymd, False)
        set_day_hours(ymd, start, end)
        await cq.message.edit_text(
            _day_text(ymd),
            reply_markup=_day_kb(ymd, 0),
            disable_web_page_preview=True,
        )
        await cq.answer("✅ Hours saved")

    # --- Blocks: pick start then end ---

    @app.on_callback_query(filters.regex(r"^na:block_start:\d{8}:\d+$"))
    async def block_start(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, ymd, page_s = cq.data.split(":")
        page = int(page_s)

        await cq.message.edit_text(
            "🚫 <b>Block time range</b>\n\n"
            "Step 1: pick a <b>block start</b> time.",
            reply_markup=_time_picker_kb(
                prefix="na:block_pickstart",
                ymd=ymd,
                page=page,
                back_cb=f"na:block_start:{ymd}",
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^na:block_pickstart:\d{8}:\d{4}$"))
    async def block_pick_start(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, ymd, start = cq.data.split(":")
        await cq.message.edit_text(
            "🚫 <b>Block time range</b>\n\n"
            "Step 2: pick a <b>block end</b> time.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🕒 Pick end time", callback_data=f"na:block_end:{ymd}:{start}:0")],
                    [InlineKeyboardButton("⬅ Back", callback_data=f"na:block_start:{ymd}:0")],
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^na:block_end:\d{8}:\d{4}:\d+$"))
    async def block_end(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, ymd, start, page_s = cq.data.split(":")
        page = int(page_s)

        grid = [t for t in _TIME_GRID if t > start]
        start_i = page * _PER_PAGE
        end_i = start_i + _PER_PAGE
        chunk = grid[start_i:end_i]

        rows = []
        for hhmm in chunk:
            label = "🕒 " + datetime.strptime(hhmm, "%H%M").strftime("%-I:%M %p")
            rows.append([InlineKeyboardButton(label, callback_data=f"na:block_pickend:{ymd}:{start}:{hhmm}")])

        nav = []
        if start_i > 0:
            nav.append(InlineKeyboardButton("⬅ Earlier", callback_data=f"na:block_end:{ymd}:{start}:{page-1}"))
        if end_i < len(grid):
            nav.append(InlineKeyboardButton("Later ➡", callback_data=f"na:block_end:{ymd}:{start}:{page+1}"))
        if nav:
            rows.append(nav)

        rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"na:day:{ymd}")])

        await cq.message.edit_text(
            "🚫 <b>Block time range</b>\n\nStep 2: pick a <b>block end</b> time.",
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^na:block_pickend:\d{8}:\d{4}:\d{4}$"))
    async def block_pick_end(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        _, _, ymd, start, end = cq.data.split(":")
        add_day_block(ymd, start, end)
        await cq.message.edit_text(
            _day_text(ymd),
            reply_markup=_day_kb(ymd, 0),
            disable_web_page_preview=True,
        )
        await cq.answer("🚫 Block saved")

    @app.on_callback_query(filters.regex(r"^na:clear_blocks:\d{8}$"))
    async def clear_blocks(_, cq: CallbackQuery):
        if not _require_roni(cq):
            await cq.answer()
            return
        ymd = cq.data.split(":")[2]
        clear_day_blocks(ymd)
        await cq.message.edit_text(
            _day_text(ymd),
            reply_markup=_day_kb(ymd, 0),
            disable_web_page_preview=True,
        )
        await cq.answer("🧹 Cleared")
