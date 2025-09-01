# Contact Admins panel + anonymous relay
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

RONI_ID  = int(os.getenv("RONI_ID", "0") or "0")
RUBY_ID  = int(os.getenv("RUBY_ID", "0") or "0")
RONI_N   = os.getenv("RONI_NAME", "Roni")
RUBY_N   = os.getenv("RUBY_NAME", "Ruby")

BTN_BACK = os.getenv("BTN_BACK", "⬅️ Back to Main")

_ANON_GATES = set()  # message_ids that act as anon prompts

def _kb_contact() -> InlineKeyboardMarkup:
    rows = []
    if RONI_ID:
        rows.append([InlineKeyboardButton(f"👑 Contact {RONI_N}", url=f"tg://user?id={RONI_ID}")])
    if RUBY_ID:
        rows.append([InlineKeyboardButton(f"👑 Contact {RUBY_N}", url=f"tg://user?id={RUBY_ID}")])
    rows.append([InlineKeyboardButton("✉️ Send anonymous message", callback_data="anon_open")])
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data="panel_back_main")])
    return InlineKeyboardMarkup(rows)

def register(app: Client):
    # Hub button → this panel
    @app.on_callback_query(filters.regex(r"^open_contact_admins$"))
    async def open_panel(_, cq: CallbackQuery):
        text = (
            "👑 <b>Contact Admins</b>\n\n"
            "• Tag an admin in chat\n"
            "• Or send an anonymous note via the bot."
        )
        await cq.message.edit_text(text, reply_markup=_kb_contact(), disable_web_page_preview=True)
        await cq.answer()

    # Optional text command to open the same panel
    @app.on_message(filters.command(["contactadmins", "contact", "admins"]))
    async def cmd_panel(_, m: Message):
        await m.reply_text(
            "👑 <b>Contact Admins</b>\n\n• Tag an admin in chat\n• Or send an anonymous note via the bot.",
            reply_markup=_kb_contact(),
            disable_web_page_preview=True,
        )

    # Open anonymous gate
    @app.on_callback_query(filters.regex(r"^anon_open$"))
    async def anon_open(_, cq: CallbackQuery):
        msg = await cq.message.reply_text(
            "🕊️ <b>Anonymous message</b>\n"
            "Reply to this message with your note and I’ll forward it privately to the owner.",
            quote=True,
        )
        _ANON_GATES.add(msg.id)
        await cq.answer("Okay! Reply to the new message I just sent.")

    # Catch replies to the anon prompt and relay to owner
    @app.on_message(filters.reply)
    async def anon_relay(app: Client, m: Message):
        if not m.reply_to_message or m.reply_to_message.id not in _ANON_GATES:
            return
        text = m.text or (m.caption or "")
        if not text.strip():
            return await m.reply("Please send text.")
        try:
            await app.send_message(
                OWNER_ID,
                f"🔔 <b>Anonymous message</b>\n\n{text}",
                disable_web_page_preview=True,
            )
            await m.reply("✅ Sent anonymously to the owner.")
        finally:
            _ANON_GATES.discard(m.reply_to_message.id)
