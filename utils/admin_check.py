# utils/admin_check.py
# Back-compat admin helpers + decorator.

import os
from typing import Set, Callable, Awaitable, Union
from pyrogram import Client
from pyrogram.types import User, Message

def _ids(env: str) -> Set[int]:
    raw = os.getenv(env, "") or ""
    s: Set[int] = set()
    for tok in raw.replace(";", ",").split(","):
        tok = tok.strip()
        if not tok: continue
        try: s.add(int(tok))
        except: pass
    return s

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = _ids("SUPER_ADMINS")
ADMINS = _ids("ADMINS")

def is_owner_id(user_id: int) -> bool:
    return OWNER_ID and user_id == OWNER_ID

def is_super_admin_id(user_id: int) -> bool:
    return user_id in SUPER_ADMINS or is_owner_id(user_id)

def is_admin_id(user_id: int) -> bool:
    return user_id in ADMINS or is_super_admin_id(user_id)

# Back-compat names used across various handlers
def is_owner_or_admin_id(user_id: int) -> bool:
    return is_admin_id(user_id)

async def is_admin(client: Client, subject: Union[User, Message, None]) -> bool:
    if subject is None: return False
    user = subject if isinstance(subject, User) else getattr(subject, "from_user", None)
    return bool(user and is_admin_id(user.id))

def require_admin(fn: Callable[..., Awaitable]):
    async def wrapper(client: Client, m: Message, *args, **kwargs):
        uid = m.from_user.id if m.from_user else 0
        if not is_admin_id(uid):
            await m.reply_text("❌ You’re not allowed to use this command.")
            return
        return await fn(client, m, *args, **kwargs)
    return wrapper
