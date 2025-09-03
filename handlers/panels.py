# handlers/panels.py
# Navigation panels (no /start handler here).
import os
from typing import List, Tuple
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# -------- helpers --------
def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _kb(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(rows)

def _admin_from_env(prefix: str) -> Tuple[str, int]:
    # e.g. prefix = "RONI" -> RONI_NAME, RONI_ID
    name = (os.getenv(f"{prefix}_NAME") or "").strip()
    tid  = (os.getenv(f"{prefix}_ID") or "").strip()
    return name, int(tid) if tid.isdigit() else 0

def _tg_mention(name: str, tid: int) -> str:
    if not name:
        return ""
    if tid:
        return f'<a href="tg://user?id={tid}">{name}</a>'
    return name

# -------- ENV labels/content --------
MENU_LABEL   = os.getenv("MENU_BTN", "💕 Menu")
ADMINS_LABEL = os.getenv("ADMINS_BTN", "👑 Contact Admins")
FIND_LABEL   = os.getenv("FIND_MODELS_BTN", "🔥 Find Our Models Elsewhere")
HELP_LABEL   = os.getenv("HELP_BTN", "❓ Help")

FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "").strip() or os.getenv("FIND_MODELS", "").strip()
HELP_INTRO = os.getenv("HELP_INTRO", "Here’s what I can help with:")

BUYER_RULES_TEXT        = os.getenv("BUYER_RULES_TEXT", "").strip()
BUYER_REQUIREMENTS_TEXT = os.getenv("BUYER_REQUIREMENTS_TEXT", "").strip()
GAME_RULES_TEXT         = os.getenv("GAME_RULES_TEXT", "").strip()
EXEMPTIONS_TEXT         = os.getenv("EXEMPTIONS_TEXT", "").strip()

# Admins (Roni / Ruby / Rin / Savy as you configured)
ADMIN_PREFIXES = ["RONI", "RUBY", "RIN", "SAVY"]
ADMINS = [ _admin_from_env(p) for p in ADMIN_PREFIXES ]  # List[Tuple[name, id]]

# -------- public renderers (called by callbacks or other modules) --------
async def main_menu(msg: Message):
    """Render the 4-button main panel under the welcome."""
    rows = [
        [ _btn(MENU_LABEL, "menu") ],
        [ _btn(ADMINS_LABEL, "nav:admins") ],
        [ _btn(FIND_LABEL, "nav:find") ],
        [ _btn(HELP_LABEL, "nav:help") ],
    ]
    await msg.reply_text(
        "✨ <i>Use the menu below to navigate!</i>",
        reply_markup=_kb(rows),
        disable_web_page_preview=True
    )

async def _render_admins(msg: Message):
    lines = ["<b>Contact Admins</b>"]
    added = False
    for name, tid in ADMINS:
        if name:
            lines.append(f"• {_tg_mention(name, tid)}")
            added = True
    if not added:
        lines.append("• No admins configured in env (RONI/RUBY/RIN/SAVY).")
    rows = [[ _btn("⬅️ Back to Main", "nav:main") ]]
    await msg.edit_text("\n".join(lines), reply_markup=_kb(rows), disable_web_page_preview=True)

async def _render_find(msg: Message):
    text = FIND_MODELS_TEXT or "Ask an admin where to find our models elsewhere."
    rows = [[ _btn("⬅️ Back to Main", "nav:main") ]]
    await msg.edit_text(text, reply_markup=_kb(rows), disable_web_page_preview=False)

def _help_rows() -> List[List[InlineKeyboardButton]]:
    rows: List[List[InlineKeyboardButton]] = []
    sub = []
    if BUYER_RULES_TEXT:
        sub.append(_btn("📜 Buyer Rules", "help:rules"))
    if BUYER_REQUIREMENTS_TEXT:
        sub.append(_btn("🧾 Buyer Requirements", "help:reqs"))
    if len(sub) == 2:
        rows.append(sub); sub = []
    if GAME_RULES_TEXT:
        sub.append(_btn("🎲 Game Rules", "help:games"))
    if EXEMPTIONS_TEXT:
        sub.append(_btn("🛡️ Exemptions", "help:exempt"))
    if sub:
        rows.append(sub)
    rows.append([ _btn("⬅️ Back to Main", "nav:main") ])
    return rows

async def _render_help(msg: Message):
    await msg.edit_text(
        f"❓ <b>Help</b>\n{HELP_INTRO}",
        reply_markup=_kb(_help_rows()),
        disable_web_page_preview=True
    )

async def _render_help_section(msg: Message, text: str, title: str):
    rows = [[ _btn("⬅️ Back to Help", "nav:help") ]]
    await msg.edit_text(f"<b>{title}</b>\n{text}", reply_markup=_kb(rows), disable_web_page_preview=False)

# -------- registration --------
def register(app: Client):
    # Back to main panel from anywhere
    @app.on_callback_query(filters.regex(r"^(nav:main|nav:root|back_main)$"))
    async def _go_main(c: Client, cq: CallbackQuery):
        await main_menu(cq.message)
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex(r"^nav:admins$"))
    async def _admins(c: Client, cq: CallbackQuery):
        await _render_admins(cq.message); await cq.answer()

    # Find Our Models Elsewhere
    @app.on_callback_query(filters.regex(r"^nav:find$"))
    async def _find(c: Client, cq: CallbackQuery):
        await _render_find(cq.message); await cq.answer()

    # Help root
    @app.on_callback_query(filters.regex(r"^nav:help$"))
    async def _help(c: Client, cq: CallbackQuery):
        await _render_help(cq.message); await cq.answer()

    # Help subsections (only render if text exists)
    @app.on_callback_query(filters.regex(r"^help:rules$"))
    async def _help_rules(c: Client, cq: CallbackQuery):
        if not BUYER_RULES_TEXT:
            return await cq.answer("No Buyer Rules configured.", show_alert=True)
        await _render_help_section(cq.message, BUYER_RULES_TEXT, "📜 Buyer Rules"); await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:reqs$"))
    async def _help_reqs(c: Client, cq: CallbackQuery):
        if not BUYER_REQUIREMENTS_TEXT:
            return await cq.answer("No Buyer Requirements configured.", show_alert=True)
        await _render_help_section(cq.message, BUYER_REQUIREMENTS_TEXT, "🧾 Buyer Requirements"); await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:games$"))
    async def _help_games(c: Client, cq: CallbackQuery):
        if not GAME_RULES_TEXT:
            return await cq.answer("No Game Rules configured.", show_alert=True)
        await _render_help_section(cq.message, GAME_RULES_TEXT, "🎲 Game Rules"); await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:exempt$"))
    async def _help_exempt(c: Client, cq: CallbackQuery):
        if not EXEMPTIONS_TEXT:
            return await cq.answer("No Exemptions configured.", show_alert=True)
        await _render_help_section(cq.message, EXEMPTIONS_TEXT, "🛡️ Exemptions"); await cq.answer()
