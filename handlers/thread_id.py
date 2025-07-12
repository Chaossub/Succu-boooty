from pyrogram import Client, filters
from pyrogram.types import Message


def register(app: Client):
    @app.on_message(filters.command("threadid") & filters.group)
    async def threadid_handler(client: Client, message: Message):
        # Direct thread ID of this message (if sent inside a forum topic)
        tid = getattr(message, "message_thread_id", None)
        # If user replied to another message, show its thread ID too
        reply_tid = None
        if message.reply_to_message:
            reply_tid = getattr(message.reply_to_message, "message_thread_id", None)
        
        await message.reply_text(
            f"<b>chat_id:</b> <code>{message.chat.id}</code>\n"
            f"<b>msg_id:</b> <code>{message.message_id}</code>\n"
            f"<b>thread_id:</b> <code>{tid}</code>\n"
            f"<b>reply_thread:</b> <code>{reply_tid}</code>",
            quote=True
        )
