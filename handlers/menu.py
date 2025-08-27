# handlers/menu.py
from __future__ import annotations
import os, json
from pathlib import Path
from typing import Dict, List, Optional

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

# Models list (RONI FIRST). Names are optional; defaults shown.
MODELS: List[Dict[str, str]] = [
    {"key": "roni", "display": os.getenv("RONI_NAME", "Roni"), "emoji": "💘"},
    {"key": "ruby", "display": os.getenv("RUBY_NAME", "Ruby"), "emoji": "💘"},
    {"key": "rin",  "display": os.getenv("RIN_NAME",  "Rin"),  "emoji": "💘"},
    {"key": "savy", "display": os.getenv("SAVY_NAME", "Savy"), "emoji": "💘"},
]

# JSON file where /createmenu stores text (and where you can add more later)
DATA_PATH = Path(os.getenv("MODEL_MENU_DATA", "data/model_menus.json"))

def _load_overrides() -> Dict[str, dict]:
    try:
        if DATA_PATH.is_file():
            return json.loads(DATA_PATH.read_text() or "{}")
    except Exception:
        pass
    return {}

# Build a Book link from env vars: prefer username, else numeric ID
# Env examples:
#   RONI_USERNAME=RoniJane   (without @)  -> https://t.me/RoniJane
#   RONI_ID=8087941938                    -> tg://user?id=8087941938
def _book_url_from_env(model_key: str) -> Optional[str]:
    env_map = {
        "roni": ("RONI_USERNAME", "RONI_ID"),
        "ruby": ("RUBY_USERNAME", "RUBY_ID"),
        "rin":  ("RIN_USERNAME",  "RIN_ID"),
        "savy": ("SAVY_USERNAME", "SAVY_ID"),
    }
    u_name, u_id = env_map[model_key]
    username = os.getenv(u_name, "").strip().lstrip("@")
    uid = os.getenv(u_id, "").strip()
    if username:
        return f"https://t.me/{username}"
    if uid.isdigit():
        return f"tg://user?id={uid}"
    return None

def _get_model_menu_text(model_key: str, display: str) -> str:
    # Use custom menu text from /createmenu if provided
    ov = _load_overrides().get(model_key, {})
    custom = ov.get("menu_text")
    return custom if custom else f"💘 <b>{display}</b>\nSelect an option:"

# ── Visible texts ────────────────────────────────────────────────────────────
def menu_tabs_text() -> str:
    return "💕 <b>Menus</b>\nPick a model or contact the team."

def contact_models_text() -> str:
    return "💞 <b>Contact Models</b>\nTap a name to open a DM."

# ── Helpers ──────────────────────────────────────────────────────────────────
def _chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

# ── Keyboards ────────────────────────────────────────────────────────────────
def menu_tabs_kb() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(f"{m['emoji']} {m['display']}", callback_data=f"menu:model:{m['key']}")
        for m in MODELS
    ]
    rows = [list(row) for row in _chunk(buttons, 2)]  # 2×2 grid for 4 models
    rows.append([InlineKeyboardButton("💞 Contact Models", callback_data="menu:contact_models")])
    rows.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_home")])
    return InlineKeyboardMarkup(rows)

def model_menu_kb(model_key: str) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    book_url = _book_url_from_env(model_key)
    if book_url:
        rows.append([InlineKeyboardButton("📖 Book", url=book_url)])
    else:
        rows.append([InlineKeyboardButton("📖 Book", callback_data="menu:book_missing")])
    rows.append([InlineKeyboardButton("💸 Tip (Coming soon)", callback_data="menu:tip_coming")])
    rows.append([InlineKeyboardButton("⬅️ Back to Menus", callback_data="menu:back")])
    return InlineKeyboardMarkup(rows)

def contact_models_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for m in MODELS:
        key = m["key"]
        disp = m["display"]
        url = _book_url_from_env(key)
        if url:
            rows.append([InlineKeyboardButton(f"{m['emoji']} {disp} ↗", url=url)])
        else:
            rows.append([InlineKeyboardButton(f"{m['emoji']} {disp} (set link)", callback_data="menu:book_missing")])
    rows.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_home")])
    return InlineKeyboardMarkup(rows)

# ── Handlers (edit-in-place; no new posts) ───────────────────────────────────
def register(app: Client):

    @app.on_callback_query(filters.regex(r"^menu_root$|^dmf_open_menu$|^m:menus$"))
    async def show_menus(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:model:(?P<key>roni|ruby|rin|savy)$"))
    async def show_model_menu(client: Client, cq: CallbackQuery):
        key = cq.matches[0].group("key")
        display = next((m["display"] for m in MODELS if m["key"] == key), key.title())
        text = _get_model_menu_text(key, display)
        try:
            await cq.message.edit_text(text, reply_markup=model_menu_kb(key), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:contact_models$"))
    async def show_contact_models(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(contact_models_text(), reply_markup=contact_models_kb(), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:back$"))
    async def back_to_menus(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:tip_coming$"))
    async def tip_coming(client: Client, cq: CallbackQuery):
        await cq.answer("Payments: Coming soon 💸", show_alert=True)

    @app.on_callback_query(filters.regex(r"^menu:book_missing$"))
    async def book_missing(client: Client, cq: CallbackQuery):
        await cq.answer(
            "That model’s contact isn’t configured yet. Set a USERNAME or ID in env.",
            show_alert=True,
        )
