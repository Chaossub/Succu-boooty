# handlers/panels.py
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from utils.menu_store import store

log = logging.getLogger(__name__)

### USERNAMES (NO @)
RONI = os.getenv("RONI_USERNAME", "")
RUBY = os.getenv("RUBY_USERNAME", "")
RIN  = os.getenv("RIN_USERNAME", "")
SAVY = os.getenv("SAVY_USERNAME", "")

MODELS = [
    ("Roni", RONI),
    ("Ruby", RUBY),
    ("Rin", RIN),
    ("Savy", SAVY),
]


def register(app: Client):
    log.info("panels loaded")

    # ------------------ /start ------------------
    @app.on_message(filters.command("start"))
    async def start_cmd(_, m: Message):
        txt = (
            "🔥 Welcome to SuccuBot 🔥\n"
            "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
            "😈 If you ever need to know exactly what I can do, press Help… 💋"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💕 Menus", callback_data="menus:list")],
            [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
            [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
            [InlineKeyboardButton("❓ Help", callback_data="help:open")],
        ])
        await m.reply(txt, reply_markup=kb)

    # ------------------ Menus main ------------------
    @app.on_callback_query(filters.regex("^menus:list$"))
    async def menus_list(_, cq: CallbackQuery):
        rows = []
        for name, _ in MODELS:
            rows.append([InlineKeyboardButton(name, callback_data=f"menus:model:{name}")])
        rows.append([InlineKeyboardButton("⬅ Back", callback_data="panels:root")])
        await cq.message.edit("📖 Menus\nTap a name to view.", reply_markup=InlineKeyboardMarkup(rows))
        await cq.answer()

    # ------------------ Individual model ------------------
    @app.on_callback_query(filters.regex(r"^menus:model:(.+)$"))
    async def model_page(_, cq: CallbackQuery):
        model = cq.data.split(":", 2)[2]

        # find username
        username = ""
        for n, u in MODELS:
            if n == model:
                username = u
                break

        # get saved menu (optional)
        menu = store.get_menu(model)
        if menu:
            text = f"<b>{model} — menu</b>\n\n{menu}"
        else:
            text = f"<b>{model} — menu</b>\n\n(no menu saved yet)"

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📖 Book", url=f"https://t.me/{username}") if username
                else InlineKeyboardButton("📖 Book", callback_data="book:none"),
                InlineKeyboardButton("💸 Tip (coming soon)", callback_data="tips:soon"),
            ],
            [InlineKeyboardButton("⬅ Back", callback_data="menus:list")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="panels:root")],
        ])

        await cq.message.edit(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ------------------ Back to main panel ------------------
    @app.on_callback_query(filters.regex("^panels:root$"))
    async def root(_, cq: CallbackQuery):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💕 Menus", callback_data="menus:list")],
            [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
            [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
            [InlineKeyboardButton("❓ Help", callback_data="help:open")],
        ])
        await cq.message.edit("🔥 Main Menu", reply_markup=kb)
        await cq.answer()

    # ------------------ tip/book placeholders ------------------
    @app.on_callback_query(filters.regex("^tips:soon$"))
    async def tsoon(_, cq):
        await cq.answer("Stripe tips coming soon 💕", show_alert=True)

    @app.on_callback_query(filters.regex("^book:none$"))
    async def bnone(_, cq):
        await cq.answer("No booking link set yet 💕", show_alert=True)
