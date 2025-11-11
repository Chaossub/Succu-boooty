# handlers/contact_admins.py
import os
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

OWNER_ID = int(os.getenv("OWNER_ID", "0"))
RONI_USERNAME = os.getenv("RONI_USERNAME", "@Chaossub283")
RUBY_USERNAME = os.getenv("RUBY_USERNAME", "@RubyRansom")

def register(app):

    # ─── Contact Admins button from main menu ───
    @app.on_callback_query(filters.regex("^contact_admins:open$"))
    async def open_contact_admins(_, cq: CallbackQuery):
        text = (
            "💌 Need a little help, cutie?\n\n"
            "You can message one of my lovely admins directly — or send a secret anonymous note that only the owner will see. 💋\n\n"
            "✨ Choose one below and I’ll take care of the rest!"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Message Roni", url=f"https://t.me/{RONI_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton("💎 Message Ruby", url=f"https://t.me/{RUBY_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton("💌 Send an Anonymous Message", callback_data="contact_admins:anon")],
            [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="portal:home")]
        ])

        await cq.message.edit_text(text, reply_markup=keyboard)
        await cq.answer()

    # ─── Anonymous message option ───
    @app.on_callback_query(filters.regex("^contact_admins:anon$"))
    async def ask_anonymous(_, cq: CallbackQuery):
        text = (
            "💋 Go ahead, sweetheart — send your secret message now (text only).\n\n"
            "I’ll whisper it directly to the owner, no names attached. 😉"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="portal:home")]
        ])

        await cq.message.edit_text(text, reply_markup=keyboard)
        await cq.answer()

        # Next message from this user = anonymous message
        app.set_parse_mode("Markdown")

        @app.on_message(filters.private & filters.text & filters.user(cq.from_user.id))
        async def anonymous_message(client, msg: Message):
            # Forward to owner without revealing sender
            await client.send_message(
                OWNER_ID,
                f"📨 **Anonymous Message:**\n\n{msg.text}"
            )
            await msg.reply_text("✨ Message sent anonymously! I’ve delivered it safely to the owner.")
            app.remove_handler(anonymous_message)
