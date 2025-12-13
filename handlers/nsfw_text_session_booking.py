# handlers/nsfw_text_session_booking.py
import logging
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from utils.menu_store import store  # used for AGE_OK lookup
from utils.nsfw_store import (
    is_slot_available,
    create_booking,
    list_available_slots_for_day,
)

log = logging.getLogger(__name__)

RONI_OWNER_ID = 6964994611  # your id

# Callback prefixes (keep short)
# user flow:
#   nsfw_book:open
#   nb:dur30
#   nb:day:30:YYYYMMDD
#   nb:time:30:YYYYMMDD:HHMM
#   nb:note:30:YYYYMMDD:HHMM
#   nb:confirm:30:YYYYMMDD:HHMM
#   nb:cancel
#
# NOTE: booking is only reachable from your Roni assistant keyboard (DM),
# but we still permission-check + age-gate.

def _age_key(user_id: int) -> str:
    return f"AGE_OK:{user_id}"

def _is_age_verified(user_id: int) -> bool:
    try:
        return bool(store.get_menu(_age_key(user_id)))
    except Exception:
        return False


def _kb_back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]])

def _kb_cancel():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="nb:cancel")]])


def _kb_pick_duration():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏱ 30 minutes", callback_data="nb:dur30")],
            [InlineKeyboardButton("🕰 1 hour", callback_data="nb:dur60")],
            [InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")],
        ]
    )


def _kb_pick_day(duration_min: int):
    today = datetime.now().date()
    rows = []
    # 7 days shown
    for i in range(7):
        d = today + timedelta(days=i)
        label = d.strftime("%a %b %d")
        if i == 0:
            label = f"📅 Today ({label})"
        elif i == 1:
            label = f"📅 Tomorrow ({label})"
        data = f"nb:day:{duration_min}:{d.strftime('%Y%m%d')}"
        rows.append([InlineKeyboardButton(label, callback_data=data)])

    rows.append([InlineKeyboardButton("⬅ Back", callback_data="nb:back_dur")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="nb:cancel")])
    return InlineKeyboardMarkup(rows)


def _kb_pick_time(duration_min: int, yyyymmdd: str, page: int = 0):
    slots = list_available_slots_for_day(yyyymmdd, duration_min)
    # paginate (8 per page)
    per = 8
    start = page * per
    end = start + per
    page_slots = slots[start:end]

    rows = []
    for hhmm in page_slots:
        # display in 12hr
        dt = datetime.strptime(yyyymmdd + hhmm, "%Y%m%d%H%M")
        label = "⏰ " + dt.strftime("%-I:%M %p")
        data = f"nb:time:{duration_min}:{yyyymmdd}:{hhmm}"
        rows.append([InlineKeyboardButton(label, callback_data=data)])

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅ Earlier", callback_data=f"nb:times:{duration_min}:{yyyymmdd}:{page-1}"))
    if end < len(slots):
        nav.append(InlineKeyboardButton("Later ➡", callback_data=f"nb:times:{duration_min}:{yyyymmdd}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data=f"nb:back_day:{duration_min}:{yyyymmdd}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="nb:cancel")])
    return InlineKeyboardMarkup(rows)


def _confirm_text(duration_min: int, yyyymmdd: str, hhmm: str, note: str | None = None) -> str:
    start = datetime.strptime(yyyymmdd + hhmm, "%Y%m%d%H%M")
    end = start + timedelta(minutes=duration_min)
    pretty_day = start.strftime("%A, %b %d")
    pretty_time = f"{start.strftime('%-I:%M %p')} – {end.strftime('%-I:%M %p')}"

    out = (
        "💗 Let me confirm this before I lock it in 💕\n\n"
        f"📱 Session: <b>Private NSFW texting session</b>\n"
        f"⏱ Length: <b>{duration_min} minutes</b>\n"
        f"📅 Date: <b>{pretty_day}</b>\n"
        f"⏰ Time: <b>{pretty_time}</b>\n\n"
        "🚫 <b>NO meetups</b> — online/text only.\n"
    )
    if note:
        out += f"\n📝 Note: <i>{note}</i>\n"
    return out


# In-memory note capture state: user_id -> (duration, yyyymmdd, hhmm)
_NOTE_PENDING: dict[int, tuple[int, str, str]] = {}


def register(app: Client) -> None:
    log.info("✅ handlers.nsfw_text_session_booking registered")

    @app.on_callback_query(filters.regex(r"^nsfw_book:open$"))
    async def open_booking(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else 0
        # age gate (owner always allowed)
        if user_id != RONI_OWNER_ID and not _is_age_verified(user_id):
            await cq.answer("✅ Please complete Age Verify first 💕", show_alert=True)
            # bounce them to the assistant home (they’ll see Age Verify button there)
            try:
                await cq.message.edit_text(
                    "💞 To book a private session, please tap ✅ <b>Age Verify</b> first.\n\n"
                    "🚫 NO meetups — online/text only.",
                    reply_markup=_kb_back_home(),
                    disable_web_page_preview=True,
                )
            finally:
                return

        await cq.message.edit_text(
            "💞 Let’s book your private NSFW texting session 💕\n\n"
            "⏱ Pick your session length:\n\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=_kb_pick_duration(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nb:dur(30|60)$"))
    async def pick_duration(_, cq: CallbackQuery):
        dur = 30 if cq.data.endswith("30") else 60
        await cq.message.edit_text(
            f"🗓 Pick a day for your <b>{dur}-minute</b> session 💕\n\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=_kb_pick_day(dur),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nb:back_dur$"))
    async def back_to_duration(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "💞 Let’s book your private NSFW texting session 💕\n\n"
            "⏱ Pick your session length:\n\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=_kb_pick_duration(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nb:day:(30|60):\d{8}$"))
    async def pick_day(_, cq: CallbackQuery):
        _, _, dur_s, yyyymmdd = cq.data.split(":")
        dur = int(dur_s)

        kb = _kb_pick_time(dur, yyyymmdd, page=0)
        await cq.message.edit_text(
            "⏰ Pick a start time 💕\n\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nb:times:(30|60):\d{8}:\d+$"))
    async def times_page(_, cq: CallbackQuery):
        _, _, dur_s, yyyymmdd, page_s = cq.data.split(":")
        dur = int(dur_s)
        page = int(page_s)

        kb = _kb_pick_time(dur, yyyymmdd, page=page)
        await cq.message.edit_text(
            "⏰ Pick a start time 💕\n\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nb:back_day:(30|60):\d{8}$"))
    async def back_to_days(_, cq: CallbackQuery):
        _, _, dur_s, _yyyymmdd = cq.data.split(":")
        dur = int(dur_s)
        await cq.message.edit_text(
            f"🗓 Pick a day for your <b>{dur}-minute</b> session 💕\n\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=_kb_pick_day(dur),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nb:time:(30|60):\d{8}:\d{4}$"))
    async def pick_time(_, cq: CallbackQuery):
        _, _, dur_s, yyyymmdd, hhmm = cq.data.split(":")
        dur = int(dur_s)

        # final availability check right now
        if not is_slot_available(yyyymmdd, hhmm, dur):
            await cq.answer("⚠️ That time just got booked. Pick another 💕", show_alert=True)
            return

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Confirm session", callback_data=f"nb:confirm:{dur}:{yyyymmdd}:{hhmm}")],
                [InlineKeyboardButton("✏️ Add a note", callback_data=f"nb:note:{dur}:{yyyymmdd}:{hhmm}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="nb:cancel")],
            ]
        )
        await cq.message.edit_text(
            _confirm_text(dur, yyyymmdd, hhmm),
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nb:note:(30|60):\d{8}:\d{4}$"))
    async def add_note(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else 0
        _, _, dur_s, yyyymmdd, hhmm = cq.data.split(":")
        dur = int(dur_s)

        _NOTE_PENDING[user_id] = (dur, yyyymmdd, hhmm)

        await cq.message.edit_text(
            "📝 Send your note in <b>one message</b> 💕\n"
            "Preferences, boundaries, or requests.\n\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=_kb_cancel(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_message(filters.private & filters.text, group=50)
    async def capture_note(_, m: Message):
        if not m.from_user:
            return
        user_id = m.from_user.id
        if user_id not in _NOTE_PENDING:
            return

        dur, yyyymmdd, hhmm = _NOTE_PENDING.pop(user_id)

        # show confirm screen w/ note
        note = (m.text or "").strip()
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Confirm session", callback_data=f"nb:confirm:{dur}:{yyyymmdd}:{hhmm}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="nb:cancel")],
            ]
        )
        await m.reply_text(
            _confirm_text(dur, yyyymmdd, hhmm, note=note),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

        # stash note inside store for confirm step (very small + per user)
        store.set_menu(f"_NSFW_NOTE:{user_id}:{yyyymmdd}:{hhmm}:{dur}", note)

    @app.on_callback_query(filters.regex(r"^nb:confirm:(30|60):\d{8}:\d{4}$"))
    async def confirm_booking(_, cq: CallbackQuery):
        user = cq.from_user
        user_id = user.id if user else 0
        _, _, dur_s, yyyymmdd, hhmm = cq.data.split(":")
        dur = int(dur_s)

        if user_id != RONI_OWNER_ID and not _is_age_verified(user_id):
            await cq.answer("✅ Please Age Verify first 💕", show_alert=True)
            return

        # re-check availability
        if not is_slot_available(yyyymmdd, hhmm, dur):
            await cq.answer("⚠️ That time is no longer available. Pick another 💕", show_alert=True)
            return

        note_key = f"_NSFW_NOTE:{user_id}:{yyyymmdd}:{hhmm}:{dur}"
        note = (store.get_menu(note_key) or "").strip()
        store.set_menu(note_key, "")  # clear

        create_booking(
            user_id=user_id,
            username=(user.username or ""),
            first_name=(user.first_name or ""),
            yyyymmdd=yyyymmdd,
            hhmm=hhmm,
            duration_min=dur,
            note=note,
        )

        start = datetime.strptime(yyyymmdd + hhmm, "%Y%m%d%H%M")
        pretty = start.strftime("%A, %b %d at %-I:%M %p")

        await cq.message.edit_text(
            "💞 You’re booked, baby 💕\n\n"
            f"📅 <b>{pretty}</b>\n"
            f"⏱ <b>{dur} minutes</b>\n\n"
            "💋 I’ll message you here when it’s time to start.\n"
            "🚫 <b>NO meetups</b> — online/text only.",
            reply_markup=_kb_back_home(),
            disable_web_page_preview=True,
        )
        await cq.answer("✅ Saved 💕")

    @app.on_callback_query(filters.regex(r"^nb:cancel$"))
    async def cancel_flow(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "❌ All good 💕\n"
            "Cancelled.\n\n"
            "🚫 NO meetups — online/text only.",
            reply_markup=_kb_back_home(),
            disable_web_page_preview=True,
        )
        await cq.answer()
