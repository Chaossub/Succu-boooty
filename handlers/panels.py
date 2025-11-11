# handlers/panels.py
# Model picker → show saved menu text + Book/Tip buttons
# + "Find Our Models Elsewhere" panel (read from env)

import os
from typing import List
from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
)
from utils.menu_store import store

# ======= CONFIG =======
_DEFAULT_MODELS = ["Roni", "Ruby", "Rin", "Savy"]
_MODELS_ENV = os.getenv("MODELS", "")
MODELS: List[str] = [x.strip() for x in _MODELS_ENV.split(",") if x.strip()] or _DEFAULT_MODELS

def _norm(name: str) -> str:
    return "".join(ch for ch in name.upper() if ch.isalnum())

def _get_url(kind: str, name: str) -> str | None:
    key = f"{_norm(name)}_{kind}_URL"
    return os.getenv(key)

ROOT_CB   = "panels:root"
PICK_CB_P = "panels:pick:"
BOOK_CB_P = "panels:book:"
TIP_CB_P  = "panels:tip:"

def _clean(name: str) -> str:
    return name.strip().strip("»«‘’“”\"'`").strip()

# ───────────────────────────
# "Models Elsewhere" (from env)
# MODELS_ELSEWHERE="Label|https://url, Label2|https://url2"
# ───────────────────────────
def _elsewhere_rows() -> list[list[InlineKeyboardButton]]:
    raw = os.getenv("MODELS_ELSEWHERE", "")
    rows: list[list[InlineKeyboardButton]] = []
    for part in [p.strip() for p in raw.split(",") if p.strip()]:
        if "|" not in part:
            continue
        label, url = [s.strip() for s in part.split("|", 1)]
        if label and url.startswith("http"):
            rows.append([InlineKeyboardButton(label, url=url)])
    rows.append([InlineKeyboardButton("⬅ Back", callback_data="home:main")])
    return rows

# ───────────────────────────
# Keyboards
# ───────────────────────────
def _models_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, n in enumerate(MODELS, 1):
        row.append(InlineKeyboardButton(n, callback_data=f"{PICK_CB_P}{n}"))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton("⬅ Back", callback_data="home:main"),
        InlineKeyboardButton("🏠 Main", callback_data="home:main")
    ])
    return InlineKeyboardMarkup(rows)

def _menu_keyboard(name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Book", callback_data=f"{BOOK_CB_P}{name}")],
        [InlineKeyboardButton("💸 Tip", callback_data=f"{TIP_CB_P}{name}")],
        [InlineKeyboardButton("⬅ Back", callback_data=ROOT_CB)],
    ])

def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 Menus", callback_data=ROOT_CB)],
        [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
        [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
        [InlineKeyboardButton("❓ Help", callback_data="help:open")],
    ])

# ───────────────────────────
# Handlers
# ───────────────────────────
def register(app):

    # /start — main entry screen
    @app.on_message(filters.command("start"))
    async def start_cmd(_, m: Message):
        await m.reply_text(
            "🔥 **Welcome to SuccuBot**\n"
            "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
            "✨ Use the menu below to navigate!",
            reply_markup=_main_keyboard(),
            disable_web_page_preview=True
        )

    # /menu — shortcut to model picker
    @app.on_message(filters.command("menu"))
    async def menu_cmd(_, m: Message):
        await m.reply_text("💕 **Choose a model:**", reply_markup=_models_keyboard())

    # Back to model list
    @app.on_callback_query(filters.regex(f"^{ROOT_CB}$"))
    async def back_to_models(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text("💕 **Choose a model:**", reply_markup=_models_keyboard())
        finally:
            await cq.answer()

    # Pick a specific model → show its saved menu
    @app.on_callback_query(filters.regex(r"^panels:pick:.+"))
    async def pick_cb(_, cq: CallbackQuery):
        raw = cq.data[len(PICK_CB_P):]
        name = _clean(raw)
        text = store.get_menu(name) or "No menu saved yet.\n\nUse /createmenu <Name> <text…> to set one."
        content = f"**{name} — Menu**\n\n{text}"
        try:
            await cq.message.edit_text(
                content,
                reply_markup=_menu_keyboard(name),
                disable_web_page_preview=True
            )
        finally:
            await cq.answer()

    # Book button
    @app.on_callback_query(filters.regex(r"^panels:book:.+"))
    async def book_cb(_, cq: CallbackQuery):
        name = _clean(cq.data[len(BOOK_CB_P):])
        url = _get_url("BOOK", name)
        if url:
            await cq.message.reply_text(f"📖 **Booking for {name}**\n{url}", disable_web_page_preview=False)
        else:
            await cq.answer("No booking link set for this model.", show_alert=True)

    # Tip button
    @app.on_callback_query(filters.regex(r"^panels:tip:.+"))
    async def tip_cb(_, cq: CallbackQuery):
        name = _clean(cq.data[len(TIP_CB_P):])
        url = _get_url("TIP", name)
        if url:
            await cq.message.reply_text(f"💸 **Tip {name}**\n{url}", disable_web_page_preview=False)
        else:
            await cq.answer("No tip link set for this model.", show_alert=True)

    # 🍑 Find Our Models Elsewhere (inside panels)
    @app.on_callback_query(filters.regex(r"^models_elsewhere:open$"))
    async def elsewhere_cb(_, cq: CallbackQuery):
        rows = _elsewhere_rows()
        text = "🍑 **Find Our Models Elsewhere**\nTap a link below:"
        try:
            await cq.message.edit_text(text, reply_markup=InlineKeyboardMarkup(rows), disable_web_page_preview=True)
        finally:
            await cq.answer()

    # Home button — returns to main /start screen
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
