# handlers/panels.py
import os
from typing import List
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from utils.menu_store import store

_DEFAULT_MODELS = ["Roni", "Ruby", "Rin", "Savy"]
_MODELS_ENV = os.getenv("MODELS", "")
MODELS: List[str] = [x.strip() for x in _MODELS_ENV.split(",") if x.strip()] or _DEFAULT_MODELS

FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "No links set yet.")

def _norm(name: str) -> str:
    return "".join(ch for ch in name.upper() if ch.isalnum())

def _get_username(name: str) -> str | None:
    v = os.getenv(f"{_norm(name)}_USERNAME")
    return v.lstrip("@").strip() if v else None

def _get_url(kind: str, name: str) -> str | None:
    return os.getenv(f"{_norm(name)}_{kind}_URL")

ROOT_CB   = "panels:root"
PICK_CB_P = "panels:pick:"
TIP_CB_P  = "panels:tip:"

def _clean(name: str) -> str:
    return name.strip().strip("»«‘’“”\"'`").strip()

def _models_keyboard() -> InlineKeyboardMarkup:
    rows, row = [], []
    for i, n in enumerate(MODELS, 1):
        row.append(InlineKeyboardButton(n, callback_data=f"{PICK_CB_P}{n}"))
        if i % 2 == 0:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([
        InlineKeyboardButton("⬅ Back", callback_data="home:main"),
        InlineKeyboardButton("🏠 Main", callback_data="home:main"),
    ])
    return InlineKeyboardMarkup(rows)

def _menu_keyboard(name: str) -> InlineKeyboardMarkup:
    uname = _get_username(name)
    book_btn = (InlineKeyboardButton("📖 Book", url=f"https://t.me/{uname}")
                if uname else InlineKeyboardButton("📖 Book", callback_data="panels:nobook"))
    return InlineKeyboardMarkup([
        [book_btn],
        [InlineKeyboardButton("💸 Tip", callback_data=f"{TIP_CB_P}{name}")],
        [InlineKeyboardButton("⬅ Back", callback_data=ROOT_CB),
         InlineKeyboardButton("🏠 Main", callback_data="home:main")],
    ])

def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 Menus", callback_data=ROOT_CB)],
        [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
        [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
        [InlineKeyboardButton("❓ Help", callback_data="help:open")],
    ])

def register(app):
    @app.on_message(filters.command("start"))
    async def start_cmd(_, m: Message):
        await m.reply_text(
            "🔥 **Welcome to SuccuBot**\n"
            "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
            "✨ Use the menu below to navigate!",
            reply_markup=_main_keyboard(),
            disable_web_page_preview=True
        )

    @app.on_message(filters.command("menu"))
    async def menu_cmd(_, m: Message):
        await m.reply_text("💕 **Choose a model:**", reply_markup=_models_keyboard())

    @app.on_callback_query(filters.regex(f"^{ROOT_CB}$"))
    async def back_to_models(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text("💕 **Choose a model:**", reply_markup=_models_keyboard())
        finally:
            await cq.answer()

    @app.on_callback_query(filters.regex(r"^panels:pick:.+"))
    async def pick_cb(_, cq: CallbackQuery):
        name = _clean(cq.data[len(PICK_CB_P):])
        text = store.get_menu(name) or "No menu saved yet.\n\nUse /createmenu <Name> <text…> to set one."
        try:
            await cq.message.edit_text(f"**{name} — Menu**\n\n{text}",
                                       reply_markup=_menu_keyboard(name),
                                       disable_web_page_preview=True)
        finally:
            await cq.answer()

    @app.on_callback_query(filters.regex(r"^panels:nobook$"))
    async def no_book(_, cq: CallbackQuery):
        await cq.answer("No booking username set for this model.", show_alert=True)

    @app.on_callback_query(filters.regex(r"^panels:tip:.+"))
    async def tip_cb(_, cq: CallbackQuery):
        name = _clean(cq.data[len(TIP_CB_P):])
        url = _get_url("TIP", name)
        if url:
            await cq.message.reply_text(f"💸 **Tip {name}**\n{url}")
        else:
            await cq.answer("No tip link set for this model.", show_alert=True)

    @app.on_callback_query(filters.regex(r"^models_elsewhere:open$"))
    async def models_elsewhere(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text(
                FIND_MODELS_TEXT,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="home:main")]]),
                disable_web_page_preview=True
            )
        finally:
            await cq.answer()

    @app.on_callback_query(filters.regex("^home:main$"))
    async def home_cb(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text(
                "🔥 **Welcome back to SuccuBot**\n"
                "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
                "✨ Use the menu below to navigate!",
                reply_markup=_main_keyboard(),
                disable_web_page_preview=True
            )
        finally:
            await cq.answer()
