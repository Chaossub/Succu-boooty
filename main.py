# main.py — start the bot, wire a failsafe /start with highest priority,
# then load root dm_foolproof + the rest of handlers.
import logging, os, importlib, pkgutil
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("SuccuBot")

API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

OWNER_ID = int(os.getenv("OWNER_ID", "0"))
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RUBY_ID   = int(os.getenv("RUBY_ID", "0"))
RIN_NAME  = os.getenv("RIN_NAME",  "Rin")
RIN_ID    = int(os.getenv("RIN_ID",  "0"))
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")
SAVY_ID   = int(os.getenv("SAVY_ID", "0"))

app = Client("succubot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

def _welcome_text(first_name: str | None) -> str:
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

def _wire_failsafe_start():
    # Highest-priority /start. Replies even if other modules register /start.
    @app.on_message(filters.command("start"), group=-1)
    async def _failsafe_start(client: Client, m: Message):
        if not m.chat or m.chat.type != "private":
            # ignore /start in groups; DM-only welcome
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

def _wire_root_dm():
    # Your root DM module handles DM-ready flagging, help callbacks, etc.
    try:
        from dm_foolproof import register as register_dm
        register_dm(app)
        log.info("wired: dm_foolproof (root)")
    except Exception as e:
        log.exception("Failed wiring dm_foolproof: %s", e)

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

def main():
    _wire_failsafe_start()  # <- guarantees /start works
    _wire_root_dm()         # <- your DM logic (dm-ready, callbacks)
    _wire_handlers_pkg()    # <- /dmnow and others
    log.info("✅ Starting SuccuBot… (Pyrogram)")
    app.start()

    api = FastAPI()

    @api.get("/")
    async def root():
        return {"ok": True, "bot": "SuccuBot"}

    port = int(os.getenv("PORT", "8000"))
    try:
        uvicorn.run(api, host="0.0.0.0", port=port)
    finally:
        app.stop()

if __name__ == "__main__":
    main()
