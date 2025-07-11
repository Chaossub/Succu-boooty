# handlers/debug_thread.py

from pyrogram import Client, filters
from pyrogram.types import Message

# Debug command to retrieve forum topic (thread) IDs
# Usage: in any forum topic, send "/test" to get its message_thread_id

def register(app: Client):
    @app.on_message(filters.command("test") & filters.group)
    async def test_thread(client: Client, message: Message):
        tid = message.message_thread_id
        if tid:
            await message.reply_text(
                f"▶️ Thread ID is: <code>{tid}</code>",
                parse_mode="html",
                disable_web_page_preview=True
            )
        else:
            await message.reply_text(
                "⚠️ No thread ID detected (not in a forum topic).",
                disable_web_page_preview=True
            )
