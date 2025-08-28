# dm_foolproof.py
# Single source of truth for /start:
# - Sends the main panel (once, with debounce)
# - Marks users DM-ready (persisted via utils.dmready_store)
# - Handles panel button callbacks locally so they always work

import os
import time
from typing import Dict, Tuple, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    User,
)
from pyrogram.enums import ChatType

# ---- storage for DM-ready (persisted) ----------------------------------------
# Ensure you have utils/dmready_store.py as we added earlier
try:
    from utils.dmready_store import DMReadyStore
except Exception:
    # very tiny in-memory fallback (won't persist) — only used if the real store is missing
    class DMReadyStore:
        def __init__(self): self._g=set()
        def set_dm_ready_global(self, uid:int): self._g.add(uid); return True
        def is_dm_ready_global(self, uid:int)->bool: return uid in self._g

_store = DMReadyStore()

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

# Text blocks
FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "All verified off-platform links for our models are collected here. Check pinned messages or official posts for updates.")
HELP_TEXT = os.getenv("HELP_TEXT", "Choose an option.")

WELCOME_TITLE = "🔥 <b>Welcome to SuccuBot</b> 🔥\nYour naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n✨ <i>Use the menu below to navigate!</i>"
MENUS_TITLE = "💕 <b>Menus</b>\nPick a model or contact the team."
ADMINS_TITLE = "👑 <b>Contact Admins</b>"
MODELS_TITLE = "✨ <b>Find Our Models Elsewhere</b> ✨"
HELP_TITLE = "❓ <b>Help</b>\nChoose an option."

# Fixed callback IDs (do not change without changing handlers below)
CB_OPEN_MENUS  = "open:menus"
CB_OPEN_ADMINS = "open:admins"
CB_OPEN_MODELS = "open:models"
CB_OPEN_HELP   = "open:help"
CB_BACK_MAIN   = "open:main"

# Debounce so the main panel doesn't post twice
_recent: Dict[Tuple[int,int], float] = {}
DEDUP_WINDOW = 12.0  # seconds

def _too_soon(chat_id: int, user_id: int) -> bool:
    now = time.time()
    key = (chat_id, user_id)
    last = _recent.get(key, 0.0)
    if now - last < DEDUP_WINDOW:
        return True
    _recent[key] = now
    # prune old entries
    for k, ts in list(_recent.items()):
        if now - ts > 5 * DEDUP_WINDOW:
            _recent.pop(k, None)
    return False

# ---- Keyboards ---------------------------------------------------------------

def main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💕 Menus", callback_data=CB_OPEN_MENUS)],
            [InlineKeyboardButton("👑 Contact Admins", callback_data=CB_OPEN_ADMINS)],
            [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data=CB_OPEN_MODELS)],
            [InlineKeyboardButton("❓ Help", callback_data=CB_OPEN_HELP)],
        ]
    )

def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)]])

# If you have a more detailed menus/admins panel elsewhere, you can
# replace these with calls to that code. For now we show compact, working panels.

def menus_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💘 Roni", callback_data="menus:roni"),
             InlineKeyboardButton("💘 Ruby", callback_data="menus:ruby")],
            [InlineKeyboardButton("💘 Rin",  callback_data="menus:rin"),
             InlineKeyboardButton("💘 Savy", callback_data="menus:savy")],
            [InlineKeyboardButton("💞 Contact Models", callback_data="menus:contact")],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_BACK_MAIN)],
        ]
    )

# ---- Helpers ----------------------------------------------------------------

async def _announce_dm_ready(client: Client, user: User):
    if not OWNER_ID:
        return
    try:
        handle = f"@{user.username}" if user.username else ""
        await client.send_message(OWNER_ID, f"✅ DM-ready — {user.first_name} {handle}")
    except Exception:
        pass

async def _mark_dm_ready(client: Client, m: Message):
    # Only relevant in private chat with a human
    if m.chat.type != ChatType.PRIVATE or (m.from_user and m.from_user.is_bot):
        return
    u = m.from_user
    # set persisted DM-ready
    first_time = False
    try:
        # naive: set returns True if we just added (your implementation may differ)
        first_time = _store.set_dm_ready_global(u.id)
    except Exception:
        # best effort
        pass

    # Announce to owner the very first time
    if first_time:
        await _announce_dm_ready(client, u)

# ---- /start handler ----------------------------------------------------------

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def on_start(client: Client, m: Message):
        # mark DM-ready first
        await _mark_dm_ready(client, m)

        # debounce duplicate panels
        if _too_soon(m.chat.id, m.from_user.id if m.from_user else 0):
            return

        # Send the main panel
        try:
            await m.reply_text(WELCOME_TITLE, reply_markup=main_kb(), disable_web_page_preview=True)
        except Exception:
            # fallback to send_message
            await client.send_message(m.chat.id, WELCOME_TITLE, reply_markup=main_kb(), disable_web_page_preview=True)

    # ---- Callbacks for the main panel (kept in this file so buttons always work)

    @app.on_callback_query(filters.regex(f"^{CB_BACK_MAIN}$"))
    async def cb_back_main(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(WELCOME_TITLE, reply_markup=main_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(WELCOME_TITLE, reply_markup=main_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(f"^{CB_OPEN_MENUS}$"))
    async def cb_open_menus(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(MENUS_TITLE, reply_markup=menus_panel_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(MENUS_TITLE, reply_markup=menus_panel_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(f"^{CB_OPEN_ADMINS}$"))
    async def cb_open_admins(client: Client, cq: CallbackQuery):
        text = f"{ADMINS_TITLE}\n\n• Use the group to tag an admin\n• Or send an anonymous message via the bot."
        try:
            await cq.message.edit_text(text, reply_markup=back_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(text, reply_markup=back_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(f"^{CB_OPEN_MODELS}$"))
    async def cb_open_models(client: Client, cq: CallbackQuery):
        text = f"{MODELS_TITLE}\n\n{FIND_MODELS_TEXT}"
        try:
            await cq.message.edit_text(text, reply_markup=back_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(text, reply_markup=back_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(f"^{CB_OPEN_HELP}$"))
    async def cb_open_help(client: Client, cq: CallbackQuery):
        text = f"{HELP_TITLE}\n\n{HELP_TEXT}"
        try:
            await cq.message.edit_text(text, reply_markup=back_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(text, reply_markup=back_kb(), disable_web_page_preview=True)
        await cq.answer()

    # ---- Optional: capture the model buttons here so the panel always responds

    @app.on_callback_query(filters.regex(r"^menus:(roni|ruby|rin|savy|contact)$"))
    async def cb_model_slots(client: Client, cq: CallbackQuery):
        slot = cq.data.split(":")[1]
        if slot == "contact":
            text = "💞 <b>Contact Models</b>\nPick who you’d like to message."
        else:
            # In your repo you save custom menus per model; show a placeholder if not found
            text = f"💘 <b>{slot.capitalize()}</b>\nMenu coming soon."
        try:
            await cq.message.edit_text(text, reply_markup=back_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(text, reply_markup=back_kb(), disable_web_page_preview=True)
        await cq.answer()
