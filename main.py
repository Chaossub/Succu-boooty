import logging
import asyncio
from pyrogram import Client

# Import your handlers
import handlers.health
import handlers.dmnow
import handlers.dm_foolproof

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("main")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=20,
    in_memory=True
)

def register_handlers(app: Client):
    handlers.health.register(app)
    handlers.dmnow.register(app)
    handlers.dm_foolproof.register(app)

async def main():
    register_handlers(app)
    await app.start()
    log.info("SuccuBot is running.")
    await idle()   # from pyrogram
    await app.stop()

if __name__ == "__main__":
    from pyrogram import idle
    asyncio.run(main())
