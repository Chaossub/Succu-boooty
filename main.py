# main.py — Pyrogram runner with robust logging & root+handlers portal wiring

import os, sys, asyncio, logging, signal
from contextlib import suppress
from logging.handlers import RotatingFileHandler

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, ChatMemberUpdated

# ---------- Logging ----------
LOGLEVEL = os.getenv("LOGLEVEL", "INFO").upper()
PYROGRAM_DEBUG = os.getenv("PYROGRAM_DEBUG", "0") in ("1","true","True","YES","yes")

logger = logging.getLogger("SuccuBot")
logger.setLevel(LOGLEVEL)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

ch = logging.StreamHandler(sys.stdout); ch.setFormatter(_fmt); logger.addHandler(ch)
os.makedirs("logs", exist_ok=True)
fh = RotatingFileHandler("logs/bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
fh.setFormatter(_fmt); logger.addHandler(fh)

if PYROGRAM_DEBUG:
    logging.getLogger("pyrogram").setLevel(logging.DEBUG)
    logging.getLogger("pyrogram.session").setLevel(logging.DEBUG)
    logging.getLogger("pyrogram.connection").setLevel(logging.DEBUG)

# ---------- Env ----------
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

OWNER_ID = int(os.getenv("OWNER_ID", "0")) or None
TRACE_UPDATES = os.getenv("TRACE_UPDATES", "0") in ("1","true","True","YES","yes")

def build_client() -> Client:
    if not (API_ID and API_HASH and BOT_TOKEN):
        raise RuntimeError("Missing API_ID/API_HASH/BOT_TOKEN envs")
    return Client("SuccuBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workdir=".", in_memory=True)

# Expose a hook so /start can show the nice portal even if the handlers didn’t import yet
_portal_builder = None
def _try_import_root_portal():
    global _portal_builder
    try:
        # root module name is EXACTLY "foolproofdms.py"
        mod = __import__("foolproofdms")
        _portal_builder = getattr(mod, "portal_keyboard", None)
        if hasattr(mod, "register"):
            return mod
        return None
    except Exception as e:
        logger.warning("Module not found (skipped): foolproofdms (%s)", e)
        return None

def wire_handlers(app: Client):
    """Wire baseline handlers + your modules with exception visibility."""
    # ---- baseline / health ----
    @app.on_message(filters.command("start") & filters.private)
    async def _fallback_start(client: Client, m: Message):
        # If we have the portal keyboard builder, use it. Otherwise, fallback.
        kb = _portal_builder() if callable(_portal_builder) else None
        text = (
            "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
            "If you don’t see the portal, try again in a moment."
        )
        await m.reply_text(text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_message(filters.command("ping"))
    async def _ping(_, m: Message): await m.reply_text("pong ✅")

    @app.on_message(filters.command("traceon"))
    async def trace_on(_, m: Message):
        global TRACE_UPDATES; TRACE_UPDATES = True
        logger.warning("TRACE_UPDATES enabled by %s", getattr(m.from_user, "id", "?"))
        await m.reply_text("Tracing enabled.")

    @app.on_message(filters.command("traceoff"))
    async def trace_off(_, m: Message):
        global TRACE_UPDATES; TRACE_UPDATES = False
        logger.warning("TRACE_UPDATES disabled by %s", getattr(m.from_user, "id", "?"))
        await m.reply_text("Tracing disabled.")

    @app.on_message(filters.command("diag"))
    async def diag(client: Client, m: Message):
        me = await client.get_me()
        await m.reply_text(
            "🤖 <b>Diag</b>\n"
            f"• Me: @{me.username} (<code>{me.id}</code>)\n"
            f"• Trace: {'ON' if TRACE_UPDATES else 'OFF'}\n"
            f"• Pyrogram debug: {'ON' if PYROGRAM_DEBUG else 'OFF'}\n"
            f"• Handlers wired: see logs\n",
            disable_web_page_preview=True,
        )

    # ---- global trace taps ----
    @app.on_message(filters.all, group=-1000)
    async def _trace_msg(_, m: Message):
        if TRACE_UPDATES:
            logger.info("MSG chat=%s from=%s text=%r", getattr(m.chat, "id", None),
                        getattr(m.from_user, "id", None), m.text or m.caption or "")

    @app.on_callback_query(group=-1000)
    async def _trace_cbq(_, cq: CallbackQuery):
        if TRACE_UPDATES:
            logger.info("CBQ from=%s data=%r chat=%s msg=%s",
                        getattr(cq.from_user, "id", None), cq.data,
                        getattr(getattr(cq.message, "chat", None), "id", None),
                        getattr(cq.message, "id", None))

    @app.on_chat_member_updated(group=-1000)
    async def _trace_cmu(_, ev: ChatMemberUpdated):
        if TRACE_UPDATES:
            logger.info("CMU chat=%s user=%s %s->%s",
                        getattr(ev.chat, "id", None),
                        getattr(getattr(ev.new_chat_member, "user", None), "id", None),
                        getattr(ev.old_chat_member, "status", None),
                        getattr(ev.new_chat_member, "status", None))

    # ---- wire root portal (if present) ----
    mod = _try_import_root_portal()
    if mod:
        try:
            mod.register(app)             # root/foolproofdms.py
            logger.info("wired: foolproofdms (root)")
        except Exception:
            logger.exception("Failed to wire root portal")

    # ---- wire handlers modules ----
    modules = [
        "handlers.dm_foolproof",     # DM portal (Pyrogram)
        "handlers.menu",             # model menu tabs
        "handlers.help_panel",       # help submenu
        "handlers.help_cmd",         # /help text
        "handlers.req_handlers",     # /reqstatus etc.
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
                m.register(app); wired += 1; logger.info("wired: %s", name)
            else:
                logger.warning("module %s has no register()", name)
        except Exception:
            logger.exception("Failed to wire %s", name)
    logger.info("Handlers wired: %d module(s).", wired)

# ---------- lifecycle ----------
async def amain():
    logger.info("✅ Starting SuccuBot with enhanced logging")
    app = build_client()
    wire_handlers(app)

    # asyncio exception hook
    def _asyncio_ex_handler(loop, context):
        msg = context.get("message", "")
        exc = context.get("exception")
        if exc: logger.exception("UNHANDLED asyncio exception: %s", exc)
        else:   logger.error("Asyncio error: %s | context=%r", msg, context)

    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_asyncio_ex_handler)

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


