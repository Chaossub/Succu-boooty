# handlers/menu.py
from __future__ import annotations
import os
from typing import Dict, List

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ── Models (RONI FIRST) ───────────────────────────────────────────────────────
MODELS: List[Dict[str, str]] = [
    {"key": "roni", "display": "Roni", "emoji": "💘", "username": os.getenv("RONI_USERNAME", "").strip("@")},
    {"key": "ruby", "display": "Ruby", "emoji": "💘", "username": os.getenv("RUBY_USERNAME", "").strip("@")},
    {"key": "rin",  "display": "Rin",  "emoji": "💘", "username": os.getenv("RIN_USERNAME", "").strip("@")},
    {"key": "savy", "display": "Savy", "emoji": "💘", "username": os.getenv("SAVY_USERNAME", "").strip("@")},
]

def menu_tabs_text() -> str:
    return "💕 <b>Menus</b>\nPick a model or contact the team."

def model_menu_text(display: str) -> str:
    return f"💘 <b>{display}</b>\nSelect an option:"

def contact_models_text() -> str:
    return "💞 <b>Contact Models</b>\nTap a name to open a DM."

def _chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

# ── 2×2 GRID for model buttons ───────────────────────────────────────────────
def menu_tabs_kb() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(f"{m['emoji']} {m['display']}", callback_data=f"menu:model:{m['key']}") for m in MODELS]
    rows = [list(chunk) for chunk in _chunk(buttons, 2)]  # 2 per row
    rows.append([InlineKeyboardButton("💞 Contact Models", callback_data="menu:contact_models")])
    rows.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_home")])
    return InlineKeyboardMarkup(rows)

def model_menu_kb(model_key: str) -> InlineKeyboardMarkup:
    m = next((x for x in MODELS if x["key"] == model_key), None)
    if not m:
        return menu_tabs_kb()
    uname = m.get("username") or ""
    if uname:
        book_button = InlineKeyboardButton("📖 Book", url=f"https://t.me/{uname}")
    else:
        book_button = InlineKeyboardButton("📖 Book", callback_data="menu:book_missing")
    return InlineKeyboardMarkup([
        [book_button],
        [InlineKeyboardButton("💸 Tip (Coming soon)", callback_data="menu:tip_coming")],
        [InlineKeyboardButton("⬅️ Back to Menus", callback_data="menu:back")],
    ])

def contact_models_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for m in MODELS:
        uname = m.get("username") or ""
        if uname:
            rows.append([InlineKeyboardButton(f"{m['emoji']} {m['display']} ↗", url=f"https://t.me/{uname}")])
        else:
            rows.append([InlineKeyboardButton(f"{m['emoji']} {m['display']} (set username)", callback_data="menu:book_missing")])
    rows.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_home")])
    return InlineKeyboardMarkup(rows)

def register(app: Client):
    @app.on_callback_query(filters.regex(r"^menu_root$|^dmf_open_menu$|^m:menus$"))
    async def show_menus(client: Client, cq: CallbackQuery):
        await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:model:(?P<key>roni|ruby|rin|savy)$"))
    async def show_model_menu(client: Client, cq: CallbackQuery):
        key = cq.matches[0].group("key")
        display = next((m["display"] for m in MODELS if m["key"] == key), key.title())
        await cq.message.edit_text(model_menu_text(display), reply_markup=model_menu_kb(key), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:contact_models$"))
    async def show_contact_models(client: Client, cq: CallbackQuery):
        await cq.message.edit_text(contact_models_text(), reply_markup=contact_models_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:back$"))
    async def back_to_menus(client: Client, cq: CallbackQuery):
        await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:tip_coming$"))
    async def tip_coming(client: Client, cq: CallbackQuery):
        await cq.answer("Payments: Coming soon 💸", show_alert=True)

    @app.on_callback_query(filters.regex(r"^menu:book_missing$"))
    async def book_missing(client: Client, cq: CallbackQuery):
        await cq.answer("That model's @username isn't configured yet. Set it via env (e.g., RONI_USERNAME).", show_alert=True)
