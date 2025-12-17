# handlers/nsfw_text_session_booking.py
import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from utils.menu_store import store

log = logging.getLogger(__name__)
TZ_LA = pytz.timezone("America/Los_Angeles")

# Business hours (LA time) for booking UI
OPEN_HOUR = 9    # 9 AM
CLOSE_HOUR = 22  # 10 PM
SLOT_MINUTES = 30

# Durations users can pick (minutes)
DURATIONS = [30, 60, 90, 120]

# Simple in-memory selection (good enough for button flow)
# If your bot restarts mid-flow, user can just click again.
_user_state: Dict[int, Dict[str, int]] = {}  # {user_id: {"dur": 60}}


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


def _fmt_week_range(ws: date) -> str:
    we = ws + timedelta(days=6)
    return f"Week of <b>{ws.strftime('%B %d')}</b> → <b>{we.strftime('%B %d')}</b>"


def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _min_to_hhmm(m: int) -> str:
    return f"{m//60:02d}:{m%60:02d}"


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    # Overlap if A starts before B ends and B starts before A ends
    return a_start < b_end and b_start < a_end


def _slot_id_to_hhmm(slot_id: str) -> str:
    # "0930" -> "09:30"
    return f"{slot_id[:2]}:{slot_id[2:]}"


def _hhmm_to_slot_id(hhmm: str) -> str:
    # "09:30" -> "0930"
    return hhmm.replace(":", "")


def _label_hhmm(hhmm: str) -> str:
    # "09:30" -> "9:30 AM"
    t = datetime(2000, 1, 1, int(hhmm[:2]), int(hhmm[3:]))
    try:
        return t.strftime("%-I:%M %p")
    except Exception:
        return t.strftime("%I:%M %p").lstrip("0")


def _load_day_obj(d: str) -> dict:
    raw = store.get_menu(_avail_key(d))
    obj = _jloads(raw, {}) if raw else {}
    if not isinstance(obj, dict):
        obj = {}

    # Normalize both formats:
    # - New: blocked_windows: [["09:00","11:30"], ...]
    # - Legacy: blocked: ["0900","0930",...]
    obj.setdefault("blocked_windows", [])
    obj.setdefault("blocked", [])

    if not isinstance(obj["blocked_windows"], list):
        obj["blocked_windows"] = []
    if not isinstance(obj["blocked"], list):
        obj["blocked"] = []

    # Clean up invalid window shapes
    cleaned: List[List[str]] = []
    for w in obj["blocked_windows"]:
        if (
            isinstance(w, (list, tuple))
            and len(w) == 2
            and isinstance(w[0], str)
            and isinstance(w[1], str)
            and ":" in w[0]
            and ":" in w[1]
        ):
            cleaned.append([w[0], w[1]])
    obj["blocked_windows"] = cleaned

    # Normalize legacy slot list to strings like "0930"
    obj["blocked"] = [str(x).zfill(4) for x in obj["blocked"] if str(x).isdigit()]

    return obj


def _is_blocked(day_obj: dict, start_hhmm: str, end_hhmm: str) -> bool:
    """
    Returns True if the proposed interval overlaps any blocked window OR any legacy blocked slot.
    """
    s = _to_minutes(start_hhmm)
    e = _to_minutes(end_hhmm)

    # Check window blocks
    for w in day_obj.get("blocked_windows", []) or []:
        try:
            ws = _to_minutes(w[0])
            we = _to_minutes(w[1])
        except Exception:
            continue
        if _overlaps(s, e, ws, we):
            return True

    # Check legacy per-slot blocks (treat each as SLOT_MINUTES block)
    for slot_id in day_obj.get("blocked", []) or []:
        try:
            slot_start = _to_minutes(_slot_id_to_hhmm(slot_id))
            slot_end = slot_start + SLOT_MINUTES
        except Exception:
            continue
        if _overlaps(s, e, slot_start, slot_end):
            return True

    return False


def _get_user_duration(user_id: int) -> int:
    return int(_user_state.get(user_id, {}).get("dur", 60))


def _set_user_duration(user_id: int, dur: int):
    _user_state.setdefault(user_id, {})
    _user_state[user_id]["dur"] = int(dur)


def _week_kb(ws: date) -> InlineKeyboardMarkup:
    days = [ws + timedelta(days=i) for i in range(7)]
    rows = []
    for i in range(0, 6, 2):
        rows.append([
            InlineKeyboardButton(days[i].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[i]:%Y-%m-%d}"),
            InlineKeyboardButton(days[i+1].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[i+1]:%Y-%m-%d}"),
        ])
    rows.append([
        InlineKeyboardButton(days[6].strftime("%a %b %d"), callback_data=f"nsfw_book:day:{days[6]:%Y-%m-%d}")
    ])
    rows.append([
        InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_book:week:{(ws - timedelta(days=7)):%Y-%m-%d}"),
        InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_book:week:{(ws + timedelta(days=7)):%Y-%m-%d}"),
    ])
    rows.append([
        InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")
    ])
    return InlineKeyboardMarkup(rows)


def _dur_kb(current_dur: int, d: str) -> InlineKeyboardMarkup:
    row = []
    for dur in DURATIONS:
        label = f"{dur}m" + (" ✅" if dur == current_dur else "")
        row.append(InlineKeyboardButton(label, callback_data=f"nsfw_book:dur:{dur}:{d}"))
    return InlineKeyboardMarkup([row])


def _build_times_kb(d: str, dur: int, available_starts: List[str]) -> InlineKeyboardMarkup:
    """
    available_starts: list of "HH:MM"
    """
    # Put times into 3-column grid
    rows = []
    row = []
    for i, hhmm in enumerate(available_starts, start=1):
        row.append(InlineKeyboardButton(_label_hhmm(hhmm), callback_data=f"nsfw_book:time:{d}:{_hhmm_to_slot_id(hhmm)}:{dur}"))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back to week", callback_data=f"nsfw_book:week:{d}")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)


async def _render_week(cq: CallbackQuery, any_day: date):
    ws = _monday(any_day)
    await cq.message.edit_text(
        "💞 <b>Book a private NSFW texting session</b>\n\n"
        "Pick a day (LA time):\n"
        f"{_fmt_week_range(ws)}",
        reply_markup=_week_kb(ws),
        disable_web_page_preview=True,
    )
    await cq.answer()


def _generate_available_start_times(d: str, dur: int) -> List[str]:
    """
    Generates start times every SLOT_MINUTES between OPEN_HOUR and CLOSE_HOUR
    and filters out any that overlap blocked_windows.
    """
    day_obj = _load_day_obj(d)

    open_min = OPEN_HOUR * 60
    close_min = CLOSE_HOUR * 60

    # last start time must fit full duration
    last_start = close_min - dur
    if last_start < open_min:
        return []

    out: List[str] = []
    m = open_min
    while m <= last_start:
        start = _min_to_hhmm(m)
        end = _min_to_hhmm(m + dur)
        if not _is_blocked(day_obj, start, end):
            out.append(start)
        m += SLOT_MINUTES

    return out


def register(app: Client):
    log.info("✅ nsfw_text_session_booking registered (supports multiple blocked windows)")

    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def open_new(_, cq: CallbackQuery):
        await _render_week(cq, _today_la())

    # Back-compat aliases (keep your old buttons working)
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
        uid = cq.from_user.id if cq.from_user else 0
        dur = _get_user_duration(uid)

        available = _generate_available_start_times(d, dur)

        header = f"📅 <b>{datetime.strptime(d, '%Y-%m-%d').strftime('%A, %B %d')}</b> (LA time)\n"
        header += f"🕘 Hours: <b>{_label_hhmm(f'{OPEN_HOUR:02d}:00')}</b> – <b>{_label_hhmm(f'{CLOSE_HOUR:02d}:00')}</b>\n\n"
        header += f"Choose your duration:\n"

        await cq.message.edit_text(
            header,
            reply_markup=_dur_kb(dur, d),
            disable_web_page_preview=True,
        )
        await cq.answer()

        # After choosing duration, we will show times.
        # (This keeps the UI clean and avoids a giant message.)

    @app.on_callback_query(filters.regex(r"^nsfw_book:dur:(\d+):(\d{4}-\d{2}-\d{2})$"))
    async def choose_duration(_, cq: CallbackQuery):
        parts = (cq.data or "").split(":")
        dur = int(parts[2])
        d = parts[3]

        uid = cq.from_user.id if cq.from_user else 0
        _set_user_duration(uid, dur)

        available = _generate_available_start_times(d, dur)

        title = f"📅 <b>{datetime.strptime(d, '%Y-%m-%d').strftime('%A, %B %d')}</b> (LA time)\n"
        title += f"⏱ Duration: <b>{dur} minutes</b>\n\n"

        if not available:
            title += "❌ No start times available (everything is blocked)."
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_book:day:{d}")],
                [InlineKeyboardButton("⬅ Back to week", callback_data=f"nsfw_book:week:{d}")],
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
            ])
            await cq.message.edit_text(title, reply_markup=kb, disable_web_page_preview=True)
            await cq.answer()
            return

        title += "Pick a start time:"
        await cq.message.edit_text(
            title,
            reply_markup=_build_times_kb(d, dur, available),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:time:(\d{4}-\d{2}-\d{2}):(\d{4}):(\d+)$"))
    async def pick_time(_, cq: CallbackQuery):
        parts = (cq.data or "").split(":")
        d = parts[2]
        slot_id = parts[3]
        dur = int(parts[4])

        start_hhmm = _slot_id_to_hhmm(slot_id)
        start_m = _to_minutes(start_hhmm)
        end_hhmm = _min_to_hhmm(start_m + dur)

        # Final guard: re-check blocked (in case admin changed blocks while user was picking)
        day_obj = _load_day_obj(d)
        if _is_blocked(day_obj, start_hhmm, end_hhmm):
            await cq.answer("That time just got blocked. Pick another time.", show_alert=True)
            # Re-render times
            available = _generate_available_start_times(d, dur)
            await cq.message.edit_text(
                f"📅 <b>{datetime.strptime(d, '%Y-%m-%d').strftime('%A, %B %d')}</b> (LA time)\n"
                f"⏱ Duration: <b>{dur} minutes</b>\n\n"
                "Pick a start time:",
                reply_markup=_build_times_kb(d, dur, available),
                disable_web_page_preview=True,
            )
            return

        # At this point you would normally create a booking record / notify admin.
        # For now, we confirm selection and provide a "message admin" or "back" buttons.
        msg = (
            "✅ <b>Request drafted</b>\n\n"
            f"📅 <b>{datetime.strptime(d, '%Y-%m-%d').strftime('%A, %B %d')}</b> (LA time)\n"
            f"🕒 <b>{_label_hhmm(start_hhmm)}</b> → <b>{_label_hhmm(end_hhmm)}</b>\n"
            f"⏱ <b>{dur} minutes</b>\n\n"
            "Next step: (wire this to your payment/DM flow) 💕"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅ Pick another time", callback_data=f"nsfw_book:dur:{dur}:{d}")],
            [InlineKeyboardButton("⬅ Back to week", callback_data=f"nsfw_book:week:{d}")],
            [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
        ])

        await cq.message.edit_text(msg, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()
