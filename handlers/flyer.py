import os
from pymongo import MongoClient

# ─── ENVIRONMENT ───────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB  = os.environ.get("MONGO_DBNAME") or os.environ.get("MONGO_DB_NAME")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# ─── BASIC FLYER CRUD ──────────────────────────

def add_flyer(group_id, name, file_id, caption=""):
    db.flyers.update_one(
        {"group_id": int(group_id), "name": name},
        {"$set": {"file_id": file_id, "caption": caption}},
        upsert=True
    )

def get_flyer_by_name(group_id, flyer_name):
    """
    Return (file_id, caption) for flyer with name for a group_id.
    Returns None if not found.
    """
    doc = db.flyers.find_one({
        "group_id": int(group_id),
        "name": flyer_name
    })
    if doc:
        return doc["file_id"], doc.get("caption", "")
    return None

def delete_flyer(group_id, name):
    db.flyers.delete_one({"group_id": int(group_id), "name": name})

def list_flyers(group_id):
    flyers = db.flyers.find({"group_id": int(group_id)})
    return [doc["name"] for doc in flyers]

# ─── PYROGRAM HANDLER REGISTRATION (IF NEEDED) ───
def register(app):
    # Add all your flyer command handlers here if you want to register them in main.py
    pass

# ─── END OF FILE ───────────────────────────────
