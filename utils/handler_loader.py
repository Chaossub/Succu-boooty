# utils/handler_loader.py
"""
Robust handler auto-loader to stop the "one fix breaks another" loop.

Usage (in main.py, after you create `app`):
    from utils.handler_loader import register_all_handlers
    register_all_handlers(app)

This will import handlers and call their `register(app)` if present.
It logs import/register failures instead of silently skipping them.
"""
import importlib
import logging

log = logging.getLogger(__name__)

# Add/keep all your handler modules here.
HANDLERS = [
    "handlers.dmnow",
    "handlers.portal_cmd",
    "handlers.dm_portal",
    "handlers.roni_portal",
    "handlers.roni_portal_age",
    "handlers.nsfw_availability",
    "handlers.nsfw_text_session_booking",
    "handlers.requirements_panel",
    # Add other modules your bot uses:
    # "handlers.flyers",
    # "handlers.schedulemsg",
    # ...
]

def register_all_handlers(app) -> None:
    ok = 0
    failed = 0
    for mod_name in HANDLERS:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            failed += 1
            log.exception("❌ Failed to import %s", mod_name)
            continue

        reg = getattr(mod, "register", None)
        if callable(reg):
            try:
                reg(app)
                ok += 1
                log.info("✅ Registered %s", mod_name)
            except Exception:
                failed += 1
                log.exception("❌ Failed to register %s", mod_name)
        else:
            log.warning("⚠️ %s has no register(app)", mod_name)

    log.info("📦 Handler load summary: ok=%s failed=%s", ok, failed)
