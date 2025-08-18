# main.py — single-loop Pyrogram runner with robust logging & tracing
import os, sys, asyncio, logging, signal
from contextlib import suppress
from logging.handlers import RotatingFileHandler

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, ChatMemberUpdated

# ---------- Logging setup ----------
LOGLEVEL = os.getenv("LOGLEVEL", "INFO").upper()
PYROGRAM_DEBUG = os.getenv("PYROGRAM_DEBUG", "0") in ("1", "true", "True", "YES", "yes")

logger = logging.getLogger("SuccuBot")
logger.setLevel(LOGLEVEL)

_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

# console
_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(_fmt)
logger.addHandler(_ch)

# rotating file (optional but helpful on platforms that keep /logs)
os.makedirs("logs", exist_ok=True)
_fh = RotatingFileHandler("logs/bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
_fh.setFormatter(_fmt)
logger.addHandler(_fh)

# make pyrogram very chatty when you need it
if PYROGRAM_DEBUG:
    logging.getLogger("pyrogram").setLevel(logging.DEBUG)
    logging.getLogger("pyrogram.session").setLevel(logging.DEBUG)
    logging.getLogger("pyrogram.connection").setLevel(logging.DEBUG)

# ---------- Env ----------
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Who to DM when a handler explodes (optional)
OWNER_ID = int(os.getenv("OWNER_ID", "0")) or None

# runtime switch for update tracing
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

def _bot_has_username(client: Client) -> bool:
    # Helps diagnose deep-link issues for DM buttons
    return bool(getattr(client, "_me", None) and getattr(client._me, "username", None))


def wire_handlers(app: Client):
    """Wire baseline handlers + your modules with exception visibility."""

    # ---- baseline safety handlers ----
    @app.on_message(filters.command("start") & filters.private)
    async def _fallback_start(_, m: Message):
        await m.reply_text(
            "🔥 Welcome to SuccuBot 🔥\n"
            "I’m alive. Try /ping or /diag.\n"
            "Use /traceon to trace every update (verbose).",
            disable_web_page_preview=True,
        )

    @app.on_message(filters.command("ping"))
    async def _ping(_, m: Message):
        await m.reply_text("pong ✅")

    # Toggle tracing live
    @app.on_message(filters.command("traceon"))
    async def trace_on(_, m: Message):
        global TRACE_UPDATES
        TRACE_UPDATES = True
        logger.warning("TRACE_UPDATES enabled by %s", m.from_user.id if m.from_user else "?")
        await m.reply_text("Tracing enabled. Check logs.")

    @app.on_message(filters.command("traceoff"))
    async def trace_off(_, m: Message):
        global TRACE_UPDATES
        TRACE_UPDATES = False
        logger.warning("TRACE_UPDATES disabled by %s", m.from_user.id if m.from_user else "?")
        await m.reply_text("Tracing disabled.")

    # Quick health dump
    @app.on_message(filters.command("diag"))
    async def diag(client: Client, m: Message):
        me = await client.get_me()
        await m.reply_text(
            "🤖 <b>Diag</b>\n"
            f"• Me: @{me.username} (<code>{me.id}</code>)\n"
            f"• Trace: {'ON' if TRACE_UPDATES else 'OFF'}\n"
            f"• Pyrogram debug: {'ON' if PYROGRAM_DEBUG else 'OFF'}\n"
            f"• Handlers wired: check logs\n",
            disable_web_page_preview=True,
        )

    # ---- global trace taps (lowest group so they run first) ----
    @app.on_message(filters.all, group=-1000)
    async def _trace_msg(_, m: Message):
        if TRACE_UPDATES:
            logger.info("MSG chat=%s from=%s text=%r", getattr(m.chat, "id", None),
                        getattr(m.from_user, "id", None), m.text or m.caption or "")

    @app.on_callback_query(group=-1000)
    async def _trace_cbq(_, cq: CallbackQuery):
        if TRACE_UPDATES:
            logger.info("CBQ from=%s data=%r in chat=%s msg_id=%s",
                        getattr(cq.from_user, "id", None), cq.data,
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

    # ---- import your modules, but log failures instead of dying ----
    modules = [
        "dm_foolproof",            # << root-level (your logs showed handlers.dm_foolproof missing)
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
    ]
    wired = 0
    for mod in modules:
        try:
            m = __import__(mod, fromlist=["register"])
            if hasattr(m, "register"):
                m.register(app)
                logger.info("wired: %s", mod)
                wired += 1
            else:
                logger.warning("module %s has no register()", mod)
        except Exception:
            logger.exception("Failed to wire %s", mod)
    logger.info("Handlers wired: %d module(s).", wired)

    # --- Force-welcome shim (runs late; ensures buttons appear even if other /start crashes)
    try:
        from dm_foolproof import _welcome_kb as _df_welcome_kb, _spicy_intro as _df_intro
    except Exception:
        _df_welcome_kb = None
        _df_intro = None

    @app.on_message(filters.private & filters.command("start"), group=998)
    async def _force_welcome(client: Client, m: Message):
        if _df_welcome_kb and _df_intro:
            try:
                name = (m.from_user.first_name if m.from_user else "there")
                await m.reply_text(_df_intro(name), reply_markup=_df_welcome_kb())
                return
            except Exception as e:
                logger.exception("dm_foolproof welcome failed: %s", e)
        # else: the normal fallback /start (group=999) will handle


# ---------- Asyncio lifecycle ----------
async def amain():
    logger.info("✅ Starting SuccuBot with enhanced logging")
    app = build_client()
    wire_handlers(app)

    # Global asyncio exception hook
    def _asyncio_ex_handler(loop, context):
        msg = context.get("message", "")
        exc = context.get("exception")
        if exc:
            logger.exception("UNHANDLED asyncio exception: %s", exc)
        else:
            logger.error("Asyncio error: %s | context=%r", msg, context)

    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_asyncio_ex_handler)

    await app.start()
    me = await app.get_me()
    app._me = me  # cache for deep-link sanity
    if not me.username:
        logger.warning("Bot has no @username. Deep-link DM buttons (e.g., /dmnow) will not work.")
    logger.info("Bot started as @%s (%s)", me.username, me.id)

    # Graceful stop on signals
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
