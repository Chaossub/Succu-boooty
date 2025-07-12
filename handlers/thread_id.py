from pyrogram import Client, filters
from pyrogram.types import Message

def register(app: Client):
    @app.on_message(filters.command("threadid"))  # listen in any chat
    async def threadid_handler(client: Client, message: Message):
        # ID of this message
        msg_id = message.id
        # Thread ID if in a forum topic
        thread_id = getattr(message, "message_thread_id", None)
        # If replying, thread of original
        reply_thread = None
        if message.reply_to_message:
            reply_thread = getattr(message.reply_to_message, "message_thread_id", None)

        await message.reply_text(
            f"<b>chat_id:</b> <code>{message.chat.id}</code>\n"
            f"<b>msg_id:</b> <code>{msg_id}</code>\n"
            f"<b>thread_id:</b> <code>{thread_id}</code>\n"
            f"<b>reply_thread:</b> <code>{reply_thread}</code>",
            quote=True
        )
