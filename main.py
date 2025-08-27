# main.py
import os
import logging
import inspect
from importlib import import_module
from typing import Optional, Callable

from dotenv import load_dotenv
from pyrogram import Client

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")

# ── Env ───────────────────────────────────────────────────────────────────────
load_dotenv()
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not (API_ID and API_HASH and BOT_TOKEN):
    log.warning("API_ID / API_HASH / BOT_TOKEN are not fully set in the environment")

# ── Pyrogram Client ───────────────────────────────────────────────────────────
app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=os.getcwd(),
    in_memory=True,
)

# ── Flexible module wiring ────────────────────────────────────────────────────
CANDIDATE_FUNCS = ("register", "setup", "bootstrap", "init", "wire", "attach")

def _call_initializer(fn: Callable, module_name: str) -> bool:
    """Call fn with (app) if it accepts one; else with no args."""
    try:
        sig = inspect.signature(fn)
        if len(sig.parameters) >= 1:
            fn(app)
        else:
            fn()
        log.info("wired: %s", module_name)
        return True
    except Exception as e:
        log.error("Failed to wire %s: %s", module_name, e, exc_info=True)
        return False

def wire(module_path: str, title: Optional[str] = None) -> None:
    """Import module and call one of the accepted initializer names."""
    display = title or module_path
    try:
        mod = import_module(module_path)
    except Exception as e:
        log.error("Failed to import %s: %s", display, e, exc_info=True)
        return

    # Try any of the common initializer names
    for name in CANDIDATE_FUNCS:
        fn = getattr(mod, name, None)
        if callable(fn):
            if _call_initializer(fn, display):
                return

    # If the module exposes a factory called get_handlers() returning callables,
    # attach each to the app (optional convenience).
    gh = getattr(mod, "get_handlers", None)
    if callable(gh):
        try:
            handlers = gh()
            attached = 0
            for h in handlers or []:
                # Each handler should already be a pyrogram Handler added inside get_handlers,
                # but in case they return callables, call them with app.
                if callable(h):
                    try:
                        sig = inspect.signature(h)
                        if len(sig.parameters) >= 1:
                            h(app)
                        else:
                            h()
                        attached += 1
                    except Exception:
                        pass
            if attached:
                log.info("wired: %s (via get_handlers, %d handlers)", display, attached)
                return
        except Exception as e:
            log.error("Failed to wire %s via get_handlers: %s", display, e, exc_info=True)
            return

    # Nothing matched
    log.error("Failed to wire %s: no register/setup/bootstrap/init/wire/attach found", display)

# ── Wire all handlers (order preserved) ───────────────────────────────────────
def wire_all_handlers() -> None:
    log.info("✅ Booting SuccuBot")

    # NOTE: dm_foolproof is at project root and may not have register(app),
    # so the flexible loader above will try setup()/init()/etc.
    wire("dm_foolproof", "dm_foolproof")

    wire("handlers.menu", "handlers.menu")
    wire("handlers.help_panel", "handlers.help_panel")
    wire("handlers.help_cmd", "handlers.help_cmd")
    wire("handlers.req_handlers", "handlers.req_handlers")

    wire("handlers.enforce_requirements", "handlers.enforce_requirements")
    wire("handlers.exemptions", "handlers.exemptions")
    wire("handlers.membership_watch", "handlers.membership_watch")

    wire("handlers.flyer", "handlers.flyer")
    wire("handlers.flyer_scheduler", "handlers.flyer_scheduler")

    wire("handlers.schedulemsg", "handlers.schedulemsg")

    wire("handlers.warmup", "handlers.warmup")
    wire("handlers.hi", "handlers.hi")
    wire("handlers.fun", "handlers.fun")
    wire("handlers.warnings", "handlers.warnings")
    wire("handlers.moderation", "handlers.moderation")
    wire("handlers.federation", "handlers.federation")
    wire("handlers.summon", "handlers.summon")
    wire("handlers.xp", "handlers.xp")
    wire("handlers.dmnow", "handlers.dmnow")

# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    wire_all_handlers()
    app.run()
