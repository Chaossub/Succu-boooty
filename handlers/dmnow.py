# handlers/dmnow.py
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))

def _build_dm_button(bot_username: str) -> InlineKeyboardMarkup:
    deep_link = f"https://t.me/{bot_username}?start=dm"
    return InlineKeyboardMarkup([[InlineKeyboardButton("💌 DM Now", url=deep_link)]])

async def _is_group_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "owner", "creator") or bool(getattr(member, "privileges", None))
    except Exception:
        return False

def register(app: Client):
    # /dmnow — posts ONLY the button (no extra text)
    @app.on_message(filters.command("dmnow"))
    async def dmnow(client: Client, message):
        chat = message.chat
        user = message.from_user

        # In groups/supergroups: allow any admin to run it
        if chat.type in ("group", "supergroup"):
            if not user or not await _is_group_admin(client, chat.id, user.id):
                await message.reply_text("Admins only.")
                return
        else:
            # In private chats: restrict to OWNER_ID
            if not user or user.id != OWNER_ID:
                await message.reply_text("Only the owner can run this here.")
                return

        me = await client.get_me()
        await client.send_message(
            chat_id=chat.id,
            text="",  # no caption, just the inline keyboard
            reply_markup=_build_dm_button(me.username),
            disable_web_page_preview=True,
        )
