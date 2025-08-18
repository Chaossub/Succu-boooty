from pyrogram import Client, filters
from pyrogram.types import Message

def register(app: Client):
    @app.on_message(filters.private & filters.command("health"))
    async def health(client: Client, m: Message):
        me = await client.get_me()
        await m.reply_text(f"OK ✅ as @{me.username} (id={me.id})")

    @app.on_message(filters.private)
    async def any_dm(client: Client, m: Message):
        # proves we receive *any* DM at all
        try:
            txt = m.text or m.caption or "(non-text)"
        except Exception:
            txt = "(unknown)"
        print(f"[DM TRACE] from {m.from_user.id}: {txt}")
