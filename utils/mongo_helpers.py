# utils/mongo_helpers.py
# Unified Mongo connection helper

from __future__ import annotations
from typing import Optional, Tuple
from pymongo import MongoClient
import os

def get_mongo() -> Tuple[Optional[MongoClient], Optional["Database"]]:
    """
    Returns (client, db) or (None, None) if not configured or unavailable.
    Always compare db with None instead of using it in if-statements directly.
    """
    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
    dbname = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or os.getenv("DB_NAME")

    if not uri:
        return None, None

    client = None
    db = None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        if dbname:
            db = client[dbname]
        else:
            try:
                db = client.get_default_database()
            except Exception:
                db = None
    except Exception:
        client = None
        db = None

    return client, db
