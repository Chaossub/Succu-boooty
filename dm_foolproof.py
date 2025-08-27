# dm_foolproof.py
# Single /start entrypoint & main portal (no duplicates on navigation).
# Marks users DM-ready when they /start in PRIVATE chat.

from __future__ import annotations
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

log = logging.getLogger("dm_foolproof")

# ── Env-driven texts (with safe fallbacks) ────────────────────────────────────
WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

MODELS_LINKS_TEXT = os.getenv("FIND_MODELS_TEXT") or (
    "✨ <b>Find Our Models Elsewhere</b> ✨\n\n"
    "All verified off-platform links for our models are collected here. "
    "Check pinned messages or official posts for updates."
)

# Optional help fallbacks (your help_panel will override if present)
BUYER_RULES_TEXT = os.getenv("BUYER_RULES_TEXT") or "📜 Buyer rules are not configured yet."
BUYER_REQS_TEXT  = os.getenv("BUYER_REQUIREMENTS_TEXT") or "✅ Buyer requirements are not configured yet."
GAME_RULES_TEXT  = os.getenv("GAME_RULES_TEXT") or "🕹️ Game rules are not configured yet."

# ── Optional DM-ready storage (best-effort) ───────────────────────────────────
# We try to import your requirement store; if missing, we just skip.
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception as e:
    _store = None
    log.info("ReqStore not available; DM-ready marking is best-effort only")

def _set_dm_ready(uid: int) -> bool:
    """
    Mark a user as DM-ready in your store (if available).
    Returns True if we changed it from False->True; False otherwise.
    """
    if not _store or not uid:
        return False
    try:
        # Prefer global API if present
        if hasattr(_store, "is_dm_ready_global") and hasattr(_store, "set_dm_ready_global"):
            if not _store.is_dm_ready_global(uid):
                _store.set_dm_ready_global(uid, True, by_admin=False)
                return True
            return False
        # Fallback older API
        if hasattr(_store, "is_dm_ready") and hasattr(_store, "set_dm_ready"):
            if not _store.is_dm_ready(uid):
                _store.set_dm_ready(uid, True)
                return True
            return False
    except Exception as e:
        log.warning(f"Failed to set dm-ready for {uid}: {e}")
    return False

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

# ── Safe edit helper (prevents MESSAGE_NOT_MODIFIED noise) ───────────────────
async def _safe_edit(message, text, **kwargs):
    try:
        return await message.edit_text(text, **kwargs)
    except MessageNotModified:
        if kwargs.get("reply_markup") is not None:
            try:
                return await message.edit_reply_markup(kwargs["reply_markup"])
            except MessageNotModified:
                pass
    return None

# ── Register ─────────────────────────────────────────────────────────────────
def register(app: Client):

    # /start in PRIVATE marks DM-ready, then shows portal.
    @app.on_message(filters.private & filters.command("start"))
    async def start_private(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else None
        changed = _set_dm_ready(uid) if uid else False
        if changed:
            log.info(f"DM-ready set for user {uid}")
        # send a fresh portal message in DM
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # /start in groups just posts the portal once (no DM-ready changes)
    @app.on_message(~filters.private & filters.command("start"))
    async def start_group(client: Client, m: Message):
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # Back/Home — edits in place (no duplicates)
    @app.on_callback_query(filters.regex(r"^(dmf_home|portal:home|back_home)$"))
    async def cb_home(client: Client, cq: CallbackQuery):
        await _safe_edit(cq.message, WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)
        await cq.answer()

    # Find Our Models Elsewhere (env-driven text)
    @app.on_callback_query(filters.regex(r"^(dmf_links|open_links|portal:links)$"))
    async def cb_links(client: Client, cq: CallbackQuery):
        await _safe_edit(cq.message, MODELS_LINKS_TEXT, reply_markup=_back_home_kb(), disable_web_page_preview=False)
        await cq.answer()

    # Menus — accept several callback aliases, delegate to handlers.menu if present
    @app.on_callback_query(filters.regex(r"^(dmf_open_menus|dmf_open_menu|open_menu|portal:menus|menus)$"))
    async def cb_menus(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            await _safe_edit(cq.message, menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception as e:
            log.warning(f"menus fallback used: {e}")
            await _safe_edit(
                cq.message,
                "💕 <b>Menus</b>\nPick a model or contact the team.",
                reply_markup=_back_home_kb(),
                disable_web_page_preview=True,
            )
        await cq.answer()

    # Contact Admins — use real panel if present
    @app.on_callback_query(filters.regex(r"^(dmf_admins|open_admins|portal:admins)$"))
    async def cb_admins(client: Client, cq: CallbackQuery):
        try:
            from handlers.contact_admins import CONTACT_TEXT, _kb_admins
            await _safe_edit(cq.message, CONTACT_TEXT, reply_markup=_kb_admins(), disable_web_page_preview=True)
        except Exception as e:
            log.warning(f"admins fallback used: {e}")
            await _safe_edit(
                cq.message,
                "👑 <b>Contact Admins</b>\nAdmin panel isn’t configured yet.",
                reply_markup=_back_home_kb(),
                disable_web_page_preview=True,
            )
        await cq.answer()

    # Help — prefer handlers.help_panel, else show simple fallback
    @app.on_callback_query(filters.regex(r"^(dmf_help|open_help|portal:help)$"))
    async def cb_help(client: Client, cq: CallbackQuery):
        try:
            from handlers.help_panel import HELP_MENU_TEXT, _help_menu_kb
            await _safe_edit(cq.message, HELP_MENU_TEXT, reply_markup=_help_menu_kb(), disable_web_page_preview=True)
        except Exception as e:
            log.warning(f"help fallback used: {e}")
            text = (
                "❓ <b>Help</b>\nChoose an option.\n\n"
                "<b>📜 Buyer Rules</b>\n" + BUYER_RULES_TEXT + "\n\n"
                "<b>✅ Buyer Requirements</b>\n" + BUYER_REQS_TEXT + "\n\n"
                "<b>🕹️ Game Rules</b>\n" + GAME_RULES_TEXT
            )
            await _safe_edit(cq.message, text, reply_markup=_back_home_kb(), disable_web_page_preview=True)
        await cq.answer()
