# utils/admin_check.py
import os
from typing import Iterable, Set
from pyrogram.types import Message
from pyrogram import Client

def _parse_ids(env_name: str) -> Set[int]:
    raw = os.getenv(env_name, "") or ""
    out: Set[int] = set()
    for tok in raw.replace(";", ",").split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.add(int(tok))
        except Exception:
            pass
    return out

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = _parse_ids("SUPER_ADMINS")
ADMINS = _parse_ids("ADMINS")

def is_owner(user_id: int) -> bool:
    return OWNER_ID and user_id == OWNER_ID

def is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS or is_owner(user_id)

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS or is_super_admin(user_id)

def is_owner_or_admin(user_id: int) -> bool:
    return is_admin(user_id)

def require_admin(fn):
    async def wrapper(client: Client, m: Message, *args, **kwargs):
        uid = (m.from_user.id if m.from_user else 0)
        if not is_admin(uid):
            await m.reply_text("❌ You’re not allowed to use this command.")
            return
        return await fn(client, m, *args, **kwargs)
    return wrapper
