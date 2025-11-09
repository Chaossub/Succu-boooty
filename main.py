# main.py
from __future__ import annotations

import asyncio
import importlib
import logging
import os
import pkgutil
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv
from pyrogram import Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ──────────────────────────────────────────────────────────────────────────────
# Env & paths
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()

API_ID    = int(os.getenv("API_ID", "0") or 0)
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

OWNER_ID  = int(os.getenv("OWNER_ID", "0") or 0)
TIMEZONE  = os.getenv("TIMEZONE", "America/Los_Angeles")  # default: LA
TZ        = timezone(TIMEZONE)

# Data dir for JSON persistence (warm chats, dm-ready cache, etc.)
DATA_DIR = Path(os.getenv("DATA_DIR", "data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Make these paths available to all handlers via env (no imports needed)
os.environ.setdefault("DATA_DIR", str(DATA_DIR))
os.environ.setdefault("WARM_CHATS_PATH", str(DATA_DIR / "warm_chats.json"))
os.environ.setdefault("DMREADY_JSON_PATH", str(DATA_DIR / "dm_ready.json"))

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")

# ──────────────────────────────────────────────────────────────────────────────
# Pyrogram client
# ──────────────────────────────────────────────────────────────────────────────
if not (API_ID and API_HASH and BOT_TOKEN):
    log.error("Missing API_ID/API_HASH/BOT_TOKEN in environment.")
    raise SystemExit(1)

app = Client(
    name="succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,  # no local session file
    parse_mode="html",
)

# ──────────────────────────────────────────────────────────────────────────────
# Scheduler (shared)
# ──────────────────────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# Expose to handlers (they can pick it up via getattr(client, 'scheduler', …))
setattr(app, "scheduler", scheduler)
setattr(app, "tz", TZ)
setattr(app, "owner_id", OWNER_ID)

# ──────────────────────────────────────────────────────────────────────────────
# Handler loader
# ──────────────────────────────────────────────────────────────────────────────
def _wire_module(mod_path: str, reg_name: str = "register") -> bool:
    """
    Import a module by dotted path and call its `register(app)` if present.
    Returns True if successfully wired.
    """
    try:
        mod = importlib.import_module(mod_path)
    except Exception as e:
        log.error("❌ Import failed: %s (%s)", mod_path, e)
        return False

    func: Optional[Callable] = getattr(mod, reg_name, None)
    if not callable(func):
        log.warning("⚠️  No %s(app) in %s — skipped.", reg_name, mod_path)
        return False

    try:
        func(app)  # register all handlers inside this module
        log.info("✅ Wired: %s", mod_path)
        return True
    except Exception as e:
        log.exception("❌ Failed wiring %s: %s", mod_path, e)
        return False


def wire_handlers() -> None:
    """
    Wire essential modules in a controlled order, then auto-discover the rest
    under handlers/ (skipping ones we already loaded).
    """
    base_pkg = "handlers"
    loaded = set()

    # 1) Critical first (welcome/panels/menu so UI always renders)
    priority = [
        "handlers.welcome",
        "handlers.panels",
        "handlers.menu",
        "handlers.help_panel",
        "handlers.help_cmd",
    ]

    # 2) DM-Ready flow (admin & user)
    priority += [
        "handlers.dm_ready",         # /dmready, /dmreadylist
        "handlers.dm_ready_admin",   # admin-only views
        "handlers.dm_admin",         # if you use it
        "handlers.dm_portal",        # if you use it
        "handlers.dmnow",            # now helper
        "handlers.dmready_watch",    # background checks (optional)
        "handlers.dmready_cleanup",  # maintenance (optional)
    ]

    # 3) Warmup + schedulers (both, as requested)
    priority += [
        "handlers.hi",               # /hi warmup -> writes warm_chats.json
        "handlers.flyer_scheduler",  # your flyer auto-posts (daily themes)
        "handlers.schedulesmsg",     # your general scheduled messages
    ]

    # 4) Moderation / xp / fun / federation / membership / summons, etc.
    priority += [
        "handlers.moderation",
        "handlers.warnings",
        "handlers.xp",
        "handlers.fun",
        "handlers.membership_watch",
        "handlers.summon",
        "handlers.req_handlers",
        "handlers.health",
        "handlers.whoami",
        "handlers.menu_save_fix",
        "handlers.test_send",
        "handlers.enforce_requirements",
        "handlers.exemptions",
        "handlers.federation",
        "handlers.flyer",
    ]

    # Wire priority list
    for dotted in priority:
        if _wire_module(dotted):
            loaded.add(dotted)

    # 5) Auto-discover the rest of handlers/ and wire anything with register(app)
    pkg = importlib.import_module(base_pkg)
    pkg_path = Path(pkg.__file__).parent
    for m in pkgutil.iter_modules([str(pkg_path)]):
        dotted = f"{base_pkg}.{m.name}"
        if dotted in loaded:
            continue
        _wire_module(dotted)

# ──────────────────────────────────────────────────────────────────────────────
# Startup/Shutdown
# ──────────────────────────────────────────────────────────────────────────────
async def _startup():
    log.info("👑 OWNER_ID = %s", OWNER_ID or "unset")
    wire_handlers()

    # Start shared scheduler
    if not scheduler.running:
        scheduler.start()
        log.info("⏰ Scheduler started (%s)", TIMEZONE)

async def _main():
    async with app:
        await _startup()
        log.info("🚀 SuccuBot is up and running.")
        await asyncio.Event().wait()  # keep alive

if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except (KeyboardInterrupt, SystemExit):
        log.info("👋 Shutting down…")
