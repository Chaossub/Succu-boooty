# handlers/contact_admins.py
# Contact Roni / Ruby + Anonymous message to OWNER_ID, with a working Back to Main.

import os
import logging
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

# In-memory state for anonymous messages
_PENDING_ANON: set[int] = set()

# ────────────── COPY ──────────────
CONTACT_COPY = (
    "💌 Need a little help, cutie?\n"
    "You can message an admin directly, or send a secret anonymous note that only the owner will see. 💌\n\n"
    "✨ Choose below and I’ll take care of the rest!"
)

ANON_PROMPT = (
    "💋 Anonymous Message\n"
    "Go ahead, sweetheart — send your secret message now (text only).\n"
    "I’ll whisper it directly to the owner, no names attached. 😉"
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

# ────────────── RENDER HELPERS ──────────────
async def _render_contact_panel(target_message: Message, edit: bool = True):
    if edit:
        try:
            await target_message.edit_text(CONTACT_COPY, reply_markup=_kb_contact(), disable_web_page_preview=True)
            return
        except Exception:
            pass
    await target_message._client.send_message(
        target_message.chat.id, CONTACT_COPY, reply_markup=_kb_contact(), disable_web_page_preview=True
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
        _PENDING_ANON.add(q.from_user.id)
        try:
            await q.message.edit_text(ANON_PROMPT, reply_markup=_kb_back_main(), disable_web_page_preview=True)
        except Exception:
            await q.message.reply_text(ANON_PROMPT, reply_markup=_kb_back_main(), disable_web_page_preview=True)
        await q.answer()

    # Collect the user's next private message as the anonymous note
    @app.on_message(filters.private & filters.text)
    async def anon_collect(client: Client, m: Message):
        if m.from_user is None or m.from_user.id not in _PENDING_ANON:
            return

        if OWNER_ID <= 0:
            _PENDING_ANON.discard(m.from_user.id)
            await m.reply_text("Owner is not configured.", reply_markup=_kb_back_main())
            return

        text = m.text.strip()
        if not text:
            await m.reply_text("Please send text only for your anonymous note.", reply_markup=_kb_back_main())
            return

        try:
            await client.send_message(OWNER_ID, f"🕵️ Anonymous message:\n\n{text}")
            await m.reply_text("✅ Sent anonymously.", reply_markup=_kb_back_main())
        except Exception as e:
            log.warning("Anonymous forward failed: %s", e)
            await m.reply_text("❌ I couldn’t send that right now. Try again in a moment.", reply_markup=_kb_back_main())
        finally:
            _PENDING_ANON.discard(m.from_user.id)

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

    log.info("contact_admins wired")
