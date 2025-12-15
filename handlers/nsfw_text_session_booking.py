# handlers/nsfw_text_session_booking.py
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

import pytz
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.menu_store import store

AGE_OK_PREFIX = "AGE_OK:"
RONI_OWNER_ID = 6964994611

def _is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id == RONI_OWNER_ID:
        return True
    try:
        return bool(store.get_menu(f"{AGE_OK_PREFIX}{user_id}"))
    except Exception:
        return False

from utils.nsfw_store import (
    TZ,
    add_booking,
    find_latest_booking_for_user,
    get_allowed_for_date,
    get_business_hours_for_weekday,
    is_blocked,
    is_within_allowed,
    update_booking,
)

RONI_OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))
RONI_MENU_KEY = "RoniPersonalMenu"


def _tz():
    return pytz.timezone(TZ)


def _now() -> datetime:
    return datetime.now(_tz())


def _dt_to_ymd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _ymd_to_dt(ymd: str) -> datetime:
    return _tz().localize(datetime(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]), 0, 0, 0))


def _pretty_date(dt: datetime) -> str:
    return dt.strftime("%a %b %d").replace(" 0", " ")


def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(m: int) -> str:
    return f"{m//60:02d}:{m%60:02d}"


def _intro_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 View Roni’s Menu", callback_data="roni_portal:menu:src=nsfw")],
            [InlineKeyboardButton("➡️ Continue Booking", callback_data="nsfw_book:start")],
            [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
        ]
    )


def _duration_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏱ 30 minutes", callback_data="nsfw_book:dur:30")],
            [InlineKeyboardButton("🕰 1 hour", callback_data="nsfw_book:dur:60")],
            [InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:open")],
        ]
    )


def _date_picker(duration: int, week: int) -> InlineKeyboardMarkup:
    base = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = base + timedelta(days=week * 7)

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for i in range(7):
        d = start + timedelta(days=i)
        ymd = _dt_to_ymd(d)
        row.append(InlineKeyboardButton(_pretty_date(d), callback_data=f"nsfw_book:day:{duration}:{ymd}:{week}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav: List[InlineKeyboardButton] = []
    if week > 0:
        nav.append(InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_book:daypick:{duration}:{week-1}"))
    nav.append(InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_book:daypick:{duration}:{week+1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data="nsfw_book:start")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)


def _candidate_windows_for_day(ymd: str) -> List[Tuple[str, str]]:
    """
    If allowed windows exist -> use them.
    Else -> use business hours for that weekday.
    """
    allowed = get_allowed_for_date(ymd)
    if allowed:
        return allowed

    day = _ymd_to_dt(ymd)
    open_h, close_h = get_business_hours_for_weekday(day.weekday())
    return [(open_h, close_h)]


def _slots(ymd: str, duration: int) -> List[str]:
    """
    Generates valid start times in 30-min increments, obeying:
    - allowed windows (if set) OR business hours
    - blocks always remove times
    """
    windows = _candidate_windows_for_day(ymd)
    starts: List[str] = []

    for open_h, close_h in windows:
        open_m = _min(open_h)
        close_m = _min(close_h)
        latest_start = close_m - duration

        m = open_m
        while m <= latest_start:
            s = _hhmm(m)
            e = _hhmm(m + duration)

            # Must be within allowed windows if any exist
            if not is_within_allowed(ymd, s, e):
                m += 30
                continue

            # Must NOT intersect a block
            if not is_blocked(ymd, s, e):
                starts.append(s)

            m += 30

    starts = sorted(set(starts), key=_min)
    return starts


def _times_kb(duration: int, ymd: str, week: int) -> InlineKeyboardMarkup:
    starts = _slots(ymd, duration)
    if not starts:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Pick another date", callback_data=f"nsfw_book:daypick:{duration}:{week}")],
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
            ]
        )

    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for s in starts[:45]:
        row.append(
            InlineKeyboardButton(
                s,
                callback_data=f"nsfw_book:time:{duration}:{ymd}:{week}:{s.replace(':','')}",
            )
        )
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nsfw_book:daypick:{duration}:{week}")])
    rows.append([InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")])
    return InlineKeyboardMarkup(rows)


def _note_kb(booking_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✍️ Add a note", callback_data=f"nsfw_book:note:{booking_id}")],
            [InlineKeyboardButton("⏭ Skip", callback_data=f"nsfw_book:skipnote:{booking_id}")],
        ]
    )


def _final_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 View Roni’s Menu", callback_data="roni_portal:menu:src=nsfw")],
            [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
        ]
    )


def _final_text() -> str:
    return (
        "Your session is booked 💞\n"
        "Roni will reach out to you for payment :)\n\n"
        "You can find current prices in 📖 Roni’s Menu."
    )


async def _notify_roni(app: Client, booking: dict) -> None:
    """
    DM Roni whenever someone books.
    """
    try:
        user_id = booking.get("user_id")
        username = booking.get("username") or ""
        display_name = booking.get("display_name") or ""
        ymd = booking.get("date")
        start = booking.get("start_time")
        dur = booking.get("duration")
        note = (booking.get("note") or "").strip()

        day_dt = _ymd_to_dt(ymd)
        pretty = day_dt.strftime("%A, %b %d").replace(" 0", " ")

        who = f"{display_name}".strip()
        if username:
            who = f"{who} {username}".strip()
        if not who:
            who = f"User {user_id}"

        msg = (
            "📩 <b>New scheduled NSFW texting session</b>\n\n"
            f"👤 <b>Client:</b> {who}\n"
            f"📅 <b>Date:</b> {pretty}\n"
            f"⏰ <b>Time:</b> {start} ({TZ})\n"
            f"⏳ <b>Duration:</b> {dur} minutes\n"
        )
        if note:
            msg += f"\n📝 <b>Note:</b>\n{note}\n"

        await app.send_message(RONI_OWNER_ID, msg, disable_web_page_preview=True)
    except Exception:
        # Don’t crash booking if DM fails
        return


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def nsfw_open(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if user_id != RONI_OWNER_ID and not _is_age_verified(user_id):
            await cq.answer("Photo age verification required 💕", show_alert=True)
            try:
                await cq.message.edit_text(
                    "🔒 <b>Locked</b>\n\n"
                    "To book a private NSFW texting session, please complete photo age verification first.\n\n"
                    "Tap ✅ <b>Age Verify</b> and submit the required photo.",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("✅ Age Verify", callback_data="roni_portal:age")],
                            [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                        ]
                    ),
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
            return
        await cq.message.edit_text(
            "💞 <b>Before booking</b>\n"
            "Please check 📖 <b>Roni’s Menu</b> for pricing first.\n\n"
            "<b>Texting only — NO meetups.</b>\n\n"
            "Continue when you’re ready:",
            reply_markup=_intro_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:start$"))
    async def nsfw_start(_, cq: CallbackQuery):
        await cq.message.edit_text("Choose your session length 💕", reply_markup=_duration_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:dur:(30|60)$"))
    async def nsfw_dur(_, cq: CallbackQuery):
        duration = int(cq.data.split(":")[2])
        await cq.message.edit_text(
            "Pick a date 📅 (Los Angeles time)",
            reply_markup=_date_picker(duration, 0),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:daypick:(30|60):\d+$"))
    async def nsfw_daypick(_, cq: CallbackQuery):
        # nsfw_book:daypick:<dur>:<week>
        _, _, dur_s, week_s = cq.data.split(":")
        duration = int(dur_s)
        week = int(week_s)
        await cq.message.edit_text(
            "Pick a date 📅 (Los Angeles time)",
            reply_markup=_date_picker(duration, week),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(30|60):\d{8}:\d+$"))
    async def nsfw_day(_, cq: CallbackQuery):
        # nsfw_book:day:<dur>:<yyyymmdd>:<week>
        _, _, dur_s, ymd, week_s = cq.data.split(":")
        duration = int(dur_s)
        week = int(week_s)

        day_dt = _ymd_to_dt(ymd)
        label = day_dt.strftime("%A, %b %d").replace(" 0", " ")

        await cq.message.edit_text(
            f"{label}\n\nPick a start time (LA) ⏰",
            reply_markup=_times_kb(duration, ymd, week),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:time:(30|60):\d{8}:\d+:\d{4}$"))
    async def nsfw_time(_, cq: CallbackQuery):
        # nsfw_book:time:<dur>:<yyyymmdd>:<week>:<hhmm>
        _, _, dur_s, ymd, week_s, hhmm_compact = cq.data.split(":")
        duration = int(dur_s)
        hhmm = f"{hhmm_compact[:2]}:{hhmm_compact[2:]}"
        end = _hhmm(_min(hhmm) + duration)

        # FINAL SAFETY CHECK: if blocked, refuse
        if is_blocked(ymd, hhmm, end):
            await cq.answer("That time is no longer available 💕 Please pick another.", show_alert=True)
            await cq.message.edit_text(
                "Pick a date 📅 (Los Angeles time)",
                reply_markup=_date_picker(duration, int(week_s)),
                disable_web_page_preview=True,
            )
            return

        # FINAL SAFETY CHECK: if allowed windows exist, enforce
        if not is_within_allowed(ymd, hhmm, end):
            await cq.answer("That time is not available 💕 Please pick another.", show_alert=True)
            await cq.message.edit_text(
                "Pick a date 📅 (Los Angeles time)",
                reply_markup=_date_picker(duration, int(week_s)),
                disable_web_page_preview=True,
            )
            return

        user = cq.from_user
        booking_id = uuid.uuid4().hex[:10]

        booking = {
            "booking_id": booking_id,
            "created_ts": time.time(),
            "user_id": user.id if user else 0,
            "username": f"@{user.username}" if user and user.username else "",
            "display_name": (user.first_name or "").strip() if user else "",
            "date": ymd,
            "start_time": hhmm,
            "duration": duration,
            "note": "",
            "status": "awaiting_note",
            "tz": TZ,
        }
        add_booking(booking)

        await cq.message.edit_text(
            "Optional 💬\n"
            "Leave a short note about what you’re looking for (or skip).",
            reply_markup=_note_kb(booking_id),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:note:[0-9a-f]{10}$"))
    async def nsfw_note_start(_, cq: CallbackQuery):
        booking_id = cq.data.split(":")[2]
        store.set_menu(f"NSFW_NOTE_PENDING:{cq.from_user.id}", booking_id)

        await cq.message.edit_text(
            "Send your note in <b>one message</b> 💕",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⏭ Skip", callback_data=f"nsfw_book:skipnote:{booking_id}")]]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:skipnote:[0-9a-f]{10}$"))
    async def nsfw_skipnote(_, cq: CallbackQuery):
        booking_id = cq.data.split(":")[2]
        store.set_menu(f"NSFW_NOTE_PENDING:{cq.from_user.id}", "")
        update_booking(booking_id, {"status": "pending_payment"})

        # Notify Roni
        try:
            latest = find_latest_booking_for_user(cq.from_user.id, statuses=["pending_payment", "awaiting_note"])
            if latest:
                await _notify_roni(app, latest)
        except Exception:
            pass

        await cq.message.edit_text(_final_text(), reply_markup=_final_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_message(filters.private & filters.text, group=-5)
    async def nsfw_note_capture(_, m: Message):
        if not m.from_user:
            return
        user_id = m.from_user.id
        pending = (store.get_menu(f"NSFW_NOTE_PENDING:{user_id}") or "").strip()

        booking_id = pending
        if not booking_id:
            latest = find_latest_booking_for_user(user_id, statuses=["awaiting_note"])
            if not latest:
                return
            booking_id = (latest.get("booking_id") or "").strip()
            if not booking_id:
                return

        note = (m.text or "").strip()
        if not note:
            return
        if len(note) > 700:
            note = note[:700]

        store.set_menu(f"NSFW_NOTE_PENDING:{user_id}", "")
        update_booking(booking_id, {"note": note, "status": "pending_payment"})

        # Notify Roni with note
        try:
            latest = find_latest_booking_for_user(user_id, statuses=["pending_payment"])
            if latest:
                await _notify_roni(app, latest)
        except Exception:
            pass

        await m.reply_text(_final_text(), reply_markup=_final_kb(), disable_web_page_preview=True)
