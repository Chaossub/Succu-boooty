import os
import asyncio
import logging
import contextlib
import importlib
import pkgutil
from dotenv import load_dotenv

from pyrogram import Client
from pyrogram.enums import ParseMode

# ================== ENV / LOG ==================
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

# ================== APP ==================
def build_app() -> Client:
    return Client(
        "SuccuBot",  # keep your original session name
        api_id=int(need("API_ID")),
        api_hash=need("API_HASH"),
        bot_token=need("BOT_TOKEN"),
        parse_mode=ParseMode.HTML,
        in_memory=True,
        workdir=".",
    )

# ================== HEALTH (optional) ==================
async def run_http_health():
    if os.getenv("USE_HTTP_HEALTH", "0") != "1":
        return
    port = int(os.getenv("PORT", "8000"))
    try:
        from fastapi import FastAPI
        import uvicorn
        app = FastAPI()

        @app.get("/health")
        def health():
            return {"ok": True}

        log.info("Starting FastAPI health server on :%d", port)
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()
    except Exception as e:
        log.warning("Health server unavailable: %s", e)

# ================== AUTO-WIRING ==================
def wire_handlers(app: Client) -> None:
    """
    Auto-import every module in the `handlers` package.
    - If a module has set_main_loop(loop), call it (for schedulers).
    - If a module has register(app), call it.
    Also tries to wire dm_foolproof (root-level module).
    """
    try:
        import handlers  # must be a package (handlers/__init__.py)
    except Exception as e:
        log.error("handlers package not found: %s", e)
        handlers = None

    loop = asyncio.get_event_loop()
    wired = 0

    if handlers:
        for _, module_name, _ in pkgutil.iter_modules(handlers.__path__, handlers.__name__ + "."):
            try:
                mod = importlib.import_module(module_name)

                # Optional: give scheduler modules their loop
                if hasattr(mod, "set_main_loop"):
                    try:
                        mod.set_main_loop(loop)
                        log.info("set_main_loop: %s", module_name)
                    except Exception as e:
                        log.error("set_main_loop failed for %s: %s", module_name, e)

                # Register commands/handlers
                if hasattr(mod, "register"):
                    mod.register(app)
                    log.info("wired: %s", module_name)
                    wired += 1
                else:
                    log.debug("skipped (no register): %s", module_name)
            except Exception as e:
                log.error("failed wiring %s: %s", module_name, e)

    # dm_foolproof lives at top level
    try:
        import dm_foolproof as dmf
        dmf.register(app)
        log.info("wired: dm_foolproof")
        wired += 1
    except Exception as e:
        log.warning("dm_foolproof not wired: %s", e)

    log.info("Total modules wired: %d", wired)

# ================== MAIN LOOP ==================
async def main():
    app = build_app()
    wire_handlers(app)

    log.info("✅ Starting SuccuBot…")
    await app.start()
    log.info("🤖 Bot is online.")

    # Optional health server
    health_task = asyncio.create_task(run_http_health())

    try:
        # Keep the process alive
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        log.info("🛑 Stopping SuccuBot…")
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
