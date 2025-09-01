# dm_foolproof.py
import os, logging
from typing import Optional
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_foolproof")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

BTN_MENU   = os.getenv("BTN_MENU",  "💕 Menu")
BTN_ADMINS = os.getenv("BTN_ADMINS","👑 Contact Admins")
BTN_FIND   = os.getenv("BTN_FIND",  "🔥 Find Our Models Elsewhere")
BTN_HELP   = os.getenv("BTN_HELP",  "❓ Help")
BTN_BACK   = os.getenv("BTN_BACK",  "⬅️ Back to Main")

def _main_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(BTN_MENU,   callback_data="dmf_open_menu")],
        [InlineKeyboardButton(BTN_ADMINS, callback_data="contact_admins_open")],
        [InlineKeyboardButton(BTN_FIND,   callback_data="help_open_links")],
        [InlineKeyboardButton(BTN_HELP,   callback_data="help_open_main")],
    ]
    return InlineKeyboardMarkup(rows)

def _welcome_text() -> str:
    return (
        "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
        "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
        "✨ <i>Use the menu below to navigate!</i>"
    )

_store = DMReadyStore()

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def start_dm(client: Client, m: Message):
        u = m.from_user
        if not u:
            return

        # Mark DM-ready once (persists across restarts)
        first_time = _store.mark_ready_once(u.id, u.username, u.first_name)
        if first_time and OWNER_ID:
            try:
                uname = f"@{u.username}" if u.username else ""
                await client.send_message(
                    OWNER_ID,
                    f"✅ <b>DM-ready</b> — {u.first_name or 'User'} {uname}".strip()
                )
            except Exception as e:
                log.warning("Owner notify failed: %s", e)

        # Show main portal panel
        await m.reply_text(_welcome_text(), reply_markup=_main_kb(), disable_web_page_preview=True)

    # generic "Back to Main" for other panels
    @app.on_callback_query(filters.regex("^dmf_main$"))
    async def cb_main(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(_welcome_text(), reply_markup=_main_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(_welcome_text(), reply_markup=_main_kb(), disable_web_page_preview=True)
        await cq.answer()
