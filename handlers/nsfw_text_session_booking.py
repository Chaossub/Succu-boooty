# handlers/nsfw_text_session_booking.py
"""
Buyer-facing booking flow (DM-only) for NSFW texting sessions (LA time).

- Uses business hours by default (Mon–Fri 9–22, Sat 9–21, Sun 9–22)
- Admin can add multiple availability windows per date (optional)
- Admin can block ranges per date
- Prevents booking in blocked/taken slots
- Sends Roni a DM when someone books
- Survives restarts via menu_store persistence

Callback prefixes:
  nsfw_book:open
  nsfw_book:dur:<30|60>
  nsfw_book:day:<YYYYMMDD>:<dur>
  nsfw_book:time:<YYYYMMDD>:<dur>:<HHMM>
  nsfw_book:confirm
  nsfw_book:note
  nsfw_book:cancel
  nsfw_book:back:<...>
  nsfw_book:prices
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, time as dtime

import pytz
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.menu_store import store

log = logging.getLogger(__name__)

TZ = pytz.timezone("America/Los_Angeles")
RONI_OWNER_ID = 6964994611

RONI_MENU_KEY = "RoniPersonalMenu"  # same as roni_portal.py


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


def _parse_date(yyyymmdd: str) -> datetime:
    return datetime.strptime(yyyymmdd, "%Y%m%d")


def _today_local() -> datetime:
    return datetime.now(TZ)


def _weekday_default_hours(yyyymmdd: str) -> tuple[str, str]:
    wd = _parse_date(yyyymmdd).weekday()
    if wd == 5:  # Saturday
        return "09:00", "21:00"
    return "09:00", "22:00"


def _fmt_day(dt: datetime) -> str:
    return dt.strftime("%a %b %d")


def _fmt_time(hhmm: str) -> str:
    return datetime.strptime(hhmm, "%H%M").strftime("%I:%M %p").lstrip("0")


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
    return _jget(_bookings_key(yyyymmdd), [])


def _save_bookings(yyyymmdd: str, items: list[dict]) -> None:
    _jset(_bookings_key(yyyymmdd), items)


def _build_duration_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 View prices (Roni’s Menu)", callback_data="nsfw_book:prices")],
            [InlineKeyboardButton("⏱ 30 minutes", callback_data="nsfw_book:dur:30")],
            [InlineKeyboardButton("🕰 1 hour", callback_data="nsfw_book:dur:60")],
            [InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:home")],
            [InlineKeyboardButton("❌ Nevermind", callback_data="nsfw_book:cancel")],
        ]
    )


def _build_days_kb(dur: int) -> InlineKeyboardMarkup:
    now = _today_local()
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    # show 14 days so you can book ahead
    for i in range(14):
        day = now.date() + timedelta(days=i)
        d = datetime.combine(day, dtime(0, 0))
        label = _fmt_day(d)
        if i == 0:
            label = f"Today • {label}"
        if i == 1:
            label = f"Tomorrow • {label}"
        yyyymmdd = day.strftime("%Y%m%d")
        row.append(InlineKeyboardButton(f"📅 {label}", callback_data=f"nsfw_book:day:{yyyymmdd}:{dur}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data="nsfw_book:back:dur"),
        InlineKeyboardButton("❌ Cancel", callback_data="nsfw_book:cancel"),
    ])
    return InlineKeyboardMarkup(rows)


def _windows_for_day(yyyymmdd: str) -> list[tuple[str, str]]:
    avail = _load_day_availability(yyyymmdd)
    if not avail.get("on", True):
        return []

    windows = avail.get("windows") or []
    out: list[tuple[str, str]] = []
    for w in windows:
        if isinstance(w, list) and len(w) == 2:
            out.append((w[0], w[1]))

    if out:
        return out

    # fallback: business hours
    bh0, bh1 = _weekday_default_hours(yyyymmdd)
    return [(bh0, bh1)]


def _build_times_kb(yyyymmdd: str, dur: int) -> InlineKeyboardMarkup:
    avail = _load_day_availability(yyyymmdd)
    if not avail.get("on", True):
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data=f"nsfw_book:back:day:{dur}"),
              InlineKeyboardButton("❌ Cancel", callback_data="nsfw_book:cancel")]]
        )

    day0 = TZ.localize(_parse_date(yyyymmdd))
    blocks = avail.get("blocks") or []
    bookings = _load_bookings(yyyymmdd)

    # candidate step always 30 minutes (you said sessions are 30m or 1h)
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
                    b_start = day0.replace(hour=int(b[0][:2]), minute=int(b[0][3:5]))
                    b_end = day0.replace(hour=int(b[1][:2]), minute=int(b[1][3:5]))
                    if _overlaps(cur, cand_end, b_start, b_end):
                        blocked = True
                        break
                except Exception:
                    continue
            if blocked:
                cur += step
                continue

            # existing bookings overlap
            taken = False
            for bk in bookings:
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

    # build buttons
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for hhmm in options[:30]:
        row.append(
            InlineKeyboardButton(
                f"⏰ {_fmt_time(hhmm)}",
                callback_data=f"nsfw_book:time:{yyyymmdd}:{dur}:{hhmm}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    if not rows:
        rows.append([InlineKeyboardButton("⚠️ No open times", callback_data="nsfw_book:noop")])

    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"nsfw_book:back:day:{dur}"),
        InlineKeyboardButton("❌ Cancel", callback_data="nsfw_book:cancel"),
    ])
    return InlineKeyboardMarkup(rows)


def _confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Confirm session", callback_data="nsfw_book:confirm")],
            [InlineKeyboardButton("✏️ Add a note", callback_data="nsfw_book:note")],
            [InlineKeyboardButton("📖 View prices (Roni’s Menu)", callback_data="nsfw_book:prices")],
            [InlineKeyboardButton("❌ Cancel", callback_data="nsfw_book:cancel")],
        ]
    )


@dataclass
class Draft:
    yyyymmdd: str
    dur: int
    hhmm: str
    note: str = ""

    def start_end(self) -> tuple[datetime, datetime]:
        day0 = TZ.localize(_parse_date(self.yyyymmdd))
        start = day0.replace(hour=int(self.hhmm[:2]), minute=int(self.hhmm[2:]))
        end = start + timedelta(minutes=self.dur)
        return start, end


def _draft_from_state(user_id: int) -> Draft | None:
    st = _jget(_state_key(user_id), {})
    d = st.get("draft")
    if not isinstance(d, dict):
        return None
    try:
        return Draft(
            yyyymmdd=d["date"],
            dur=int(d["dur"]),
            hhmm=d["time"],
            note=str(d.get("note") or ""),
        )
    except Exception:
        return None


def _save_draft_state(user_id: int, draft: Draft, mode: str = "draft") -> None:
    _jset(
        _state_key(user_id),
        {
            "mode": mode,
            "draft": {
                "date": draft.yyyymmdd,
                "dur": draft.dur,
                "time": draft.hhmm,
                "note": draft.note,
            },
            "updated": datetime.utcnow().isoformat(),
        },
    )


def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_text_session_booking registered")

    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def open_flow(_, cq: CallbackQuery):
        # DM-only
        if cq.message and cq.message.chat and cq.message.chat.type != ChatType.PRIVATE:
            await cq.answer("Open this in DM 💕", show_alert=True)
            return

        user_id = cq.from_user.id if cq.from_user else None
        if not _is_age_verified(user_id):
            await cq.answer("Please tap ✅ Age Verify first 💕", show_alert=True)
            return

        text = (
            "💞 <b>Book a private NSFW texting session</b>\n"
            "🚫 <b>NO meetups</b> — online/texting only.\n\n"
            "📖 Prices are in <b>Roni’s Menu</b> (tap the button below).\n\n"
            "⏱ How long do you want your session to be?"
        )
        await cq.message.edit_text(text, reply_markup=_build_duration_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:prices$"))
    async def show_prices(_, cq: CallbackQuery):
        menu_text = store.get_menu(RONI_MENU_KEY) or "Roni hasn’t added prices yet 💕"
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅️ Back to booking", callback_data="nsfw_book:back:dur")],
                [InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:home")],
            ]
        )
        await cq.message.edit_text(
            f"📖 <b>Roni’s Menu</b>\n\n{menu_text}",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:dur:(30|60)$"))
    async def pick_duration(_, cq: CallbackQuery):
        dur = int(cq.data.split(":")[-1])
        text = (
            "🗓 Pick a day that works for you 💕\n"
            "🚫 <b>NO meetups</b> — online/texting only.\n\n"
            "Dates shown are in <b>Los Angeles time</b>."
        )
        await cq.message.edit_text(text, reply_markup=_build_days_kb(dur), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(\d{8}):(30|60)$"))
    async def pick_day(_, cq: CallbackQuery):
        _, _, yyyymmdd, dur = cq.data.split(":")
        dur_i = int(dur)

        # if day is OFF, show alert and stay
        avail = _load_day_availability(yyyymmdd)
        if not avail.get("on", True):
            await cq.answer("That day is not bookable 💕 Pick another date.", show_alert=True)
            return

        day = _parse_date(yyyymmdd)
        label = day.strftime("%A, %B %d")
        text = (
            f"⏰ For <b>{label}</b>, pick a start time 💕\n"
            f"⏱ Session length: <b>{'30 minutes' if dur_i == 30 else '1 hour'}</b>\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
        kb = _build_times_kb(yyyymmdd, dur_i)
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:time:(\d{8}):(30|60):(\d{4})$"))
    async def pick_time(_, cq: CallbackQuery):
        _, _, yyyymmdd, dur, hhmm = cq.data.split(":")
        dur_i = int(dur)
        user_id = cq.from_user.id

        draft = Draft(yyyymmdd=yyyymmdd, dur=dur_i, hhmm=hhmm)
        _save_draft_state(user_id, draft, mode="draft")

        start, end = draft.start_end()
        day_label = start.strftime("%A, %B %d")
        time_label = f"{start.strftime('%I:%M %p').lstrip('0')} – {end.strftime('%I:%M %p').lstrip('0')} (LA time)"

        text = (
            "💗 <b>Confirm your session</b>\n\n"
            f"💞 Session: <b>Private NSFW texting</b>\n"
            f"⏱ Length: <b>{'30 minutes' if dur_i == 30 else '1 hour'}</b>\n"
            f"📅 Date: <b>{day_label}</b>\n"
            f"⏰ Time: <b>{time_label}</b>\n\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
        await cq.message.edit_text(text, reply_markup=_confirm_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:note$"))
    async def add_note(_, cq: CallbackQuery):
        if not cq.from_user:
            return
        user_id = cq.from_user.id
        draft = _draft_from_state(user_id)
        if not draft:
            await cq.answer("Session draft expired — start again 💕", show_alert=True)
            return
        _save_draft_state(user_id, draft, mode="await_note")

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
        try:
            draft = Draft(yyyymmdd=d["date"], dur=int(d["dur"]), hhmm=d["time"], note=m.text)
        except Exception:
            _jset(_state_key(user_id), {})
            return

        _save_draft_state(user_id, draft, mode="draft")

        start, end = draft.start_end()
        day_label = start.strftime("%A, %B %d")
        time_label = f"{start.strftime('%I:%M %p').lstrip('0')} – {end.strftime('%I:%M %p').lstrip('0')} (LA time)"

        text = (
            "💗 <b>Confirm your session</b>\n\n"
            f"💞 Session: <b>Private NSFW texting</b>\n"
            f"⏱ Length: <b>{'30 minutes' if draft.dur == 30 else '1 hour'}</b>\n"
            f"📅 Date: <b>{day_label}</b>\n"
            f"⏰ Time: <b>{time_label}</b>\n"
            f"📝 Note: <i>{draft.note}</i>\n\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
        await m.reply_text(text, reply_markup=_confirm_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^nsfw_book:confirm$"))
    async def confirm(client: Client, cq: CallbackQuery):
        if not cq.from_user:
            return
        user_id = cq.from_user.id
        draft = _draft_from_state(user_id)
        if not draft:
            await cq.answer("Session draft expired — start again 💕", show_alert=True)
            return

        start, end = draft.start_end()
        yyyymmdd = draft.yyyymmdd

        # re-check: day must still be ON
        avail = _load_day_availability(yyyymmdd)
        if not avail.get("on", True):
            await cq.answer("That day is no longer bookable 💕", show_alert=True)
            return

        # re-check overlap: blocks + existing bookings
        blocks = avail.get("blocks") or []
        day0 = TZ.localize(_parse_date(yyyymmdd))
        for b in blocks:
            try:
                b_start = day0.replace(hour=int(b[0][:2]), minute=int(b[0][3:5]))
                b_end = day0.replace(hour=int(b[1][:2]), minute=int(b[1][3:5]))
                if _overlaps(start, end, b_start, b_end):
                    await cq.answer("That time is blocked — pick another 💕", show_alert=True)
                    return
            except Exception:
                continue

        items = _load_bookings(yyyymmdd)
        for bk in items:
            try:
                bs = TZ.localize(datetime.strptime(bk["start"], "%Y-%m-%d %H:%M"))
                be = TZ.localize(datetime.strptime(bk["end"], "%Y-%m-%d %H:%M"))
                if _overlaps(start, end, bs, be):
                    await cq.answer("That time just got booked — pick another 💕", show_alert=True)
                    return
            except Exception:
                continue

        items.append(
            {
                "user_id": user_id,
                "username": (cq.from_user.username or ""),
                "name": (cq.from_user.first_name or ""),
                "dur": draft.dur,
                "start": start.strftime("%Y-%m-%d %H:%M"),
                "end": end.strftime("%Y-%m-%d %H:%M"),
                "note": draft.note,
                "status": "booked",
                "created": datetime.utcnow().isoformat(),
            }
        )
        _save_bookings(yyyymmdd, items)
        _jset(_state_key(user_id), {})

        # notify Roni
        try:
            who = f"{cq.from_user.first_name or 'Someone'}"
            if cq.from_user.username:
                who += f" (@{cq.from_user.username})"
            note_part = f"\n📝 Note: {draft.note}" if draft.note else ""
            await client.send_message(
                RONI_OWNER_ID,
                "💞 <b>New NSFW texting session booked</b>\n\n"
                f"👤 {who}\n"
                f"📅 {start.strftime('%A, %B %d')}\n"
                f"⏰ {start.strftime('%I:%M %p').lstrip('0')} (LA time)\n"
                f"⏱ {'30 minutes' if draft.dur == 30 else '1 hour'}"
                f"{note_part}",
                disable_web_page_preview=True,
            )
        except Exception:
            log.exception("Failed to notify Roni about booking")

        # final user message (your requested wording)
        day_label = start.strftime("%A, %B %d")
        time_label = start.strftime("%I:%M %p").lstrip("0")

        text = (
            "💞 <b>Your session is booked</b> 💕\n\n"
            f"📅 <b>{day_label}</b>\n"
            f"⏰ <b>{time_label}</b> (LA time)\n"
            f"⏱ <b>{'30 minutes' if draft.dur == 30 else '1 hour'}</b>\n\n"
            "Roni will reach out to you for payment :)\n"
            "You can find current prices in 📖 <b>Roni’s Menu</b>.\n\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📖 View prices (Roni’s Menu)", callback_data="nsfw_book:prices")],
                [InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:home")],
            ]
        )
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer("Booked 💕")

    @app.on_callback_query(filters.regex(r"^nsfw_book:back:dur$"))
    async def back_to_dur(_, cq: CallbackQuery):
        text = (
            "💞 <b>Book a private NSFW texting session</b>\n"
            "🚫 <b>NO meetups</b> — online/texting only.\n\n"
            "📖 Prices are in <b>Roni’s Menu</b>.\n\n"
            "⏱ How long do you want your session to be?"
        )
        await cq.message.edit_text(text, reply_markup=_build_duration_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:back:day:(30|60)$"))
    async def back_to_day(_, cq: CallbackQuery):
        dur = int(cq.data.split(":")[-1])
        text = (
            "🗓 Pick a day that works for you 💕\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
        await cq.message.edit_text(text, reply_markup=_build_days_kb(dur), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:cancel$"))
    async def cancel(_, cq: CallbackQuery):
        if cq.from_user:
            _jset(_state_key(cq.from_user.id), {})
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back to Roni Assistant", callback_data="roni_portal:home")]]
        )
        await cq.message.edit_text(
            "❌ All good 💕 Booking cancelled.\n"
            "🚫 <b>NO meetups</b> — online/texting only.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nsfw_book:noop$"))
    async def noop(_, cq: CallbackQuery):
        await cq.answer()

