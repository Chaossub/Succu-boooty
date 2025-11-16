# handlers/dm_requirements.py
from __future__ import annotations

import logging
import random
import json
import calendar
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus

log = logging.getLogger("handlers.dm_requirements")

# Your main Sanctuary group
TARGET_CHAT_ID = -1002823762054

# Requirements storage
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
REQ_FILE = DATA_DIR / "requirements.json"

try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception as e:
    log.warning("dm_requirements: ReqStore unavailable: %s", e)
    _store = None


# ────────────── Helpers: JSON storage ──────────────

def _load_reqs() -> Dict[str, Any]:
    if not REQ_FILE.exists():
        return {}
    try:
        return json.loads(REQ_FILE.read_text("utf-8"))
    except Exception as e:
        log.warning("dm_requirements: failed to load requirements.json: %s", e)
        return {}


def _save_reqs(data: Dict[str, Any]) -> None:
    try:
        REQ_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        log.error("dm_requirements: failed to save requirements.json: %s", e)


def _month_key(now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    return f"{now.year:04d}-{now.month:02d}"  # e.g. "2025-11"


def _days_left_in_month(now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    last_day = calendar.monthrange(now.year, now.month)[1]
    end_date = datetime(now.year, now.month, last_day).date()
    return max((end_date - now.date()).days, 0)


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


def _mark_met(chat_id: int, user_id: int, when: datetime | None = None) -> None:
    """
    Mark that a user in TARGET_CHAT_ID has met their requirements
    for the current month.
    """
    if chat_id != TARGET_CHAT_ID:
        return

    now = when or datetime.utcnow()
    month = _month_key(now)

    data = _load_reqs()
    chat_key = str(TARGET_CHAT_ID)
    month_map = data.setdefault(chat_key, {})
    users_map: Dict[str, Any] = month_map.setdefault(month, {})

    ukey = str(user_id)
    users_map[ukey] = {
        "met": True,
        "met_at": now.isoformat(),
    }

    _save_reqs(data)


def _has_met_this_month(user_id: int, now: datetime | None = None) -> bool:
    """
    Returns True if user has met requirements this month in TARGET_CHAT_ID.
    """
    now = now or datetime.utcnow()
    month = _month_key(now)
    data = _load_reqs()

    chat_key = str(TARGET_CHAT_ID)
    month_map = data.get(chat_key, {})
    users_map: Dict[str, Any] = month_map.get(month, {})
    ukey = str(user_id)

    info = users_map.get(ukey)
    return bool(info and info.get("met"))


# ────────────── Flirty randomized reminder text ──────────────

REMINDER_TEMPLATES = [
    (
        "Hey {name} 😈\n\n"
        "This is your little Sanctuary nudge… you still haven’t hit your monthly requirements yet. "
        "You’ve got about {days_left} day(s) left this month to make me proud. 💋"
    ),
    (
        "Pssst, {name} 👀\n\n"
        "My logs say you haven’t finished your Sanctuary requirements for this month yet. "
        "Don’t make me put you on the wrong kind of naughty list. You’ve got ~{days_left} day(s) left. 😘"
    ),
    (
        "Hi {name} 💞\n\n"
        "Just a playful reminder that your Sanctuary requirements for this month are still waiting for you. "
        "There are {days_left} day(s) left before the month ends… think you can spoil me in time? 😈"
    ),
    (
        "Gorgeous {name} 💋\n\n"
        "You’re so close to being in my ‘gold star’ column, but my notes say you still need to hit your requirements "
        "for this month. You’ve got about {days_left} day(s) left. Come tempt me properly. 🔥"
    ),
    (
        "Hey love {name} 💗\n\n"
        "Quick Sanctuary check-in: requirements for this month still look incomplete on my side. "
        "You’ve got {days_left} day(s) left before the month resets, so now’s the perfect time to catch up. 😇👉😈"
    ),
]


def _build_random_reminder(name: str | None, days_left: int) -> str:
    if not name:
        name = "gorgeous"
    template = random.choice(REMINDER_TEMPLATES)
    return template.format(name=name, days_left=days_left)


# ────────────── Registration ──────────────

def register(app: Client):
    log.info("✅ handlers.dm_requirements wired for chat %s", TARGET_CHAT_ID)

    @app.on_message(filters.group & filters.command(["metreq", "metrequirements"]))
    async def met_requirements(client: Client, m: Message):
        """
        Member command: mark monthly requirements as completed.
        Only meaningful in TARGET_CHAT_ID.
        """
        chat = m.chat
        user = m.from_user
        if not user:
            return

        if chat.id != TARGET_CHAT_ID:
            await m.reply_text(
                "This command only applies inside the Sanctuary requirements group. 💋"
            )
            return

        if _has_met_this_month(user.id):
            await m.reply_text(
                "You’re already marked as having met this month’s requirements. Good girl. 😈💕"
            )
            return

        _mark_met(chat.id, user.id)
        await m.reply_text(
            "Got it, baby. You’re now marked as having met this month’s Sanctuary requirements. 💋"
        )

    @app.on_message(filters.group & filters.command(["reqremind", "requirements"]))
    async def req_remind(client: Client, m: Message):
        """
        Admin-only:
        DMs all DM-ready users in TARGET_CHAT_ID who have NOT met requirements this month.
        Messages are randomized flirty reminders mentioning how many days are left.

        Usage:
          /reqremind
          /reqremind custom override text...
          (or reply to a message with /reqremind to use that text instead)
        """
        if _store is None:
            await m.reply_text("❌ DM storage not available right now.")
            return

        # Force this to only run for your main group
        if m.chat.id != TARGET_CHAT_ID:
            await m.reply_text(
                "This reminder command only works in the main Sanctuary group. 💋"
            )
            return

        sender = m.from_user
        if not sender:
            return

        # Admin check in the target group
        if not await _is_admin(client, TARGET_CHAT_ID, sender.id):
            await m.reply_text("Only group admins can use this command.")
            return

        # Optional: admin can override text, but default is randomized per-user
        override_text = None
        if len(m.command) > 1:
            override_text = m.text.split(maxsplit=1)[1]
        elif m.reply_to_message:
            override_text = m.reply_to_message.text or m.reply_to_message.caption

        now = datetime.utcnow()
        days_left = _days_left_in_month(now)

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

            # Skip users who already met requirements this month
            if _has_met_this_month(uid, now=now):
                skipped_already_met += 1
                continue

            # Figure out name for personalization
            name = None
            if isinstance(info, dict):
                name = info.get("first_name") or info.get("username")

            # Build per-user message
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
            f"• DMed (not met yet): {sent}\n"
            f"• Skipped (already met this month): {skipped_already_met}\n"
            f"• Skipped (not in this group): {skipped_not_in_chat}\n"
            f"• Failed to deliver: {failed}"
        )
