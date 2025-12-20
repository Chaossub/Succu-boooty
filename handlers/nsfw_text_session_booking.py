import json
import logging
import os
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.menu_store import store

log = logging.getLogger(__name__)

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))

LA_TZ = pytz.timezone("America/Los_Angeles")
SLOT_MINUTES = 30


def _jget(key: str, default):
    try:
        raw = store.get_menu(key)
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default


def _jset(key: str, obj) -> None:
    try:
        store.set_menu(key, json.dumps(obj))
    except Exception:
        log.exception("Failed saving %s", key)


def _key_day(date_yyyy_mm_dd: str) -> str:
    # must match nsfw_text_session_availability.py
    return f"NSFW_AVAIL_DAY:{date_yyyy_mm_dd}"


def _key_pending() -> str:
    return "NSFW_BOOKING_REQUESTS"


def _today_la() -> datetime:
    return datetime.now(LA_TZ)


def _fmt_day(d: datetime) -> str:
    return d.strftime("%a %b %d")


def _parse_hhmm(val: str) -> time:
    h, m = val.split(":")
    return time(int(h), int(m))


def _time_range_slots(open_t: time, close_t: time) -> List[time]:
    # slots represent START times
    start = datetime(2000, 1, 1, open_t.hour, open_t.minute)
    end = datetime(2000, 1, 1, close_t.hour, close_t.minute)
    out: List[time] = []
    cur = start
    while cur < end:
        out.append(cur.time())
        cur += timedelta(minutes=SLOT_MINUTES)
    return out


def _is_slot_blocked(blocked: List[List[str]], slot_start: time, slot_end: time) -> bool:
    """blocked windows are [["HH:MM","HH:MM"], ...]"""
    ss = datetime(2000, 1, 1, slot_start.hour, slot_start.minute)
    se = datetime(2000, 1, 1, slot_end.hour, slot_end.minute)
    for b0, b1 in blocked:
        bs = datetime(2000, 1, 1, _parse_hhmm(b0).hour, _parse_hhmm(b0).minute)
        be = datetime(2000, 1, 1, _parse_hhmm(b1).hour, _parse_hhmm(b1).minute)
        # overlap
        if ss < be and se > bs:
            return True
    return False


def _load_day(date_yyyy_mm_dd: str) -> Dict:
    """Returns dict with open, close, blocked; provides defaults if empty."""
    day = _jget(
        _key_day(date_yyyy_mm_dd),
        {
            "open": "09:00",
            "close": "22:00",
            "blocked": [],
        },
    )
    if not isinstance(day, dict):
        day = {"open": "09:00", "close": "22:00", "blocked": []}
    day.setdefault("open", "09:00")
    day.setdefault("close", "22:00")
    day.setdefault("blocked", [])
    return day


def _available_start_times(date_yyyy_mm_dd: str) -> Tuple[time, time, List[time]]:
    day = _load_day(date_yyyy_mm_dd)
    open_t = _parse_hhmm(day["open"])
    close_t = _parse_hhmm(day["close"])
    blocked = day.get("blocked", []) or []

    starts = []
    for st in _time_range_slots(open_t, close_t):
        en_dt = datetime(2000, 1, 1, st.hour, st.minute) + timedelta(minutes=SLOT_MINUTES)
        en = en_dt.time()
        if _is_slot_blocked(blocked, st, en):
            continue
        # also don't allow the very last slot if it would end after close
        close_dt = datetime(2000, 1, 1, close_t.hour, close_t.minute)
        if en_dt > close_dt:
            continue
        starts.append(st)

    return open_t, close_t, starts


def _week_keyboard(offset_weeks: int) -> InlineKeyboardMarkup:
    base = _today_la().date() + timedelta(days=offset_weeks * 7)

    rows = []
    for i in range(7):
        d = base + timedelta(days=i)
        # never show past days
        if d < _today_la().date():
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    _fmt_day(datetime.combine(d, time(0, 0)).replace(tzinfo=LA_TZ)),
                    callback_data=f"nsfw_book:day:{d.isoformat()}",
                )
            ]
        )

    nav = []
    if offset_weeks > 0:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"nsfw_book:week:{offset_weeks-1}"))
    nav.append(InlineKeyboardButton("Next ➡", callback_data=f"nsfw_book:week:{offset_weeks+1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)


def _times_keyboard(date_yyyy_mm_dd: str, offset: int = 0) -> InlineKeyboardMarkup:
    _, _, starts = _available_start_times(date_yyyy_mm_dd)

    per_page = 12  # 6 rows x 2 cols
    page = starts[offset : offset + per_page]

    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(page), 2):
        row = []
        for t in page[i : i + 2]:
            label = datetime(2000, 1, 1, t.hour, t.minute).strftime("%I:%M %p").lstrip("0")
            row.append(
                InlineKeyboardButton(
                    f"🕒 {label}",
                    callback_data=f"nsfw_book:time:{date_yyyy_mm_dd}:{t.strftime('%H:%M')}",
                )
            )
        rows.append(row)

    nav: List[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"nsfw_book:times:{date_yyyy_mm_dd}:{max(0, offset - per_page)}"))
    if offset + per_page < len(starts):
        nav.append(InlineKeyboardButton("More ➡", callback_data=f"nsfw_book:times:{date_yyyy_mm_dd}:{offset + per_page}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back to week", callback_data="nsfw_book:week:0")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")])

    return InlineKeyboardMarkup(rows)


def _duration_keyboard(date_yyyy_mm_dd: str, hhmm: str) -> InlineKeyboardMarkup:
    mins = [30, 60, 90, 120]
    rows = []
    for m in mins:
        label = f"{m}m" if m < 60 else f"{m//60}h" if m % 60 == 0 else f"{m//60}h {m%60}m"
        rows.append([InlineKeyboardButton(label, callback_data=f"nsfw_book:confirm:{date_yyyy_mm_dd}:{hhmm}:{m}")])

    rows.append([InlineKeyboardButton("⬅ Pick a different time", callback_data=f"nsfw_book:day:{date_yyyy_mm_dd}")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)


def _render_week_text(offset_weeks: int) -> str:
    base = _today_la().date() + timedelta(days=offset_weeks * 7)
    start = base
    end = base + timedelta(days=6)
    return (
        "💗 <b>Book a private NSFW texting session</b>\n\n"
        f"Pick a day (LA time):\n<b>{start.strftime('%b %d')}</b> — <b>{end.strftime('%b %d')}</b>"
    )


def _render_day_text(date_yyyy_mm_dd: str) -> str:
    d = datetime.strptime(date_yyyy_mm_dd, "%Y-%m-%d").date()
    day = _load_day(date_yyyy_mm_dd)

    open_t, close_t, starts = _available_start_times(date_yyyy_mm_dd)
    open_label = datetime(2000, 1, 1, open_t.hour, open_t.minute).strftime("%H:%M")
    close_label = datetime(2000, 1, 1, close_t.hour, close_t.minute).strftime("%H:%M")

    return (
        f"🗓️ <b>{d.strftime('%A, %B %d')} (LA time)</b>\n"
        f"Open: <b>{open_label}</b> · Close: <b>{close_label}</b>\n\n"
        f"Available start times: <b>{len(starts)}</b>\n"
        "Pick a start time:" 
    )


def _render_duration_text(date_yyyy_mm_dd: str, hhmm: str) -> str:
    d = datetime.strptime(date_yyyy_mm_dd, "%Y-%m-%d").date()
    label = datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")
    return (
        f"🗓️ <b>{d.strftime('%A, %B %d')}</b>\n"
        f"Start: <b>{label}</b>\n\n"
        "Choose a duration:" 
    )


def _is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID


def register(app: Client):
    @app.on_callback_query(filters.regex(r"^nsfw_book:"))
    async def _on_cb(_, cq: CallbackQuery):
        data = cq.data or ""

        try:
            if data == "nsfw_book:open" or data.startswith("nsfw_book:week:"):
                off = 0
                if data.startswith("nsfw_book:week:"):
                    off = int(data.split(":")[-1])
                await cq.message.edit_text(
                    _render_week_text(off),
                    reply_markup=_week_keyboard(off),
                    disable_web_page_preview=True,
                )
                await cq.answer()
                return

            if data.startswith("nsfw_book:day:"):
                date_yyyy_mm_dd = data.split(":", 2)[-1]
                await cq.message.edit_text(
                    _render_day_text(date_yyyy_mm_dd),
                    reply_markup=_times_keyboard(date_yyyy_mm_dd, 0),
                    disable_web_page_preview=True,
                )
                await cq.answer()
                return

            if data.startswith("nsfw_book:times:"):
                _, _, date_yyyy_mm_dd, off_s = data.split(":", 3)
                await cq.message.edit_reply_markup(reply_markup=_times_keyboard(date_yyyy_mm_dd, int(off_s)))
                await cq.answer()
                return

            if data.startswith("nsfw_book:time:"):
                _, _, date_yyyy_mm_dd, hhmm = data.split(":", 3)
                await cq.message.edit_text(
                    _render_duration_text(date_yyyy_mm_dd, hhmm),
                    reply_markup=_duration_keyboard(date_yyyy_mm_dd, hhmm),
                    disable_web_page_preview=True,
                )
                await cq.answer()
                return

            if data.startswith("nsfw_book:confirm:"):
                _, _, date_yyyy_mm_dd, hhmm, mins_s = data.split(":", 4)
                mins = int(mins_s)

                # store request
                req = {
                    "user_id": cq.from_user.id,
                    "user_name": cq.from_user.first_name,
                    "username": cq.from_user.username,
                    "date": date_yyyy_mm_dd,
                    "time": hhmm,
                    "duration_minutes": mins,
                    "requested_at": datetime.utcnow().isoformat() + "Z",
                }
                pending = _jget(_key_pending(), [])
                if not isinstance(pending, list):
                    pending = []
                pending.append(req)
                _jset(_key_pending(), pending)

                pretty_time = datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")
                msg = (
                    "📩 <b>New NSFW texting booking request</b>\n\n"
                    f"From: <b>{cq.from_user.first_name}</b>"
                )
                if cq.from_user.username:
                    msg += f" (@{cq.from_user.username})"
                msg += (
                    f"\nUser ID: <code>{cq.from_user.id}</code>\n"
                    f"When (LA): <b>{date_yyyy_mm_dd}</b> at <b>{pretty_time}</b>\n"
                    f"Duration: <b>{mins} minutes</b>\n\n"
                    "Reply to the user directly if you want to confirm details."
                )

                try:
                    await app.send_message(OWNER_ID, msg, disable_web_page_preview=True)
                except Exception:
                    log.exception("Failed to notify owner about booking request")

                await cq.message.edit_text(
                    "✅ Request sent!\n\nRoni will reach out to confirm availability and payment details.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]]
                    ),
                    disable_web_page_preview=True,
                )
                await cq.answer("Sent!")
                return

        except Exception:
            log.exception("nsfw booking callback failed: %s", data)
            try:
                await cq.answer("Something went wrong", show_alert=True)
            except Exception:
                pass

    log.info("✅ nsfw_text_session_booking registered (availability-aware)")
