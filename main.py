# main.py — single process, Pyrogram-only run, safe handler wiring

import os
import asyncio
import logging
from contextlib import suppress
from importlib import import_module
from pyrogram import Client, idle

logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("SuccuBot")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    workers=20,
)

def wire_handlers(app_client: Client):
    # 1) Root-level dm_foolproof.py
    try:
        dm_root = import_module("dm_foolproof")
        if hasattr(dm_root, "register"):
            dm_root.register(app_client)
            log.info("wired: dm_foolproof (root)")
    except Exception as e:
        log.exception("Failed to wire dm_foolproof (root): %s", e)

    # 2) Everything else from handlers/ (requires handlers/__init__.py to exist)
    modules = [
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
        "handlers.menu",
        "handlers.moderation",
        "handlers.req_handlers",
        "handlers.schedulemsg",
        "handlers.summon",
        "handlers.warmup",
        "handlers.warnings",
        "handlers.welcome",
        "handlers.xp",
        # optional: "handlers.health"
    ]
    for mod in modules:
        with suppress(Exception):
            m = import_module(mod)
            if hasattr(m, "register"):
                m.register(app_client)
                log.info("wired: %s", mod)
    log.info("Handlers wired.")

async def _amain():
    log.info("✅ Starting SuccuBot…")
    wire_handlers(app)
    await app.start()
    log.info("Pyrogram started")
    await idle()
    await app.stop()
    log.info("Pyrogram stopped")

def main():
    asyncio.run(_amain())

if __name__ == "__main__":
    main()
