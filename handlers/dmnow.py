# handlers/dmnow.py
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))

def build_dm_button(bot_username: str) -> InlineKeyboardMarkup:
    deep_link = f"https://t.me/{bot_username}?start=dm"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💌 DM Now", url=deep_link)]]
    )

async def _is_group_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return (member.status in ("administrator", "owner", "creator")) or bool(getattr(member, "privileges", None))
    except Exception:
        return False

def register(app: Client):
    # /dmnow — posts ONLY the button (no extra text)
    @app.on_message(filters.command("dmnow"))
    async def dmnow(client: Client, message):
        chat = message.chat
        user_id = message.from_user.id if message.from_user else 0

        # In groups/supergroups: allow any admin
        if chat.type in ("group", "supergroup"):
            if not await _is_group_admin(client, chat.id, user_id):
                await message.reply_text("Admins only.")
                return
        else:
            # In private chats: restrict to OWNER_ID
            if user_id != OWNER_ID:
                await message.reply_text("Only the owner can run this here.")
                return

        me = await client.get_me()
        markup = build_dm_
