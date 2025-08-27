# handlers/test_send.py
from __future__ import annotations
import os
import asyncio
from typing import Iterable, List, Set

from pyrogram import Client, filters
from pyrogram.types import Message

# ---- Admins who can use /test ------------------------------------------------
OWNER_IDS = {int(x) for x in os.getenv("OWNER_IDS", "").replace(" ", "").split(",") if x.isdigit()}
SUPER_ADMIN_IDS = {int(x) for x in os.getenv("SUPER_ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()}
ADMINS = OWNER_IDS | SUPER_ADMIN_IDS

# ---- ReqStore (your project’s data access) -----------------------------------
try:
    from req_store import ReqStore
    STORE = ReqStore()
except Exception:
    STORE = None


# ---- Helpers: adapt to your ReqStore’s API -----------------------------------
def _is_dm_ready(uid: int) -> bool:
    if not STORE:
        return False
    # try common APIs
    try:
        if hasattr(STORE, "is_dm_ready_global"):
            return bool(STORE.is_dm_ready_global(uid))
    except Exception:
        pass
    try:
        if hasattr(STORE, "is_dm_ready"):
            return bool(STORE.is_dm_ready(uid))
    except Exception:
        pass
    return False

def _meets_requirements(uid: int) -> bool:
    if not STORE:
        return False
    # try common APIs in order; return True if *qualified*
    for attr in ("meets_requirements", "is_qualified", "user_meets_requirements"):
        try:
            fn = getattr(STORE, attr, None)
            if callable(fn):
                return bool(fn(uid))
        except Exception:
            pass
    # structured status dict?
    for attr in ("get_user_status", "status_for_user", "fetch_user_status"):
        try:
            fn = getattr(STORE, attr, None)
            if callable(fn):
                st = fn(uid) or {}
                q = st.get("qualified") or st.get("meets_requirements")
                if q is not None:
                    return bool(q)
        except Exception:
            pass
    return False  # default: treat as NOT qualified unless store says otherwise

def _all_user_ids() -> Iterable[int]:
    """Best-effort enumeration of user ids from the store."""
    if not STORE:
        return []
    # Prefer explicit dm-ready lists, else all users then filter.
    for attr in ("get_dm_ready_user_ids", "all_dm_ready_users", "iter_dm_ready", "dm_ready_list"):
        try:
            fn = getattr(STORE, attr, None)
            if callable(fn):
                ids = list(fn())
                if ids:
                    return ids
        except Exception:
            pass
    # Fallback: enumerate every known user and filter by _is_dm_ready
    for attr in ("list_all_users", "all_users", "get_all_users", "iter_users", "users"):
        try:
            obj = getattr(STORE, attr, None)
            if callable(obj):
                ids = [u for u in obj()]
                if ids:
                    return ids
            elif isinstance(obj, (list, set, tuple)):
                if obj:
                    return list(obj)
        except Exception:
            pass
    return []


# ---- Pyrogram wiring ----------------------------------------------------------
def register(app: Client):

    @app.on_message(filters.private & filters.command(["test"]))
    async def send_test_to_dm_ready_not_qualified(client: Client, m: Message):
        # auth
        if not m.from_user or m.from_user.id not in ADMINS:
            return await m.reply_text("Not authorized.")

        if STORE is None:
            return await m.reply_text("ReqStore not available in this build.")

        # Collect candidates: DM-ready AND not meeting requirements
        all_ids: Iterable[int] = _all_user_ids()
        dm_ready_ids: List[int] = [uid for uid in all_ids if _is_dm_ready(int(uid))]
        targets: List[int] = [int(uid) for uid in dm_ready_ids if not _meets_requirements(int(uid))]

        if not targets:
            return await m.reply_text("No DM-ready users missing requirements were found.")

        # Send “test” to each; be polite with a tiny delay
        sent, failed = 0, 0
        for uid in targets:
            try:
                await client.send_message(uid, "test")
                sent += 1
                await asyncio.sleep(0.05)  # small throttle
            except Exception:
                failed += 1

        return await m.reply_text(f"✅ Sent to {sent} user(s). ❌ Failed: {failed}.")
