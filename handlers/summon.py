# handlers/summon.py

import os
import logging
from typing import Set, List

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType

log = logging.getLogger(__name__)

# ────────────── ENV & HELPERS ──────────────

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))


def _parse_id_list(val: str | None) -> Set[int]:
    if not val:
        return set()
    out: Set[int] = set()
    for part in val.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            log.warning("summon: bad ID in list: %r", part)
    return out


SUPER_ADMINS: Set[int] = _parse_id_list(os.getenv("SUPER_ADMINS", ""))
MODELS: Set[int] = _parse_id_list(os.getenv("MODELS", ""))


def _can_use_summon(user_id: int) -> bool:
    """
    Only:
    - Owner
    - MODELS
    - SUPER_ADMINS
    can use /summon.
    """
    if user_id == OWNER_ID:
        return True
    if user_id in MODELS:
        return True
    if user_id in SUPER_ADMINS:
        return True
    return False


def _chunk_list(items: List[str], chunk_size: int) -> List[List[str]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


# ────────────── REGISTER ──────────────


def register(app: Client):
    log.info(
        "✅ handlers.summon registered (OWNER_ID=%s, SUPER_ADMINS=%s, MODELS=%s)",
        OWNER_ID,
        SUPER_ADMINS,
        MODELS,
    )

    @app.on_message(
        filters.command(["summon", "summonall", "all"], prefixes=["/", "!"])
        & (filters.group | filters.supergroup)
    )
    async def summon_cmd(client: Client, msg: Message):
        from_user = msg.from_user
        if not from_user:
            return

        chat = msg.chat
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return

        user_id = from_user.id
        chat_id = chat.id

        # ── Permission check: only Roni + models + super_admins ──
        if not _can_use_summon(user_id):
            await msg.reply_text(
                "Only Roni and approved models can use /summon here."
            )
            return

        # Optional extra text after the command
        # e.g. "/summon Game night is starting!" → "Game night is starting!"
        extra_text = ""
        if msg.text:
            parts = msg.text.split(maxsplit=1)
            if len(parts) > 1:
                extra_text = parts[1].strip()

        # ── Collect members ─────────────
        mentions: List[str] = []
        try:
            async for member in client.get_chat_members(chat_id):
                user = member.user
                if not user:
                    continue
                if user.is_bot:
                    continue

                # Build an inline mention link
                name = (user.first_name or user.last_name or "Member").strip()
                mention = f'<a href="tg://user?id={user.id}">{name}</a>'
                mentions.append(mention)
        except Exception as e:
            log.exception("summon: error while iterating chat members: %s", e)
            await msg.reply_text(
                "I couldn’t fetch the member list for this chat. "
                "Make sure I have permission to see members."
            )
            return

        if not mentions:
            await msg.reply_text("I don’t see any members to tag (besides bots).")
            return

        # ── Send in chunks to avoid limits ─────────────
        # Roughly 20 mentions per message keeps things safe.
        chunks = _chunk_list(mentions, 20)

        base_text = extra_text or "Summoning everyone 💋"

        # If used as a reply, keep everything threaded
        reply_to_id = msg.reply_to_message_id or msg.id

        sent_count = 0
        for chunk in chunks:
            text = base_text + "\n\n" + " ".join(chunk)
            try:
                await client.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_to_message_id=reply_to_id,
                    disable_web_page_preview=True,
                )
                sent_count += 1
            except Exception as e:
                log.warning("summon: failed to send summon chunk: %s", e)

        # Try to clean up the command message if possible
        try:
            await msg.delete()
        except Exception:
            pass

        if sent_count == 0:
            await client.send_message(
                chat_id=chat_id,
                text="Something went wrong trying to tag everyone. I couldn’t send the mentions.",
                reply_to_message_id=reply_to_id,
            )
