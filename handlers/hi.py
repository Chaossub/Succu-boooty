from pyrogram import Client, filters
from pyrogram.types import Message

def register(app: Client):

    # Group warm-up: use this to touch a chat so schedulers can post there later.
    @app.on_message(filters.group & filters.command(["hi"]))
    async def warmup_hi(client: Client, m: Message):
        who = m.from_user.first_name if m.from_user else "there"
        await m.reply_text(
            "👋 Hey {who}! I’m online.\n"
            "• Use /reqhelp for requirement commands\n"
            "• Admins: /dmsetup to drop the DM button"
            .format(who=who)
        )

    # Simple health check. Allowed everywhere.
    @app.on_message(filters.command(["ping"]))
    async def ping(client: Client, m: Message):
        await m.reply_text("pong ✅")
