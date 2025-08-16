# dm_foolproof.py
# DM-ready flow, spicy intro, Contact/Help menu,
# direct-DM buttons (Roni/Ruby), identified & anonymous relay,
# and admin "reply anonymously" bridge back to user.
#
# /dmsetup caption default:
#   "Tap to DM for quick support—Contact menu, Help, and anonymous relay in one click."
# Override with:
#   DMSETUP_TEXT="your custom text"
#   DMSETUP_BTN="💌 DM Now"
#
# Other env:
#   OWNER_ID=6964994611
#   RONI_NAME=Roni
#   RUBY_ID=<ruby_user_id>      (optional)
#   RUBY_NAME=Ruby              (optional)
#   SUPER_ADMIN_ID=6964994611   (optional for showing admin help in DMs)
#   DM_READY_NOTIFY_MODE=first_time|always|off
#   DM_FORWARD_MODE=all|first|off
#   SHOW_RELAY_KB=first_time|always|daily

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
)
from pyrogram.errors import RPCError, FloodWait, UserIsBlocked, PeerIdInvalid

from req_store import ReqStore
_store = ReqStore()

# ========= CONFIG / ENV =========
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_ID = int(os.getenv("RUBY_ID", "0"))
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "6964994611"))

DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_time").lower()  # first_time|always|off
DM_FORWARD_MODE = os.getenv("DM_FORWARD_MODE", "all").lower()                   # all|first|off
SHOW_RELAY_KB = os.getenv("SHOW_RELAY_KB", "first_time").lower()                # first_time|always|daily

# ========= STATE =========
_awaiting_relay: Dict[int, Dict[str, bool]] = {}  # { user_id: {"anon": bool} }
_kb_last_shown: Dict[int, float] = {}
_anon_threads: Dict[str, int] = {}                # token -> user_id
_admin_pending_reply: Dict[int, str] = {}         # admin_id -> token

# ========= HELPERS =========
def _targets() -> List[int]:
    if OWNER_ID > 0:
        return [OWNER_ID]
    return _store.list_admins()

async def _is_admin(app: Client, chat_id: int, user_id: int) -> bool:
    if user_id in _store.list_admins():
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.privileges is not None or member.status in ("administrator", "creator")
    except Exception:
        return False

async def _notify_admins(app: Client, text: str):
    # NOTE: intentionally NO "Reply in DM" buttons here (per your request)
    for uid in _targets():
        try:
            await app.send_message(uid, text)
        except Exception:
            pass

async def _copy_to_admins(
    app: Client,
    src: Message,
    header: str,
    extra_kb: InlineKeyboardMarkup | None = None
):
    # NOTE: intentionally NO "Reply in DM" link; anon flow uses its own button.
    recips = _targets()
    if not recips:
        return
    for target in recips:
        try:
            await app.send_message(target, header, reply_markup=extra_kb)
            await app.copy_message(chat_id=target, from_chat_id=src.chat.id, message_id=src.id)
        except FloodWait as e:
            await asyncio.sleep(int(getattr(e, "value", 1)) or 1)
        except RPCError:
            continue

def _should_show_kb(uid: int) -> bool:
    if SHOW_RELAY_KB == "always":
        return True
    if SHOW_RELAY_KB == "first_time":
        return False
    if SHOW_RELAY_KB == "daily":
        last = _kb_last_shown.get(uid, 0)
        return (time.time() - last) >= 24 * 3600
    return False

def _mark_kb_shown(uid: int) -> None:
    _kb_last_shown[uid] = time.time()

# ========= UI =========
def _intro_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📇 Contact", callback_data="dmf_open_contact")],
        [InlineKeyboardButton("❔ Help", callback_data="dmf_show_help")],
    ])

def _relay_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    direct_row: List[InlineKeyboardButton] = []
    if OWNER_ID > 0:
        direct_row.append(InlineKeyboardButton(f"💬 Message {RONI_NAME} Directly", url=f"tg://user?id={OWNER_ID}"))
    if RUBY_ID > 0:
        direct_row.append(InlineKeyboardButton(f"💬 Message {RUBY_NAME} Directly", url=f"tg://user?id={RUBY_ID}"))
    if direct_row:
        rows.append(direct_row)
    rows.append([InlineKeyboardButton(f"📣 Relay to {RONI_NAME} (via bot)", callback_data="dmf_relay_start")])
    rows.append([InlineKeyboardButton("🙈 Relay Anonymously", callback_data="dmf_relay_anon_start")])
    return InlineKeyboardMarkup(rows)

def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancel", callback_data="dmf_relay_cancel")]])

def _spicy_intro(name: Optional[str]) -> str:
    name = name or "there"
    return f"Welcome to the Sanctuary, {name} 😈\nYou’re all set — need us? Tap a button below 👇"

def _dm_help_text(uid: int, is_owner_or_super: bool) -> str:
    lines = ["<b>What you can do here</b>"]
    lines += [
        "\n🛠 <b>General</b>",
        "/hi — say hi",
        "/ping — health check",
        "/message — contact options",
        "/help — full help",
        "/cancel — cancel current action",
    ]
    lines += [
        "\n📩 <b>DM Ready</b>",
        "/dmready — mark yourself ready",
        "/dmunready — remove ready",
    ]
    lines += [
        "\n📋 <b>Requirements</b>",
        "/reqstatus — check your status",
    ]
    if is_owner_or_super:
        lines += [
            "\n👑 <b>Admin (for you)</b>",
            "/dmreadylist — list DM-ready",
            "/dmnudge <@user|id> — nudge",
            "/reqexempt list/add/remove — exemptions",
            "/reqadd <amount>, /reqgame, /reqnote <text>, /reqexport",
            "/reqadmins — manage req-admins",
            "/reqscan, /reqenforce — (group)",
            "/trackall — (group)",
        ]
    return "\n".join(lines)

# ========= REGISTER =========
def register(app: Client):
    # 1) Group: deep-link to open DM
    @app.on_message(filters.command("dmsetup") & ~filters.scheduled)
    async def dmsetup(client: Client, m: Message):
        if not await _is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a username set to create a DM button.")

        url = f"https://t.me/{me.username}?start=ready"
        btn_label = os.getenv("DMSETUP_BTN", "💌 DM Now")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(btn_label, url=url)]])
        text = os.getenv(
            "DMSETUP_TEXT",
            "Tap to DM for quick support—Contact menu, Help, and anonymous relay in one click."
        )
        await m.reply_text(text, reply_markup=kb)

    # 2) DM: /message (also /contact, /menu) → open contact options directly
    @app.on_message(filters.private & filters.command(["message", "contact", "menu"]) & ~filters.scheduled)
    async def dm_message_menu(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _store.is_dm_ready_global(uid):
            _store.set_dm_ready_global(uid, True, by_admin=False)
            if DM_READY_NOTIFY_MODE in ("always", "first_time") and _targets():
                await _notify_admins(client, f"🔔 DM-ready: {m.from_user.mention} (<code>{uid}</code>) — via /message")
        await m.reply_text("How would you like to reach us?", reply_markup=_relay_kb())
        _mark_kb_shown(uid)

    # 3) DM: any message — admin reply bridge, user relay, spicy intro, pings/forward
    @app.on_message(filters.private & ~filters.scheduled)
    async def on_private_message(client: Client, m: Message):
        if not m.from_user:
            return
        uid = m.from_user.id

        # --- ADMIN REPLY MODE (responding to an anon thread) ---
        if uid in _admin_pending_reply:
            token = _admin_pending_reply.pop(uid)
            target_uid = _anon_threads.get(token)
            if not target_uid:
                return await m.reply_text("This anonymous thread has expired or was cleared.")
            header = f"📮 Message from {RONI_NAME}:"
            try:
                await client.send_message(target_uid, header)
                await client.copy_message(chat_id=target_uid, from_chat_id=m.chat.id, message_id=m.id)
                await m.reply_text("Sent anonymously ✅")
            except RPCError:
                await m.reply_text("Could not deliver message (user may have blocked the bot).")
            return

        # --- USER RELAY MODE (if user chose relay) ---
        if uid in _awaiting_relay:
            anon = _awaiting_relay.pop(uid).get("anon", False)
            if anon:
                token = secrets.token_urlsafe(8)
                _anon_threads[token] = uid
                kb = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("↩️ Reply anonymously", callback_data=f"dmf_anon_reply:{token}")]]
                )
                await _copy_to_admins(client, m, header=f"📨 Anonymous relay to {RONI_NAME}", extra_kb=kb)
                await m.reply_text(f"Sent anonymously to {RONI_NAME} ✅")
            else:
                header = f"📨 Relay to {RONI_NAME} from {m.from_user.mention} (<code>{uid}</code>)"
                await _copy_to_admins(client, m, header=header)
                await m.reply_text(f"Sent to {RONI_NAME} ✅")
            return

        # --- NORMAL DM FLOW ---
        first_time = not _store.is_dm_ready_global(uid)
        _store.set_dm_ready_global(uid, True, by_admin=False)

        # Ping admin about readiness (per mode) — NO reply link
        should_ping_ready = (
            DM_READY_NOTIFY_MODE == "always" or
            (DM_READY_NOTIFY_MODE == "first_time" and first_time)
        ) and bool(_targets())
        if should_ping_ready:
            await _notify_admins(
                client,
                f"🔔 DM-ready: {m.from_user.mention} (<code>{uid}</code>) — via private chat"
            )

        # Optional: auto-forward this DM (skip /start noise) — NO reply link
        is_start_cmd = bool(m.text and m.text.strip().lower().startswith("/start"))
        should_forward = (
            not is_start_cmd and
            (DM_FORWARD_MODE == "all" or (DM_FORWARD_MODE == "first" and first_time)) and
            bool(_targets())
        )
        if should_forward:
            header = f"💌 New DM from {m.from_user.mention} (<code>{uid}</code>):"
            await _copy_to_admins(client, m, header=header)

        # Always show intro on /start in DMs so the two buttons appear every time
        show_intro = False
        if is_start_cmd:
            show_intro = True
        elif first_time and SHOW_RELAY_KB == "first_time":
            show_intro = True
        elif SHOW_RELAY_KB in ("always", "daily") and _should_show_kb(uid):
            show_intro = True

        if show_intro:
            await m.reply_text(_spicy_intro(m.from_user.first_name if m.from_user else None), reply_markup=_intro_kb())
            _mark_kb_shown(uid)

    # 4) Callback: open contact options
    @app.on_callback_query(filters.regex("^dmf_open_contact$"))
    async def cb_open_contact(client: Client, cq: CallbackQuery):
        await cq.message.reply_text("How would you like to reach us?", reply_markup=_relay_kb())
        await cq.answer()

    # 5) Callback: show DM help (only what they can use)
    @app.on_callback_query(filters.regex("^dmf_show_help$"))
    async def cb_show_help(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        is_owner_or_super = (uid == OWNER_ID) or (uid == SUPER_ADMIN_ID)
        await cq.message.reply_text(_dm_help_text(uid, is_owner_or_super))
        await cq.answer()

    # 6) Callbacks: start relay (identified / anonymous) to Roni
    @app.on_callback_query(filters.regex("^dmf_relay_start$"))
    async def cb_relay_start(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        if not _targets():
            return await cq.answer("No admin configured to receive relays.", show_alert=True)
        _awaiting_relay[uid] = {"anon": False}
        await cq.message.reply_text(
            f"Okay! Type the message you want me to send to {RONI_NAME}.",
            reply_markup=_cancel_kb()
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^dmf_relay_anon_start$"))
    async def cb_relay_anon_start(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        if not _targets():
            return await cq.answer("No admin configured to receive relays.", show_alert=True)
        _awaiting_relay[uid] = {"anon": True}
        await cq.message.reply_text(
            f"You're anonymous. Type the message you want me to send to {RONI_NAME}.",
            reply_markup=_cancel_kb()
        )
        await cq.answer()

    # 7) Callback: admin chooses to reply to an anonymous thread (one-shot)
    @app.on_callback_query(filters.regex("^dmf_anon_reply:"))
    async def cb_anon_reply(client: Client, cq: CallbackQuery):
        admin_id = cq.from_user.id
        token = cq.data.split(":", 1)[1]
        if admin_id not in _targets():
            return await cq.answer("Only admins can reply.", show_alert=True)
        if token not in _anon_threads:
            return await cq.answer("That anonymous thread has expired.", show_alert=True)
        _admin_pending_reply[admin_id] = token
        await cq.message.reply_text("Reply mode enabled. Type your reply now — it will be sent anonymously. Use /cancel to exit.")
        await cq.answer("Reply to this message to send anonymously.")

    # 8) Callback: cancel user-side relay
    @app.on_callback_query(filters.regex("^dmf_relay_cancel$"))
    async def cb_relay_cancel(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        _awaiting_relay.pop(uid, None)
        await cq.answer("Relay canceled.", show_alert=False)
        try:
            await cq.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    # 9) Admin/manual DM-ready toggle (reply or self)
    @app.on_message(filters.command(["dmready", "dmunready"]) & ~filters.scheduled)
    async def dm_ready_toggle(client: Client, m: Message):
        ready = m.command[0].lower() == "dmready"
        target_id = m.from_user.id
        if m.reply_to_message and m.reply_to_message.from_user:
            if not await _is_admin(client, m.chat.id, m.from_user.id):
                return await m.reply_text("Admins only for toggling others.")
            target_id = m.reply_to_message.from_user.id

        _store.set_dm_ready_global(target_id, ready, by_admin=(target_id != m.from_user.id))
        status = "✅ DM-ready (global)" if ready else "❌ Not DM-ready"
        who = "you" if target_id == m.from_user.id else f"<code>{target_id}</code>"
        await m.reply_text(f"{status} set for {who}.")

        if ready and _targets():
            try:
                u = await client.get_users(target_id)
                await _notify_admins(client, f"🔔 DM-ready: {u.mention} (<code>{target_id}</code>) — set by admin")
            except Exception:
                await _notify_admins(client, f"🔔 DM-ready: <code>{target_id}</code> — set by admin")

    # 10) List global DM-ready
    @app.on_message(filters.command("dmreadylist") & ~filters.scheduled)
    async def dmreadylist(client: Client, m: Message):
        dm = _store.list_dm_ready_global()
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

    # 11) Admin nudge
    @app.on_message(filters.command("dmnudge") & ~filters.scheduled)
    async def dmnudge(client: Client, m: Message):
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
