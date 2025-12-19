import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from pyrogram import Client, filters
from pyrogram.types import Message

log = logging.getLogger(__name__)

# Owner (defaults to your ID)
OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))

# Optional: legacy local JSON file (some setups used this)
DMREADY_JSON = os.getenv("DMREADY_JSON", "dm_ready.json")

# Mongo (Requirements panel collection)
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or os.getenv("MONGOURL") or ""
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "Succubot"
MEMBERS_COLL_NAME = os.getenv("REQ_MEMBERS_COLL", "requirements_members")

# How often to auto-sync (minutes)
AUTO_SYNC_MINUTES = int(os.getenv("DMREADY_AUTO_SYNC_MINUTES", "5"))


def _safe_json_load(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _get_members_coll():
    """
    Returns a pymongo Collection or None.
    Kept isolated so this file doesn't crash the bot if Mongo is down.
    """
    if not MONGO_URI:
        return None
    try:
        from pymongo import MongoClient  # local import (avoid hard dependency on startup failures)

        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
        )
        db = client[MONGO_DB]
        return db[MEMBERS_COLL_NAME]
    except Exception as e:
        log.warning("dmready_bridge: Mongo not available for requirements_members (%s)", e)
        return None


def _collect_dmready_user_ids() -> List[int]:
    """
    Collect DM-ready users from:
    1) handlers.dm_ready store (Mongo-backed DMReadyStore) if available
    2) req_store DM-ready (if used)
    3) legacy dm_ready.json (if present)
    """
    uids: set[int] = set()

    # 1) handlers.dm_ready store
    try:
        from handlers.dm_ready import store as dm_store  # type: ignore

        for item in dm_store.all():
            uid = int(item.get("user_id") or 0)
            if uid:
                uids.add(uid)
    except Exception:
        pass

    # 2) req_store (some older builds)
    try:
        from req_store import ReqStore  # type: ignore

        rs = ReqStore()
        uids.update(rs.get_dm_ready_global())
    except Exception:
        pass

    # 3) legacy local JSON
    legacy = _safe_json_load(DMREADY_JSON)
    raw_uids = legacy.get("dm_ready_users") or legacy.get("users") or []
    if isinstance(raw_uids, list):
        for x in raw_uids:
            try:
                uids.add(int(x))
            except Exception:
                continue
    elif isinstance(raw_uids, dict):
        for k, v in raw_uids.items():
            try:
                if v:
                    uids.add(int(k))
            except Exception:
                continue

    return sorted(uids)


async def _mirror_into_requirements_members(members_coll) -> int:
    """
    For every DM-ready user, set dm_ready=True in requirements_members.
    Returns number of updated docs.
    """
    if members_coll is None:
        return 0

    dm_uids = _collect_dmready_user_ids()
    if not dm_uids:
        return 0

    updated = 0
    now = datetime.utcnow()
    try:
        for uid in dm_uids:
            res = members_coll.update_one(
                {"user_id": uid},
                {"$set": {"dm_ready": True, "dm_ready_synced_at": now}},
                upsert=False,
            )
            if getattr(res, "modified_count", 0) or getattr(res, "matched_count", 0):
                updated += 1
    except Exception as e:
        log.warning("dmready_bridge: sync failed (%s)", e)

    return updated


def register(app: Client):
    """
    Call register(app) from main.py.
    """
    log.info("✅ handlers.dmready_bridge wired (OWNER_ID=%s, auto_sync=%sm)", OWNER_ID, AUTO_SYNC_MINUTES)

    members_coll = _get_members_coll()

    async def _sync_and_reply(msg: Optional[Message] = None):
        n = await _mirror_into_requirements_members(members_coll)
        if msg:
            await msg.reply_text(f"✅ DM-ready sync complete.\nUpdated/confirmed: <b>{n}</b> users.", quote=True)

    @app.on_message(filters.private & filters.command("dmreadysync"))
    async def dmreadysync_cmd(_, msg: Message):
        if not msg.from_user or msg.from_user.id != OWNER_ID:
            return
        await _sync_and_reply(msg)

    async def _auto_loop():
        # Initial delay so other handlers + Mongo can come up
        await asyncio.sleep(5)
        while True:
            try:
                await _mirror_into_requirements_members(members_coll)
            except Exception:
                pass
            await asyncio.sleep(max(60, AUTO_SYNC_MINUTES * 60))

    # Fire-and-forget periodic sync
    try:
        app.loop.create_task(_auto_loop())
    except Exception:
        asyncio.get_event_loop().create_task(_auto_loop())
