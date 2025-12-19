# handlers/dmready_bridge.py
import os
import logging
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message

log = logging.getLogger("dmready_bridge")

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))

# Requirements panel uses db="Succubot" and coll="requirements_members"
MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")


def _get_members_coll():
    if not MONGO_URI:
        return None
    try:
        from pymongo import MongoClient
        mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        db = mongo["Succubot"]
        return db["requirements_members"]
    except Exception as e:
        log.warning("dmready_bridge: could not connect to mongo for requirements_members: %s", e)
        return None


def _upsert_dm_ready_flag(user_id: int) -> None:
    """
    Mirror DM-ready status into requirements_members.
    We only set dm_ready=True (never auto-unset).
    """
    coll = _get_members_coll()
    if coll is None:
        return

    try:
        coll.update_one(
            {"user_id": user_id},
            {"$set": {"dm_ready": True}},
            upsert=True,
        )
    except Exception as e:
        log.warning("dmready_bridge: update_one failed for user_id=%s: %s", user_id, e)


def register(app: Client):
    log.info("✅ handlers.dmready_bridge wired (OWNER_ID=%s)", OWNER_ID)

    # Passive mirror: whenever someone DMs the bot, dm_ready.py marks them.
    # We ALSO mirror into requirements_members so the Requirements Panel can show them.
    @app.on_message(filters.private & ~filters.service, group=11)
    async def _mirror_on_private_message(_: Client, m: Message):
        try:
            if not m.from_user:
                return
            _upsert_dm_ready_flag(m.from_user.id)
        except Exception as e:
            log.warning("dmready_bridge: mirror on private message failed: %s", e)

    # Owner tool: force a one-time full sync from dm_ready store into requirements_members
    @app.on_message(filters.private & filters.command("dmreadysync"), group=-1)
    async def _dmreadysync(_: Client, m: Message):
        if not m.from_user or m.from_user.id != OWNER_ID:
            await m.reply_text("Only the owner can run this.")
            return

        try:
            # Import your existing store without modifying it
            from handlers.dm_ready import store as dm_store

            users = dm_store.all()
            if not users:
                await m.reply_text("✅ dmreadysync: no DM-ready users found in dm_ready store.")
                return

            count = 0
            for u in users:
                uid = u.get("user_id")
                if isinstance(uid, int):
                    _upsert_dm_ready_flag(uid)
                    count += 1

            await m.reply_text(f"✅ dmreadysync complete: mirrored {count} users into requirements_members.dm_ready=true")
        except Exception as e:
            log.exception("dmready_bridge: dmreadysync failed: %s", e)
            await m.reply_text(f"❌ dmreadysync failed: {e}")
