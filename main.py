# main.py
import os, logging, signal, asyncio
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
log = logging.getLogger("SuccuBot")

API_ID   = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN= os.getenv("BOT_TOKEN")

app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="."
)

def wire(import_path: str):
    try:
        mod = __import__(import_path, fromlist=["register"])
        mod.register(app)
        log.info(f"✅ Wired: {import_path}")
    except Exception as e:
        log.error(f"❌ Failed to wire {import_path}: {e}", exc_info=True)

async def main():
    # core first
    wire("dm_foolproof")
    wire("handlers.menu")
    wire("handlers.createmenu")
    wire("handlers.contact_admins")
    wire("handlers.help_panel")

    # req + tools
    wire("handlers.enforce_requirements")
    wire("handlers.req_handlers")
    wire("handlers.test_send")
    wire("handlers.dm_admin")          # /dmreadylist + /dmnow

    # scheduling / flyers
    wire("handlers.flyer")
    wire("handlers.flyer_scheduler")
    wire("handlers.schedulemsg")

    # moderation / misc
    wire("handlers.moderation")
    wire("handlers.warnings")
    wire("handlers.federation")
    wire("handlers.summon")
    wire("handlers.xp")
    wire("handlers.fun")
    wire("handlers.hi")
    wire("handlers.warmup")
    wire("handlers.health")
    wire("handlers.welcome")
    wire("handlers.bloop")
    wire("handlers.whoami")  # optional; ignore if not present

    log.info("🚀 SuccuBot starting…")
    await app.start()
    stop = asyncio.Future()

    def _stop(*_):
        if not stop.done():
            stop.set_result(True)

    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, _stop)

    await stop
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
