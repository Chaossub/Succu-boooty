# handlers/menu.py
import logging
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
log = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.get_database()
col_model_menus = db["model_menus"]

# --- Fixed index creation ---
try:
    col_model_menus.create_index(
        [("key", 1)],
        name="uniq_model_key",
        unique=True,
        partialFilterExpression={"key": {"$type": "string"}}  # ignore nulls
    )
except Exception as e:
    log.warning(f"Menu index already exists or failed: {e}")

# Continue with your existing logic
def register(app):
    log.info("✅ handlers.menu registered")
    # (add your existing handler wiring here if it had any)
