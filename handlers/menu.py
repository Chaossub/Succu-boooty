# handlers/menu.py
import os
import logging
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

# Optional Mongo import
try:
    from pymongo import MongoClient
except Exception as e:
    MongoClient = None
    log.warning("pymongo not available: %s", e)

MONGO_URI = os.getenv("MONGO_URI")
# If your URI doesn't include a DB name, we pick one via env or default.
DB_NAME = os.getenv("MONGO_DB") or os.getenv("MONGO_DB_NAME") or "chaossunflowerbusiness321"

client = None
col_model_menus = None

if MONGO_URI and MongoClient:
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]  # avoids "No default database defined"
        col_model_menus = db["model_menus"]

        # Partial unique index so multiple null/missing keys don't collide
        try:
            col_model_menus.create_index(
                [("key", 1)],
                name="uniq_model_key",
                unique=True,
                partialFilterExpression={"key": {"$type": "string"}}
            )
        except Exception as idx_err:
            log.warning("Menu index create (possibly exists): %s", idx_err)

    except Exception as conn_err:
        log.error("Mongo connection failed: %s", conn_err)
else:
    if not MONGO_URI:
        log.warning("MONGO_URI not set; handlers.menu running without DB.")
    if not MongoClient:
        log.warning("pymongo not installed; handlers.menu running without DB support.")

def register(app):
    db_state = DB_NAME if col_model_menus is not None else "DISABLED"
    coll_state = "model_menus" if col_model_menus is not None else "N/A"
    log.info("✅ handlers.menu registered (DB=%s, collection=%s)", db_state, coll_state)
    # Wire menu-related handlers here when needed.
