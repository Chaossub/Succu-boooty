# handlers/requirements_sanctuary_admin.py
import logging
import os
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient, ASCENDING
from pyrogram.errors import RPCError

log = logging.getLogger(__name__)

# ────────────── ENV / CONSTANTS ──────────────

OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # 6964994611 for you
MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB = os.getenv("MONGO_DB", "Succubot")

# main group where requirements apply
SANCTU_GROUP_ID = int(os.getenv("SANCTU_GROUP_ID", "-1002823762054"))

# Mongo collections
mongo = MongoClient(MONGO_URI) if MONGO_URI else None
db = mongo[MONGO_DB] if mongo else None

payments_col = db["sanctuary_payments"] if db else None
exempt_col = db["sanctuary_exempt"] if db else None

# This MUST match whatever dm_ready.py uses; if we ever change it there, change it here too.
DMREADY_COL = db["dm_ready_users"] if db else None


def _owner_only(func):
    async def wrapper(client: Client, message: Message):
        if not message.from_user or message.from_user.id != OWNER_ID:
            return await message.reply_text("This command is for Roni only. 💕")
        return await func(client, message)
    return wrapper


def register(app: Client) -> None:
    """
    Register admin / owner commands for the Sanctuary requirements system.
    """

    if not mongo:
        log.warning("requirements_sanctuary_admin: MONGO_URI not set; commands will be disabled.")
    else:
        # make sure indexes exist
        payments_col.create_index(
            [("user_id", ASCENDING), ("created_at", ASCENDING)],
            name="payments_user_created_at",
        )
        exempt_col.create_index(
            [("user_id", ASCENDING)],
            name="exempt_user_id",
            unique=True,
        )

    log.info(
        "✅ handlers.requirements_sanctuary_admin registered (SANCTU_GROUP_ID=%s)",
        SANCTU_GROUP_ID,
    )

    # ─────────────────────────────────────────────────────────
    # /exempt and /unexempt
    # ─────────────────────────────────────────────────────────

    @app.on_message(filters.command("exempt") & filters.private)
    @_owner_only
    async def cmd_exempt(_, m: Message):
        if not exempt_col:
            return await m.reply_text("MongoDB not configured for exemptions.")

        if not m.reply_to_message and len(m.command) < 2:
            return await m.reply_text("Reply to a user or use `/exempt @username`.", quote=True)

        target = None
        if m.reply_to_message:
            target = m.reply_to_message.from_user
        else:
            # /exempt @user
            if not m.entities or len(m.entities) < 2:
                return await m.reply_text("Tag the user you want to exempt.", quote=True)
            # Pyrogram already resolves @user in the entities, easier to just rely on reply usually.
            return await m.reply_text("Please reply to a user to exempt them 💕", quote=True)

        exempt_col.update_one(
            {"user_id": target.id},
            {"$set": {"user_id": target.id, "username": target.username, "ts": datetime.utcnow()}},
            upsert=True,
        )
        await m.reply_text(f"✅ <b>{target.mention}</b> is now <b>EXEMPT</b> from requirements.")

    @app.on_message(filters.command("unexempt") & filters.private)
    @_owner_only
    async def cmd_unexempt(_, m: Message):
        if not exempt_col:
            return await m.reply_text("MongoDB not configured for exemptions.")

        if not m.reply_to_message and len(m.command) < 2:
            return await m.reply_text("Reply to a user or use `/unexempt @username`.", quote=True)

        target = None
        if m.reply_to_message:
            target = m.reply_to_message.from_user
        else:
            return await m.reply_text("Please reply to a user to unexempt them 💕", quote=True)

        exempt_col.delete_one({"user_id": target.id})
        await m.reply_text(f"🚫 <b>{target.mention}</b> is no longer exempt.")

    # ─────────────────────────────────────────────────────────
    # /testsanctuarydm  → send test DM to DM-ready + in Sanctuary
    # ─────────────────────────────────────────────────────────

    @app.on_message(filters.command("testsanctuarydm") & filters.private)
    @_owner_only
    async def cmd_test_sanctuary_dm(client: Client, m: Message):
        """
        Sends a test message ONLY to users who are:
        - marked DM-ready in Mongo
        - AND currently in the Succubus Sanctuary group
        """
        if not DMREADY_COL:
            return await m.reply_text("DM-ready store is not available (Mongo issue).")

        test_text = "🧪 This is a test message from SuccuBot to verify DM-ready + Sanctuary membership."  # default
        if len(m.command) > 1:
            # allow custom text after command
            test_text = m.text.split(None, 1)[1]

        await m.reply_text("Scanning DM-ready users and Sanctuary members… this may take a moment.")

        # 1) Get DM-ready users from Mongo
        dm_ready_docs = list(DMREADY_COL.find({}))
        dm_ready_ids = {doc.get("user_id") for doc in dm_ready_docs if doc.get("user_id")}
        dm_ready_ids.discard(None)

        # 2) Cross-check who is in the Sanctuary group
        qualified_ids = set()
        scanned_members = 0

        async for member in client.get_chat_members(SANCTU_GROUP_ID):
            scanned_members += 1
            uid = member.user.id
            if uid in dm_ready_ids:
                qualified_ids.add(uid)

        # 3) Send test DMs
        delivered = 0
        failed = 0
        failed_users = []

        for uid in qualified_ids:
            try:
                await client.send_message(uid, test_text)
                delivered += 1
            except RPCError as e:
                failed += 1
                failed_users.append((uid, str(e)))

        # 4) Build report text
        report_lines = [
            "✅ <b>Test Sanctuary DM — completed</b>",
            "",
            f"• Sanctuary members scanned: <b>{scanned_members}</b>",
            f"• DM-ready users in DB: <b>{len(dm_ready_ids)}</b>",
            f"• Qualified (DM-ready + in Sanctuary): <b>{len(qualified_ids)}</b>",
            "",
            f"• Messages delivered: <b>{delivered}</b>",
            f"• Delivery failures: <b>{failed}</b>",
        ]

        if failed_users:
            report_lines.append("")
            report_lines.append("Failed to deliver to:")
            for uid, reason in failed_users[:10]:
                report_lines.append(f"• <code>{uid}</code> — {reason}")

            if len(failed_users) > 10:
                report_lines.append(f"…and {len(failed_users) - 10} more")

        await m.reply_text("\n".join(report_lines))

    # ─────────────────────────────────────────────────────────
    # /reqstatus  → tiny summary helper for you
    # ─────────────────────────────────────────────────────────

    @app.on_message(filters.command("reqstatus") & filters.private)
    @_owner_only
    async def cmd_req_status(_, m: Message):
        """Lightweight status summary for your requirements system."""
        total_payments = payments_col.count_documents({}) if payments_col else 0
        exempt_count = exempt_col.count_documents({}) if exempt_col else 0
        dm_ready_count = DMREADY_COL.count_documents({}) if DMREADY_COL else 0

        txt = (
            "📊 <b>Sanctuary Requirements Status</b>\n\n"
            f"• Total payments recorded: <b>{total_payments}</b>\n"
            f"• Exempt users: <b>{exempt_count}</b>\n"
            f"• DM-ready users: <b>{dm_ready_count}</b>\n"
            f"• Group ID (Sanctuary): <code>{SANCTU_GROUP_ID}</code>"
        )
        await m.reply_text(txt)
