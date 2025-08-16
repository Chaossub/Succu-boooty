# dm_foolproof.py
# DM entry & messaging helper:
#  • /start in DM -> spicy welcome with [💕 Menu] + [❔ Help]
#  • “💕 Menu” callback -> handled by handlers/menu.py (four tabs: Roni, Ruby, Rin, Savy)
#  • /message -> Contact & Messaging panel (Roni/Ruby direct, Anonymous, Suggestions)
#  • Anonymous bridge: owner can reply anonymously back
#  • Admin tools: /dmready, /dmunready, /dmreadylist, /dmnudge
#  • Group helper: /dmsetup -> deep link to DM

import os
import time
import asyncio
import secrets
from typing import Optional, List, Dict

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from pyrogram.errors import RPCError, FloodWait, UserIsBlocked, PeerIdInvalid

# If you use a central store for admins/dm_ready, import it here.
# This is optional; file will still run with simple defaults.
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    class _DummyStore:
        def __init__(self): self._dm = set(); self._admins = set()
        def is_dm_ready_global(self, uid:int)->bool: return uid in self._dm
        def set_dm_ready_global(self, uid:int, ready:bool, by_admin:bool=False): 
            (self._dm.add(uid) if ready else self._dm.discard(uid))
        def list_dm_ready_global(self): return {str(x): True for x in self._dm}
        def list_admins(self): return list(self._admins)
    _store = _DummyStore()

# ========= CONFIG / ENV =========
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_ID = int(os.getenv("RUBY_ID", "0"))
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "6964994611"))

DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_time").lower()  # first_time|always|off
DM_FORWARD_MODE       = os.getenv("DM_FORWARD_MODE", "off").lower()             # off|first|all
SHOW_RELAY_KB         = os.getenv("SHOW_RELAY_KB", "first_time").lower()        # first_time|daily

RULES_TEXT = os.getenv("RULES_TEXT", "")
BUYER_REQ_TEXT = os.getenv("BUYER_REQ_TEXT", "")
RULES_PHOTO = os.getenv("RULES_PHOTO")
BUYER_REQ_PHOTO = os.getenv("BUYER_REQ_PHOTO")

# ========= STATE =========
# pending action per user: {"kind": "anon" | "suggest", "anon": bool}
_pending: Dict[int, Dict[str, bool]] = {}
_kb_last_shown: Dict[int, float] = {}
# anon bridges
_anon_threads: Dict[str, int] = {}         # token -> user_id
_admin_pending_reply: Dict[int, str] = {}  # admin_id -> token

# ========= HELPERS =========
def _targets_owner_only() -> List[int]:
    return [OWNER_ID] if OWNER_ID > 0 else []

def _targets_any() -> List[int]:
    if OWNER_ID > 0:
        return [OWNER_ID]
    try:
        return _store.list_admins()
    except Exception:
        return []

async def _is_admin(app: Client, chat_id: int, user_id: int) -> bool:
    if user_id in getattr(_store, "list_admins", lambda: [])() or user_id in (OWNER_ID, SUPER_ADMIN_ID):
        return True
    try:
        m = await app.get_chat_member(chat_id, user_id)
        return (m.privileges is not None) or (m.status in ("administrator", "creator"))
    except Exception:
        return False

def _should_show_kb_daily(uid: int) -> bool:
    last = _kb_last_shown.get(uid, 0)
    return (time.time() - last) >= 24 * 3600

def _mark_kb_shown(uid: int) -> None:
    _kb_last_shown[uid] = time.time()

async def _notify(app: Client, targets: List[int], text: str, reply_markup: InlineKeyboardMarkup | None = None):
    for uid in targets:
        try:
            await app.send_message(uid, text, reply_markup=reply_markup)
        except Exception:
            pass

async def _copy_to(app: Client, targets: List[int], src: Message, header: str, reply_markup: InlineKeyboardMarkup | None = None):
    for uid in targets:
        try:
            await app.send_message(uid, header, reply_markup=reply_markup)
            await app.copy_message(chat_id=uid, from_chat_id=src.chat.id, message_id=src.id)
        except FloodWait as e:
            await asyncio.sleep(int(getattr(e, "value", 1)) or 1)
        except RPCError:
            continue

# ========= UI =========
def _welcome_kb() -> InlineKeyboardMarkup:
    # Short welcome = “💕 Menu” + “❔ Help”
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("❔ Help", callback_data="dmf_show_help")],
    ])

def _contact_panel_kb() -> InlineKeyboardMarkup:
    rows = []
    row_direct = []
    if OWNER_ID > 0:
        row_direct.append(InlineKeyboardButton(f"💌 Message {RONI_NAME}", url=f"tg://user?id={OWNER_ID}"))
    if RUBY_ID:
        row_direct.append(InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
    if row_direct:
        rows.append(row_direct)
    rows.append([InlineKeyboardButton("🙈 Send anonymous message to the admins", callback_data="dmf_anon_admins")])
    rows.append([InlineKeyboardButton("💡 Send a suggestion", callback_data="dmf_open_suggest")])
    return InlineKeyboardMarkup(rows)

def _suggest_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Send suggestion", callback_data="dmf_suggest_ident")],
        [InlineKeyboardButton("🙈 Send suggestion anonymously", callback_data="dmf_suggest_anon")],
        [InlineKeyboardButton("✖️ Cancel", callback_data="dmf_cancel")],
    ])

def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancel", callback_data="dmf_cancel")]])

def _spicy_intro(name: Optional[str]) -> str:
    name = name or "there"
    return f"Welcome to the Sanctuary, {name} 😈\nYou’re all set — tap Menu to see your options 👇"

# Fallback help if central builder not available
def _fallback_full_help(is_admin: bool) -> str:
    lines = ["<b>SuccuBot Commands</b>"]
    lines += [
        "\n🛠 <b>General</b>",
        "/help — show this menu",
        "/menu — open the model menus",
        "/message — contact & anonymous options",
        "/cancel — cancel current action",
        "/ping — bot check",
    ]
    lines += [
        "\n💌 <b>DM Ready</b>",
        "/dmready, /dmunready, /dmreadylist, /dmnudge",
    ]
    if is_admin:
        lines += [
            "\n⚒ <b>Admin</b>",
            "… (your moderation/federation/flyers commands if present)",
        ]
    return "\n".join(lines)

def _build_full_help_text(is_admin: bool) -> str:
    try:
        from handlers.help_cmd import _build_help_text as _central_help
        return _central_help(is_admin)
    except Exception:
        return _fallback_full_help(is_admin)

# ========= REGISTER =========
def register(app: Client):

    # 1) Group helper: post a DM deep link to onboard users
    @app.on_message(filters.command("dmsetup") & ~filters.scheduled)
    async def dmsetup(client: Client, m: Message):
        if not await _is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a username set to create a DM button.")
        url = f"https://t.me/{me.username}?start=ready"
        btn = os.getenv("DMSETUP_BTN", "💌 DM Now")
        text = os.getenv("DMSETUP_TEXT", "Tap to DM and open the Menu.")
        await m.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(btn, url=url)]]))

    # 2) DM: /message → contact & messaging panel
    @app.on_message(filters.private & filters.command(["message", "contact"]) & ~filters.scheduled)
    async def dm_message_panel(client: Client, m: Message):
        uid = m.from_user.id
        first_time = not _store.is_dm_ready_global(uid)
        if first_time:
            _store.set_dm_ready_global(uid, True, by_admin=False)
            if DM_READY_NOTIFY_MODE in ("always", "first_time") and _targets_any():
                await _notify(client, _targets_any(), f"🔔 DM-ready: {m.from_user.mention} (<code>{uid}</code>) — via /message")
        await m.reply_text("How would you like to reach us?", reply_markup=_contact_panel_kb())
        _mark_kb_shown(uid)

    # 3) DM: general inbox — handle pending flows, anon-reply bridge, welcome, (optional) forward
    @app.on_message(filters.private & ~filters.command(["message", "contact"]) & ~filters.scheduled)
    async def on_private_message(client: Client, m: Message):
        if not m.from_user:
            return
        uid = m.from_user.id

        # OWNER: anonymous reply bridge
        if uid in _admin_pending_reply:
            token = _admin_pending_reply.pop(uid)
            target_uid = _anon_threads.get(token)
            if not target_uid:
                return await m.reply_text("This anonymous thread has expired or was cleared.")
            if uid != OWNER_ID:
                return await m.reply_text("Only the owner can send anonymous replies.")
            try:
                await client.send_message(target_uid, f"📮 Message from {RONI_NAME}:")
                await client.copy_message(chat_id=target_uid, from_chat_id=m.chat.id, message_id=m.id)
                await m.reply_text("Sent anonymously ✅")
            except RPCError:
                await m.reply_text("Could not deliver message (user may have blocked the bot).")
            return

        # User pending flows (anon or suggestion)
        if uid in _pending:
            spec = _pending.pop(uid)
            kind = spec.get("kind")
            anon = spec.get("anon", False)
            targets = _targets_owner_only()
            if not targets:
                return await m.reply_text("Owner is not configured. Please try again later.")

            if kind == "anon":
                token = secrets.token_urlsafe(8)
                _anon_threads[token] = uid
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Reply anonymously", callback_data=f"dmf_anon_reply:{token}")]])
                await _copy_to(client, targets, m, header="📨 Anonymous message", reply_markup=kb)
                return await m.reply_text("Sent anonymously ✅")

            if kind == "suggest":
                if anon:
                    token = secrets.token_urlsafe(8)
                    _anon_threads[token] = uid
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Reply anonymously", callback_data=f"dmf_anon_reply:{token}")]])
                    await _copy_to(client, targets, m, header="💡 Anonymous suggestion", reply_markup=kb)
                    return await m.reply_text("Suggestion sent anonymously ✅")
                else:
                    header = f"💡 Suggestion from {m.from_user.mention} (<code>{uid}</code>)"
                    await _copy_to(client, targets, m, header=header)
                    return await m.reply_text("Thanks! Your suggestion was sent ✅")

        # First-time DM setup + optional notify
        first_time = not _store.is_dm_ready_global(uid)
        if first_time:
            _store.set_dm_ready_global(uid, True, by_admin=False)
            if DM_READY_NOTIFY_MODE in ("always", "first_time") and _targets_any():
                await _notify(client, _targets_any(), f"🔔 DM-ready: {m.from_user.mention} (<code>{uid}</code>) — via private chat")

        # Optional auto-forward of DMs to owner/admins (default OFF to avoid flood)
        is_start_cmd = bool(m.text and m.text.strip().lower().startswith("/start"))
        if DM_FORWARD_MODE in ("all", "first") and not is_start_cmd and _targets_any():
            if DM_FORWARD_MODE == "all" or (DM_FORWARD_MODE == "first" and first_time):
                await _copy_to(client, _targets_any(), m, header=f"💌 New DM from {m.from_user.mention} (<code>{uid}</code>):")

        # Show short welcome on /start, first DM, or daily reminder
        show_intro = is_start_cmd or (first_time and SHOW_RELAY_KB == "first_time") or (SHOW_RELAY_KB == "daily" and _should_show_kb_daily(uid))
        if show_intro:
            await m.reply_text(_spicy_intro(m.from_user.first_name if m.from_user else None), reply_markup=_welcome_kb())
            _mark_kb_shown(uid)

    # 4) CONTACT & HELP callbacks (Menu callback itself is handled by handlers/menu.py)
    @app.on_callback_query(filters.regex("^dmf_show_help$"))
    async def cb_show_help(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        is_admin = (uid in (OWNER_ID, SUPER_ADMIN_ID)) or (uid in getattr(_store, "list_admins", lambda: [])())
        await cq.message.reply_text(_build_full_help_text(is_admin))
        await cq.answer()

    # Open contact panel (also used by /message)
    @app.on_callback_query(filters.regex("^dmf_open_direct$"))
    async def cb_open_direct(client: Client, cq: CallbackQuery):
        await cq.message.reply_text("Choose how you want to reach us:", reply_markup=_contact_panel_kb())
        await cq.answer()

    # Anonymous message start
    @app.on_callback_query(filters.regex("^dmf_anon_admins$"))
    async def cb_anon_admins(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        if not _targets_owner_only():
            return await cq.answer("Owner is not configured to receive messages.", show_alert=True)
        _pending[uid] = {"kind": "anon", "anon": True}
        await cq.message.reply_text("You're anonymous. Type the message you want me to send to the admins.", reply_markup=_cancel_kb())
        await cq.answer()

    # Suggestions flow
    @app.on_callback_query(filters.regex("^dmf_open_suggest$"))
    async def cb_open_suggest(client: Client, cq: CallbackQuery):
        await cq.message.reply_text("How would you like to send your suggestion?", reply_markup=_suggest_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex("^dmf_suggest_ident$"))
    async def cb_suggest_ident(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        if not _targets_owner_only():
            return await cq.answer("Owner is not configured to receive messages.", show_alert=True)
        _pending[uid] = {"kind": "suggest", "anon": False}
        await cq.message.reply_text("Great! Type your suggestion and I’ll send it to the admins.", reply_markup=_cancel_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex("^dmf_suggest_anon$"))
    async def cb_suggest_anon(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        if not _targets_owner_only():
            return await cq.answer("Owner is not configured to receive messages.", show_alert=True)
        _pending[uid] = {"kind": "suggest", "anon": True}
        await cq.message.reply_text("You're anonymous. Type your suggestion for the admins.", reply_markup=_cancel_kb())
        await cq.answer()

    # Anonymous reply bridge (owner)
    @app.on_callback_query(filters.regex("^dmf_anon_reply:"))
    async def cb_anon_reply(client: Client, cq: CallbackQuery):
        admin_id = cq.from_user.id
        token = cq.data.split(":", 1)[1]
        if admin_id != OWNER_ID:
            return await cq.answer("Only the owner can reply to anonymous messages.", show_alert=True)
        if token not in _anon_threads:
            return await cq.answer("That anonymous thread has expired.", show_alert=True)
        _admin_pending_reply[admin_id] = token
        await cq.message.reply_text("Reply mode enabled. Type your reply now — it will be sent anonymously. Use /cancel to exit.")
        await cq.answer("Reply to this message to send anonymously.")

    # Cancel any pending flow
    @app.on_callback_query(filters.regex("^dmf_cancel$"))
    async def cb_cancel(client: Client, cq: CallbackQuery):
        _pending.pop(cq.from_user.id, None)
        await cq.answer("Canceled.")
        try:
            await cq.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        try:
            await client.send_message(cq.from_user.id, "Canceled.", reply_markup=ReplyKeyboardRemove())
        except Exception:
            pass

    # 5) Admin / utility: dm-ready toggle & list, nudge
    @app.on_message(filters.command(["dmready", "dmunready"]) & ~filters.scheduled)
    async def dm_ready_toggle(client: Client, m: Message):
        ready = m.command[0].lower() == "dmready"
        target_id = m.from_user.id
        if m.reply_to_message and m.reply_to_message.from_user:
            if m.chat.type != "private" and not await _is_admin(client, m.chat.id, m.from_user.id):
                return await m.reply_text("Admins only for toggling others.")
            target_id = m.reply_to_message.from_user.id

        try:
            _store.set_dm_ready_global(target_id, ready, by_admin=(target_id != m.from_user.id))
        except Exception:
            pass
        status = "✅ DM-ready (global)" if ready else "❌ Not DM-ready"
        who = "you" if target_id == m.from_user.id else f"<code>{target_id}</code>"
        await m.reply_text(f"{status} set for {who}.")
        if ready and _targets_any():
            try:
                u = await client.get_users(target_id)
                await _notify(client, _targets_any(), f"🔔 DM-ready: {u.mention} (<code>{target_id}</code>) — set by admin")
            except Exception:
                await _notify(client, _targets_any(), f"🔔 DM-ready: <code>{target_id}</code> — set by admin")

    @app.on_message(filters.command("dmreadylist") & ~filters.scheduled)
    async def dmreadylist(client: Client, m: Message):
        try:
            dm = _store.list_dm_ready_global()
        except Exception:
            dm = {}
        if not dm:
            return await m.reply_text("No one is marked DM-ready (global) yet.")
        lines = []
        for uid_str in list(dm.keys())[:200]:
            uid = int(uid_str)
            try:
                u = await client.get_users(uid)
                lines.append(f"• {u.mention} (<code>{uid}</code>)")
            except Exception:
                lines.append(f"• <code>{uid}</code>")
        await m.reply_text("<b>DM-ready (global):</b>\n" + "\n".join(lines))

    @app.on_message(filters.command("dmnudge") & ~filters.scheduled)
    async def dmnudge(client: Client, m: Message):
        if m.chat.type == "private":
            # Owner or super in DM
            if m.from_user.id not in (OWNER_ID, SUPER_ADMIN_ID):
                return await m.reply_text("Admins only.")
        else:
            if not await _is_admin(client, m.chat.id, m.from_user.id):
                return await m.reply_text("Admins only.")
        target: Optional[int] = None
        if m.reply_to_message and m.reply_to_message.from_user:
            target = m.reply_to_message.from_user.id
        elif len(m.command) > 1:
            arg = m.command[1]
            if arg.isdigit():
                target = int(arg)
            else:
                try:
                    u = await client.get_users(arg)
                    target = u.id
                except Exception:
                    pass
        if not target:
            return await m.reply_text("Reply to a user or pass @username/user_id.")
        text = (
            "Hey! Quick nudge from the Sanctuary 💋\n\n"
            "Please keep your DMs open to receive content you purchase and game rewards. "
            "If you’d rather not, just let us know and we’ll arrange an alternative.\n\n"
            "Thanks for helping things run smoothly! 😇"
        )
        try:
            await client.send_message(target, text)
            await m.reply_text("Nudge sent ✅")
        except UserIsBlocked:
            await m.reply_text("User blocked the bot ❌")
        except (PeerIdInvalid, FloodWait, RPCError):
            await m.reply_text("Could not DM user (privacy/flood).")

