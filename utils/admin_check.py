# utils/admin_check.py
import os
from typing import Iterable, Set
from pyrogram import Client
from pyrogram.types import User

def _ids_from_env(name: str) -> Set[int]:
    raw = os.getenv(name, "") or ""
    out: Set[int] = set()
    for piece in raw.replace(";", ",").split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            out.add(int(piece))
        except ValueError:
            pass
    return out

OWNER_ID: int = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS: Set[int] = _ids_from_env("SUPER_ADMINS")
ADMINS: Set[int] = _ids_from_env("ADMINS")  # optional static list

SANCTUARY_GROUP_IDS: Set[int] = _ids_from_env("SANCTUARY_GROUP_IDS")  # optional; bot checks admin role in these

def is_owner(user: User | None) -> bool:
    return bool(user and OWNER_ID and user.id == OWNER_ID)

def is_super_admin(user: User | None) -> bool:
    return bool(user and user.id in SUPER_ADMINS)

def is_list_admin(user: User | None) -> bool:
    return bool(user and user.id in ADMINS)

async def _is_chat_admin_any(client: Client, user_id: int, chat_ids: Iterable[int]) -> bool:
    # Checks Telegram admin status in any provided group (optional)
    for gid in chat_ids:
        try:
            m = await client.get_chat_member(gid, user_id)
            if m and (m.privileges or (m.status and m.status.name in {"ADMINISTRATOR", "OWNER"})):
                return True
        except Exception:
            continue
    return False

async def is_owner_or_admin(client: Client, user: User | None) -> bool:
    """
    Unified gate used by admin-only commands.
    True if OWNER, SUPER_ADMIN, in static ADMINS list, or is an admin in any SANCTUARY_GROUP_IDS.
    """
    if not user:
        return False
    if is_owner(user) or is_super_admin(user) or is_list_admin(user):
        return True
    if SANCTUARY_GROUP_IDS:
        return await _is_chat_admin_any(client, user.id, SANCTUARY_GROUP_IDS)
    return False
