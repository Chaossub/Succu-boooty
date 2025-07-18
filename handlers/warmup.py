import os
from pyrogram import filters
from pyrogram.types import Message

def resolve_group_name(group):
    if group.startswith('-') or group.startswith('@'):
        return group
    val = os.environ.get(group)
    if val:
        return val.split(",")[0].strip()
    return group

def register(app):
    @app.on_message(filters.command("warmup") & filters.user(6964994611))  # Only owner can use
    async def warmup_handler(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /warmup <group_id | @username | GROUP_ALIAS>")
            return

        group = resolve_group_name(args[1].strip())
        try:
            chat = await client.get_chat(group)
            await message.reply(f"✅ Warmed up <b>{chat.title or group}</b> (<code>{chat.id}</code>)!\n"
                               f"Bot can now post scheduled flyers here.")
        except Exception as e:
            await message.reply(f"❌ Failed to warm up <code>{group}</code>: <code>{e}</code>")
