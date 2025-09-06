from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import os

RONI_USERNAME = os.getenv("RONI_USERNAME", "RoniMissing")
RUBY_USERNAME = os.getenv("RUBY_USERNAME", "RubyMissing")

def get_main_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="menu")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ])

def get_admins_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Contact Roni", url=f"https://t.me/{RONI_USERNAME}")],
        [InlineKeyboardButton("✉️ Contact Ruby", url=f"https://t.me/{RUBY_USERNAME}")],
        [InlineKeyboardButton("🕵️ Anonymous Suggestions", callback_data="anon")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="main")]
    ])

def register(app):
    @app.on_callback_query(filters.regex("^main$"))
    async def main_panel(client, cq):
        await cq.message.edit_text(
            "🔥 Welcome to SuccuBot 🔥\n"
            "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
            "✨ Use the menu below to navigate!",
            reply_markup=get_main_panel()
        )

    @app.on_callback_query(filters.regex("^admins$"))
    async def admins_panel(client, cq):
        await cq.message.edit_text(
            "📬 Contact Admins\nChoose how you want to reach us:",
            reply_markup=get_admins_panel()
        )
