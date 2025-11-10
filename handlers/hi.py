# handlers/hi.py
# Warm-up (/hi) + Start (/start) with inline buttons

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

def register(app: Client):

    # Simple warm-up
    @app.on_message(filters.command("hi"))
    async def hi_handler(client: Client, m: Message):
        name = (m.from_user.first_name if m.from_user else "there")
        await m.reply_text(f"👋 Hey {name}! This is just a warm-up command.")

    # Start with buttons
    @app.on_message(filters.command("start"))
    async def start_handler(client: Client, m: Message):
        # Menus button points to your panels menu (no new handlers needed)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💞 Menus", callback_data="panels:root")],
                # Add/keep any others you already support:
                # [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
                # [InlineKeyboardButton("❓ Help", callback_data="help:open")],
            ]
        )
        await m.reply_text(
            "🔥 <b>Welcome to SuccuBot</b>\n"
            "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
            "✨ Tap <b>Menus</b> below to open the model menu.",
            reply_markup=kb,
        )
