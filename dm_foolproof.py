# dm_foolproof.py — /start portal, DM-ready (one-time), admin DM-ready list, contact + links + help

import os
import time
from typing import List, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ReqStore (JSON-backed) for dm_ready tracking
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

# -------- ENV / Names / IDs --------
OWNER_ID        = int(os.getenv("OWNER_ID", "0")) or None
SUPER_ADMIN_ID  = int(os.getenv("SUPER_ADMIN_ID", "0")) or None
RUBY_ID         = int(os.getenv("RUBY_ID", "0")) or None

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

# Welcome/portal text
WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing. 💋\n\n"
    "Tap a button to begin:"
)

# “Find our models elsewhere” (includes Ruby link explicitly)
MODELS_LINKS_TEXT = os.getenv(
    "MODELS_LINKS_TEXT",
    "🔥 <b>Find Our Models Elsewhere</b> 🔥\n\n"
    f"👑 <b>{RONI_NAME} (Owner)</b>\n"
    "<a href='https://allmylinks.com/chaossub283'>https://allmylinks.com/chaossub283</a>\n\n"
    f"💎 <b>{RUBY_NAME} (Co-Owner)</b>\n"
    "<a href='https://allmylinks.com/rubyransoms'>https://allmylinks.com/rubyransoms</a>\n\n"
    "🍑 <b>Peachy Rin</b>\n"
    "<a href='https://allmylinks.com/peachybunsrin'>https://allmylinks.com/peachybunsrin</a>\n\n"
    "⚡ <b>Savage Savy</b>\n"
    "<a href='https://allmylinks.com/savannahxsavage'>https://allmylinks.com/savannahxsavage</a>"
)
MODELS_LINKS_PHOTO = os.getenv("MODELS_LINKS_PHOTO", None)

# -------- Keyboards --------
def _portal_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ]
    return InlineKeyboardMarkup(rows)

def _back_to_portal_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back to Start", callback_data="dmf_back_welcome")]])

def _contact_admins_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    # Roni (Owner) button
    if OWNER_ID:
        rows.append([InlineKeyboardButton(f"💌 Message {RONI_NAME}", url=f"tg://user?id={OWNER_ID}")])
    # Ruby button (same row if possible)
    if RUBY_ID:
        if rows:
            rows[-1].append(InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
        else:
            rows.append([InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}")])
    rows.append([InlineKeyboardButton("◀️ Back", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

# -------- Helpers --------
async def _notify_owner_dmready(client: Client, uid: int):
    """Ping owner only when a user becomes DM-ready for the first time."""
    if not OWNER_ID:
        return
    try:
        await client.send_message(
            OWNER_ID,
            f"✅ <b>DM-ready</b> — <a href='tg://user?id={uid}'>User {uid}</a> just opened the portal.",
            disable_web_page_preview=True,
        )
    except Exception:
        pass

async def _mark_dm_ready_once(client: Client, uid: int):
    """Set global DM-ready for user; notify owner only if newly set."""
    if not _store or not uid:
        return
    try:
        already = _store.is_dm_ready_global(uid)
        if not already:
            _store.set_dm_ready_global(uid, True, by_admin=False)
            await _notify_owner_dmready(client, uid)
    except Exception:
        # never block /start on store errors
        pass

def _is_admin(uid: Optional[int]) -> bool:
    if not uid:
        return False
    if uid in (OWNER_ID, SUPER_ADMIN_ID):
        return True
    try:
        if _store and (uid in _store.list_admins()):
            return True
    except Exception:
        pass
    return False

# -------- Handlers --------
def register(app: Client):

    # /start — show portal & mark DM-ready (one-time)
    @app.on_message(filters.private & filters.command("start"))
    async def start(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        await _mark_dm_ready_once(client, uid)
        await m.reply_text(
            WELCOME_TEXT,
            reply_markup=_portal_kb(),
            disable_web_page_preview=True
        )

    # Back to start (does NOT re-notify owner thanks to one-time logic)
    @app.on_callback_query(filters.regex(r"^dmf_back_welcome$"))
    async def on_back_welcome(client: Client, cq: CallbackQuery):
        await cq.answer()
        try:
            await cq.message.edit_text(
                WELCOME_TEXT,
                reply_markup=_portal_kb(),
                disable_web_page_preview=True
            )
        except Exception:
            await cq.message.reply_text(
                WELCOME_TEXT,
                reply_markup=_portal_kb(),
                disable_web_page_preview=True
            )

    # Menu → delegate to handlers.menu (model menus + back button there)
    @app.on_callback_query(filters.regex(r"^dmf_open_menu$"))
    async def on_open_menu(client: Client, cq: CallbackQuery):
        await cq.answer()
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            try:
                await cq.message.edit_text(
                    menu_tabs_text(),
                    reply_markup=menu_tabs_kb(),
                    disable_web_page_preview=True
                )
            except Exception:
                await cq.message.reply_text(
                    menu_tabs_text(),
                    reply_markup=menu_tabs_kb(),
                    disable_web_page_preview=True
                )
        except Exception:
            await cq.message.reply_text("Menu is unavailable right now.", reply_markup=_back_to_portal_kb())

    # Contact admins
    @app.on_callback_query(filters.regex(r"^dmf_open_direct$"))
    async def on_open_direct(client: Client, cq: CallbackQuery):
        await cq.answer()
        try:
            await cq.message.edit_text(
                "How would you like to reach us?",
                reply_markup=_contact_admins_kb(),
                disable_web_page_preview=True
            )
        except Exception:
            await cq.message.reply_text(
                "How would you like to reach us?",
                reply_markup=_contact_admins_kb(),
                disable_web_page_preview=True
            )

    # Find models elsewhere (links/photo)
    @app.on_callback_query(filters.regex(r"^dmf_models_links$"))
    async def on_models_links(client: Client, cq: CallbackQuery):
        await cq.answer()
        try:
            if MODELS_LINKS_PHOTO:
                await client.send_photo(
                    cq.from_user.id,
                    MODELS_LINKS_PHOTO,
                    caption=MODELS_LINKS_TEXT,
                    reply_markup=_back_to_portal_kb()
                )
            else:
                await cq.message.edit_text(
                    MODELS_LINKS_TEXT,
                    reply_markup=_back_to_portal_kb(),
                    disable_web_page_preview=False
                )
        except Exception:
            await cq.message.reply_text(
                MODELS_LINKS_TEXT,
                reply_markup=_back_to_portal_kb(),
                disable_web_page_preview=False
            )

    # Help — delegate to handlers.help_panel if available
    @app.on_callback_query(filters.regex(r"^dmf_show_help$"))
    async def on_show_help(client: Client, cq: CallbackQuery):
        await cq.answer()
        try:
            # If your help module exposes a helper to open root menu:
            from handlers.help_panel import _help_menu_kb  # type: ignore
            await cq.message.edit_text("❔ <b>Help Center</b>\nChoose a topic:", reply_markup=_help_menu_kb())
        except Exception:
            await cq.message.reply_text("Type /help to open the help menu.", reply_markup=_back_to_portal_kb())

    # /dmready — admins only: list all DM-ready users
    @app.on_message(filters.private & filters.command("dmready"))
    async def list_dm_ready(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _is_admin(uid):
            return await m.reply_text("Admins only.")
        if not _store:
            return await m.reply_text("❌ Store not available.")

        data = _store.list_dm_ready_global()
        if not data:
            return await m.reply_text("Nobody is DM-ready yet.")

        lines = []
        for s_uid, rec in sorted(data.items(), key=lambda kv: int(kv[0])):
            since_ts = rec.get("since", 0)
            since_str = time.strftime("%Y-%m-%d", time.localtime(since_ts)) if since_ts else "unknown"
            by_admin = " (set by admin)" if rec.get("by_admin") else ""
            lines.append(f"• <a href='tg://user?id={s_uid}'>User {s_uid}</a> — since {since_str}{by_admin}")

        await m.reply_text(
            "📋 <b>DM-ready users</b>\n\n" + "\n".join(lines),
            disable_web_page_preview=True
        )
