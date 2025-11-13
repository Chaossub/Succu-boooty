# handlers/panels.py
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message,
)
from utils.menu_store import store

log = logging.getLogger(__name__)

# --------- model usernames (no @) ----------
RONI = os.getenv("RONI_USERNAME", "")
RUBY = os.getenv("RUBY_USERNAME", "")
RIN  = os.getenv("RIN_USERNAME", "")
SAVY = os.getenv("SAVY_USERNAME", "")

MODELS = {
    "Roni": RONI,
    "Ruby": RUBY,
    "Rin":  RIN,
    "Savy": SAVY,
}


def _main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="menus:list")],
        [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
        [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
        [InlineKeyboardButton("❓ Help", callback_data="help:open")],
    ])


def register(app: Client):
    log.info("✅ handlers.panels registered (fixed 2x2 model grid)")

    # ---------- /start ----------
    @app.on_message(filters.command("start"))
    async def start_cmd(_, m: Message):
        text = (
            "🔥 Welcome to SuccuBot 🔥\n"
            "I’m your naughty little helper inside the Sanctuary — here to keep "
            "things fun, flirty, and flowing.\n\n"
            "😈 If you ever need to know exactly what I can do, just press the "
            "Help button and I’ll spill all my secrets… 💋"
        )
        await m.reply_text(text, reply_markup=_main_menu_kb())

    # ---------- Menus: fixed 2x2 model grid ----------
    @app.on_callback_query(filters.regex(r"^menus:list$"))
    async def menus_list_cb(_, cq: CallbackQuery):
        # Force exact layout:
        rows = [
            [
                InlineKeyboardButton("Roni", callback_data="menus:model:Roni"),
                InlineKeyboardButton("Ruby", callback_data="menus:model:Ruby"),
            ],
            [
                InlineKeyboardButton("Rin",  callback_data="menus:model:Rin"),
                InlineKeyboardButton("Savy", callback_data="menus:model:Savy"),
            ],
            [InlineKeyboardButton("⬅ Back", callback_data="panels:root")],
        ]
        kb = InlineKeyboardMarkup(rows)
        await cq.message.edit_text(
            "📖 <b>Menus</b>\nTap a name to view.",
            reply_markup=kb,
        )
        await cq.answer()

    # ---------- Individual model page ----------
    @app.on_callback_query(filters.regex(r"^menus:model:(.+)$"))
    async def model_page_cb(_, cq: CallbackQuery):
        model = cq.data.split(":", 2)[2]

        username = MODELS.get(model, "") or ""
        menu_text = store.get_menu(model)

        if menu_text:
            text = f"<b>{model} — Menu</b>\n\n{menu_text}"
        else:
            text = f"<b>{model} — Menu</b>\n\n(no menu saved yet)"

        if username:
            book_button = InlineKeyboardButton("📖 Book", url=f"https://t.me/{username}")
        else:
            # still clickable, just shows alert if username not set
            book_button = InlineKeyboardButton("📖 Book", callback_data="book:none")

        kb = InlineKeyboardMarkup([
            [
                book_button,
                InlineKeyboardButton("💸 Tip (coming soon)", callback_data="tips:soon"),
            ],
            [InlineKeyboardButton("⬅ Back", callback_data="menus:list")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="panels:root")],
        ])

        await cq.message.edit_text(
            text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ---------- Back to main menu ----------
    @app.on_callback_query(filters.regex(r"^panels:root$"))
    async def panels_root_cb(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "🔥 Welcome back to SuccuBot\n"
            "Use the menu below to navigate!",
            reply_markup=_main_menu_kb(),
        )
        await cq.answer()

    # ---------- placeholders ----------
    @app.on_callback_query(filters.regex(r"^tips:soon$"))
    async def tips_soon_cb(_, cq: CallbackQuery):
        await cq.answer("Stripe tips coming soon 💕", show_alert=True)

    @app.on_callback_query(filters.regex(r"^book:none$"))
    async def book_none_cb(_, cq: CallbackQuery):
        await cq.answer("No booking link set yet 💕", show_alert=True)
