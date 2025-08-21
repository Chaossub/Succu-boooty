# handlers/dm_foolproof.py
# Start portal + DM-ready flag + admin/contact/links/help with back buttons

import os
from typing import Optional, List
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ---- Optional ReqStore (used across your project) ----
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

# ---- ENV ----
OWNER_ID  = int(os.getenv("OWNER_ID", "0")) or None
SUPER_ID  = int(os.getenv("SUPER_ADMIN_ID", "0")) or None

RONI_ID   = int(os.getenv("RONI_ID", "0") or os.getenv("OWNER_ID", "0")) or None
RUBY_ID   = int(os.getenv("RUBY_ID", "0")) or None
RIN_ID    = int(os.getenv("RIN_ID", "0")) or None
SAVY_ID   = int(os.getenv("SAVY_ID", "0")) or None

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME", "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

# DM-ready notify options
DM_READY_NOTIFY_MODE = (os.getenv("DM_READY_NOTIFY_MODE", "owner") or "owner").lower()
# if MODE == "chat", send to this chat id (e.g., -4702726782). Otherwise send to OWNER_ID
DM_READY_NOTIFY_CHAT = int(os.getenv("DM_READY_NOTIFY_CHAT", "0")) or None

MODELS_LINKS_TEXT = os.getenv(
    "MODELS_LINKS_TEXT",
    "🔥 <b>Find Our Models Elsewhere</b> 🔥\n\n"
    f"👑 <b>{RONI_NAME}</b>\n<a href='https://allmylinks.com/chaossub283'>https://allmylinks.com/chaossub283</a>\n\n"
    f"💎 <b>{RUBY_NAME}</b>\n<a href='https://allmylinks.com/rubyransoms'>https://allmylinks.com/rubyransoms</a>\n\n"
    f"🧁 <b>{RIN_NAME}</b>\n<a href='https://allmylinks.com/peachybunsrin'>https://allmylinks.com/peachybunsrin</a>\n\n"
    f"⚡ <b>{SAVY_NAME}</b>\n<a href='https://allmylinks.com/savannahxsavage'>https://allmylinks.com/savannahxsavage</a>"
)
MODELS_LINKS_PHOTO = os.getenv("MODELS_LINKS_PHOTO")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing. 💋\n\n"
    "Tap a button to begin:"
)

# ---------- Keyboards ----------

def _welcome_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ])

def _back_welcome_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_back_welcome")]])

def _contact_admins_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    # Direct DM buttons
    if RONI_ID:
        rows.append([InlineKeyboardButton(f"💌 Message {RONI_NAME}", url=f"tg://user?id={RONI_ID}")])
    if RUBY_ID:
        if rows:
            rows[-1].append(InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
        else:
            rows.append([InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}")])
    # Anonymous relay trigger (you can wire the receiver in another handler)
    rows.append([InlineKeyboardButton("🙈 Send Anonymous Message", callback_data="dmf_anon_admins")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

# ---------- DM-ready helpers ----------

async def _notify_dm_ready(client: Client, user_id: int, first_name: str, username: Optional[str]):
    # where to notify?
    target_chat = None
    if DM_READY_NOTIFY_MODE == "chat" and DM_READY_NOTIFY_CHAT:
        target_chat = DM_READY_NOTIFY_CHAT
    elif OWNER_ID:
        target_chat = OWNER_ID

    if not target_chat:
        return

    handle = f"@{username}" if username else f"<code>{user_id}</code>"
    text = f"✅ <b>DM-ready</b>: {first_name} ({handle})"
    try:
        await client.send_message(target_chat, text, disable_web_page_preview=True)
    except Exception:
        pass  # don’t break the flow if we can’t notify

def _mark_dm_ready(uid: int):
    try:
        if _store and not _store.is_dm_ready_global(uid):
            _store.set_dm_ready_global(uid, True, by_admin=False)
    except Exception:
        # fail silently — DM-ready flag is best-effort
        pass

# ---------- Handlers ----------

def register(app: Client):

    # /start: mark DM-ready, notify, show portal
    @app.on_message(filters.private & filters.command("start"))
    async def start(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        _mark_dm_ready(uid)
        await _notify_dm_ready(client, uid, m.from_user.first_name, m.from_user.username)
        await m.reply_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)

    # Back to welcome
    @app.on_callback_query(filters.regex("^dmf_back_welcome$"))
    async def back_welcome(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        _mark_dm_ready(uid)
        await _notify_dm_ready(client, uid, cq.from_user.first_name, cq.from_user.username)
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
            await cq.message.reply_text("Menu is unavailable right now.", reply_markup=_back_welcome_kb())
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex("^dmf_open_direct$"))
    async def open_direct(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("How would you like to reach us?", reply_markup=_contact_admins_kb())
        except Exception:
            await cq.message.reply_text("How would you like to reach us?", reply_markup=_contact_admins_kb())
        await cq.answer()

    # Anonymous message entry prompt (you can catch next message elsewhere)
    @app.on_callback_query(filters.regex("^dmf_anon_admins$"))
    async def anon_admins(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(
                "You’re anonymous. Type the message you want me to relay to the admins.",
                reply_markup=_back_welcome_kb()
            )
        except Exception:
            await cq.message.reply_text(
                "You’re anonymous. Type the message you want me to relay to the admins.",
                reply_markup=_back_welcome_kb()
            )
        await cq.answer()

    # Links panel
    @app.on_callback_query(filters.regex("^dmf_models_links$"))
    async def models_links(client: Client, cq: CallbackQuery):
        try:
            if MODELS_LINKS_PHOTO:
                await client.send_photo(cq.from_user.id, MODELS_LINKS_PHOTO, caption=MODELS_LINKS_TEXT, reply_markup=_back_welcome_kb())
            else:
                await cq.message.edit_text(MODELS_LINKS_TEXT, reply_markup=_back_welcome_kb(), disable_web_page_preview=False)
        except Exception:
            await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=_back_welcome_kb(), disable_web_page_preview=False)
        await cq.answer()

    # Help: open the help submenu implemented in handlers.help_panel
    @app.on_callback_query(filters.regex("^dmf_show_help$"))
    async def show_help(client: Client, cq: CallbackQuery):
        try:
            # Reuse the callback root the help module listens for
            await cq.message.edit_text("❔ <b>Help Center</b>\nChoose a topic:",
                                       reply_markup=InlineKeyboardMarkup([
                                           [InlineKeyboardButton("📖 Member Commands", callback_data="dmf_help_cmds")],
                                           [InlineKeyboardButton("✨ Buyer Requirements", callback_data="dmf_help_buyer_req")],
                                           [InlineKeyboardButton("‼️ Buyer Rules", callback_data="dmf_help_buyer_rules")],
                                           [InlineKeyboardButton("🎲 Game Rules", callback_data="dmf_help_game_rules")],
                                           [InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_back_welcome")],
                                       ]))
        except Exception:
            await cq.message.reply_text("Type /help to open the help menu.", reply_markup=_back_welcome_kb())
        await cq.answer()
