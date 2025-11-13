# handlers/contact_admins.py
# Contact Roni / Ruby + Anonymous message to OWNER_ID, with reply + cancel support.

import os
import logging
import itertools
from typing import Dict, Set

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

log = logging.getLogger("contact_admins")

# ────────────── ENV / CONFIG ──────────────
OWNER_ID        = int(os.getenv("OWNER_ID", "0") or "0")

# Prefer usernames from env; fall back to provided handles
RONI_USERNAME   = (os.getenv("RONI_USERNAME") or "Chaossub283").lstrip("@")
RUBY_USERNAME   = (os.getenv("RUBY_USERNAME") or "RubyRansom").lstrip("@")
RONI_NAME       = os.getenv("RONI_NAME", "Roni")
RUBY_NAME       = os.getenv("RUBY_NAME", "Ruby")

BTN_BACK_MAIN   = "⬅️ Back to Main Menu"

# ────────────── STATE ──────────────
# Users currently composing an anonymous message
_PENDING_ANON: Set[int] = set()

# Thread id -> real user id (kept secret from owner)
_ANON_THREADS: Dict[int, int] = {}

# Owner currently replying: owner_id -> thread_id
_OWNER_REPLY_TARGET: Dict[int, int] = {}

# Simple in-memory thread id generator
_THREAD_ID_COUNTER = itertools.count(1)

# ────────────── COPY ──────────────
CONTACT_COPY = (
    "💌 Need a little help, cutie?\n"
    "You can message an admin directly, or send a secret anonymous note that only the owner will see. 💌\n\n"
    "✨ Choose below and I’ll take care of the rest!"
)

ANON_PROMPT = (
    "💋 Anonymous Message\n"
    "Go ahead, sweetheart — send your secret message now (text only).\n"
    "I’ll whisper it directly to the owner, no names attached. 😉\n\n"
    "You can also cancel with the button below if you change your mind."
)

OWNER_REPLY_PROMPT = (
    "✉️ Reply mode active.\n"
    "Send your message now and I’ll deliver it back to this anon thread.\n\n"
    "Use <b>❌ Cancel Reply</b> if you change your mind."
)

# ────────────── KEYBOARDS ──────────────
def _kb_contact() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"🔥 Message {RONI_NAME}", url=f"https://t.me/{RONI_USERNAME}")],
        [InlineKeyboardButton(f"💎 Message {RUBY_NAME}", url=f"https://t.me/{RUBY_USERNAME}")],
        [InlineKeyboardButton("🕵️ Send an Anonymous Message", callback_data="contact:anon")],
        [InlineKeyboardButton(BTN_BACK_MAIN, callback_data="portal:home")],
    ]
    return InlineKeyboardMarkup(rows)


def _kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK_MAIN, callback_data="portal:home")]])


def _kb_home() -> InlineKeyboardMarkup:
    # Main 4-button home used by /start and portal:home
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 Menus", callback_data="panels:root")],
        [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
        [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
        [InlineKeyboardButton("❓ Help", callback_data="help:open")],
    ])


def _kb_anon() -> InlineKeyboardMarkup:
    # While user is composing an anon message
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="contact:anon_cancel")],
        [InlineKeyboardButton(BTN_BACK_MAIN, callback_data="portal:home")],
    ])


def _kb_owner_thread(thread_id: int) -> InlineKeyboardMarkup:
    # Shown to OWNER when they receive an anon
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Reply to this anon", callback_data=f"contact_owner_reply:{thread_id}")],
        [InlineKeyboardButton(BTN_BACK_MAIN, callback_data="portal:home")],
    ])


def _kb_owner_reply(thread_id: int) -> InlineKeyboardMarkup:
    # Shown to OWNER while in reply mode
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Reply", callback_data=f"contact_owner_cancel:{thread_id}")],
        [InlineKeyboardButton(BTN_BACK_MAIN, callback_data="portal:home")],
    ])


# ────────────── RENDER HELPERS ──────────────
async def _render_contact_panel(target_message: Message, edit: bool = True):
    if edit:
        try:
            await target_message.edit_text(
                CONTACT_COPY,
                reply_markup=_kb_contact(),
                disable_web_page_preview=True,
            )
            return
        except Exception:
            pass
    await target_message._client.send_message(
        target_message.chat.id,
        CONTACT_COPY,
        reply_markup=_kb_contact(),
        disable_web_page_preview=True,
    )

# ────────────── REGISTER ──────────────
def register(app: Client):

    # Open via main menu button
    @app.on_callback_query(filters.regex(r"^contact_admins:open$"))
    async def open_contact_cb(_, q: CallbackQuery):
        await _render_contact_panel(q.message, edit=True)
        await q.answer()

    # Optional command: /contactadmins, /contact, /admins
    @app.on_message(filters.private & filters.command(["contactadmins", "contact", "admins"]))
    async def cmd_contact(_, m: Message):
        await _render_contact_panel(m, edit=False)

    # Begin anonymous message flow
    @app.on_callback_query(filters.regex(r"^contact:anon$"))
    async def anon_begin(_, q: CallbackQuery):
        if q.from_user:
            _PENDING_ANON.add(q.from_user.id)
        try:
            await q.message.edit_text(
                ANON_PROMPT,
                reply_markup=_kb_anon(),
                disable_web_page_preview=True,
            )
        except Exception:
            await q.message.reply_text(
                ANON_PROMPT,
                reply_markup=_kb_anon(),
                disable_web_page_preview=True,
            )
        await q.answer()

    # Cancel anonymous message flow (user side)
    @app.on_callback_query(filters.regex(r"^contact:anon_cancel$"))
    async def anon_cancel(_, q: CallbackQuery):
        uid = q.from_user.id if q.from_user else None
        if uid is not None and uid in _PENDING_ANON:
            _PENDING_ANON.discard(uid)
        await q.answer("Anonymous message canceled.", show_alert=True)
        # Back to Contact panel
        await _render_contact_panel(q.message, edit=True)

    # OWNER taps "Reply to this anon"
    @app.on_callback_query(filters.regex(r"^contact_owner_reply:(\d+)$"))
    async def owner_reply_begin(_, q: CallbackQuery):
        if not q.from_user or q.from_user.id != OWNER_ID:
            await q.answer("Only the owner can reply to anon messages.", show_alert=True)
            return

        data = q.data or ""
        try:
            thread_id = int(data.split(":", 1)[1])
        except Exception:
            await q.answer("Invalid thread id.", show_alert=True)
            return

        if thread_id not in _ANON_THREADS:
            await q.answer("This anonymous thread has expired.", show_alert=True)
            return

        _OWNER_REPLY_TARGET[q.from_user.id] = thread_id

        try:
            await q.message.edit_text(
                OWNER_REPLY_PROMPT,
                reply_markup=_kb_owner_reply(thread_id),
                disable_web_page_preview=True,
            )
        except Exception:
            await q.message.reply_text(
                OWNER_REPLY_PROMPT,
                reply_markup=_kb_owner_reply(thread_id),
                disable_web_page_preview=True,
            )

        await q.answer("Reply mode enabled for this anon thread.")

    # OWNER cancels reply mode
    @app.on_callback_query(filters.regex(r"^contact_owner_cancel:(\d+)$"))
    async def owner_reply_cancel(_, q: CallbackQuery):
        if not q.from_user or q.from_user.id != OWNER_ID:
            await q.answer("Only the owner can do that.", show_alert=True)
            return

        uid = q.from_user.id
        _OWNER_REPLY_TARGET.pop(uid, None)

        await q.answer("Reply canceled.", show_alert=True)
        # Go back to contact panel or just say done
        await _render_contact_panel(q.message, edit=True)

    # Collect private messages for anon + owner replies
    @app.on_message(filters.private & filters.text)
    async def private_router(client: Client, m: Message):
        if not m.from_user:
            return

        uid = m.from_user.id
        text = (m.text or "").strip()
        if not text:
            return

        # 1) User composing anonymous message
        if uid in _PENDING_ANON:
            if OWNER_ID <= 0:
                _PENDING_ANON.discard(uid)
                await m.reply_text("Owner is not configured.", reply_markup=_kb_back_main())
                return

            # allocate a thread id for this anon
            thread_id = next(_THREAD_ID_COUNTER)
            _ANON_THREADS[thread_id] = uid

            try:
                # Forward to OWNER with a reply button
                await client.send_message(
                    OWNER_ID,
                    f"🕵️ Anonymous message (Thread #{thread_id}):\n\n{text}",
                    reply_markup=_kb_owner_thread(thread_id),
                )
                await m.reply_text("✅ Sent anonymously.", reply_markup=_kb_back_main())
            except Exception as e:
                log.warning("Anonymous forward failed: %s", e)
                await m.reply_text(
                    "❌ I couldn’t send that right now. Try again in a moment.",
                    reply_markup=_kb_back_main(),
                )
            finally:
                _PENDING_ANON.discard(uid)
            return

        # 2) Owner replying to anon
        if uid == OWNER_ID and uid in _OWNER_REPLY_TARGET:
            thread_id = _OWNER_REPLY_TARGET.get(uid)
            target_id = _ANON_THREADS.get(thread_id or -1)

            if not thread_id or not target_id:
                # Thread vanished or never existed
                _OWNER_REPLY_TARGET.pop(uid, None)
                await m.reply_text("That anon thread has expired.", reply_markup=_kb_back_main())
                return

            try:
                await client.send_message(
                    target_id,
                    f"💌 Reply from admin:\n\n{text}",
                )
                await m.reply_text("✅ Your reply was sent to the anon.", reply_markup=_kb_back_main())
            except Exception as e:
                log.warning("Owner reply forward failed: %s", e)
                await m.reply_text(
                    "❌ I couldn’t deliver that reply. Try again in a moment.",
                    reply_markup=_kb_back_main(),
                )
            finally:
                _OWNER_REPLY_TARGET.pop(uid, None)
            return

        # Otherwise: ignore, let other handlers handle this private message if needed.
        return

    # Universal Back to Main handler (works from any panel using callback_data='portal:home')
    @app.on_callback_query(filters.regex(r"^portal:home$"))
    async def back_to_main(_, q: CallbackQuery):
        try:
            await q.message.edit_text(
                "🔥 Welcome back to SuccuBot\n"
                "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
                "✨ Use the menu below to navigate!",
                reply_markup=_kb_home(),
                disable_web_page_preview=True,
            )
        except Exception:
            await q.message.reply_text(
                "🔥 Welcome back to SuccuBot\n"
                "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
                "✨ Use the menu below to navigate!",
                reply_markup=_kb_home(),
                disable_web_page_preview=True,
            )
        finally:
            await q.answer()

    log.info("contact_admins wired (anon + owner replies enabled)")