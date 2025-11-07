# handlers/menu.py
import os
import logging
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

# Mongo
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI")
# If your URI has no db in it, define one via env; default to your username/db name.
DB_NAME = os.getenv("MONGO_DB") or os.getenv("MONGO_DB_NAME") or "chaossunflowerbusiness321"

client = MongoClient(MONGO_URI) if MONGO_URI else None

if client is None:
    log.warning("MONGO_URI not set; handlers.menu will run without DB.")
    col_model_menus = None
else:
    db = client[DB_NAME]  # <- avoids "No default database defined"
    col_model_menus = db["model_menus"]
    # Create a partial unique index so null/absent keys won't conflict
    try:
        col_model_menus.create_index(
            [("key", 1)],
            name="uniq_model_key",
            unique=True,
            partialFilterExpression={"key": {"$type": "string"}}
        )
    except Exception as e:
        log.warning(f"Menu index create (possibly exists): {e}")


def register(app):
    # If you had handlers here previously, wire them in the same way.
    # Keeping a simple marker log so main.py wiring succeeds even if DB is absent.
    log.info("✅ handlers.menu registered (DB=%s, collection=%s)",
             DB_NAME if client else "DISABLED",
             "model_menus" if col_model_menus else "N/A_
