# handlers/panels.py
# Model picker → show saved menu text + Book/Tip buttons
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
# Default models (2x2 grid). You can override with MODELS env: e.g. "Roni,Ruby,Rin,Savy,Jade"
_DEFAULT_MODELS = ["Roni", "Ruby", "Rin", "Savy"]
_MODELS_ENV = os.getenv("MODELS", "")
MODELS: List[str] = [x.strip() for x in _MODELS_ENV.split(",") if x.strip()] or _DEFAULT_MODELS

# Optional per-model links (set in environment):
#   <NAME>_BOOK_URL, <NAME>_TIP_URL
# e.g. RONI_BOOK_URL, RONI_TIP_URL, RUBY_BOOK_URL, RUBY_TIP_URL, etc.
def _norm(name: str) -> str:
    # ENV keys: upper + alnum only
    return "".join(ch for ch in name.upper() if ch.isalnum())

def _get_url(kind: str, name: str) -> str | None:
    # kind in {"BOOK", "TIP"}
    key = f"{_norm(name)}_{kind}_URL"
    return os.getenv(key)

# Callback namespaces (avoid collisions with other modules)
ROOT_CB     = "panels:root"
PICK_CB_P   = "panels:pick:"   # panels:pick:<Name>
BOOK_CB_P   = "panels:book:"   # panels:book:<Name>
TIP_CB_P    = "panels:tip:"    # panels:tip:<Name>

def _clean(name: str) -> str:
    return name.strip().strip("»«‘’“”\"'`").strip()

def _models_keyboard() -> InlineKeyboardMarkup:
    # 2x2 layout, then back/main
    rows = []
    row = []
    for i, n in enumerate(MODELS, 1):
        row.append(InlineKeyboardButton(n, callback_data=f"{PICK_CB_P}{n}"))
        if i % 2 == 0:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅ Back", callback_data=ROOT_CB),
                 InlineKeyboardButton("🏠 Main", callback_data="help:open")])
    return InlineKeyboardMarkup(rows)

def _menu_keyboard(name: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📖 Book", callback_data=f"{BOOK_CB_P}{name}")],
        [InlineKeyboardButton("💸 Tip",  callback_data=f"{TIP_CB_P}{name}")],
        [InlineKeyboardButton("⬅ Back", callback_data=ROOT_CB)],
    ]
    return InlineKeyboardMarkup(buttons)

def register(app):
    # /menu → choose a model
    @app.on_message(filters.command("menu"))
    async def menu_cmd(_, m: Message):
        await m.reply_text("💕 <b>Choose a model:</b>", reply_markup=_models_keyboard())

    # Back to model list
    @app.on_callback_query(filters.regex(f"^{ROOT_CB}$"))
    async def root_cb(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text("💕 <b>Choose a model:</b>", reply_markup=_models_keyboard())
        except Exception:
            await cq.answer()
            await cq.message.reply_text("💕 <b>Choose a model:</b>", reply_markup=_models_keyboard())

    # Pick a specific model → show saved menu + Book/Tip
    @app.on_callback_query(filters.regex(r"^panels:pick:.+"))
    async def pick_cb(_, cq: CallbackQuery):
        raw = cq.data[len(PICK_CB_P):]
        name = _clean(raw)
        text = store.get_menu(name) or "No menu saved yet.\n\nUse /createmenu <Name> <text…> to set one."
        content = f"<b>{name} — Menu</b>\n\n{text}"
        try:
            await cq.message.edit_text(
                content,
                reply_markup=_menu_keyboard(name),
                disable_web_page_preview=True
            )
        except Exception:
            await cq.answer()
            await cq.message.reply_text(
                content,
                reply_markup=_menu_keyboard(name),
                disable_web_page_preview=True
            )

    # Book button
    @app.on_callback_query(filters.regex(r"^panels:book:.+"))
    async def book_cb(_, cq: CallbackQuery):
        name = _clean(cq.data[len(BOOK_CB_P):])
        url = _get_url("BOOK", name)
        if url:
            # Send a small message with the link so it’s clickable
            await cq.message.reply_text(
                f"📖 <b>Booking for {name}</b>\n{url}",
                disable_web_page_preview=False
            )
        else:
            await cq.answer("No booking link set for this model.", show_alert=True)

    # Tip button
    @app.on_callback_query(filters.regex(r"^panels:tip:.+"))
    async def tip_cb(_, cq: CallbackQuery):
        name = _clean(cq.data[len(TIP_CB_P):])
        url = _get_url("TIP", name)
        if url:
            await cq.message.reply_text(
                f"💸 <b>Tip {name}</b>\n{url}",
                disable_web_page_preview=False
            )
        else:
            await cq.answer("No tip link set for this model.", show_alert=True)
