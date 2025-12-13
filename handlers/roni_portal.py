# handlers/roni_portal.py
import logging
import os

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from utils.menu_store import store

log = logging.getLogger(__name__)

BOT_USERNAME = (os.getenv("BOT_USERNAME") or "").lstrip("@")
RONI_OWNER_ID = 6964994611

def _age_key(user_id: int) -> str:
    return f"AGE_OK:{user_id}"

def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id == RONI_OWNER_ID:
        return True
    return bool(store.get_menu(_age_key(user_id)))

@Client.on_message(filters.command("portal") & filters.private)
async def portal_cmd(client: Client, message: Message):
    uid = message.from_user.id

    buttons = []

    if is_age_verified(uid):
        buttons.append(
            [InlineKeyboardButton("📅 Booking Options", callback_data="booking_menu")]
        )
    else:
        buttons.append(
            [InlineKeyboardButton("🔞 Age Verification Required", callback_data="age_verify")]
        )

    await message.reply_text(
        "✨ **Roni’s Portal** ✨\n\nChoose an option below:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
