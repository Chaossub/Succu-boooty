import os
import asyncio
import logging
import contextlib
from dotenv import load_dotenv

from pyrogram import Client
from pyrogram.enums import ParseMode

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")

def need(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

def build_app() -> Client:
    return Client(
        "succubus_sanctuary_bot",
        api_id=int(need("API_ID")),
        api_hash=need("API_HASH"),
        bot_token=need("BOT_TOKEN"),
        parse_mode=ParseMode.HTML,
        in_memory=True,
        workdir=".",
    )

def _try_wire(modpath: str, label: str, app: Client) -> None:
    try:
        mod = __import__(modpath, fromlist=["register"])
        mod.register(app)
        log.info("wired: %s", label)
    except Exception as e:
        log.error("failed wiring %s: %s", label, e)

def wire_handlers(app: Client) -> None:
    # Always-on basic ping
    _try_wire("handlers.hi", "hi", app)

    # Requirements tracker
    _try_wire("handlers.req_handlers", "requirements", app)

    # DM foolproof helpers
    try:
        import dm_foolproof as dmf
        dmf.register(app)
        log.info("wired: dm_foolproof")
    except Exception as e:
        log.error("failed wiring dm_foolproof: %s", e)

async def run_http_health():
    """Tiny HTTP health server; useful for hosts that expect a web port (Render/Railway)."""
    from wsgiref.simple_server import make_server, WSGIRequestHandler

    def app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"ok"]

    class Silent(WSGIRequestHandler):
        def log_message(self, *_args):  # quiet logs
            pass

    port = int(os.getenv("PORT", "8000"))
    for _ in range(3):
        try:
            httpd = make_server("0.0.0.0", port, app, handler_class=Silent)
            break
        except OSError:
            await asyncio.sleep(1)
    else:
        log.warning("health server not started (port busy?)")
        return

    log.info("HTTP health server on :%d", port)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, httpd.serve_forever)

async def main():
    app = build_app()
    wire_handlers(app)

    log.info("✅ Starting SuccuBot…")
    await app.start()
    log.info("🤖 Bot is online.")

    health_task = None
    if os.getenv("USE_HTTP_HEALTH", "1") == "1":
        health_task = asyncio.create_task(run_http_health())

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        log.info("🛑 Stopping SuccuBot…")
        if health_task:
            health_task.cancel()
            with contextlib.suppress(Exception):
                await health_task
        await app.stop()
        log.info("🧹 Clean shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        log.exception("❌ Fatal error during startup")
        raise
