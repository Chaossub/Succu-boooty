# main.py
# Run Pyrogram + Uvicorn on ONE asyncio loop with graceful shutdown.

import os
import asyncio
import logging
import signal
from contextlib import suppress

from pyrogram import Client
from uvicorn import Config, Server

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")

# ----------------------------
# FastAPI app loader
# ----------------------------
def load_fastapi_app():
    candidates = [
        ("webserver", "app"),  # webserver.py -> app = FastAPI()
        ("server", "app"),
        ("api", "app"),
        ("web.api", "app"),
        ("web.app", "app"),
    ]
    for mod, attr in candidates:
        try:
            module = __import__(mod, fromlist=[attr])
            return getattr(module, attr)
        except Exception:
            continue
    return None

# ----------------------------
# Handler wiring
# ----------------------------
def wire_handlers(app_client: Client):
    """Import modules that call register(app_client)."""
    try:
        import dm_foolproof as dm_root
        dm_root.register(app_client)
        log.info("wired: dm_foolproof (root)")
    except Exception as e:
        log.exception("Failed to wire dm_foolproof: %s", e)

    for mod in [
        "handlers.dmnow",
        "handlers.enforce_requirements",
        "handlers.exemptions",
        "handlers.federation",
        "handlers.flyer",
        "handlers.flyer_scheduler",
        "handlers.fun",
        "handlers.help_cmd",
        "handlers.help_panel",
        "handlers.hi",
        "handlers.membership_watch",

        # NEW: menu save/edit backend first
        "handlers.menu_save_fix",

        # Existing menu viewer
        "handlers.menu",
        "handlers.moderation",
        "handlers.req_handlers",
        "handlers.schedulemsg",
        "handlers.summon",
        "handlers.warmup",
        "handlers.warnings",
        "handlers.welcome",
        "handlers.xp",
    ]:
        with suppress(Exception):
            m = __import__(mod, fromlist=["register"])
            if hasattr(m, "register"):
                m.register(app_client)
                log.info("wired: %s", mod)
    log.info("Handlers wired.")

# ----------------------------
# Build the Pyrogram client from env
# ----------------------------
def build_client() -> Client:
    return Client(
        "SuccuBot",
        api_id=int(os.getenv("API_ID", "0")),
        api_hash=os.getenv("API_HASH", ""),
        bot_token=os.getenv("BOT_TOKEN", ""),
        workdir=".",
        in_memory=True,
    )

# ----------------------------
# Uvicorn task (same loop)
# ----------------------------
async def run_uvicorn(app) -> Server:
    cfg = Config(
        app=app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        loop="asyncio",   # same loop as Pyrogram
        lifespan="on",
        log_level="info",
        timeout_keep_alive=10,
        proxy_headers=True,
    )
    server = Server(cfg)
    asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    log.info("Uvicorn started on 0.0.0.0:%s", cfg.port)
    return server

# ----------------------------
# Main async
# ----------------------------
async def amain():
    log.info("✅ Starting SuccuBot… (single event loop)")

    app = build_client()
    wire_handlers(app)

    await app.start()
    log.info("Pyrogram started")

    uvicorn_server = None
    fastapi_app = load_fastapi_app()
    if fastapi_app is not None:
        uvicorn_server = await run_uvicorn(fastapi_app)
    else:
        log.info("No FastAPI app found; skipping Uvicorn")

    stop_event = asyncio.Event()

    def _signal_handler(*_):
        log.info("Stop signal received. Shutting down…")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()

    if uvicorn_server is not None:
        uvicorn_server.should_exit = True
        await asyncio.sleep(0.1)
        log.info("Uvicorn stopped")

    await app.stop()
    log.info("Pyrogram stopped")

# ----------------------------
# Entrypoint
# ----------------------------
def main():
    try:
        asyncio.run(amain())
    except RuntimeError as e:
        if "attached to a different loop" in str(e):
            log.warning("Suppressed cross-loop RuntimeError during shutdown: %s", e)
        else:
            raise

if __name__ == "__main__":
    main()
