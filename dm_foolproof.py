# dm_foolproof.py
# The single /start entrypoint & main portal menu.

from __future__ import annotations
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ── Texts ────────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
    "Use the buttons below to explore menus, contact admins, find our models elsewhere, "
    "or get help with rules and requirements."
)

# This is what shows when they click "Find Our Models Elsewhere"
MODELS_LINKS_TEXT = (
    "✨ <b>Find Our Models Elsewhere</b> ✨\n\n"
    "All verified off-platform links for our models are collected here. "
    "Check pinned messages or official posts for updates."
)

# ── Keyboards ────────────────────────────────────────────────────────────
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="dmf_open_menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="dmf_admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="dmf_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_help")],
    ])

def _back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_home")]])

# ── Register ─────────────────────────────────────────────────────────────
def register(app: Client):

    # /start command → show the main portal
    @app.on_message(filters.command("start"))
    async def start_cmd(client: Client, m: Message):
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # Main menu home
    @app.on_callback_query(filters.regex("^dmf_home$"))
    async def cb_home(client: Client, cq):
        await cq.message.edit_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)
        await cq.answer()

    # Find Our Models Elsewhere
    @app.on_callback_query(filters.regex("^dmf_links$"))
    async def cb_links(client: Client, cq):
        await cq.message.edit_text(MODELS_LINKS_TEXT, reply_markup=_back_home_kb(), disable_web_page_preview=False)
        await cq.answer()

