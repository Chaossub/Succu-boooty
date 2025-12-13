# handlers/summon.py
import os
import logging
from typing import Set, List

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

log = logging.getLogger(__name__)


def _parse_id_set(val: str | None) -> Set[int]:
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


OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))
SUPER_ADMINS: Set[int] = _parse_id_set(os.getenv("SUPER_ADMINS"))
MODELS: Set[int] = _parse_id_set(os.getenv("MODELS"))


def _can_use_summon(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in SUPER_ADMINS or user_id in MODELS


def _chunk(items: List[str], size: int) -> List[List[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def register(app: Client) -> None:
    log.info(
        "✅ handlers.summon registered (OWNER_ID=%s SUPER_ADMINS=%s MODELS=%s)",
        OWNER_ID,
        len(SUPER_ADMINS),
        len(MODELS),
    )

    @app.on_message(filters.command(["summonall", "summon"], prefixes=["/", "!"]))
    async def summon_cmd(client: Client, msg: Message):
        if not msg.from_user or not msg.chat:
            return

        if msg.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return

        user_id = msg.from_user.id
        chat_id = msg.chat.id

        if not _can_use_summon(user_id):
            await msg.reply_text("Only Roni and approved models can use /summonall here.")
            return

        header_text = ""
        if msg.text:
            parts = msg.text.split(maxsplit=1)
            if len(parts) > 1:
                header_text = parts[1].strip()

        mentions: List[str] = []
        try:
            async for member in client.get_chat_members(chat_id):
                u = member.user
                if not u or u.is_bot:
                    continue
                name = (u.first_name or u.last_name or "Member").strip()
                mentions.append(f'<a href="tg://user?id={u.id}">{name}</a>')
        except Exception as e:
            log.exception("summon: get_chat_members failed: %s", e)
            await msg.reply_text(
                "I couldn’t read the member list.\n\n"
                "Fix: make me an admin in the group and (in @BotFather) set Privacy Mode to DISABLED."
            )
            return

        if not mentions:
            await msg.reply_text(
                "I don’t see any members to tag.\n\n"
                "If this is a big group, I usually need admin + Privacy Mode disabled."
            )
            return

        chunks = _chunk(mentions, 20)
        total = len(mentions)
        reply_to_id = msg.reply_to_message_id or msg.id

        for i, chunk in enumerate(chunks, start=1):
            header_lines = [f"Summoning {total} member(s) – batch {i}/{len(chunks)}"]
            if header_text:
                header_lines.append(header_text)
            text = "\n".join(header_lines) + "\n\n" + " ".join(chunk)

            try:
                await client.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_to_message_id=reply_to_id,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                log.warning("summon: failed to send batch %s: %s", i, e)

        try:
            await msg.delete()
        except Exception:
            pass
