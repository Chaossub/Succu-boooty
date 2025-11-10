# handlers/req_handlers.py
import logging, os, pkgutil, importlib
log = logging.getLogger(__name__)

DISABLED = {x.strip() for x in os.getenv("DISABLE_HANDLERS", "").split(",") if x.strip()}

def register_all(app):
    """
    Auto-load every module in handlers/ that defines register(app).
    Skips files that start with '_' and anything listed in DISABLE_HANDLERS.
    """
    import handlers  # package root

    for modinfo in pkgutil.iter_modules(handlers.__path__):
        name = modinfo.name
        if name.startswith("_") or name in DISABLED:
            continue

        try:
            module = importlib.import_module(f"handlers.{name}")
        except Exception as e:
            log.exception("Failed importing handlers.%s: %s", name, e)
            continue

        reg = getattr(module, "register", None)
        if callable(reg):
            try:
                reg(app)
                log.info("✅ registered handlers.%s", name)
            except Exception as e:
                log.exception("Error registering handlers.%s: %s", name, e)
        else:
            log.debug("handlers.%s has no register(app); skipped.", name)
