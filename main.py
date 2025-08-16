# main.py
import os, asyncio, logging, contextlib, importlib, pkgutil
from typing import Optional, List, Set
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
        name=os.getenv("SESSION_NAME", "SuccuBot"),
        api_id=int(need("API_ID")),
        api_hash=need("API_HASH"),
        bot_token=need("BOT_TOKEN"),
        parse_mode=ParseMode.HTML,
        in_memory=True,
        workdir=".",
    )

# ---------- optional FastAPI health ----------
async def run_http_health():
    if os.getenv("USE_HTTP_HEALTH", "1") != "1":
        return
    port = int(os.getenv("PORT", "8000"))
    try:
        from fastapi import FastAPI
        import uvicorn
        app = FastAPI()
        @app.get("/health")
        def health(): return {"ok": True}
        log.info("Starting FastAPI health server on :%d", port)
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()
    except Exception as e:
        log.warning("Health server unavailable: %s", e)

# ---------- wiring ----------
WIRED: Set[str] = set()
FOUND_NO_REGISTER: Set[str] = set()

def _priority_key(modname: str) -> tuple:
    # stable, sensible order (schedulers get loop early)
    prio = {
        "handlers.flyer_scheduler": 10,
        "handlers.schedulemsg": 10,
        "handlers.welcome": 20,
        "handlers.hi": 25,
        "handlers.help_cmd": 30,
        "handlers.req_handlers": 40,
        "handlers.enforce_requirements": 45,
        "handlers.moderation": 50,
        "handlers.federation": 55,
        "handlers.warnings": 60,
        "handlers.summon": 65,
        "handlers.fun": 70,
        "handlers.xp": 75,
        "handlers.flyer": 80,
        "handlers.menu": 85,
        "handlers.warmup": 90,
    }
    return (prio.get(modname, 100), modname)

def _wire_handlers_package(app: Client, package_name: str = "handlers") -> None:
    try:
        pkg = importlib.import_module(package_name)
    except ModuleNotFoundError:
        log.warning("Package '%s' not found. Skipping.", package_name)
        return

    loop = asyncio.get_event_loop()
    mods: List[str] = []
    for _, modname, _ in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        mods.append(modname)
    for modname in sorted(mods, key=_priority_key):
        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            log.exception("Failed import: %s (%s)", modname, e)
            continue

        # Pass the main loop first, if module exposes set_main_loop(loop)
        if hasattr(mod, "set_main_loop"):
            try:
                mod.set_main_loop(loop)
                log.info("set_main_loop: %s", modname)
            except Exception as e:
                log.exception("Error set_main_loop on %s: %s", modname, e)

        if hasattr(mod, "register") and callable(mod.register):
            try:
                mod.register(app)
                log.info("wired: %s", modname)
                WIRED.add(modname)
            except Exception as e:
                log.exception("Failed register: %s (%s)", modname, e)
        else:
            FOUND_NO_REGISTER.add(modname)

def _wire_dm_foolproof(app: Client) -> None:
    try:
        mod = importlib.import_module("dm_foolproof")
        if hasattr(mod, "register") and callable(mod.register):
            mod.register(app)
            log.info("wired: dm_foolproof")
        else:
            log.warning("dm_foolproof found but no register(app).")
    except ModuleNotFoundError:
        log.info("dm_foolproof not found (skipping).")
    except Exception as e:
        log.exception("failed wiring dm_foolproof: %s", e)

def wire_everything(app: Client) -> None:
    _wire_handlers_package(app, "handlers")
    _wire_dm_foolproof(app)

    # Summary (so you can verify every handler you expect is live)
    expected = {
        "handlers.enforce_requirements",
        "handlers.federation",
        "handlers.flyer",
        "handlers.flyer_scheduler",
        "handlers.fun",
        "handlers.help_cmd",
        "handlers.hi",
        "handlers.menu",
        "handlers.moderation",
        "handlers.req_handlers",
        "handlers.schedulemsg",
        "handlers.summon",
        "handlers.warmup",
        "handlers.warnings",
        "handlers.welcome",
        "handlers.xp",
    }
    missing = sorted(list(expected - WIRED))
    if missing:
        log.warning("Some expected modules were not wired (no register() or import error): %s", ", ".join(missing))
    else:
        log.info("All expected handlers wired successfully.")

# ---------- main ----------
async def main():
    app = build_app()
    wire_everything(app)

    log.info("✅ Starting SuccuBot…")
    await app.start()
    log.info("🤖 Bot is online.")

    health_task: Optional[asyncio.Task] = None
    if os.getenv("USE_HTTP_HEALTH", "1") == "1":
        health_task = asyncio.create_task(run_http_health())

    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
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
