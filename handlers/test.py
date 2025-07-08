# handlers/test.py

from pyrogram import Client, filters

def register(app: Client):
    @app.on_message(filters.command("ping"))
    async def ping_handler(client, message):
        await message.reply("🏓 Pong!")
