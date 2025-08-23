# dm_foolproof.py — Portal & DM-ready logic
import os
from typing import List
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

PROVIDES_START = True

OWNER_ID  = int(os.getenv("OWNER_ID", "0") or 0) or None
RUBY_ID   = int(os.getenv("RUBY_ID", "0") or 0) or None
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

ADMIN_ALERT_CHAT = int(os.getenv("ADMIN_ALERT_CHAT", str(OWNER_ID or 0)) or 0) or None

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing. 💋\n\n"
    "Tap a button to begin:"
)

_seen_ready = set()

def portal_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ]
    return InlineKeyboardMarkup(rows)

def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_home")]])

def _admins_kb() -> InlineKeyboardMarkup:
    rows = []
    if OWNER_ID:
        rows.append([InlineKeyboardButton(f"💌 Message {RONI_NAME}", url=f"tg://user?id={OWNER_ID}")])
    if RUBY_ID:
        if rows:
            rows[-1].append(InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
        else:
            rows.append([InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}")])
    rows.append([InlineKeyboardButton("🙈 Anonymous message to Admins", callback_data="dmf_anon_admins")])
    rows.append([InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_home")])
    return InlineKeyboardMarkup(rows)

async def _alert_ready(client: Client, uid: int, name: str):
    if ADMIN_ALERT_CHAT:
        await client.send_message(
            ADMIN_ALERT_CHAT,
            f"✅ <b>DM-ready:</b> {name} (<code>{uid}</code>)"
        )

def _mark_ready(uid: int) -> bool:
    already = False
    if _store:
        try:
            already = _store.is_dm_ready_global(uid)
            if not already:
                _store.set_dm_ready_global(uid, True, by_admin=False)
        except Exception:
            pass
    else:
        already = uid in _seen_ready
        if not already:
            _seen_ready.add(uid)
    return not already

def register(app: Client):
    @app.on_message(filters.private & filters.command("start"))
    async def start(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        first_time = _mark_ready(uid)
        if first_time:
            name = m.from_user.first_name if m.from_user else "Unknown"
            await _alert_ready(client, uid, name)
        await m.reply_text(WELCOME_TEXT, reply_markup=portal_keyboard(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^dmf_home$"))
    async def back_home(_, cq: CallbackQuery):
        await cq.message.edit_text(WELCOME_TEXT, reply_markup=portal_keyboard(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_open_menu$"))
    async def open_menu(_, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("Menu is unavailable.", reply_markup=_back_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_open_direct$"))
    async def open_direct(_, cq: CallbackQuery):
        await cq.message.edit_text("How would you like to reach the admins?", reply_markup=_admins_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_anon_admins$"))
    async def anon_admins(_, cq: CallbackQuery):
        await cq.message.edit_text("You're anonymous. Type your message for admins.", reply_markup=_back_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_models_links$"))
    async def models_links(_, cq: CallbackQuery):
        await cq.message.edit_text("🔥 Links to models coming soon!", reply_markup=_back_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_show_help$"))
    async def show_help(_, cq: CallbackQuery):
        try:
            from handlers.help_panel import _help_menu_kb
            await cq.message.edit_text("❔ <b>Help Center</b>\nChoose a topic:", reply_markup=_help_menu_kb())
        except Exception:
            await cq.message.reply_text("Type /help for commands.", reply_markup=_back_kb())
        await cq.answer()
