# handlers/dmready_bridge.py
"""
Bridge DM-ready tracking into the Requirements Panel DB WITHOUT touching dm_ready.py.

Why:
- /dmreadylist uses dm_ready.py store (JSON or dm_ready_users collection)
- Requirements Panel "DM-Ready (This Group)" reads from Mongo collection: requirements_members
  with dm_ready=true AND groups contains the group id.

This handler:
1) Passively mirrors DM-ready -> requirements_members.dm_ready = True whenever someone DMs the bot.
2) Adds owner-only /dmreadysync to backfill existing dm_ready store into requirements_members.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message

log = logging.getLogger("dmready_bridge")

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "0")) or 0)

# Requirements Panel Mongo settings (must match requirements_panel.py)
MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")

_DB_NAME = "Succubot"
_MEMBERS_COLL = "requirements_members"


def _utc_now_dt():
    return datetime.now(timezone.utc)


def _get_members_coll():
    if not MONGO_URI:
        return None
    try:
        from pymongo import MongoClient, ASCENDING

        mongo = MongoClient(MONGO_URI)
        db = mongo[_DB_NAME]
        coll = db[_MEMBERS_COLL]
        # harmless if it already exists
        coll.create_index([("user_id", ASCENDING)], unique=True)
        return coll
    except Exception:
        log.exception("dmready_bridge: failed to init Mongo")
        return None


def _upsert_dm_ready(coll, user_id: int, username: str, first_name: str, last_name: str):
    """
    Set dm_ready=true in requirements_members for this user.
    Do NOT touch spend/exempt/etc. Only minimal safe fields.
    """
    if not coll:
        return False

    # prefer not overwriting names with blanks
    set_fields = {"dm_ready": True, "last_updated": _utc_now_dt()}
    if username:
        set_fields["username"] = username
    # requirements_panel uses first_name and username for display
    name = (first_name or "").strip()
    if last_name:
        name = (name + " " + last_name.strip()).strip()
    if name:
        set_fields["first_name"] = name

    coll.update_one(
        {"user_id": user_id},
        {"$set": set_fields, "$setOnInsert": {"user_id": user_id}},
        upsert=True,
    )
    return True


def register(app: Client):
    log.info("✅ handlers.dmready_bridge wired (OWNER_ID=%s)", OWNER_ID)

    @app.on_message(filters.private & filters.command("dmreadysync"), group=-1)
    async def _dmreadysync(_: Client, m: Message):
        """
        Owner-only.
        Backfills dm_ready store into requirements_members.dm_ready=true.

        Usage:
          /dmreadysync
          /dmreadysync <group_id>     (only mark users already indexed in that group)
          /dmreadysync clear          (optional: clears dm_ready for non-DM-ready users)
        """
        uid = m.from_user.id if m.from_user else 0
        if uid != OWNER_ID:
            await m.reply_text("Only the owner can run this.")
            return

        coll = _get_members_coll()
        if not coll:
            await m.reply_text("❌ Mongo not available (MONGODB_URI/MONGO_URI missing or failing).")
            return

        # Import dm_ready store
        try:
            from handlers.dm_ready import store as dm_store
        except Exception as e:
            log.exception("dmready_bridge: failed importing dm_ready.store")
            await m.reply_text(f"❌ Could not import dm_ready store: {e}")
            return

        arg = ""
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) > 1:
            arg = parts[1].strip()

        # Optional modes
        mode_clear = (arg.lower() == "clear")
        gid_filter: Optional[int] = None
        if arg and not mode_clear:
            try:
                gid_filter = int(arg)
            except ValueError:
                await m.reply_text("Usage:\n/dmreadysync\n/dmreadysync <group_id>\n/dmreadysync clear")
                return

        dm_users = dm_store.all() or []
        dm_ids = {int(r.get("user_id")) for r in dm_users if r.get("user_id") is not None}

        marked = 0
        skipped = 0

        if gid_filter is None:
            # Mark every DM-ready user
            for r in dm_users:
                rid = r.get("user_id")
                if rid is None:
                    continue
                ok = _upsert_dm_ready(
                    coll,
                    int(rid),
                    r.get("username") or "",
                    r.get("first_name") or "",
                    r.get("last_name") or "",
                )
                if ok:
                    marked += 1
                else:
                    skipped += 1
        else:
            # Only mark DM-ready users that are ALREADY indexed in that group (requires 📡 Scan Group Members ran)
            indexed = list(coll.find({"groups": gid_filter}, {"user_id": 1}))
            indexed_ids = {int(d.get("user_id")) for d in indexed if d.get("user_id") is not None}
            target_ids = dm_ids.intersection(indexed_ids)

            for rid in target_ids:
                # find best metadata from store if present
                rec = next((x for x in dm_users if int(x.get("user_id", -1)) == rid), {}) or {}
                ok = _upsert_dm_ready(
                    coll,
                    rid,
                    rec.get("username") or "",
                    rec.get("first_name") or "",
                    rec.get("last_name") or "",
                )
                if ok:
                    marked += 1
                else:
                    skipped += 1

        cleared = 0
        if mode_clear:
            # Only do this when you explicitly run "clear"
            # It will turn OFF dm_ready for users not in dm_ready store.
            res = coll.update_many(
                {"dm_ready": True, "user_id": {"$nin": list(dm_ids)}},
                {"$set": {"dm_ready": False, "last_updated": _utc_now_dt()}},
            )
            cleared = int(getattr(res, "modified_count", 0) or 0)

        msg = (
            "✅ DM-Ready sync complete.\n"
            f"Marked: {marked}\n"
            f"Skipped: {skipped}"
        )
        if gid_filter is not None:
            msg += f"\nScoped to group: {gid_filter}"
        if mode_clear:
            msg += f"\nCleared (not DM-ready anymore): {cleared}"

        await m.reply_text(msg)

    # Passive mirror: whenever someone DMs the bot, set dm_ready=true in requirements_members
    @app.on_message(filters.private & ~filters.service, group=11)
    async def _mirror_dm_ready(_: Client, m: Message):
        try:
            if not m.from_user:
                return

            coll = _get_members_coll()
            if not coll:
                return

            u = m.from_user
            _upsert_dm_ready(
                coll,
                user_id=u.id,
                username=u.username or "",
                first_name=u.first_name or "",
                last_name=u.last_name or "",
            )
        except Exception:
            log.exception("dmready_bridge: passive mirror failed")
