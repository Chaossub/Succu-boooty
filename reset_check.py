# reset_check.py
import os, asyncio, logging
from pyrogram import Client

logging.basicConfig(level=logging.INFO)
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))  # your ID fallback

SESSION_NAME = "reset_check"

async def main():
    app = Client(
        SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,    # don't write a session file
        no_updates=True    # we only need to send a test message
    )

    await app.start()
    me = await app.get_me()
    logging.info(f"✅ Logged in as @{me.username} (ID {me.id})")
    await app.send_message(OWNER_ID, "✅ SuccuBot booted and can send messages. (reset_check.py)")
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
