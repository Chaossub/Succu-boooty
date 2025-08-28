# handlers/dmnow.py
# /dmnow → reply with a deep-link BUTTON to open a DM with this bot.
from __future__ import annotations
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ----- auth gate --------------------------------------------------------------
def _is_allowed(uid: int) -> bool:
    # Prefer your project's helper if present
    try:
        from utils.admin_check import is_admin_or_owner  # type: ignore
        return bool(is_admin_or_owner(uid))
    except Exception:
        pass
    owner = (os.getenv("OWNER_ID") or "").strip()
    supers = [s.strip() for s in (os.getenv("SUPER_ADMINS") or "").split(",") if s.strip()]
    return str(uid) == owner or str(uid) in supers

# Optional env overrides
BTN_DMNOW = os.getenv("BTN_DMNOW", "💌 DM Now")
BOT_USERNAME_ENV = os.getenv("BOT_USERNAME", "").strip()  # e.g., SuccuBot (no @)

def register(app: Client):

    @app.on_message(filters.command("dmnow"))
    async def dmnow_button(client: Client, m: Message):
        # Gate: only owner/superadmins/admins
        uid = m.from_user.id if m.from_user else 0
        if not _is_allowed(uid):
            return await m.reply_text("❌ You’re not allowed to use this command.")

        # Resolve bot username (env first, then API)
        if BOT_USERNAME_ENV:
            bot_username = BOT_USERNAME_ENV
        else:
            me = await client.get_me()
            bot_username = me.username or ""
        if not bot_username:
            return await m.reply_text("⚠️ Bot username is missing. Set one via @BotFather.")

        deep_link = f"https://t.me/{bot_username}?start=ready"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(BTN_DMNOW, url=deep_link)]])

        await m.reply_text(
            "Tap to open a private chat with the bot:",
            reply_markup=kb,
            disable_web_page_preview=True
        )
