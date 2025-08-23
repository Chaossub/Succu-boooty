# main.py — Single-loop Pyrogram runner with clean wiring (dm_foolproof at repo root)

import os
import sys
import asyncio
import logging
import signal
from contextlib import suppress
from logging.handlers import RotatingFileHandler

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, ChatMemberUpdated

# ---------- Logging ----------
LOGLEVEL = os.getenv("LOGLEVEL", "INFO").upper()
PYROGRAM_DEBUG = os.getenv("PYROGRAM_DEBUG", "0") in ("1", "true", "True", "YES", "yes")

logger = logging.getLogger("SuccuBot")
logger.setLevel(LOGLEVEL)

fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(fmt)
logger.addHandler(ch)

os.makedirs("logs", exist_ok=True)
fh = RotatingFileHandler("logs/bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
fh.setFormatter(fmt)
logger.addHandler(fh)

if PYROGRAM_DEBUG:
    logging.getLogger("pyrogram").setLevel(logging.DEBUG)
    logging.getLogger("pyrogram.session").setLevel(logging.DEBUG)
    logging.getLogger("pyrogram.connection").setLevel(logging.DEBUG)

# ---------- Env ----------
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

TRACE_UPDATES = os.getenv("TRACE_UPDATES", "0") in ("1", "true", "True", "YES", "yes")

def build_client() -> Client:
    if not (API_ID and API_HASH and BOT_TOKEN):
        raise RuntimeError("Missing API_ID/API_HASH/BOT_TOKEN envs")
    return Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        workdir=".",
        in_memory=True,
    )

def wire_handlers(app: Client):
    """Import our modules and wire their register() if present.
       NOTE: dm_foolproof is a root module, not under handlers/."""
    # --- baseline utilities (no /start here to avoid duplicate portals) ---
    @app.on_message(filters.command("ping"))
    async def _ping(_, m: Message):
        await m.reply_text("pong ✅")

    @app.on_message(filters.command("traceon"))
    async def _trace_on(_, m: Message):
        global TRACE_UPDATES
        TRACE_UPDATES = True
        await m.reply_text("Tracing enabled.")

    @app.on_message(filters.command("traceoff"))
    async def _trace_off(_, m: Message):
        global TRACE_UPDATES
        TRACE_UPDATES = False
        await m.reply_text("Tracing disabled.")

    @app.on_message(filters.command("diag"))
    async def _diag(client: Client, m: Message):
        me = await client.get_me()
        await m.reply_text(
            "🤖 <b>Diag</b>\n"
            f"• Me: @{me.username} (<code>{me.id}</code>)\n"
            f"• Trace: {'ON' if TRACE_UPDATES else 'OFF'}\n"
            f"• Pyrogram debug: {'ON' if PYROGRAM_DEBUG else 'OFF'}\n",
            disable_web_page_preview=True,
        )

    # --- trace taps (lowest group so they run first) ---
    @app.on_message(filters.all, group=-1000)
    async def _trace_msg(_, m: Message):
        if TRACE_UPDATES:
            logger.info("MSG chat=%s from=%s text=%r",
                        getattr(m.chat, "id", None),
                        getattr(m.from_user, "id", None),
                        m.text or m.caption or "")

    @app.on_callback_query(group=-1000)
    async def _trace_cbq(_, cq: CallbackQuery):
        if TRACE_UPDATES:
            logger.info("CBQ from=%s data=%r in chat=%s msg_id=%s",
                        getattr(cq.from_user, "id", None),
                        cq.data,
                        getattr(getattr(cq.message, "chat", None), "id", None),
                        getattr(cq.message, "id", None))

    @app.on_chat_member_updated(group=-1000)
    async def _trace_cmu(_, ev: ChatMemberUpdated):
        if TRACE_UPDATES:
            logger.info("CHAT_MEMBER_UPDATE chat=%s user=%s status=%s -> %s",
                        getattr(ev.chat, "id", None),
                        getattr(getattr(ev.new_chat_member, "user", None), "id", None),
                        getattr(ev.old_chat_member, "status", None),
                        getattr(ev.new_chat_member, "status", None))

    # --- modules list (dm_foolproof sits at repo root) ---
    modules = [
        "dm_foolproof",                 # root file — portal & DM-ready
        # handlers below:
        "handlers.menu",
        "handlers.help_panel",
        "handlers.help_cmd",
        "handlers.req_handlers",
        "handlers.enforce_requirements",
        "handlers.exemptions",
        "handlers.membership_watch",
        "handlers.flyer",
        "handlers.flyer_scheduler",
        "handlers.schedulemsg",
        "handlers.warmup",
        "handlers.hi",
        "handlers.fun",
        "handlers.warnings",
        "handlers.moderation",
        "handlers.federation",
        "handlers.summon",
        "handlers.xp",
        "handlers.dmnow",
    ]

    wired = 0
    for name in modules:
        try:
            m = __import__(name, fromlist=["register"])
            if hasattr(m, "register"):
                m.register(app)
                logger.info("wired: %s", name)
                wired += 1
            else:
                logger.warning("Module %s has no register()", name)
        except ModuleNotFoundError as e:
            logger.warning("Module not found (skipped): %s (%s)", name, e)
        except Exception:
            logger.exception("Failed to wire %s", name)
    logger.info("Handlers wired: %d module(s).", wired)

async def amain():
    logger.info("✅ Starting SuccuBot with enhanced logging")
    app = build_client()
    wire_handlers(app)

    def _asyncio_err(loop, context):
        exc = context.get("exception")
        if exc:
            logger.exception("UNHANDLED asyncio exception: %s", exc)
        else:
            logger.error("Asyncio error: %r", context)

    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_asyncio_err)

    await app.start()
    me = await app.get_me()
    logger.info("Bot started as @%s (%s)", me.username, me.id)

    stop_event = asyncio.Event()
    def _signal(*_):
        logger.info("Stop signal received. Shutting down…")
        stop_event.set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _signal)

    await stop_event.wait()
    await app.stop()
    logger.info("Pyrogram stopped")

def main():
    try:
        asyncio.run(amain())
    except Exception:
        logger.exception("Fatal error in main()")
        raise

if __name__ == "__main__":
    main()
