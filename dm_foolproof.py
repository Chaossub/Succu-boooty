# dm_foolproof.py
# Private portal + DM-ready tracking and edit-in-place menus

import os, time, logging, contextlib
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_foolproof")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
# group where you want a public “DM-ready — Name” notice (optional)
ANNOUNCE_GROUP_ID = int(os.getenv("DMREADY_ANNOUNCE_GROUP_ID", "0") or "0")

# main panel strings
WELCOME_TITLE = "🔥 <b>Welcome to SuccuBot</b> 🔥"
WELCOME_BODY  = (
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

BTN_MENUS   = os.getenv("BTN_MENUS", "💕 Menus")
BTN_ADMINS  = os.getenv("BTN_ADMINS", "👑 Contact Admins")
BTN_FIND    = os.getenv("BTN_FIND",  "🔥 Find Our Models Elsewhere")
BTN_HELP    = os.getenv("BTN_HELP",  "❓ Help")

FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "✨ Find Our Models Elsewhere ✨\n\nAll verified off-platform links for our models are here.")

# de-dupe guard (same chat, same user, within window)
_last_start: dict[tuple[int, int], float] = {}
DEDUP_WINDOW = 1.2  # seconds

_store = DMReadyStore()  # persistent

def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(BTN_MENUS, callback_data="menu_open")],
            [InlineKeyboardButton(BTN_ADMINS, callback_data="contact_admins")],
            [InlineKeyboardButton(BTN_FIND, callback_data="find_elsewhere")],
            [InlineKeyboardButton(BTN_HELP, callback_data="help_panel")],
        ]
    )

def _kb_back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="open_main")]])

async def _send_or_edit_main(m: Message):
    text = f"{WELCOME_TITLE}\n{WELCOME_BODY}"
    try:
        # try to edit the message we're replying to (prevents duplicates)
        if m.reply_to_message and m.reply_to_message.from_user and m.reply_to_message.from_user.is_bot:
            await m.reply_to_message.edit_text(text, reply_markup=_kb_main(), disable_web_page_preview=True)
            return
    except Exception:
        pass
    await m.reply_text(text, reply_markup=_kb_main(), disable_web_page_preview=True, parse_mode=ParseMode.HTML)

async def _announce_dm_ready_once(client: Client, user: Optional["User"]):
    if not user:
        return
    # persist; only True if new
    created = _store.set_dm_ready_global(user.id, user.username, user.first_name)
    if created and OWNER_ID and _store.should_notify_owner(user.id):
        try:
            uname = f"@{user.username}" if user.username else "(no username)"
            await client.send_message(OWNER_ID, f"✅ DM-ready — <b>{user.first_name}</b> {uname}", parse_mode=ParseMode.HTML)
        except Exception:
            pass
        # optional public announce
        if ANNOUNCE_GROUP_ID:
            with contextlib.suppress(Exception):
                uname = f"@{user.username}" if user.username else ""
                await client.send_message(ANNOUNCE_GROUP_ID, f"✅ DM-ready — {user.first_name} {uname}")

def register(app: Client):

    # /start in private
    @app.on_message(filters.private & filters.command("start"))
    async def start_portal(client: Client, m: Message):
        # hard de-dupe
        k = (m.chat.id, m.from_user.id if m.from_user else 0)
        now = time.time()
        if now - _last_start.get(k, 0) < DEDUP_WINDOW:
            return
        _last_start[k] = now

        # mark DM-ready & notify owner once
        await _announce_dm_ready_once(client, m.from_user)

        await _send_or_edit_main(m)

    # main menu open / back
    @app.on_callback_query(filters.regex(r"^(open_main|dmf_open_menu)$"))
    async def cb_open_main(client: Client, q):
        text = f"{WELCOME_TITLE}\n{WELCOME_BODY}"
        with contextlib.suppress(Exception):
            await q.message.edit_text(text, reply_markup=_kb_main(), disable_web_page_preview=True, parse_mode=ParseMode.HTML)
        with contextlib.suppress(Exception):
            await q.answer()

    # “Find our models elsewhere”
    @app.on_callback_query(filters.regex("^find_elsewhere$"))
    async def cb_find_elsewhere(client: Client, q):
        with contextlib.suppress(Exception):
            await q.message.edit_text(FIND_MODELS_TEXT, reply_markup=_kb_back_to_main(), disable_web_page_preview=True)
        with contextlib.suppress(Exception):
            await q.answer()
