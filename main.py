# main.py
from __future__ import annotations
import os
import logging
from dotenv import load_dotenv
from pyrogram import Client, idle

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

log = logging.getLogger("SuccuBot")

# ── Owner / Supers ────────────────────────────────────────────────────────────
OWNER_ID_ENV = (os.getenv("OWNER_ID") or "").strip()
if not OWNER_ID_ENV:
    # Fallback to your ID if not set in env
    OWNER_ID_ENV = "6964994611"
os.environ["OWNER_ID"] = OWNER_ID_ENV
log.info("👑 OWNER_ID = %s", OWNER_ID_ENV)

# ── Pyrogram Client ───────────────────────────────────────────────────────────
API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("Missing API_ID / API_HASH / BOT_TOKEN env vars.")

app = Client(
    name=os.getenv("SESSION_NAME", "succubot"),
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=int(os.getenv("WORKERS", "8")),
    in_memory=True,  # no local session file needed on hosts like Railway/Render
)

# ── Safe wire helper ──────────────────────────────────────────────────────────
def wire(module_path: str):
    try:
        mod = __import__(module_path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)  # type: ignore
            log.info("✅ Wired: %s", module_path)
        else:
            log.warning("ℹ️ %s has no register()", module_path)
    except Exception as e:
        log.error("❌ Failed to wire %s: %s", module_path, e)

# ── Which modules to wire (ONLY one /start comes from handlers.dm_ready) ─────
MODULES = [
    # DM-ready flow (single /start + persistence + admin list)
    "handlers.dm_ready",
    "handlers.dmready_admin",

    # (optional) light panel/menu callbacks if you use them; they MUST NOT define /start
    # Comment out if you don't use these.
    "handlers.panels",
    "handlers.menu",

    # If you have the legacy callback shim that DOES NOT register /start, you can keep it:
    # "handlers.dm_portal",
]

if __name__ == "__main__":
    for m in MODULES:
        wire(m)
    log.info("🚀 SuccuBot starting…")
    app.start()
    idle()
    app.stop()
