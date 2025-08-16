from pyrogram import Client, filters
from pyrogram.types import Message

def register(app: Client):
    @app.on_message(filters.command(["start", "hi", "ping"]) & ~filters.scheduled)
    async def start_hi(client: Client, m: Message):
        if m.command[0].lower() == "ping":
            return await m.reply_text("pong ✅")
        who = m.from_user.first_name if m.from_user else "there"
        await m.reply_text(
            "👋 Hey {who}! I’m online.\n"
            "• Use /reqhelp for requirement commands\n"
            "• Admins: /dmsetup to drop the DM button"
            .format(who=who)
        )
