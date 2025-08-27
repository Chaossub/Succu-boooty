# dm_foolproof.py
# Single /start entrypoint & main portal. Includes alias callbacks so
# Menus / Contact Admins / Help / Links work even if other modules use
# different callback_data names.

from __future__ import annotations
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

# ── Texts (env-driven) ────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

# Pull from env; keep a safe fallback if not provided
MODELS_LINKS_TEXT = os.getenv("FIND_MODELS_TEXT") or (
    "✨ <b>Find Our Models Elsewhere</b> ✨\n\n"
    "All verified off-platform links for our models are collected here. "
    "Check pinned messages or official posts for updates."
)

# Optional help texts via env (fallbacks still handled by help_panel, this is only used if that import fails)
BUYER_RULES_TEXT = os.getenv("BUYER_RULES_TEXT") or "📜 Buyer rules are not configured yet."
BUYER_REQS_TEXT  = os.getenv("BUYER_REQUIREMENTS_TEXT") or "✅ Buyer requirements are not configured yet."
GAME_RULES_TEXT  = os.getenv("GAME_RULES_TEXT") or "🕹️ Game rules are not configured yet."

# ── Keyboards ────────────────────────────────────────────────────────────────
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="dmf_open_menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="dmf_admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="dmf_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_help")],
    ])

def _back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_home")]])

# ── Helpers ──────────────────────────────────────────────────────────────────
async def _safe_edit(message, text, **kwargs):
    try:
        return await message.edit_text(text, **kwargs)
    except MessageNotModified:
        # try only updating markup if text didn't change
        if "reply_markup" in kwargs and kwargs["reply_markup"] is not None:
            try:
                return await message.edit_reply_markup(kwargs["reply_markup"])
            except MessageNotModified:
                pass
    return None

# ── Register ─────────────────────────────────────────────────────────────
def register(app: Client):

    # /start command → show the main portal
    @app.on_message(filters.command("start"))
    async def start_cmd(client: Client, m: Message):
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # Home / Back
    @app.on_callback_query(filters.regex(r"^(dmf_home|portal:home|back_home)$"))
    async def cb_home(client: Client, cq):
        await _safe_edit(cq.message, WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)
        await cq.answer()

    # ── Find Our Models Elsewhere ────────────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^(dmf_links|open_links|portal:links)$"))
    async def cb_links(client: Client, cq):
        # Use env-driven text
        await _safe_edit(cq.message, MODELS_LINKS_TEXT, reply_markup=_back_home_kb(), disable_web_page_preview=False)
        await cq.answer()

    # ── Menus (robust aliases) ──────────────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^(dmf_open_menus|dmf_open_menu|open_menu|portal:menus|menus)$"))
    async def cb_menus(client: Client, cq):
        # Prefer real menu module if present
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            text = menu_tabs_text()
            kb = menu_tabs_kb()
            await _safe_edit(cq.message, text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            # Soft fallback
            await _safe_edit(
                cq.message,
                "💕 <b>Menus</b>\nPick a model or contact the team.",
                reply_markup=_back_home_kb(),
                disable_web_page_preview=True,
            )
        await cq.answer()

    # ── Contact Admins (robust aliases) ─────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^(dmf_admins|open_admins|portal:admins)$"))
    async def cb_admins(client: Client, cq):
        try:
            from handlers.contact_admins import CONTACT_TEXT, _kb_admins
            await _safe_edit(cq.message, CONTACT_TEXT, reply_markup=_kb_admins(), disable_web_page_preview=True)
        except Exception:
            await _safe_edit(
                cq.message,
                "👑 <b>Contact Admins</b>\nAdmin panel isn’t configured yet.",
                reply_markup=_back_home_kb(),
                disable_web_page_preview=True,
            )
        await cq.answer()

    # ── Help (robust aliases) ───────────────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^(dmf_help|open_help|portal:help)$"))
    async def cb_help(client: Client, cq):
        try:
            # Use the real help panel if present
            from handlers.help_panel import HELP_MENU_TEXT, _help_menu_kb
            await _safe_edit(cq.message, HELP_MENU_TEXT, reply_markup=_help_menu_kb(), disable_web_page_preview=True)
        except Exception:
            # Fallback consolidated help panel
            text = (
                "❓ <b>Help</b>\nChoose an option.\n\n"
                "<b>📜 Buyer Rules</b>\n" + BUYER_RULES_TEXT + "\n\n"
                "<b>✅ Buyer Requirements</b>\n" + BUYER_REQS_TEXT + "\n\n"
                "<b>🕹️ Game Rules</b>\n" + GAME_RULES_TEXT
            )
            await _safe_edit(cq.message, text, reply_markup=_back_home_kb(), disable_web_page_preview=True)
        await cq.answer()

