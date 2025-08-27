# handlers/whoami.py
from pyrogram import Client, filters
from pyrogram.types import Message

def register(app: Client):

    @app.on_message(filters.command("whoami"))
    async def whoami_cmd(client: Client, m: Message):
        if not m.from_user:
            return
        text = (
            f"🙋‍♂️ <b>Your Info</b>\n\n"
            f"🆔 ID: <code>{m.from_user.id}</code>\n"
            f"👤 Name: {m.from_user.first_name}"
        )
        if m.from_user.username:
            text += f"\n🔗 Username: @{m.from_user.username}"
        await m.reply_text(text)
