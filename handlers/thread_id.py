from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import BadRequest

def register(app: Client):
    @app.on_message(filters.command("threadid"))
    async def threadid_handler(client: Client, message: Message):
        # Gather IDs
        chat_id = message.chat.id
        msg_id = message.id
        thread_id = getattr(message, "message_thread_id", None)
        reply_thread = None
        if message.reply_to_message:
            reply_thread = getattr(message.reply_to_message, "message_thread_id", None)

        text = (
            f"<b>chat_id:</b> <code>{chat_id}</code>\n"
            f"<b>msg_id:</b> <code>{msg_id}</code>\n"
            f"<b>thread_id:</b> <code>{thread_id}</code>\n"
            f"<b>reply_thread:</b> <code>{reply_thread}</code>"
        )

        # Try replying in the same thread/topic
        try:
            await message.reply_text(text, quote=True)
        except BadRequest as e:
            # If topic is closed or forbidden, fallback to main chat without quote
            if "TOPIC_CLOSED" in str(e) or "CHAT_WRITE_FORBIDDEN" in str(e):
                await client.send_message(chat_id, text)
            else:
                raise
