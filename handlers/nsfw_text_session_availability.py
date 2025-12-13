# handlers/nsfw_text_session_availability.py
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.menu_store import store

log = logging.getLogger(__name__)

# ────────────── CONFIG ──────────────

RONI_OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))
TZ_NAME = os.getenv("RONI_TZ", "America/Los_Angeles")
TZ = pytz.timezone(TZ_NAME)

# Business hours fallback (when no custom "allowed windows" exist for a date)
# Mon-Fri: 9:00 AM - 10:00 PM
# Sat:     9:00 AM -  9:00 PM
# Sun:     9:00 AM - 10:00 PM
BUSINESS_HOURS = {
    0: ("09:00", "22:00"),  # Mon
    1: ("09:00", "22:00"),  # Tue
    2: ("09:00", "22:00"),  # Wed
    3: ("09:00", "22:00"),  # Thu
    4: ("09:00", "22:00"),  # Fri
    5: ("09:00", "21:00"),  # Sat
    6: ("09:00", "22:00"),  # Sun
}

STATE_KEY = "NSFW_TEXTING_AVAIL_STATE"

# Callback prefixes
CB_OPEN = "nsfw_avail:open"
CB_WEEK = "nsfw_avail:week"            # nsfw_avail:week:<page>
CB_DATE = "nsfw_avail:date"            # nsfw_avail:date:<yyyymmdd>

CB_BLOCK_PICK = "nsfw_avail:blockpick" # nsfw_avail:blockpick:<yyyymmdd>:<mins>
CB_BLOCK = "nsfw_avail:block"          # nsfw_avail:block:<yyyymmdd>:<mins>:<hhmm>
CB_BLOCK_DAY = "nsfw_avail:blockday"   # nsfw_avail:blockday:<yyyymmdd>
CB_CLEAR_BLOCKS = "nsfw_avail:clrblk"  # nsfw_avail:clrblk:<yyyymmdd>

# Availability windows (allowed)
CB_ALLOW_ADD = "nsfw_avail:allowadd"   # nsfw_avail:allowadd:<yyyymmdd>
CB_ALLOW_PRESET = "nsfw_avail:allowpre"  # nsfw_avail:allowpre:<yyyymmdd>:<preset>
CB_ALLOW_START = "nsfw_avail:allowst"    # nsfw_avail:allowst:<yyyymmdd>
CB_ALLOW_END = "nsfw_avail:allowen"      # nsfw_avail:allowen:<yyyymmdd>:<hhmmStart>:<hhmmEnd>
CB_CLEAR_ALLOW = "nsfw_avail:clralw"     # nsfw_avail:clralw:<yyyymmdd>
CB_CLEAR_ALL = "nsfw_avail:clrall"       # nsfw_avail:clrall:<yyyymmdd>

CB_BACK_ADMIN = "roni_admin:open"


# ────────────── TIME HELPERS ──────────────

def _hm_to_min(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)

def _min_to_hm(m: int) -> str:
    m = max(0, min(24 * 60, m))
    return f"{m//60:02d}:{m%60:02d}"

def _hhmm_to_hm(hhmm: str) -> str:
    return f"{hhmm[0:2]}:{hhmm[2:4]}"

def _hm_to_hhmm(hm: str) -> str:
    return hm.replace(":", "")

def _date_key(d: datetime) -> str:
    return d.strftime("%Y%m%d")

def _fmt_date(yyyymmdd: str) -> str:
    dt = datetime.strptime(yyyymmdd, "%Y%m%d")
    return dt.strftime("%A, %b %d")

def _business_hours_for_date(yyyymmdd: str) -> Tuple[str, str]:
    dt = datetime.strptime(yyyymmdd, "%Y%m%d")
    wd = dt.weekday()
    return BUSINESS_HOURS.get(wd, ("09:00", "22:00"))

def _time_slots_between(start_hm: str, end_hm: str, step_min: int = 30) -> List[str]:
    s = _hm_to_min(start_hm)
    e = _hm_to_min(end_hm)
    out = []
    cur = s
    while cur < e:
        out.append(_min_to_hm(cur))
        cur += step_min
    return out


# ────────────── INTERVAL HELPERS ──────────────

def _clip_interval(s: int, e: int) -> Tuple[int, int]:
    s = max(0, min(24 * 60, s))
    e = max(0, min(24 * 60, e))
    return (s, e)

def _merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    intervals = [(s, e) for (s, e) in intervals if e > s]
    if not intervals:
        return []
    intervals.sort(key=lambda x: (x[0], x[1]))
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        ps, pe = merged[-1]
        if s <= pe:  # overlap/touch
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged

def _as_pairs_hm(intervals: List[Tuple[int, int]]) -> List[List[str]]:
    return [[_min_to_hm(s), _min_to_hm(e)] for (s, e) in intervals]

def _from_pairs_hm(pairs: List[List[str]]) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for p in pairs or []:
        if not isinstance(p, list) or len(p) != 2:
            continue
        try:
            s = _hm_to_min(p[0])
            e = _hm_to_min(p[1])
            s, e = _clip_interval(s, e)
            if e > s:
                out.append((s, e))
        except Exception:
            continue
    return out


# ────────────── PERSISTENCE ──────────────
# {
#   "20251214": {
#      "allowed": [["09:00","12:00"], ...],
#      "blocked": [["10:30","11:00"], ...],
#      "blocked_all_day": false
#   }
# }

def _load_state() -> Dict[str, dict]:
    raw = store.get_menu(STATE_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_state(state: Dict[str, dict]) -> None:
    try:
        store.set_menu(STATE_KEY, json.dumps(state, ensure_ascii=False))
    except Exception as e:
        log.warning("nsfw_avail: failed to save state: %s", e)

def _get_day(state: Dict[str, dict], yyyymmdd: str) -> dict:
    day = state.get(yyyymmdd)
    if not isinstance(day, dict):
        day = {"allowed": [], "blocked": [], "blocked_all_day": False}
        state[yyyymmdd] = day
    day.setdefault("allowed", [])
    day.setdefault("blocked", [])
    day.setdefault("blocked_all_day", False)
    return day


# ────────────── MUTATIONS ──────────────

def _add_block(state: Dict[str, dict], yyyymmdd: str, start_hm: str, mins: int) -> None:
    day = _get_day(state, yyyymmdd)
    if bool(day.get("blocked_all_day")):
        return
    s = _hm_to_min(start_hm)
    e = s + mins
    s, e = _clip_interval(s, e)

    blocks = _from_pairs_hm(day.get("blocked", []))
    blocks.append((s, e))
    blocks = _merge_intervals(blocks)
    day["blocked"] = _as_pairs_hm(blocks)

def _set_block_all_day(state: Dict[str, dict], yyyymmdd: str, on: bool) -> None:
    day = _get_day(state, yyyymmdd)
    day["blocked_all_day"] = bool(on)
    if on:
        day["blocked"] = []

def _clear_blocks(state: Dict[str, dict], yyyymmdd: str) -> None:
    day = _get_day(state, yyyymmdd)
    day["blocked_all_day"] = False
    day["blocked"] = []

def _add_allowed(state: Dict[str, dict], yyyymmdd: str, start_hm: str, end_hm: str) -> None:
    day = _get_day(state, yyyymmdd)
    s = _hm_to_min(start_hm)
    e = _hm_to_min(end_hm)
    s, e = _clip_interval(s, e)
    if e <= s:
        return

    allowed = _from_pairs_hm(day.get("allowed", []))
    allowed.append((s, e))
    allowed = _merge_intervals(allowed)
    day["allowed"] = _as_pairs_hm(allowed)

def _clear_allowed(state: Dict[str, dict], yyyymmdd: str) -> None:
    day = _get_day(state, yyyymmdd)
    day["allowed"] = []

def _clear_all_for_date(state: Dict[str, dict], yyyymmdd: str) -> None:
    day = _get_day(state, yyyymmdd)
    day["allowed"] = []
    day["blocked"] = []
    day["blocked_all_day"] = False


# ────────────── UI ──────────────

def _is_owner(user_id: int) -> bool:
    return user_id == RONI_OWNER_ID

def _kb_admin_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Roni Admin", callback_data=CB_BACK_ADMIN)]])

def _kb_week_picker(page: int = 0) -> InlineKeyboardMarkup:
    now = datetime.now(TZ)
    start = (now.date() + timedelta(days=page * 7))
    days = [datetime.combine(start + timedelta(days=i), datetime.min.time()).replace(tzinfo=TZ) for i in range(7)]

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for d in days:
        label = d.strftime("%a %b %d")  # "Fri Dec 12"
        key = _date_key(d)
        row.append(InlineKeyboardButton(label, callback_data=f"{CB_DATE}:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav_row: List[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅ Prev week", callback_data=f"{CB_WEEK}:{page-1}"))
    nav_row.append(InlineKeyboardButton("Next week ➡", callback_data=f"{CB_WEEK}:{page+1}"))
    rows.append(nav_row)

    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data=CB_BACK_ADMIN)])
    return InlineKeyboardMarkup(rows)

def _render_overview_text() -> str:
    return (
        "🗓 <b>NSFW Availability (Roni)</b>\n\n"
        "Business hours are the default.\n"
        "Pick a date to add <b>availability windows</b> (when you’re working) and/or <b>blocks</b>.\n\n"
        f"Timezone: <b>{TZ_NAME}</b>"
    )

def _render_day_text(state: Dict[str, dict], yyyymmdd: str) -> str:
    day = _get_day(state, yyyymmdd)
    open_hm, close_hm = _business_hours_for_date(yyyymmdd)

    allowed_pairs = day.get("allowed", []) or []
    blocked_pairs = day.get("blocked", []) or []
    blocked_all_day = bool(day.get("blocked_all_day"))

    lines = [f"📅 <b>{_fmt_date(yyyymmdd)}</b>\n"]
    lines.append(f"🕘 <b>Business hours:</b> {open_hm} – {close_hm} (default)\n")

    if allowed_pairs:
        lines.append("✅ <b>Availability windows (custom):</b>")
        for a in allowed_pairs:
            if isinstance(a, list) and len(a) == 2:
                lines.append(f"• {a[0]} – {a[1]}")
        lines.append("")
    else:
        lines.append("✅ <b>Availability windows:</b> none set (using business hours)\n")

    if blocked_all_day:
        lines.append("⛔ <b>Blocked:</b> ALL DAY\n")
    elif blocked_pairs:
        lines.append("⛔ <b>Blocked:</b>")
        for b in blocked_pairs:
            if isinstance(b, list) and len(b) == 2:
                lines.append(f"• {b[0]} – {b[1]}")
        lines.append("")
    else:
        lines.append("⛔ <b>Blocked:</b> none\n")

    lines.append("Choose what to do:")
    return "\n".join(lines)

def _kb_day_actions(yyyymmdd: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("➕ Add availability window", callback_data=f"{CB_ALLOW_ADD}:{yyyymmdd}")],
        [
            InlineKeyboardButton("➕ Block 30 minutes", callback_data=f"{CB_BLOCK_PICK}:{yyyymmdd}:30"),
            InlineKeyboardButton("➕ Block 60 minutes", callback_data=f"{CB_BLOCK_PICK}:{yyyymmdd}:60"),
        ],
        [InlineKeyboardButton("⛔ Block entire day", callback_data=f"{CB_BLOCK_DAY}:{yyyymmdd}")],
        [InlineKeyboardButton("🧼 Clear ALL blocks (this date)", callback_data=f"{CB_CLEAR_BLOCKS}:{yyyymmdd}")],
        [InlineKeyboardButton("🔄 Clear availability windows (use business hours)", callback_data=f"{CB_CLEAR_ALLOW}:{yyyymmdd}")],
        [InlineKeyboardButton("🧨 Clear EVERYTHING (this date)", callback_data=f"{CB_CLEAR_ALL}:{yyyymmdd}")],
        [InlineKeyboardButton("📅 Pick another date", callback_data=f"{CB_WEEK}:0")],
        [InlineKeyboardButton("⬅ Back to Roni Admin", callback_data=CB_BACK_ADMIN)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_pick_start_times_for_block(yyyymmdd: str, mins: int) -> InlineKeyboardMarkup:
    open_hm, close_hm = _business_hours_for_date(yyyymmdd)
    slots = _time_slots_between(open_hm, close_hm, 30)

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for hm in slots:
        cb = f"{CB_BLOCK}:{yyyymmdd}:{mins}:{_hm_to_hhmm(hm)}"
        row.append(InlineKeyboardButton(hm, callback_data=cb))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"{CB_DATE}:{yyyymmdd}")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data=CB_BACK_ADMIN)])
    return InlineKeyboardMarkup(rows)

def _kb_allow_add_screen(state: Dict[str, dict], yyyymmdd: str) -> InlineKeyboardMarkup:
    """
    This screen is what you asked for:
    - It shows current allowed windows
    - Lets you add multiple windows (presets or custom)
    - You can keep adding without going back
    """
    open_hm, close_hm = _business_hours_for_date(yyyymmdd)

    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("🌞 Morning (09:00–12:00)", callback_data=f"{CB_ALLOW_PRESET}:{yyyymmdd}:morning")],
        [InlineKeyboardButton("☀️ Afternoon (12:00–17:00)", callback_data=f"{CB_ALLOW_PRESET}:{yyyymmdd}:afternoon")],
        [InlineKeyboardButton(f"🌙 Evening (17:00–{close_hm})", callback_data=f"{CB_ALLOW_PRESET}:{yyyymmdd}:evening")],
        [InlineKeyboardButton(f"🕘 Full business hours ({open_hm}–{close_hm})", callback_data=f"{CB_ALLOW_PRESET}:{yyyymmdd}:full")],
        [InlineKeyboardButton("🧩 Custom window (pick start)", callback_data=f"{CB_ALLOW_START}:{yyyymmdd}")],
        [InlineKeyboardButton("🔄 Clear availability windows (use business hours)", callback_data=f"{CB_CLEAR_ALLOW}:{yyyymmdd}")],
        [InlineKeyboardButton("⬅ Back", callback_data=f"{CB_DATE}:{yyyymmdd}")],
        [InlineKeyboardButton("⬅ Back to Roni Admin", callback_data=CB_BACK_ADMIN)],
    ]
    return InlineKeyboardMarkup(rows)

def _render_allow_add_text(state: Dict[str, dict], yyyymmdd: str) -> str:
    day = _get_day(state, yyyymmdd)
    allowed_pairs = day.get("allowed", []) or []
    open_hm, close_hm = _business_hours_for_date(yyyymmdd)

    lines = [
        f"✅ <b>Availability windows</b>\n",
        f"Date: <b>{_fmt_date(yyyymmdd)}</b>\n",
        "These are the ONLY times people can book on this date (blocks still subtract).\n",
    ]

    if allowed_pairs:
        lines.append("Current windows:")
        for a in allowed_pairs:
            if isinstance(a, list) and len(a) == 2:
                lines.append(f"• {a[0]} – {a[1]}")
        lines.append("")
    else:
        lines.append(f"Current windows: none (using business hours {open_hm}–{close_hm})\n")

    lines.append("Add one or more windows below:")
    return "\n".join(lines)

def _kb_pick_allow_start(yyyymmdd: str) -> InlineKeyboardMarkup:
    """
    Pick a START time, then we show END choices.
    (Buttons only, and you can add multiple windows.)
    """
    open_hm, close_hm = _business_hours_for_date(yyyymmdd)
    slots = _time_slots_between(open_hm, close_hm, 30)

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for hm in slots:
        cb = f"{CB_ALLOW_START}:{yyyymmdd}:{_hm_to_hhmm(hm)}"
        row.append(InlineKeyboardButton(hm, callback_data=cb))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"{CB_ALLOW_ADD}:{yyyymmdd}")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data=CB_BACK_ADMIN)])
    return InlineKeyboardMarkup(rows)

def _kb_pick_allow_end(yyyymmdd: str, start_hm: str) -> InlineKeyboardMarkup:
    open_hm, close_hm = _business_hours_for_date(yyyymmdd)
    s = _hm_to_min(start_hm)
    emax = _hm_to_min(close_hm)

    ends: List[str] = []
    cur = s + 30
    while cur <= emax:
        ends.append(_min_to_hm(cur))
        cur += 30

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for end_hm in ends:
        cb = f"{CB_ALLOW_END}:{yyyymmdd}:{_hm_to_hhmm(start_hm)}:{_hm_to_hhmm(end_hm)}"
        row.append(InlineKeyboardButton(end_hm, callback_data=cb))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"{CB_ALLOW_START}:{yyyymmdd}")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Admin", callback_data=CB_BACK_ADMIN)])
    return InlineKeyboardMarkup(rows)


# ────────────── REGISTER ──────────────

def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_text_session_availability registered (tz=%s owner=%s)", TZ_NAME, RONI_OWNER_ID)

    @app.on_callback_query(filters.regex(r"^nsfw_avail:open$"))
    async def nsfw_avail_open(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        text = _render_overview_text()
        kb = _kb_week_picker(page=0)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:week:\d+$"))
    async def nsfw_avail_week(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        try:
            page = int(cq.data.split(":")[-1])
        except Exception:
            page = 0

        text = "Pick a date 📅 (Los Angeles time)"
        kb = _kb_week_picker(page=max(0, page))
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:date:\d{8}$"))
    async def nsfw_avail_date(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        yyyymmdd = cq.data.split(":")[-1]
        state = _load_state()
        text = _render_day_text(state, yyyymmdd)
        kb = _kb_day_actions(yyyymmdd)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ───────── BLOCK FLOW ─────────

    @app.on_callback_query(filters.regex(r"^nsfw_avail:blockpick:\d{8}:(30|60)$"))
    async def nsfw_block_pick(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        parts = cq.data.split(":")
        yyyymmdd = parts[2]
        mins = int(parts[3])

        text = f"Pick a start time to block ({mins} minutes)\n\nDate: <b>{_fmt_date(yyyymmdd)}</b>"
        kb = _kb_pick_start_times_for_block(yyyymmdd, mins)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:block:\d{8}:(30|60):\d{4}$"))
    async def nsfw_block_apply(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        parts = cq.data.split(":")
        # nsfw_avail:block:<date>:<mins>:<hhmm>
        if len(parts) != 5:
            await cq.answer("That button payload was invalid (please retry).", show_alert=True)
            return

        yyyymmdd = parts[2]
        mins = int(parts[3])
        start_hm = _hhmm_to_hm(parts[4])

        state = _load_state()
        _add_block(state, yyyymmdd, start_hm, mins)
        _save_state(state)

        text = _render_day_text(state, yyyymmdd)
        kb = _kb_day_actions(yyyymmdd)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer("Blocked ✅")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:blockday:\d{8}$"))
    async def nsfw_block_day(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        yyyymmdd = cq.data.split(":")[-1]
        state = _load_state()
        _set_block_all_day(state, yyyymmdd, True)
        _save_state(state)

        text = _render_day_text(state, yyyymmdd)
        kb = _kb_day_actions(yyyymmdd)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer("Blocked all day ⛔")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clrblk:\d{8}$"))
    async def nsfw_clear_blocks(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        yyyymmdd = cq.data.split(":")[-1]
        state = _load_state()
        _clear_blocks(state, yyyymmdd)
        _save_state(state)

        text = _render_day_text(state, yyyymmdd)
        kb = _kb_day_actions(yyyymmdd)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer("Cleared blocks ✅")

    # ───────── AVAILABILITY WINDOWS (ALLOWED) ─────────
    # This is the part you asked for: pick times you’re available that day, and add multiple windows.

    @app.on_callback_query(filters.regex(r"^nsfw_avail:allowadd:\d{8}$"))
    async def nsfw_allow_add(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        yyyymmdd = cq.data.split(":")[-1]
        state = _load_state()
        text = _render_allow_add_text(state, yyyymmdd)
        kb = _kb_allow_add_screen(state, yyyymmdd)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:allowpre:\d{8}:(morning|afternoon|evening|full)$"))
    async def nsfw_allow_preset(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        parts = cq.data.split(":")
        yyyymmdd = parts[2]
        preset = parts[3]

        open_hm, close_hm = _business_hours_for_date(yyyymmdd)

        if preset == "morning":
            start_hm, end_hm = "09:00", "12:00"
        elif preset == "afternoon":
            start_hm, end_hm = "12:00", "17:00"
        elif preset == "evening":
            start_hm, end_hm = "17:00", close_hm
        else:  # full
            start_hm, end_hm = open_hm, close_hm

        state = _load_state()
        _add_allowed(state, yyyymmdd, start_hm, end_hm)
        _save_state(state)

        # Stay on the add screen so you can add multiple easily
        text = _render_allow_add_text(state, yyyymmdd)
        kb = _kb_allow_add_screen(state, yyyymmdd)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer("Added window ✅")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:allowst:\d{8}$"))
    async def nsfw_allow_custom_start_open(_, cq: CallbackQuery):
        # Open the start-time picker
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        yyyymmdd = cq.data.split(":")[-1]
        text = (
            f"🧩 <b>Custom availability window</b>\n\n"
            f"Date: <b>{_fmt_date(yyyymmdd)}</b>\n\n"
            "Pick a start time:"
        )
        kb = _kb_pick_allow_start(yyyymmdd)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:allowst:\d{8}:\d{4}$"))
    async def nsfw_allow_custom_start_pick(_, cq: CallbackQuery):
        # Pick start, then show end options
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        parts = cq.data.split(":")
        if len(parts) != 4:
            await cq.answer("That button payload was invalid (please retry).", show_alert=True)
            return

        yyyymmdd = parts[2]
        start_hm = _hhmm_to_hm(parts[3])

        text = (
            f"🧩 <b>Custom availability window</b>\n\n"
            f"Date: <b>{_fmt_date(yyyymmdd)}</b>\n"
            f"Start: <b>{start_hm}</b>\n\n"
            "Pick an end time:"
        )
        kb = _kb_pick_allow_end(yyyymmdd, start_hm)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_avail:allowen:\d{8}:\d{4}:\d{4}$"))
    async def nsfw_allow_custom_end_pick(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        parts = cq.data.split(":")
        if len(parts) != 5:
            await cq.answer("That button payload was invalid (please retry).", show_alert=True)
            return

        yyyymmdd = parts[2]
        start_hm = _hhmm_to_hm(parts[3])
        end_hm = _hhmm_to_hm(parts[4])

        state = _load_state()
        _add_allowed(state, yyyymmdd, start_hm, end_hm)
        _save_state(state)

        # Return to the add screen so you can add multiple windows easily
        text = _render_allow_add_text(state, yyyymmdd)
        kb = _kb_allow_add_screen(state, yyyymmdd)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer("Added window ✅")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clralw:\d{8}$"))
    async def nsfw_clear_allowed(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        yyyymmdd = cq.data.split(":")[-1]
        state = _load_state()
        _clear_allowed(state, yyyymmdd)
        _save_state(state)

        # Take you back to the add screen (so you can immediately rebuild windows)
        text = _render_allow_add_text(state, yyyymmdd)
        kb = _kb_allow_add_screen(state, yyyymmdd)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer("Availability reset ✅")

    @app.on_callback_query(filters.regex(r"^nsfw_avail:clrall:\d{8}$"))
    async def nsfw_clear_all(_, cq: CallbackQuery):
        if not _is_owner(cq.from_user.id):
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        yyyymmdd = cq.data.split(":")[-1]
        state = _load_state()
        _clear_all_for_date(state, yyyymmdd)
        _save_state(state)

        text = _render_day_text(state, yyyymmdd)
        kb = _kb_day_actions(yyyymmdd)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer("Cleared ✅")

