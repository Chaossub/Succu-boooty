# handlers/panels.py
# Your home /start panel with buttons; uses the store only to decide wording.
import logging
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from utils.menu_store import store

log = logging.getLogger(__name__)
FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "Nothing here yet 💕")

def _home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 Menus", callback_data="panels:root")],
        [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
        [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
        [InlineKeyboardButton("❓ Help", callback_data="help:open")],
    ])

def _menus_root_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 View Menus", callback_data="menus:open")],
        [InlineKeyboardButton("⬅️ Back", callback_data="portal:home")],
    ])

def register(app: Client):
    log.info("✅ handlers.panels registered (CI menu lookup)")

    @app.on_message(filters.command("start"))
    async def start_cmd(_, m: Message):
        try:
            await m.reply_text(
                "🔥 Welcome to SuccuBot\n"
                "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
                "✨ Use the menu below to navigate!",
                reply_markup=_home_kb(),
                disable_web_page_preview=True,
            )
        except Exception as e:
            log.warning("start reply failed: %s", e)

    @app.on_callback_query(filters.regex("^panels:root$"))
    async def menus_root(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text(
                "💕 <b>Menus</b>",
                reply_markup=_menus_root_kb(),
                disable_web_page_preview=True,
            )
        finally:
            await cq.answer()

    # Fallback for models_elsewhere if main didn't install one
    @app.on_callback_query(filters.regex("^models_elsewhere:open$"))
    async def _models_elsewhere_cb(_, cq: CallbackQuery):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Main", callback_data="portal:home")]])
        try:
            await cq.message.edit_text(FIND_MODELS_TEXT, reply_markup=kb, disable_web_page_preview=True)
        finally:
            await cq.answer()

    # Bridge to the list UI inside handlers.menu
    @app.on_callback_query(filters.regex("^menus:open$"))
    async def _open_lists(_, cq: CallbackQuery):
        try:
            # trigger the list callback in handlers.menu by sending its list callback data
            await cq.message.edit_text("📖 <b>Menus</b>\nTap a name to view.",
                                       reply_markup=None, disable_web_page_preview=True)
            await cq.message.click(0)  # harmless if no buttons; real list is provided by handlers.menu
        except Exception:
            pass
        finally:
            await cq.answer()
