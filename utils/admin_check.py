# utils/admin_check.py
import os
from typing import Iterable, Set, Optional, Union

from pyrogram import Client
from pyrogram.types import User, Message

# ---------- helpers ----------
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
SUPER_ADMINS: Set[int] = _ids_from_env("SUPER_ADMINS")   # comma-separated user IDs
ADMINS: Set[int] = _ids_from_env("ADMINS")               # optional extra IDs
SANCTUARY_GROUP_IDS: Set[int] = _ids_from_env("SANCTUARY_GROUP_IDS")  # groups to check admin privs in

# ---------- role checks (pure env) ----------
def is_owner(user: Optional[User]) -> bool:
    return bool(user and OWNER_ID and user.id == OWNER_ID)

def is_super_admin(user: Optional[User]) -> bool:
    return bool(user and user.id in SUPER_ADMINS)

def is_list_admin(user: Optional[User]) -> bool:
    return bool(user and user.id in ADMINS)

def is_env_admin(user: Optional[User]) -> bool:
    return is_owner(user) or is_super_admin(user) or is_list_admin(user)

# ---------- chat admin check (runtime) ----------
async def _is_admin_in_any_chat(client: Client, user_id: int, chat_ids: Iterable[int]) -> bool:
    for gid in chat_ids:
        try:
            m = await client.get_chat_member(gid, user_id)
            # Pyrogram v2: privileges present for admins; status can be OWNER/ADMINISTRATOR
            if getattr(m, "privileges", None):
                return True
            status = getattr(m, "status", None)
            if status and str(status).upper() in {"ChatMemberStatus.OWNER", "ChatMemberStatus.ADMINISTRATOR", "OWNER", "ADMINISTRATOR"}:
                return True
        except Exception:
            continue
    return False

# ---------- public API (backwards-compatible) ----------
async def is_owner_or_admin(client: Client, user: Optional[User]) -> bool:
    """
    Unified gate used by newer handlers.
    True if the user is OWNER / SUPER_ADMIN / ADMINS (env) OR admin in any SANCTUARY_GROUP_IDS.
    If SANCTUARY_GROUP_IDS is empty, env roles alone are used.
    """
    if not user:
        return False
    if is_env_admin(user):
        return True
    if SANCTUARY_GROUP_IDS:
        return await _is_admin_in_any_chat(client, user.id, SANCTUARY_GROUP_IDS)
    return False

async def is_admin(client: Client, subject: Union[User, Message, None]) -> bool:
    """
    Back-compat shim for older modules (e.g., handlers.bloop).
    Accepts a User or a Message; returns same as is_owner_or_admin.
    """
    if subject is None:
        return False
    user = subject if isinstance(subject, User) else getattr(subject, "from_user", None)
    return await is_owner_or_admin(client, user)

async def is_adminish(client: Client, subject: Union[User, Message, None]) -> bool:
    """
    Another common alias seen in old handlers. Same semantics as is_admin().
    """
    return await is_admin(client, subject)
