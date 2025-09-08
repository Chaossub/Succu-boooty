# dm_foolproof.py
import os, time
from datetime import datetime, timezone
from typing import Optional, List
from pyrogram import Client, filters, enums
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.errors import MessageNotModified
from pymongo import MongoClient

# =========================
# ENV helpers & fallbacks
# =========================
def _parse_ids_csv(val: Optional[str]) -> List[int]:
    out: List[int] = []
    if not val:
        return out
    for tok in val.replace(" ", "").split(","):
        if not tok:
            continue
        try:
            out.append(int(tok))
        except Exception:
            pass
    return out

_MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not _MONGO_URL:
    raise RuntimeError("MONGO_URL / MONGODB_URI / MONGO_URI is required in ENV for DM-ready persistence.")
_DB_NAME = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

# Accept any of these for the sanctuary group(s)
_group_env = (
    os.getenv("MAIN_GROUP_ID") or
    os.getenv("SUCCUBUS_SANCTUARY") or
    os.getenv("SANCTUARY_GROUP_IDS") or
    ""
)
SANCTUARY_GROUP_IDS: List[int] = _parse_ids_csv(_group_env)
MAIN_GROUP_ID = SANCTUARY_GROUP_IDS[0] if SANCTUARY_GROUP_IDS else 0  # primary for legacy handlers

# Suppress owner alert for these user_ids (defaults to OWNER_ID so you don't alert on yourself)
SUPPRESS_ALERT_IDS = set(_parse_ids_csv(os.getenv("SUPPRESS_DMREADY_ALERT_IDS", str(OWNER_ID))))

# =========================
# Mongo
# =========================
_mcli = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=10000)
_db = _mcli[_DB_NAME]
col_dm = _db.get_collection(os.getenv("DM_READY_COLLECTION", "dm_ready"))

# =========================
# Helpers
# =========================
def _now_ts() -> int:
    return int(time.time())

def _hms(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s and not parts: parts.append(f"{s}s")
    return " ".join(parts) or "0s"

def _welcome_text() -> str:
    return (
        "🔥 Welcome to SuccuBot 🔥\n"
        "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, "
        "flirty, and flowing.\n\n"
        "✨ Use the menu below to navigate!"
    )

def _main_kb():
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    def _btn(text, data): return InlineKeyboardButton(text, callback_data=data)
    return InlineKeyboardMarkup([
        [_btn("💕 Menus", "menus")],
        [_btn("👑 Contact Admins", "admins")],
        [_btn("🔥 Find Our Models Elsewhere", "models")],
        [_btn("❓ Help", "help")],
    ])

async def _send_main_panel(msg: Message):
    await msg.reply_text(_welcome_text(), reply_markup=_main_kb(), disable_web_page_preview=True)

async def _notify_owner_new_dm_ready(c: Client, user_id: int, name: str, username: Optional[str], ts: int):
    if not OWNER_ID:
        return
    uname = f"@{username}" if username else ""
    when = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        "🆕 *New DM-ready user*\n"
        f"- Name: {name} {uname}\n"
        f"- ID: `{user_id}`\n"
        f"- Since: {when}"
    )
    try:
        await c.send_message(OWNER_ID, text, disable_web_page_preview=True)
    except Exception:
        pass  # don't break flow if owner can't be notified

async def _mark_dm_ready_once(c: Client, user_id: int, name: str, username: Optional[str]):
    # Only insert + notify if not already present
    if col_dm.find_one({"user_id": user_id}):
        return False
    ts = _now_ts()
    col_dm.insert_one({
        "user_id": user_id,
        "name": name,
        "username": username,
        "ts": ts
    })
    # Notify unless suppressed
    if user_id not in SUPPRESS_ALERT_IDS:
        await _notify_owner_new_dm_ready(c, user_id, name, username, ts)
    return True

# =========================
# Registration
# =========================
def register(app: Client):

    # /start shows the panel and marks once (only for real incoming user messages)
    @app.on_message(filters.command("start") & filters.private & filters.incoming)
    async def _on_start(c: Client, m: Message):
        if m.from_user and not m.from_user.is_bot:
            await _mark_dm_ready_once(c, m.from_user.id, m.from_user.first_name or "Someone", m.from_user.username)
        await _send_main_panel(m)

    # Universal "Home"
    @app.on_callback_query(filters.regex(r"^home$"))
    async def _go_home(c: Client, q):
        try:
            await q.message.edit_text(
                _welcome_text(),
                reply_markup=_main_kb(),
                disable_web_page_preview=True
            )
        except MessageNotModified:
            try:
                await q.message.edit_reply_markup(_main_kb())
            except MessageNotModified:
                pass
        except Exception:
            await _send_main_panel(q.message)

    # Robust /dmreadylist (skips legacy bad docs)
    @app.on_message(filters.command("dmreadylist"))
    async def _dmready_list(c: Client, m: Message):
        raw = list(col_dm.find().sort("ts", 1))
        users = [u for u in raw if "user_id" in u]
        if not users:
            await m.reply_text("📭 No DM-ready users yet.")
            return
        now = _now_ts()
        lines = ["📋 DM-ready (all)"]
        for u in users:
            uid = u.get("user_id")
            name = u.get("name") or "Someone"
            uname = f"@{u.get('username')}" if u.get("username") else ""
            ts = int(u.get("ts", now))
            age = _hms(now - ts)
            since = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            lines.append(f"- {name} {uname}\n   id: {uid} — since {since} ({age})")
        await m.reply_text("\n".join(lines))

    # FIRST inbound private user message marks DM-ready once (ignore bot/outgoing)
    @app.on_message(filters.private & filters.incoming & ~filters.service)
    async def _on_any_private(c: Client, m: Message):
        if not m.from_user or m.from_user.is_bot:
            return
        await _mark_dm_ready_once(
            c,
            m.from_user.id,
            m.from_user.first_name or "Someone",
            m.from_user.username
        )

    # === Auto-remove DM-ready when they leave/kicked from Sanctuary group(s) ===
    if SANCTUARY_GROUP_IDS:
        # Membership status change updates
        @app.on_chat_member_updated()
        async def _on_cm_update(c: Client, ev: ChatMemberUpdated):
            try:
                chat_id = ev.chat.id
                if chat_id not in SANCTUARY_GROUP_IDS:
                    return
                status = ev.new_chat_member.status
                user = ev.new_chat_member.user
            except Exception:
                return
            if status in (enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.KICKED):
                col_dm.delete_one({"user_id": user.id})

        # Some clients emit left_chat_member messages
        @app.on_message(filters.left_chat_member)
        async def _on_left(c: Client, m: Message):
            try:
                if m.chat and m.chat.id not in SANCTUARY_GROUP_IDS:
                    return
                user = m.left_chat_member
                if user:
                    col_dm.delete_one({"user_id": user.id})
            except Exception:
                pass
