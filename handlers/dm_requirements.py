# handlers/dm_requirements.py
from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Dict

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus

from req_store import ReqStore
from payments import has_met_requirements, days_left_in_month

log = logging.getLogger("handlers.dm_requirements")

# Your main Sanctuary group
TARGET_CHAT_ID = -1002823762054

_store = ReqStore()

REMINDER_TEMPLATES = [
    (
        "Hey {name} 😈\n\n"
        "This is your little Sanctuary nudge… you still haven’t hit this month’s game requirements yet. "
        "You need at least $20 in game purchases and to spoil at least two of our models. "
        "You’ve got about {days_left} day(s) left this month to make me proud. 💋"
    ),
    (
        "Pssst, {name} 👀\n\n"
        "My logs say you haven’t finished this month’s Sanctuary requirements. "
        "Remember: $20 in games and love for at least two models. "
        "There are ~{days_left} day(s) left before the month resets… don’t keep me waiting. 😘"
    ),
    (
        "Hi {name} 💞\n\n"
        "Just a playful reminder that your Sanctuary requirements aren’t complete yet. "
        "You still need to hit $20+ in games and buy from at least two models this month. "
        "You’ve got {days_left} day(s) left to catch up. Think you can spoil us in time? 😈"
    ),
    (
        "Gorgeous {name} 💋\n\n"
        "You’re so close to being in my ‘gold star’ column, but my notes say you still owe me some games. "
        "Minimum is $20 in games and two different models this month. "
        "You’ve got about {days_left} day(s) left. Come tempt me properly. 🔥"
    ),
    (
        "Hey love {name} 💗\n\n"
        "Quick Sanctuary check-in: your monthly requirements aren’t fully checked off yet. "
        "At least $20 in games and support for two of our models, and you’re all set. "
        "There are {days_left} day(s) left before the month ends… perfect time to get a little extra naughty. 😇👉😈"
    ),
]


async def _is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception as e:
        log.warning("dm_requirements: admin check failed for %s in %s: %s", user_id, chat_id, e)
        return False


async def _is_in_target_chat(client: Client, user_id: int) -> bool:
    try:
        m = await client.get_chat_member(TARGET_CHAT_ID, user_id)
        return m.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        )
    except Exception:
        return False


def _build_random_reminder(name: str | None, days_left: int) -> str:
    if not name:
        name = "gorgeous"
    template = random.choice(REMINDER_TEMPLATES)
    return template.format(name=name, days_left=days_left)


def register(app: Client):
    log.info("✅ handlers.dm_requirements (Stripe-based) wired for chat %s", TARGET_CHAT_ID)

    @app.on_message(filters.group & filters.command(["reqremind", "requirements"]))
    async def req_remind(client: Client, m: Message):
        """
        Admin-only:
        DMs all DM-ready users in TARGET_CHAT_ID who have NOT met Stripe-based
        requirements this month.

        Requirements:
          - At least $20 in Stripe payments tagged as purchase_type == "game"
          - Purchases from at least 2 different models (any purchase_type)

        Usage:
          /reqremind
          /reqremind custom override text...
          (or reply to a message with /reqremind to use that text instead)
        """
        if m.chat.id != TARGET_CHAT_ID:
            await m.reply_text(
                "This reminder command only works in the main Sanctuary group. 💋"
            )
            return

        sender = m.from_user
        if not sender:
            return

        if not await _is_admin(client, TARGET_CHAT_ID, sender.id):
            await m.reply_text("Only group admins can use this command.")
            return

        # Optional override text (everyone gets the same text)
        override_text = None
        if len(m.command) > 1:
            override_text = m.text.split(maxsplit=1)[1]
        elif m.reply_to_message:
            override_text = m.reply_to_message.text or m.reply_to_message.caption

        now = datetime.utcnow()
        days_left = days_left_in_month(now)

        # Get global DM-ready users from your existing store
        try:
            dm_map: Dict[str, dict] = _store.list_dm_ready_global()  # {uid_str: {...}}
        except Exception as e:
            log.exception("dm_requirements: list_dm_ready_global failed: %s", e)
            await m.reply_text("❌ Could not load DM-ready users.")
            return

        if not dm_map:
            await m.reply_text("No one is marked DM-ready yet. 💭")
            return

        sent = 0
        skipped_not_in_chat = 0
        skipped_already_met = 0
        failed = 0

        for s_uid, info in dm_map.items():
            try:
                uid = int(s_uid)
            except Exception:
                continue

            # Only DM users who are still in your Sanctuary group
            if not await _is_in_target_chat(client, uid):
                skipped_not_in_chat += 1
                continue

            # Skip users who already met Stripe-based requirements this month
            if has_met_requirements(uid):
                skipped_already_met += 1
                continue

            name = None
            if isinstance(info, dict):
                name = info.get("first_name") or info.get("username")

            if override_text:
                text = override_text
            else:
                text = _build_random_reminder(name=name, days_left=days_left)

            try:
                await client.send_message(uid, text)
                sent += 1
            except Exception as e:
                failed += 1
                log.warning("dm_requirements: failed to DM %s: %s", uid, e)

        await m.reply_text(
            "📨 Sanctuary requirements scan complete.\n"
            f"• DMed (requirements not met): {sent}\n"
            f"• Skipped (already met this month): {skipped_already_met}\n"
            f"• Skipped (not in this group): {skipped_not_in_chat}\n"
            f"• Failed to deliver: {failed}"
        )
