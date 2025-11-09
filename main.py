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
TIMEZONE  = os.getenv("TIMEZONE", "America/Los_Angeles")
TZ        = timezone(TIMEZONE)

# JSON persistence (optional helpers used by some handlers)
DATA_DIR = Path(os.getenv("DATA_DIR", "data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DATA_DIR", str(DATA_DIR))
os.environ.setdefault("WARM_CHATS_PATH", str(DATA_DIR / "warm_chats.json"))
os.environ.setdefault("DMREADY_JSON_PATH", str(DATA_DIR / "dm_ready.json"))

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
log = logging.getLogger("SuccuBot")

# ──────────────────────────────────────────────────────────────────────────────
# MongoDB (shared client)
# ──────────────────────────────────────────────────────────────────────────────
from pymongo import MongoClient
import builtins

MONGO_URL = os.getenv("MONGO_URL", "").strip()
MONGO_DB  = os.getenv("MONGO_DB", "succubot").strip()

mongo_client: Optional[MongoClient] = None
if MONGO_URL:
    try:
        mongo_client = MongoClient(MONGO_URL, connect=True, serverSelectionTimeoutMS=8000)
        # will raise if cannot connect in ~8s
        mongo_client.admin.command("ping")
        builtins.mongo_client = mongo_client
        log.info("🗄️  Mongo connected (DB=%s)", MONGO_DB)
    except Exception as e:
        log.error("❌ Mongo connection failed: %s", e)
        # continue starting; handlers that require mongo should handle None gracefully
else:
    log.warning("⚠️  MONGO_URL not set — handlers expecting Mongo must handle None.")

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
    in_memory=True,
    parse_mode="html",
)

# expose common things to handlers via app
setattr(app, "scheduler", None)  # will be set below
setattr(app, "tz", TZ)
setattr(app, "owner_id", OWNER_ID)
setattr(app, "mongo", mongo_client)
setattr(app, "mongo_db_name", MONGO_DB)

# ──────────────────────────────────────────────────────────────────────────────
# Scheduler (shared)
# ──────────────────────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone=TIMEZONE)
setattr(app, "scheduler", scheduler)

# ──────────────────────────────────────────────────────────────────────────────
# Handler loader
# ──────────────────────────────────────────────────────────────────────────────
def _wire_module(mod_path: str, reg_name: str = "register") -> bool:
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
        func(app)
        log.info("✅ Wired: %s", mod_path)
        return True
    except Exception as e:
        log.exception("❌ Failed wiring %s: %s", mod_path, e)
        return False


def wire_handlers() -> None:
    base_pkg = "handlers"
    loaded = set()

    # 1) Core UI first
    priority = [
        "handlers.welcome",
        "handlers.panels",
        "handlers.menu",
        "handlers.help_panel",
        "handlers.help_cmd",
    ]

    # 2) DM-ready flow
    priority += [
        "handlers.dm_ready",
        "handlers.dm_ready_admin",
        "handlers.dm_admin",
        "handlers.dm_portal",
        "handlers.dmnow",
        "handlers.dmready_watch",
        "handlers.dmready_cleanup",
    ]

    # 3) Warmup + schedulers
    priority += [
        "handlers.hi",
        "handlers.flyer_scheduler",
        "handlers.schedulemsg",     # ✅ fixed (was schedulesmsg)
    ]

    # 4) The rest
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
        "handlers.createmenu",
        "handlers.contact_admins",
        "handlers.bloop",
        "handlers.warmup",
    ]

    for dotted in priority:
        if _wire_module(dotted):
            loaded.add(dotted)

    # Auto-discover anything else in handlers/
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
    if not scheduler.running:
        scheduler.start()
        log.info("⏰ Scheduler started (%s)", TIMEZONE)

async def _main():
    async with app:
        await _startup()
        log.info("🚀 SuccuBot is up and running.")
        await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except (KeyboardInterrupt, SystemExit):
        log.info("👋 Shutting down…")
