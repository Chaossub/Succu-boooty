# handlers/dm_foolproof.py
# /start portal + DM-ready flag (one-time) + contact admins + links + help

import os
from typing import List, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

# Optional req_store for DM-ready persistence & listing
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

OWNER_ID       = int(os.getenv("OWNER_ID", "0")) or None
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0")) or None

# Model names & IDs (used in Contact buttons)
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME", "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

RONI_ID = int(os.getenv("RONI_ID", "0")) or None
RUBY_ID = int(os.getenv("RUBY_ID", "0")) or None
RIN_ID  = int(os.getenv("RIN_ID", "0")) or None
SAVY_ID = int(os.getenv("SAVY_ID", "0")) or None

MODELS_LINKS_TEXT = os.getenv(
    "MODELS_LINKS_TEXT",
    "🔥 <b>Find Our Models Elsewhere</b> 🔥\n\n"
    "👑 <b>Roni Jane (Owner)</b>\n"
    "<a href='https://allmylinks.com/chaossub283'>https://allmylinks.com/chaossub283</a>\n\n"
    "💎 <b>Ruby Ransom (Co-Owner)</b>\n"
    "<a href='https://allmylinks.com/rubyransoms'>https://allmylinks.com/rubyransoms</a>\n\n"
    "🍑 <b>Peachy Rin</b>\n"
    "<a href='https://allmylinks.com/peachybunsrin'>https://allmylinks.com/peachybunsrin</a>\n\n"
    "⚡ <b>Savage Savy</b>\n"
    "<a href='https://allmylinks.com/savannahxsavage'>https://allmylinks.com/savannahxsavage</a>"
)
MODELS_LINKS_PHOTO = os.getenv("MODELS_LINKS_PHOTO")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing. 💋\n\n"
    "Tap a button to begin:"
)

# -------- Keyboards --------
def _portal_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ]
    return InlineKeyboardMarkup(rows)

def _contact_admins_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    # Always include Roni (OWNER) if present
    if OWNER_ID:
        rows.append([InlineKeyboardButton(f"💌 Message {RONI_NAME}", url=f"tg://user?id={OWNER_ID}")])
    # Add Ruby if present (same row if owner exists)
    if RUBY_ID:
        if rows:
            rows[-1].append(InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
        else:
            rows.append([InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}")])
    rows.append([InlineKeyboardButton("🙈 Anonymous message to admins", callback_data="dmf_anon_admins")])
    rows.append([InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

def _back_to_start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_back_welcome")]])

# -------- DM-ready helpers --------
async def _ensure_dm_ready_once(client: Client, user_id: int, user_name: str):
    """Mark DM-ready only once; notify OWNER once."""
    if not _store:
        return
    if not _store.is_dm_ready_global(user_id):
        _store.set_dm_ready_global(user_id, True, by_admin=False)
        # Ping owner once when a new user becomes DM-ready
        if OWNER_ID:
            try:
                mention = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
                await client.send_message(
                    OWNER_ID,
                    f"✅ <b>DM-ready:</b> {mention}"
                )
            except Exception:
                pass

# -------- Register handlers --------
def register(app: Client):

    # /start — show portal and mark dm-ready once
    @app.on_message(filters.private & filters.command("start"))
    async def start(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        uname = (m.from_user.first_name or "Someone") if m.from_user else "Someone"
        await _ensure_dm_ready_once(client, uid, uname)
        await m.reply_text(WELCOME_TEXT, reply_markup=_portal_kb(), disable_web_page_preview=True)

    # Back to start (no repeat DM-ready ping)
    @app.on_callback_query(filters.regex(r"^dmf_back_welcome$"))
    async def back_welcome(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(WELCOME_TEXT, reply_markup=_portal_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(WELCOME_TEXT, reply_markup=_portal_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Open Menu tabs (delegates to handlers.menu)
    @app.on_callback_query(filters.regex(r"^dmf_open_menu$"))
    async def open_menu(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            try:
                await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
            except Exception:
                await cq.message.reply_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("Menu is unavailable right now.", reply_markup=_back_to_start_kb())
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex(r"^dmf_open_direct$"))
    async def open_direct(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("How would you like to reach us?", reply_markup=_contact_admins_kb())
        except Exception:
            await cq.message.reply_text("How would you like to reach us?", reply_markup=_contact_admins_kb())
        await cq.answer()

    # Anonymous admin relay (UI entry; you can connect to your existing anon flow)
    @app.on_callback_query(filters.regex(r"^dmf_anon_admins$"))
    async def anon_admins(client: Client, cq: CallbackQuery):
        text = (
            "You're anonymous. Type the message you want me to send to the admins.\n\n"
            "• I’ll relay it without your name.\n"
            "• An admin can reply to you through me."
        )
        try:
            await cq.message.edit_text(text, reply_markup=_back_to_start_kb())
        except Exception:
            await cq.message.reply_text(text, reply_markup=_back_to_start_kb())
        await cq.answer()

    # Links panel
    @app.on_callback_query(filters.regex(r"^dmf_models_links$"))
    async def models_links(client: Client, cq: CallbackQuery):
        try:
            if MODELS_LINKS_PHOTO:
                await client.send_photo(cq.from_user.id, MODELS_LINKS_PHOTO, caption=MODELS_LINKS_TEXT, reply_markup=_back_to_start_kb())
            else:
                await cq.message.edit_text(MODELS_LINKS_TEXT, reply_markup=_back_to_start_kb(), disable_web_page_preview=False)
        except Exception:
            await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=_back_to_start_kb(), disable_web_page_preview=False)
        await cq.answer()

    # Help → delegate to handlers.help_panel (if present)
    @app.on_callback_query(filters.regex(r"^dmf_show_help$"))
    async def show_help(client: Client, cq: CallbackQuery):
        try:
            # help_panel exposes callbacks itself; just send entry
            from handlers.help_panel import _help_menu_kb  # type: ignore
            try:
                await cq.message.edit_text("❔ <b>Help Center</b>\nChoose a topic:", reply_markup=_help_menu_kb())
            except Exception:
                await cq.message.reply_text("❔ <b>Help Center</b>\nChoose a topic:", reply_markup=_help_menu_kb())
        except Exception:
            await cq.message.reply_text("Type /help to open the help menu.", reply_markup=_back_to_start_kb())
        await cq.answer()

    # --- Admin utility: list all DM-ready users (global) ---
    @app.on_message(filters.command("dmready_list"))
    async def dmready_list(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        # Only owners/super-admins
        if uid not in {OWNER_ID, SUPER_ADMIN_ID}:
            return
        if not _store:
            await m.reply_text("DM-ready store is unavailable.")
            return
        recs = _store.list_dm_ready_global()
        if not recs:
            await m.reply_text("No one is marked DM-ready yet.")
            return
        lines = []
        for s_uid, meta in sorted(recs.items(), key=lambda kv: int(kv[0])):
            u = int(s_uid)
            since = meta.get("since")
            by_admin = meta.get("by_admin")
            lines.append(f"• <a href='tg://user?id={u}'>User {u}</a> — since <code>{int(since)}</code>{' (by admin)' if by_admin else ''}")
        await m.reply_text("✅ <b>DM-ready users (global)</b>\n" + "\n".join(lines), disable_web_page_preview=True)
