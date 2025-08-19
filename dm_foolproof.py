# handlers/dm_foolproof.py
# /start portal + DM-ready flag + contact admins + links + help

import os, json, time
from typing import Optional, List
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

# --- ENV ---
OWNER_ID = int(os.getenv("OWNER_ID", "0")) or None
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0")) or None

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

RUBY_ID = int(os.getenv("RUBY_ID", "0")) or None

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

def _welcome_kb(is_admin: bool=False) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ]
    return InlineKeyboardMarkup(rows)

def _contact_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    if OWNER_ID:
        rows.append([InlineKeyboardButton(f"💌 Message {RONI_NAME}", url=f"tg://user?id={OWNER_ID}")])
    if RUBY_ID:
        rows[-1].append(InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}")) if rows else rows.append([InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}")])
    rows.append([InlineKeyboardButton("🙈 Send Anonymous Message to Admins", callback_data="dmf_anon_admins")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

def _back_welcome() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="dmf_back_welcome")]])

def _mark_dm_ready(uid: int):
    try:
        if _store and not _store.is_dm_ready_global(uid):
            _store.set_dm_ready_global(uid, True, by_admin=False)
    except Exception:
        pass

def register(app: Client):

    # /start
    @app.on_message(filters.private & filters.command("start"))
    async def start(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        _mark_dm_ready(uid)
        await m.reply_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)

    # Back to welcome
    @app.on_callback_query(filters.regex("^dmf_back_welcome$"))
    async def back_welcome(client: Client, cq: CallbackQuery):
        _mark_dm_ready(cq.from_user.id)
        try:
            await cq.message.edit_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Open Menu tabs (delegates to handlers.menu)
    @app.on_callback_query(filters.regex("^dmf_open_menu$"))
    async def open_menu(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            try:
                await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
            except Exception:
                await cq.message.reply_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("Menu is unavailable right now.")
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex("^dmf_open_direct$"))
    async def open_direct(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("How would you like to reach us?", reply_markup=_contact_kb())
        except Exception:
            await cq.message.reply_text("How would you like to reach us?", reply_markup=_contact_kb())
        await cq.answer()

    # Anonymous message entry (simple relay to owner)
    @app.on_callback_query(filters.regex("^dmf_anon_admins$"))
    async def anon_admins(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("You're anonymous. Type the message you want me to send to the admins.", reply_markup=_back_welcome())
        except Exception:
            await cq.message.reply_text("You're anonymous. Type the message you want me to send to the admins.", reply_markup=_back_welcome())
        await cq.answer()
        # flag in memory that next msg from this user is anon — reuse your existing anon flow if present

    # Links panel
    @app.on_callback_query(filters.regex("^dmf_models_links$"))
    async def models_links(client: Client, cq: CallbackQuery):
        try:
            if MODELS_LINKS_PHOTO:
                await client.send_photo(cq.from_user.id, MODELS_LINKS_PHOTO, caption=MODELS_LINKS_TEXT, reply_markup=_back_welcome())
            else:
                await cq.message.edit_text(MODELS_LINKS_TEXT, reply_markup=_back_welcome(), disable_web_page_preview=False)
        except Exception:
            await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=_back_welcome(), disable_web_page_preview=False)
        await cq.answer()

    # Help delegates to your help panel (submenus + back buttons)
    @app.on_callback_query(filters.regex("^dmf_show_help$"))
    async def show_help(client: Client, cq: CallbackQuery):
        try:
            from handlers.help_panel import show_help_root
            # call into your helper if it exposes a function; otherwise just send the command
            await show_help_root(client, cq.message, from_callback=True)
        except Exception:
            await cq.message.reply_text("Type /help to open the help menu.", reply_markup=_back_welcome())
        await cq.answer()
