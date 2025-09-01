# handlers/welcome.py
# Group welcomes + randomized flirty goodbyes (NO /start here).
# Also unsets DM-ready when a user leaves / is kicked / banned in Sanctuary groups.

import os
import time
import random
import contextlib
from typing import Tuple, Dict, Optional, Set

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatMemberUpdated,
    User,
)
from pyrogram.enums import ChatType, ChatMemberStatus

# ── DM-ready store (persistent JSON) ──────────────────────────────────────────
try:
    from utils.dmready_store import DMReadyStore
    _dm = DMReadyStore()
except Exception:
    class _MemDM:
        def __init__(self): self._g=set()
        def unset_dm_ready_global(self, user_id: int) -> bool:
            if user_id in self._g:
                self._g.remove(user_id)
                return True
            return False
    _dm = _MemDM()

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

# Groups where membership matters (comma/space separated IDs)
# Example: SANCTUARY_GROUP_IDS="-1002823762054, -1001234567890"
def _load_groups() -> Set[int]:
    raw = os.getenv("SANCTUARY_GROUP_IDS", "") or ""
    ids: Set[int] = set()
    for tok in raw.replace(",", " ").split():
        tok = tok.strip()
        if tok.lstrip("-").isdigit():
            ids.add(int(tok))
    return ids
SANCTUARY_IDS: Set[int] = _load_groups()

# ── Env toggles ───────────────────────────────────────────────────────────────
WELCOME_ENABLE = os.getenv("WELCOME_ENABLE", "1") == "1"
GOODBYE_ENABLE = os.getenv("GOODBYE_ENABLE", "1") == "1"
WELCOME_DELETE_SERVICE = os.getenv("WELCOME_DELETE_SERVICE", "0") == "1"
GOODBYE_DELETE_SERVICE = os.getenv("GOODBYE_DELETE_SERVICE", "0") == "1"

# optional media
WELCOME_PHOTO = os.getenv("WELCOME_PHOTO")  # file_id or URL
GOODBYE_PHOTO = os.getenv("GOODBYE_PHOTO")  # file_id or URL

# Button labels
BTN_MENU   = os.getenv("BTN_MENU",  "💕 Menus")
BTN_DM     = os.getenv("BTN_DM",    "💌 DM Now")
BTN_RULES  = os.getenv("BTN_RULES", "‼️ Rules")
BTN_BUYER  = os.getenv("BTN_BUYER", "✨ Buyer Requirements")

# ── Randomized welcome copy (promotes the DM portal) ──────────────────────────
WELCOME_LINES = [
    "🔥 <b>Welcome to the Succubus Sanctuary</b>, {mention}! Tap <b>💌 DM Now</b> to open your portal—menus, buyer requirements, house rules, and all our models’ verified links in one place.",
    "Hey {first}—you found us 💋 Hit <b>💌 DM Now</b> to pop open your hub: menus, buyer requirements, rules, and every model’s socials.",
    "{mention} slipped in like a midnight secret… 😏 Tap <b>💌 DM Now</b> for the full portal: menus, requirements, rules, and our verified link pages.",
    "Look who wandered in—{mention}. Be bold 💋 Press <b>💌 DM Now</b> to open menus, buyer info, rules, and find all our models elsewhere.",
    "Welcome, {mention}! 😈 One tap on <b>💌 DM Now</b> unlocks your hub—model menus, buyer requirements, rules, and verified socials.",
]

# ── Randomized goodbyes (by reason) ───────────────────────────────────────────
GOODBYE_LEFT = [
    "Kiss goodbye, {mention} 💋 Come back when you’re feeling naughty.",
    "{first} slipped out of the Sanctuary… we’ll keep a spot warm 😈",
]
GOODBYE_KICKED = [
    "{mention} couldn’t handle the heat and got poofed ✨",
    "Removed: {mention}. Play fair or don’t play at all 💋",
]
GOODBYE_BANNED = [
    "Banished with a blush—good luck out there, {mention} 😉",
    "{first} triggered the sigils. Permanent exile enacted 🔥",
]

# ── De-dupe (avoid double fires from service + member_updated) ────────────────
_recent: Dict[Tuple[int, int, str], float] = {}
DEDUP_WINDOW = 90.0  # seconds

def _seen(chat_id: int, user_id: int, kind: str) -> bool:
    now = time.time()
    key = (chat_id, user_id, kind)
    last = _recent.get(key, 0.0)
    if now - last < DEDUP_WINDOW:
        return True
    _recent[key] = now
    # prune stale
    for k, ts in list(_recent.items()):
        if now - ts > 5 * DEDUP_WINDOW:
            _recent.pop(k, None)
    return False

def _mention(user: Optional[User]) -> str:
    if not user:
        return "there"
    safe = (user.first_name or "there").replace("<", "&lt;").replace(">", "&gt;")
    return f"<a href='tg://user?id={user.id}'>{safe}</a>"

def _kb(dm_username: Optional[str]) -> InlineKeyboardMarkup:
    rows = []
    # Row 1: DM deep link (portal)
    if dm_username:
        rows.append([InlineKeyboardButton(BTN_DM, url=f"https://t.me/{dm_username}?start=ready")])
    # Row 2: Menus
    rows.append([InlineKeyboardButton(BTN_MENU, callback_data="open:menus")])
    # Row 3: Rules + Buyer Requirements
    rows.append([
        InlineKeyboardButton(BTN_RULES, callback_data="dmf_rules"),
        InlineKeyboardButton(BTN_BUYER, callback_data="dmf_buyer"),
    ])
    return InlineKeyboardMarkup(rows)

async def _send_welcome(client: Client, chat_id: int, user: Optional[User], reply_to: Optional[int] = None):
    if not WELCOME_ENABLE or (user and user.is_bot):
        return
    me = await client.get_me()
    kb = _kb(me.username)
    text = random.choice(WELCOME_LINES).format(
        mention=_mention(user),
        first=(user.first_name if user else "there"),
    )
    try:
        if WELCOME_PHOTO:
            await client.send_photo(chat_id, WELCOME_PHOTO, caption=text, reply_markup=kb)
        else:
            await client.send_message(chat_id, text, reply_markup=kb, reply_to_message_id=reply_to or 0)
    except Exception:
        await client.send_message(chat_id, text, reply_markup=kb)

async def _send_goodbye(client: Client, chat_id: int, user: Optional[User], reason: str):
    if not GOODBYE_ENABLE or (user and user.is_bot):
        return
    pool = GOODBYE_LEFT
    if reason == "kicked":
        pool = GOODBYE_KICKED
    elif reason == "banned":
        pool = GOODBYE_BANNED

    text = random.choice(pool).format(
        mention=_mention(user),
        first=(user.first_name if user else "They"),
    )
    try:
        if GOODBYE_PHOTO:
            await client.send_photo(chat_id, GOODBYE_PHOTO, caption=text)
        else:
            await client.send_message(chat_id, text)
    except Exception:
        pass

async def _unset_dmready_and_notify(client: Client, user: User, chat_id: int, reason: str):
    """Unset DM-ready if present, and ping OWNER_ID once."""
    try:
        removed = _dm.unset_dm_ready_global(user.id)
    except Exception:
        removed = False
    if removed and OWNER_ID:
        try:
            uname = f"@{user.username}" if getattr(user, "username", None) else ""
            mention = f"{user.first_name or 'User'} {uname}".strip()
            await client.send_message(
                OWNER_ID,
                f"⬅️ DM-ready removed — <b>{mention}</b> (<code>{user.id}</code>)\n"
                f"Reason: <b>{reason}</b> in <code>{chat_id}</code>"
            )
        except Exception:
            pass

def register(app: Client):

    # Classic service “new chat members”
    @app.on_message(filters.group & filters.new_chat_members)
    async def on_service_join(client: Client, m: Message):
        for u in m.new_chat_members:
            if _seen(m.chat.id, u.id, "join"):
                continue
            await _send_welcome(client, m.chat.id, u, reply_to=m.id)
        if WELCOME_DELETE_SERVICE:
            with contextlib.suppress(Exception):
                await m.delete()

    # Classic service “left chat member”
    @app.on_message(filters.group & filters.left_chat_member)
    async def on_service_left(client: Client, m: Message):
        # If you only want this to apply to certain groups, enforce here:
        if SANCTUARY_IDS and m.chat.id not in SANCTUARY_IDS:
            return

        u = m.left_chat_member
        if not u:
            return
        if _seen(m.chat.id, u.id, "leave"):
            return
        await _send_goodbye(client, m.chat.id, u, reason="left")
        await _unset_dmready_and_notify(client, u, m.chat.id, "left")
        if GOODBYE_DELETE_SERVICE:
            with contextlib.suppress(Exception):
                await m.delete()

    # Member updates (works even if join/leave service messages are hidden)
    @app.on_chat_member_updated()
    async def on_member_updated(client: Client, upd: ChatMemberUpdated):
        chat = upd.chat
        if not chat or chat.type == ChatType.PRIVATE:
            return
        # Apply only to Sanctuary groups if provided
        if SANCTUARY_IDS and chat.id not in SANCTUARY_IDS:
            return

        old = upd.old_chat_member
        new = upd.new_chat_member
        user = (new.user or (old.user if old else None))
        if not user:
            return

        # Joined/approved → MEMBER
        if new.status == ChatMemberStatus.MEMBER and (not old or old.status != ChatMemberStatus.MEMBER):
            if not _seen(chat.id, user.id, "join"):
                await _send_welcome(client, chat.id, user)
            return

        # Left / kicked / banned → remove DM-ready
        if new.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            if _seen(chat.id, user.id, "leave"):
                return
            if new.status == ChatMemberStatus.BANNED:
                reason = "banned"
            else:
                # If an admin performed the action and it's not the same user, treat as "kicked"
                if getattr(upd, "from_user", None) and upd.from_user.id != user.id:
                    reason = "kicked"
                else:
                    reason = "left"
            await _send_goodbye(client, chat.id, user, reason=reason)
            await _unset_dmready_and_notify(client, user, chat.id, reason=reason)
            return
