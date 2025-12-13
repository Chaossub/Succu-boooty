# handlers/nsfw_text_session_booking.py
"""
DM-only booking flow for Roni's private NSFW texting sessions (LA time).

- Buttons only (duration -> week -> day -> time -> confirm)
- Optional note supported (user can skip)
- Booking creates a PENDING request; Roni gets ✅ Accept / ❌ Cancel buttons
- Pending/Accepted bookings block time slots
- Respects per-date availability windows + blocks (set in nsfw_text_session_availability.py)
- Survives restarts via utils.menu_store.store (JSON stored through store)

Callback prefixes:
  nsfw_book:open
  nsfw_book:start             (alias for open; used when returning from menu)
  nsfw_book:dur:<30|60>
  nsfw_book:week:<YYYYMMDD>:<dur>
  nsfw_book:day:<YYYYMMDD>:<dur>
  nsfw_book:time:<YYYYMMDD>:<dur>:<HHMM>
  nsfw_book:note
  nsfw_book:confirm
  nsfw_book:cancel
  nsfw_admin:accept:<booking_id>
  nsfw_admin:cancel:<booking_id>
"""

import json
import logging
from datetime import datetime, timedelta, time as dtime
from uuid import uuid4

import pytz
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.menu_store import store

log = logging.getLogger(__name__)

TZ = pytz.timezone("America/Los_Angeles")
RONI_OWNER_ID = 6964994611

RONI_MENU_KEY = "RoniPersonalMenu"  # same as roni_portal.py


# -------------------- storage helpers --------------------

def _age_key(user_id: int) -> str:
    return f"AGE_OK:{user_id}"


def _is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id == RONI_OWNER_ID:
        return True
    try:
        return bool(store.get_menu(_age_key(user_id)))
    except Exception:
        return False


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


def _state_key(user_id: int) -> str:
    return f"NSFW_BOOK_STATE:{user_id}"


def _bookings_key(yyyymmdd: str) -> str:
    return f"NSFW_BOOKINGS:{yyyymmdd}"


def _avail_key(yyyymmdd: str) -> str:
    return f"NSFW_AVAIL:{yyyymmdd}"


def _booking_id_key(booking_id: str) -> str:
    return f"NSFW_BOOK_ID:{booking_id}"


def _parse_date(yyyymmdd: str) -> datetime:
    return datetime.strptime(yyyymmdd, "%Y%m%d")


def _today_local() -> datetime:
    return datetime.now(TZ)


def _week_start_local(dt: datetime) -> datetime:
    d = dt.date()
    start = d - timedelta(days=d.weekday())  # Monday
    return datetime.combine(start, dtime(0, 0))


def _fmt_day(dt: datetime) -> str:
    return dt.strftime("%A, %B %d")


def _fmt_week_day(dt: datetime) -> str:
    return dt.strftime("%a %b %d")


def _fmt_time_12(hhmm: str) -> str:
    return datetime.strptime(hhmm, "%H%M").strftime("%I:%M %p").lstrip("0")


def _weekday_default_hours(yyyymmdd: str) -> tuple[str, str]:
    wd = _parse_date(yyyymmdd).weekday()  # Mon=0..Sun=6
    # Defaults (change if you ever want):
    # Mon–Fri 9–10, Sat 9–9, Sun 9–10
    if wd == 5:
        return "09:00", "21:00"
    return "09:00", "22:00"


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _load_day_availability(yyyymmdd: str) -> dict:
    d = _jget(_avail_key(yyyymmdd), {})
    if not isinstance(d, dict):
        d = {}
    d.setdefault("on", True)
    d.setdefault("windows", [])
    d.setdefault("blocks", [])
    return d


def _load_bookings(yyyymmdd: str) -> list[dict]:
    items = _jget(_bookings_key(yyyymmdd), [])
    return items if isinstance(items, list) else []


def _save_bookings(yyyymmdd: str, items: list[dict]) -> None:
    _jset(_bookings_key(yyyymmdd), items)


def _windows_for_day(yyyymmdd: str) -> list[tuple[str, str]]:
    avail = _load_day_availability(yyyymmdd)
    if not avail.get("on", True):
        return []

    windows = avail.get("windows") or []
    out: list[tuple[str, str]] = []
    for w in windows:
        if isinstance(w, list) and len(w) == 2:
            out.append((str(w[0]), str(w[1])))

    if out:
        return out

    bh0, bh1 = _weekday_default_hours(yyyymmdd)
    return [(bh0, bh1)]


def _is_taken_status(status: str | None) -> bool:
    return (status or "").lower() in ("pending", "accepted")


# -------------------- UI builders --------------------

def _prices_button_row() -> list[InlineKeyboardButton]:
    # open menu with a source marker so it can show "Back to booking"
    return [InlineKeyboardButton("📖 View prices (Roni’s Menu)", callback_data="roni_portal:menu:src=nsfw")]


def _duration_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            _prices_button_row(),
            [InlineKeyboardButton("⏱ 30 minutes", callback_data="nsfw_book:dur:30")],
            [InlineKeyboardButton("🕰 1 hour", callback_data="nsfw_book:dur:60")],
            [InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:home")],
            [InlineKeyboardButton("❌ Nevermind", callback_data="nsfw_book:cancel")],
        ]
    )


def _week_kb(week_start: datetime, dur: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for i in range(7):
        day = week_start.date() + timedelta(days=i)
        yyyymmdd = day.strftime("%Y%m%d")
        label = _fmt_week_day(datetime.combine(day, dtime(0, 0)))
        row.append(InlineKeyboardButton(f"📅 {label}", callback_data=f"nsfw_book:day:{yyyymmdd}:{dur}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    prev_w = (week_start - timedelta(days=7)).date().strftime("%Y%m%d")
    next_w = (week_start + timedelta(days=7)).date().strftime("%Y%m%d")
    rows.append(
        [
            InlineKeyboardButton("⬅ Prev week", callback_data=f"nsfw_book:week:{prev_w}:{dur}"),
            InlineKeyboardButton("Next week ➡", callback_data=f"nsfw_book:week:{next_w}:{dur}"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("⬅️ Back", callback_data="nsfw_book:start"),
            InlineKeyboardButton("❌ Cancel", callback_data="nsfw_book:cancel"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def _times_kb(yyyymmdd: str, dur: int) -> InlineKeyboardMarkup:
    avail = _load_day_availability(yyyymmdd)
    if not avail.get("on", True):
        return InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("⬅️ Back", callback_data=f"nsfw_book:week:{yyyymmdd}:{dur}"),
                InlineKeyboardButton("❌ Cancel", callback_data="nsfw_book:cancel"),
            ]]
        )

    day0 = TZ.localize(_parse_date(yyyymmdd))
    blocks = avail.get("blocks") or []
    bookings = _load_bookings(yyyymmdd)

    step = timedelta(minutes=30)
    options: list[str] = []

    for (start_s, end_s) in _windows_for_day(yyyymmdd):
        try:
            start_dt = day0.replace(hour=int(start_s[:2]), minute=int(start_s[3:5]))
            end_dt = day0.replace(hour=int(end_s[:2]), minute=int(end_s[3:5]))
        except Exception:
            continue

        cur = start_dt
        while cur + timedelta(minutes=dur) <= end_dt:
            cand_end = cur + timedelta(minutes=dur)

            # blocks overlap
            blocked = False
            for b in blocks:
                try:
                    b0 = str(b[0]); b1 = str(b[1])
                    b_start = day0.replace(hour=int(b0[:2]), minute=int(b0[3:5]))
                    b_end = day0.replace(hour=int(b1[:2]), minute=int(b1[3:5]))
                    if _overlaps(cur, cand_end, b_start, b_end):
                        blocked = True
                        break
                except Exception:
                    continue
            if blocked:
                cur += step
                continue

            # bookings overlap (pending + accepted block times)
            taken = False
            for bk in bookings:
                if not _is_taken_status(bk.get("status")):
                    continue
                try:
                    bs = TZ.localize(datetime.strptime(bk["start"], "%Y-%m-%d %H:%M"))
                    be = TZ.localize(datetime.strptime(bk["end"], "%Y-%m-%d %H:%M"))
                    if _overlaps(cur, cand_end, bs, be):
                        taken = True
                        break
                except Exception:
                    continue

            if not taken:
                options.append(cur.strftime("%H%M"))

            cur += step

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for hhmm in options[:40]:
        row.append(InlineKeyboardButton(f"⏰ {_fmt_time_12(hhmm)}", callback_data=f"nsfw_book:time:{yyyymmdd}:{dur}:{hhmm}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    if not rows:
        rows.append([InlineKeyboardButton("⚠️ No open times", callback_data="nsfw_book:noop")])

    rows.append(
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"nsfw_book:week:{yyyymmdd}:{dur}"),
            InlineKeyboardButton("❌ Cancel", callback_data="nsfw_book:cancel"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def _confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Send request", callback_data="nsfw_book:confirm")],
            [InlineKeyboardButton("✏️ Add a note", callback_data="nsfw_book:note")],
            _prices_button_row(),
            [InlineKeyboardButton("❌ Cancel", callback_data="nsfw_book:cancel")],
        ]
    )


def _admin_decision_kb(booking_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Accept", callback_data=f"nsfw_admin:accept:{booking_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"nsfw_admin:cancel:{booking_id}"),
        ]]
    )


# -------------------- draft state --------------------

def _get_draft(user_id: int) -> dict | None:
    st = _jget(_state_key(user_id), {})
    d = st.get("draft")
    return d if isinstance(d, dict) else None


def _set_state(user_id: int, mode: str, draft: dict | None) -> None:
    _jset(_state_key(user_id), {"mode": mode, "draft": draft or {}, "updated": datetime.utcnow().isoformat()})


def _clear_state(user_id: int) -> None:
    _jset(_state_key(user_id), {})


# -------------------- main handlers --------------------

def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_text_session_booking registered")

    async def _show_start(cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not _is_age_verified(user_id):
            await cq.answer("Tap ✅ Age Verify first 💕", show_alert=True)
            return

        text = (
            "💞 <b>Book a private NSFW texting session</b>\n"
            "🚫 <b>NO meetups</b> — online/texting only.\n\n"
            "📖 Prices are in <b>Roni’s Menu</b>.\n\n"
            "⏱ How long do you want your session to be?"
        )
        await cq.message.edit_text(text, reply_markup=_duration_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:(open|start)$"))
    async def open_flow(_, cq: CallbackQuery):
        if cq.message and cq.message.chat and cq.message.chat.type != ChatType.PRIVATE:
            await cq.answer("Open this in DM 💕", show_alert=True)
            return
        await _show_start(cq)

    @app.on_callback_query(filters.regex(r"^nsfw_book:dur:(30|60)$"))
    async def pick_duration(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not _is_age_verified(user_id):
            await cq.answer("Tap ✅ Age Verify first 💕", show_alert=True)
            return

        dur = int(cq.data.split(":")[-1])

        now = _today_local()
        ws = _week_start_local(now)
        text = (
            "🗓 Pick a day that works for you 💕\n"
            f"⏱ Session length: <b>{'30 minutes' if dur == 30 else '1 hour'}</b>\n"
            "Times are shown in <b>Los Angeles</b> time.\n\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
        await cq.message.edit_text(text, reply_markup=_week_kb(ws, dur), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:week:(\d{8}):(30|60)$"))
    async def week_nav(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not _is_age_verified(user_id):
            await cq.answer("Tap ✅ Age Verify first 💕", show_alert=True)
            return

        parts = cq.data.split(":")
        if len(parts) < 4:
            await cq.answer("Try again 💕", show_alert=True)
            return
        yyyymmdd = parts[2]
        dur = int(parts[3])

        ws = _week_start_local(_parse_date(yyyymmdd))
        text = (
            "🗓 Pick a day that works for you 💕\n"
            f"⏱ Session length: <b>{'30 minutes' if dur == 30 else '1 hour'}</b>\n"
            "Times are shown in <b>Los Angeles</b> time."
        )
        await cq.message.edit_text(text, reply_markup=_week_kb(ws, dur), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(\d{8}):(30|60)$"))
    async def pick_day(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not _is_age_verified(user_id):
            await cq.answer("Tap ✅ Age Verify first 💕", show_alert=True)
            return

        parts = cq.data.split(":")
        if len(parts) < 4:
            await cq.answer("Try again 💕", show_alert=True)
            return
        yyyymmdd = parts[2]
        dur = int(parts[3])

        avail = _load_day_availability(yyyymmdd)
        if not avail.get("on", True):
            await cq.answer("That day is not bookable 💕", show_alert=True)
            return

        day_label = _fmt_day(_parse_date(yyyymmdd))
        text = (
            f"⏰ For <b>{day_label}</b>, pick a start time 💕\n"
            f"⏱ Session length: <b>{'30 minutes' if dur == 30 else '1 hour'}</b>\n\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
        await cq.message.edit_text(text, reply_markup=_times_kb(yyyymmdd, dur), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:time:(\d{8}):(30|60):(\d{4})$"))
    async def pick_time(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not _is_age_verified(user_id):
            await cq.answer("Tap ✅ Age Verify first 💕", show_alert=True)
            return

        parts = cq.data.split(":")
        if len(parts) < 5:
            await cq.answer("Try again 💕", show_alert=True)
            return
        yyyymmdd = parts[2]
        dur = int(parts[3])
        hhmm = parts[4]

        _set_state(user_id, "draft", {"date": yyyymmdd, "dur": dur, "time": hhmm, "note": ""})

        start_dt = TZ.localize(_parse_date(yyyymmdd)).replace(hour=int(hhmm[:2]), minute=int(hhmm[2:]))
        end_dt = start_dt + timedelta(minutes=dur)

        text = (
            "💗 <b>Confirm your session request</b>\n\n"
            f"💞 Session: <b>Private NSFW texting</b>\n"
            f"⏱ Length: <b>{'30 minutes' if dur == 30 else '1 hour'}</b>\n"
            f"📅 Date: <b>{start_dt.strftime('%A, %B %d')}</b>\n"
            f"⏰ Time: <b>{start_dt.strftime('%I:%M %p').lstrip('0')} – {end_dt.strftime('%I:%M %p').lstrip('0')} (LA)</b>\n\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
        await cq.message.edit_text(text, reply_markup=_confirm_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:note$"))
    async def add_note(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not user_id:
            return
        d = _get_draft(user_id)
        if not d or not d.get("date") or not d.get("time"):
            await cq.answer("Start booking again 💕", show_alert=True)
            return
        _set_state(user_id, "await_note", d)

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="nsfw_book:cancel")]])
        await cq.message.edit_text(
            "📝 Send one message with what you’re looking for (preferences / boundaries / vibe) 💕\n"
            "🚫 <b>NO meetups</b> — online/texting only.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_message(filters.private & filters.text, group=-3)
    async def capture_note(_, m: Message):
        if not m.from_user:
            return
        user_id = m.from_user.id
        st = _jget(_state_key(user_id), {})
        if st.get("mode") != "await_note":
            return
        d = st.get("draft") or {}
        if not isinstance(d, dict) or not d.get("date") or not d.get("time") or not d.get("dur"):
            _clear_state(user_id)
            return

        d["note"] = m.text[:1000]
        _set_state(user_id, "draft", d)

        yyyymmdd = str(d["date"])
        dur = int(d["dur"])
        hhmm = str(d["time"])
        start_dt = TZ.localize(_parse_date(yyyymmdd)).replace(hour=int(hhmm[:2]), minute=int(hhmm[2:]))
        end_dt = start_dt + timedelta(minutes=dur)

        text = (
            "💗 <b>Confirm your session request</b>\n\n"
            f"💞 Session: <b>Private NSFW texting</b>\n"
            f"⏱ Length: <b>{'30 minutes' if dur == 30 else '1 hour'}</b>\n"
            f"📅 Date: <b>{start_dt.strftime('%A, %B %d')}</b>\n"
            f"⏰ Time: <b>{start_dt.strftime('%I:%M %p').lstrip('0')} – {end_dt.strftime('%I:%M %p').lstrip('0')} (LA)</b>\n"
            f"📝 Note: <i>{d.get('note','')}</i>\n\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
        await m.reply_text(text, reply_markup=_confirm_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^nsfw_book:confirm$"))
    async def confirm(client: Client, cq: CallbackQuery):
        if not cq.from_user:
            return
        user_id = cq.from_user.id
        if not _is_age_verified(user_id):
            await cq.answer("Tap ✅ Age Verify first 💕", show_alert=True)
            return

        st = _jget(_state_key(user_id), {})
        d = st.get("draft") or {}
        if not isinstance(d, dict) or not d.get("date") or not d.get("time") or not d.get("dur"):
            await cq.answer("Start booking again 💕", show_alert=True)
            return

        yyyymmdd = str(d["date"])
        dur = int(d["dur"])
        hhmm = str(d["time"])
        note = str(d.get("note") or "")

        avail = _load_day_availability(yyyymmdd)
        if not avail.get("on", True):
            await cq.answer("That day is not bookable 💕", show_alert=True)
            return

        day0 = TZ.localize(_parse_date(yyyymmdd))
        start_dt = day0.replace(hour=int(hhmm[:2]), minute=int(hhmm[2:]))
        end_dt = start_dt + timedelta(minutes=dur)

        # inside allowed windows
        allowed = False
        for (ws, we) in _windows_for_day(yyyymmdd):
            try:
                w_start = day0.replace(hour=int(ws[:2]), minute=int(ws[3:5]))
                w_end = day0.replace(hour=int(we[:2]), minute=int(we[3:5]))
                if start_dt >= w_start and end_dt <= w_end:
                    allowed = True
                    break
            except Exception:
                continue
        if not allowed:
            await cq.answer("That time isn’t available 💕", show_alert=True)
            return

        # blocks
        for b in (avail.get("blocks") or []):
            try:
                b0 = str(b[0]); b1 = str(b[1])
                b_start = day0.replace(hour=int(b0[:2]), minute=int(b0[3:5]))
                b_end = day0.replace(hour=int(b1[:2]), minute=int(b1[3:5]))
                if _overlaps(start_dt, end_dt, b_start, b_end):
                    await cq.answer("That time is blocked 💕", show_alert=True)
                    return
            except Exception:
                continue

        items = _load_bookings(yyyymmdd)
        for bk in items:
            if not _is_taken_status(bk.get("status")):
                continue
            try:
                bs = TZ.localize(datetime.strptime(bk["start"], "%Y-%m-%d %H:%M"))
                be = TZ.localize(datetime.strptime(bk["end"], "%Y-%m-%d %H:%M"))
                if _overlaps(start_dt, end_dt, bs, be):
                    await cq.answer("That time just got taken 💕", show_alert=True)
                    return
            except Exception:
                continue

        booking_id = uuid4().hex
        record = {
            "id": booking_id,
            "user_id": user_id,
            "username": (cq.from_user.username or ""),
            "name": (cq.from_user.first_name or ""),
            "dur": dur,
            "start": start_dt.strftime("%Y-%m-%d %H:%M"),
            "end": end_dt.strftime("%Y-%m-%d %H:%M"),
            "note": note,
            "status": "pending",
            "created": datetime.utcnow().isoformat(),
        }
        items.append(record)
        _save_bookings(yyyymmdd, items)
        store.set_menu(_booking_id_key(booking_id), yyyymmdd)

        _clear_state(user_id)

        # notify Roni with Accept/Cancel
        try:
            who = f"{cq.from_user.first_name or 'Someone'}"
            if cq.from_user.username:
                who += f" (@{cq.from_user.username})"
            note_part = f"\n📝 Note: {note}" if note else ""
            await client.send_message(
                RONI_OWNER_ID,
                "💞 <b>New NSFW texting session request</b>\n\n"
                f"👤 {who}\n"
                f"📅 {start_dt.strftime('%A, %B %d')}\n"
                f"⏰ {start_dt.strftime('%I:%M %p').lstrip('0')} (LA time)\n"
                f"⏱ {'30 minutes' if dur == 30 else '1 hour'}"
                f"{note_part}\n\n"
                "Accept or cancel:",
                reply_markup=_admin_decision_kb(booking_id),
                disable_web_page_preview=True,
            )
        except Exception:
            log.exception("Failed to notify Roni about booking request")

        # user message: pending
        text = (
            "💞 <b>Request sent</b> 💕\n\n"
            f"📅 <b>{start_dt.strftime('%A, %B %d')}</b>\n"
            f"⏰ <b>{start_dt.strftime('%I:%M %p').lstrip('0')}</b> (LA time)\n"
            f"⏱ <b>{'30 minutes' if dur == 30 else '1 hour'}</b>\n\n"
            "Roni will review your request and reach out to you for payment :)\n"
            "You can find current prices in 📖 <b>Roni’s Menu</b>.\n\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
        kb = InlineKeyboardMarkup(
            [
                _prices_button_row(),
                [InlineKeyboardButton("💞 Book another", callback_data="nsfw_book:start")],
                [InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:home")],
            ]
        )
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer("Sent 💕")

    # ---- admin accept / cancel ----

    @app.on_callback_query(filters.regex(r"^nsfw_admin:accept:([a-f0-9]+)$"))
    async def admin_accept(client: Client, cq: CallbackQuery):
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

        if (target.get("status") or "").lower() != "pending":
            await cq.answer(f"Already {target.get('status')}.", show_alert=True)
            return

        target["status"] = "accepted"
        target["accepted_at"] = datetime.utcnow().isoformat()
        _save_bookings(yyyymmdd, items)

        # notify user
        try:
            start_dt = datetime.strptime(target["start"], "%Y-%m-%d %H:%M")
            pretty_day = start_dt.strftime("%A, %B %d")
            pretty_time = start_dt.strftime("%I:%M %p").lstrip("0")
            await client.send_message(
                int(target["user_id"]),
                "✅ <b>Your session request was accepted</b> 💕\n\n"
                f"📅 <b>{pretty_day}</b>\n"
                f"⏰ <b>{pretty_time}</b> (LA time)\n\n"
                "Roni will reach out to you for payment :)\n"
                "You can find prices in 📖 <b>Roni’s Menu</b>.\n\n"
                "🚫 <b>NO meetups</b> — online/texting only.",
                disable_web_page_preview=True,
            )
        except Exception:
            log.exception("Failed to notify user for accept")

        await cq.message.edit_text("✅ Accepted. User was notified 💕", disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_admin:cancel:([a-f0-9]+)$"))
    async def admin_cancel_booking(client: Client, cq: CallbackQuery):
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
        _save_bookings(yyyymmdd, new_items)
        store.set_menu(_booking_id_key(booking_id), "")

        # notify user
        try:
            start_dt = datetime.strptime(target["start"], "%Y-%m-%d %H:%M")
            pretty_day = start_dt.strftime("%A, %B %d")
            pretty_time = start_dt.strftime("%I:%M %p").lstrip("0")
            await client.send_message(
                int(target["user_id"]),
                "❌ <b>Your session request was cancelled</b> 💕\n\n"
                f"📅 {pretty_day}\n"
                f"⏰ {pretty_time} (LA time)\n\n"
                "If you want to reschedule, just book again from the assistant.\n\n"
                "🚫 <b>NO meetups</b> — online/texting only.",
                disable_web_page_preview=True,
            )
        except Exception:
            log.exception("Failed to notify user for cancel")

        await cq.message.edit_text("❌ Cancelled and removed. User was notified 💕", disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:noop$"))
    async def noop(_, cq: CallbackQuery):
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:cancel$"))
    async def cancel(_, cq: CallbackQuery):
        if cq.from_user:
            _clear_state(cq.from_user.id)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:home")]])
        await cq.message.edit_text(
            "❌ All good 💕 Booking cancelled.\n"
            "🚫 <b>NO meetups</b> — online/texting only.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()
