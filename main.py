# main.py — runs Pyrogram in the main thread (app.run()) and FastAPI in a background thread.
# Also wires a highest-priority (/start) failsafe that replies in DMs.

import logging
import os
import importlib
import pkgutil
import threading

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("SuccuBot")

API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

OWNER_ID  = int(os.getenv("OWNER_ID", "0"))

# --- Pyrogram client ---
app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    # DO NOT use in_memory=True here; keep a normal session so Pyrogram can idle properly.
)

# --- Small helpers for the welcome UI ---
def _welcome_text(_: str | None) -> str:
    return (
        "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
        "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
        "😈 If you ever need to know exactly what I can do, just press the Help button and I’ll spill all my secrets… 💋"
    )

def _welcome_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ])

# --- Highest priority /start (DM only) ---
def _wire_failsafe_start():
    @app.on_message(filters.command("start"), group=-1)
    async def _failsafe_start(client: Client, m: Message):
        # Reply ONLY in private chats
        if getattr(m.chat, "type", "") != "private":
            return
        try:
            await m.reply_text(
                _welcome_text(m.from_user.first_name if m.from_user else None),
                reply_markup=_welcome_kb(),
                disable_web_page_preview=True,
            )
        except Exception as e:
            if OWNER_ID:
                try:
                    await client.send_message(OWNER_ID, f"❌ /start error: <code>{e}</code>")
                except Exception:
                    pass

# --- Root DM module (your dm_foolproof.py in project root) ---
def _wire_root_dm():
    try:
        from dm_foolproof import register as register_dm
        register_dm(app)
        log.info("wired: dm_foolproof (root)")
    except Exception as e:
        log.exception("Failed wiring dm_foolproof: %s", e)

# --- Handlers package (e.g., handlers/dmnow.py, etc.) ---
def _wire_handlers_pkg():
    try:
        import handlers
    except Exception as e:
        log.warning("No handlers package: %s", e)
        return
    for modinfo in pkgutil.iter_modules(handlers.__path__, handlers.__name__ + "."):
        name = modinfo.name
        try:
            mod = importlib.import_module(name)
            if hasattr(mod, "register"):
                mod.register(app)
                log.info("wired: %s", name)
        except Exception as e:
            log.exception("Failed import: %s (%s)", name, e)

# --- FastAPI (health/Render ping) in a background thread ---
api = FastAPI()

@api.get("/")
async def root():
    return {"ok": True, "bot": "SuccuBot"}

def _run_web():
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(api, host="0.0.0.0", port=port, log_level="info")

def main():
    log.info("✅ Starting SuccuBot… (Pyrogram)")
    _wire_failsafe_start()
    _wire_root_dm()
    _wire_handlers_pkg()

    # Start web server in the background
    threading.Thread(target=_run_web, daemon=True).start()

    # BLOCK here so Pyrogram keeps its dispatcher/handlers alive
    app.run()

if __name__ == "__main__":
    main()
