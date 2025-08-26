# handlers/menu.py
from __future__ import annotations

import os
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)

log = logging.getLogger("SuccuBot")

# ======== ENV ========
RONI = os.getenv("RONI_USERNAME", "").lstrip("@")
RUBY = os.getenv("RUBY_USERNAME", "").lstrip("@")
RIN  = os.getenv("RIN_USERNAME", "").lstrip("@")
SAVY = os.getenv("SAVY_USERNAME", "").lstrip("@")

FIND_ELSEWHERE_TEXT = os.getenv("FIND_MODELS_ELSEWHERE_TEXT", "Links coming soon.")

# Helper to build TG dm links (username required)
def _dm_url(username: str) -> str:
    return f"https://t.me/{username}" if username else "https://t.me/"

# ========= CALLBACK KEYS =========
CB_MAIN             = "menu:main"
CB_MENUS            = "menu:menus"
CB_CONTACT_MODELS   = "menu:contact_models"
CB_CONTACT_ADMINS   = "menu:contact_admins"
CB_FIND_ELSEWHERE   = "menu:find_elsewhere"
CB_HELP             = "menu:help"

CB_BACK_MAIN        = "menu:back_main"
CB_BACK_MENUS       = "menu:back_menus"

CB_ANON             = "menu:anon"
CB_SUGGEST          = "menu:suggest"

CB_MM_RONI          = "menu:model_menu:roni"
CB_MM_RUBY          = "menu:model_menu:ruby"
CB_MM_RIN           = "menu:model_menu:rin"
CB_MM_SAVY          = "menu:model_menu:savy"

# ========= KEYBOARDS =========

def _kb_main() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💕 Menus", callback_data=CB_MENUS)],
        [InlineKeyboardButton("👑 Contact Admins", callback_data=CB_CONTACT_ADMINS)],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data=CB_FIND_ELSEWHERE)],
        [InlineKeyboardButton("❓ Help", callback_data=CB_HELP)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_menus() -> InlineKeyboardMarkup:
    rows = [
        # 2×2 grid of model MENUS (open in-bot panels, not DMs)
        [
            InlineKeyboardButton("💗 Roni Menu", callback_data=CB_MM_RONI),
            InlineKeyboardButton("💗 Ruby Menu", callback_data=CB_MM_RUBY),
        ],
        [
            InlineKeyboardButton("💗 Rin Menu",  callback_data=CB_MM_RIN),
            InlineKeyboardButton("💗 Savy Menu", callback_data=CB_MM_SAVY),
        ],
        # Contact Models (opens DM links page)
        [InlineKeyboardButton("💬 Contact Models", callback_data=CB_CONTACT_MODELS)],
        # Back
        [InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_contact_models() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("💬 Roni ↗", url=_dm_url(RONI)),
            InlineKeyboardButton("💬 Ruby ↗", url=_dm_url(RUBY)),
        ],
        [
            InlineKeyboardButton("💬 Rin ↗",  url=_dm_url(RIN)),
            InlineKeyboardButton("💬 Savy ↗", url=_dm_url(SAVY)),
        ],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_contact_admins() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("👑 Message Roni", url=_dm_url(RONI)),
            InlineKeyboardButton("👑 Message Ruby", url=_dm_url(RUBY)),
        ],
        [
            InlineKeyboardButton("🕵️ Anonymous Message", callback_data=CB_ANON),
            InlineKeyboardButton("💡 Suggestion Box", callback_data=CB_SUGGEST),
        ],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_model_menu_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Back to Menus", callback_data=CB_MENUS)],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)],
        ]
    )

def _kb_model_menu(model: str, username: str) -> InlineKeyboardMarkup:
    # Minimal per-model panel; you can expand each later
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"📖 Book {model}", url=_dm_url(username))],
            [InlineKeyboardButton("⬅️ Back to Menus", callback_data=CB_MENUS)],
        ]
    )

# ========= TEXTS =========

WELCOME_TEXT = (
    "🔥 **Welcome to SuccuBot** 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ *Use the menu below to navigate!*"
)

MENUS_TEXT = "💕 **Menus**"
CONTACT_MODELS_TEXT = "Contact a model directly:"
CONTACT_ADMINS_TEXT = "Contact Admins:"
FIND_ELSEWHERE_TITLE = "🔥 **Find Our Models Elsewhere**"
HELP_PLACEHOLDER = (
    "❓ **Help**\n"
    "Buyer Rules, Buyer Requirements, and Game Rules live in their respective panels.\n"
    "Use the buttons you already have set up for Help (separate handler)."
)

def _model_panel_text(model: str) -> str:
    return f"💗 **{model} — Menu**\nPick an option below."

# ========= HANDLERS =========

async def _send_main_menu(c: Client, chat_id: int) -> Message:
    return await c.send_message(
        chat_id,
        WELCOME_TEXT,
        reply_markup=_kb_main(),
        disable_web_page_preview=True,
    )

# /start and /portal show main menu
@Client.on_message(filters.command(["start", "portal"]))
async def _start(c: Client, m: Message):
    await _send_main_menu(c, m.chat.id)

# ----- Callback helpers -----

async def _go_main(q: CallbackQuery):
    await q.answer()
    await q.message.edit_text(WELCOME_TEXT, reply_markup=_kb_main(), disable_web_page_preview=True)

async def _open_menus(q: CallbackQuery):
    await q.answer()
    await q.message.edit_text(MENUS_TEXT, reply_markup=_kb_menus(), disable_web_page_preview=True)

async def _open_contact_models(q: CallbackQuery):
    await q.answer()
    await q.message.edit_text(CONTACT_MODELS_TEXT, reply_markup=_kb_contact_models(), disable_web_page_preview=True)

async def _open_contact_admins(q: CallbackQuery):
    await q.answer()
    await q.message.edit_text(CONTACT_ADMINS_TEXT, reply_markup=_kb_contact_admins(), disable_web_page_preview=True)

async def _open_find_elsewhere(q: CallbackQuery):
    await q.answer()
    text = f"{FIND_ELSEWHERE_TITLE}\n\n{FIND_ELSEWHERE_TEXT}"
    # Show the ENV text right in-chat, with a Back to Main
    await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)]]), disable_web_page_preview=True)

async def _open_help(q: CallbackQuery):
    await q.answer()
    await q.message.edit_text(HELP_PLACEHOLDER, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)]]), disable_web_page_preview=True)

# Model menu panels (not DM links)
async def _model_menu(q: CallbackQuery, model: str, username: str):
    await q.answer()
    await q.message.edit_text(_model_panel_text(model), reply_markup=_kb_model_menu(model, username), disable_web_page_preview=True)

# Anonymous & Suggestion boxes — send to owner’s DM (bot owner chat) via forward to you.
# Here we simply prompt for the text and store a tiny state in memory by replying.
_pending = {}  # {user_id: ("anon"|"suggest")}

@Client.on_callback_query(filters.regex("^menu:"))
async def _router(c: Client, q: CallbackQuery):
    data = q.data or ""
    try:
        if data == CB_BACK_MAIN or data == CB_MAIN:
            return await _go_main(q)
        if data == CB_MENUS:
            return await _open_menus(q)
        if data == CB_CONTACT_MODELS:
            return await _open_contact_models(q)
        if data == CB_CONTACT_ADMINS:
            return await _open_contact_admins(q)
        if data == CB_FIND_ELSEWHERE:
            return await _open_find_elsewhere(q)
        if data == CB_HELP:
            return await _open_help(q)

        if data == CB_MM_RONI:
            return await _model_menu(q, "Roni", RONI)
        if data == CB_MM_RUBY:
            return await _model_menu(q, "Ruby", RUBY)
        if data == CB_MM_RIN:
            return await _model_menu(q, "Rin", RIN)
        if data == CB_MM_SAVY:
            return await _model_menu(q, "Savy", SAVY)

        if data == CB_ANON:
            await q.answer()
            _pending[q.from_user.id] = ("anon",)
            return await q.message.edit_text(
                "🕵️ **Anonymous Message**\nSend me the message now. I’ll forward it privately.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)]]),
            )

        if data == CB_SUGGEST:
            await q.answer()
            _pending[q.from_user.id] = ("suggest",)
            return await q.message.edit_text(
                "💡 **Suggestion Box**\nSend your suggestion. I’ll forward it privately (with your @).",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)]]),
            )

    except Exception as e:
        log.exception("menu router error: %s", e)
        try:
            await q.answer("Oops, something went wrong.", show_alert=True)
        except Exception:
            pass

# Capture the next text from user for anon/suggest
@Client.on_message(filters.text & ~filters.command(["start", "portal"]))
async def _collect_free_text(c: Client, m: Message):
    uid = m.from_user.id if m.from_user else None
    if uid in _pending:
        mode = _pending.pop(uid)[0]
        owner_id = int(os.getenv("OWNER_ID", "0"))  # your Telegram numeric ID
        try:
            if mode == "anon":
                await c.send_message(owner_id, f"🕵️ **Anonymous message**\n\n{m.text}")
                await m.reply_text("✅ Sent anonymously to the admins.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)]]))
            else:
                # include their @ if available
                mention = m.from_user.mention if m.from_user else "Unknown"
                await c.send_message(owner_id, f"💡 **Suggestion from {mention}**\n\n{m.text}")
                await m.reply_text("✅ Suggestion delivered. Thank you!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)]]))
        except Exception as e:
            log.exception("forwarding anon/suggest failed: %s", e)
            await m.reply_text("⚠️ I couldn't send that just now. Please try again later.")

# ======= public register() for main.py =======
def register(app: Client):
    log.info("wired: handlers.menu")
    # Nothing else needed; decorators above bind to this Client instance.
    # This function exists so main.py can import and call register(app).
    return
