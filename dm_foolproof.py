# dm_foolproof.py
import os, logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_foolproof")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "All verified off-platform links are in our pinned posts.")
BTN_MENUS = os.getenv("BTN_MENUS", "💕 Menus")
BTN_CONTACT_ADMINS = os.getenv("BTN_CONTACT_ADMINS", "👑 Contact Admins")
BTN_FIND_MODELS = os.getenv("BTN_FIND_MODELS", "🔥 Find Our Models Elsewhere")
BTN_HELP = os.getenv("BTN_HELP", "❓ Help")

WELCOME = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

_store = DMReadyStore()

def _main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_MENUS, callback_data="dmf_open_menu")],
        [InlineKeyboardButton(BTN_CONTACT_ADMINS, callback_data="contact_admins")],
        [InlineKeyboardButton(BTN_FIND_MODELS, callback_data="find_models_elsewhere")],
        [InlineKeyboardButton(BTN_HELP, callback_data="help_panel")],
    ])

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def on_start(client: Client, m: Message):
        u = m.from_user
        if not u or u.is_bot:
            return

        is_new = _store.set_dm_ready_global(u.id, u.username, u.first_name)
        if is_new and OWNER_ID:
            try:
                mention = f"<a href='tg://user?id={u.id}'>{u.first_name or 'User'}</a>"
                handle = f" @{u.username}" if u.username else ""
                await client.send_message(OWNER_ID, f"✅ DM-ready — {mention}{handle}")
            except Exception:
                pass
            log.info("DM-ready NEW user %s (%s)", u.id, u.first_name or "")

        await client.send_message(m.chat.id, WELCOME, reply_markup=_main_menu_kb())

    # “Find models elsewhere” card lives here so it always works
    @app.on_callback_query(filters.regex("^find_models_elsewhere$"))
    async def find_models_card(client, cq):
        await client.answer_callback_query(cq.id)
        await client.edit_message_text(
            cq.message.chat.id,
            cq.message.id,
            f"✨ <b>Find Our Models Elsewhere</b> ✨\n\n{FIND_MODELS_TEXT}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_back_main")]]),
        )

    @app.on_callback_query(filters.regex("^dmf_back_main$"))
    async def back_main(client, cq):
        await client.answer_callback_query(cq.id)
        await client.edit_message_text(cq.message.chat.id, cq.message.id, WELCOME, reply_markup=_main_menu_kb())
