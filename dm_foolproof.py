# dm_foolproof.py
import os
import asyncio
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
OWNER_ID = int(os.getenv("OWNER_ID", "0"))        # Roni's user id (who receives relays/pings)
RONI_NAME = os.getenv("RONI_NAME", "Roni")        # Display name in buttons/text

# NEW: Ruby direct DM button
RUBY_ID = int(os.getenv("RUBY_ID", "0"))
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

# Notify/ping mode for DM-ready
DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_time").lower()  # first_time|always|off
# Forward users' DMs automatically
DM_FORWARD_MODE = os.getenv("DM_FORWARD_MODE", "all").lower()                   # all|first|off

# ========= STATE =========
# Users who clicked "relay" and whose NEXT DM should be relayed.
# { user_id: {"anon": bool} }
_awaiting_relay: Dict[int, Dict[str, bool]] = {}

def _targets() -> List[int]:
    # Primary: OWNER_ID, Fallback: req-admins
    if OWNER_ID > 0:
        return [OWNER_ID]
    return _store.list_admins()

# ========= UI =========
def _relay_kb() -> InlineKeyboardMarkup:
    """Buttons shown to the user in DM after marking DM-ready."""
    rows: List[List[InlineKeyboardButton]] = []

    # Row of direct DM buttons (Roni + Ruby if available)
    direct_row: List[InlineKeyboardButton] = []
    if OWNER_ID > 0:
        direct_row.append(InlineKeyboardButton(f"💬 Message {RONI_NAME} Directly", url=f"tg://user?id={OWNER_ID}"))
    if RUBY_ID > 0:
        direct_row.append(InlineKeyboardButton(f"💬 Message {RUBY_NAME} Directly", url=f"tg://user?id={RUBY_ID}"))
    if direct_row:
        rows.append(direct_row)

    # Relay options (to Roni via bot)
    rows.append([InlineKeyboardButton(f"📣 Relay to {RONI_NAME} (via bot)", callback_data="dmf_relay_start")])
    rows.append([InlineKeyboardButton("🙈 Relay Anonymously", callback_data="dmf_relay_anon_start")])

    return InlineKeyboardMarkup(rows)

def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancel", callback_data="dmf_relay_cancel")]])

# ========= HELPERS =========
async def _is_admin(app: Client, chat_id: int, user_id: int) -> bool:
    if user_id in _store.list_admins():
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.privileges is not None or member.status in ("administrator", "creator")
    except Exception:
        return False

async def _notify_admins(app: Client, text: str, reply_uid: Optional[int] = None):
    kb = None
    if reply_uid:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Reply in DM", url=f"tg://user?id={reply_uid}")]])
    for uid in _targets():
        try:
            await app.send_message(uid, text, reply_markup=kb)
        except Exception:
            pass

async def _copy_to_admins(app: Client, src: Message, header: str, reply_uid: Optional[int] = None):
    """Send header + copy the user's message to admins/owner (preserve media/text)."""
    tg_users = _targets()
    if not tg_users:
        return
    for target in tg_users:
        try:
            kb = None
            if reply_uid:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Reply in DM", url=f"tg://user?id={reply_uid}")]])
            await app.send_message(target, header, reply_markup=kb)
            await app.copy_message(chat_id=target, from_chat_id=src.chat.id, message_id=src.id)
        except FloodWait as e:
            await asyncio.sleep(int(getattr(e, "value", 1)) or 1)
        except RPCError:
            continue

# ========= REGISTER =========
def register(app: Client):
    # 1) ADMIN: deep-link to open DM
    @app.on_message(filters.command("dmsetup") & ~filters.scheduled)
    async def dmsetup(client: Client, m: Message):
        if not await _is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a username set to create a DM button.")
        url = f"https://t.me/{me.username}?start=ready"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💌 Open DM with the bot", url=url)]])
        await m.reply_text(
            "Tap the button to open a DM with me. Send any message there and you'll be marked DM-ready automatically.\n"
            f"You can message {RONI_NAME} directly, or ask me to relay your message if you prefer.",
            reply_markup=kb
        )

    # 2) PRIVATE: auto-ready + present relay options + optional auto-forward
    @app.on_message(filters.private & ~filters.scheduled)
    async def on_private_message(client: Client, m: Message):
        if not m.from_user:
            return
        uid = m.from_user.id

        # If they're in a relay flow, consume THIS message as the content and send it to Roni/admins
        if uid in _awaiting_relay:
            anon = _awaiting_relay.pop(uid).get("anon", False)
            if anon:
                header = f"📨 Anonymous relay to {RONI_NAME}"
                await _copy_to_admins(client, m, header=header, reply_uid=None)  # don't include reply link if anon
                await m.reply_text(f"Sent anonymously to {RONI_NAME} ✅")
            else:
                header = f"📨 Relay to {RONI_NAME} from {m.from_user.mention} (<code>{uid}</code>)"
                await _copy_to_admins(client, m, header=header, reply_uid=uid)
                await m.reply_text(f"Sent to {RONI_NAME} ✅")
            return  # Do not also run auto-forward/ready ping on the relayed message

        # Mark DM-ready (global), detect first-time
        first_time = not _store.is_dm_ready_global(uid)
        _store.set_dm_ready_global(uid, True, by_admin=False)

        # Ping about readiness (per mode)
        should_ping_ready = (
            DM_READY_NOTIFY_MODE == "always" or
            (DM_READY_NOTIFY_MODE == "first_time" and first_time)
        ) and bool(_targets())
        if should_ping_ready:
            await _notify_admins(
                client,
                f"🔔 DM-ready: {m.from_user.mention} (<code>{uid}</code>) — via private chat",
                reply_uid=uid
            )

        # Auto-forward this DM (per mode)
        should_forward = (
            DM_FORWARD_MODE == "all" or
            (DM_FORWARD_MODE == "first" and first_time)
        ) and bool(_targets())
        if should_forward:
            header = f"💌 New DM from {m.from_user.mention} (<code>{uid}</code>):"
            await _copy_to_admins(client, m, header=header, reply_uid=uid)

        # Show the relay options on first-time
        if first_time:
            await m.reply_text(
                "You're now DM-ready ✅\n\n"
                f"If you’d like, you can message {RONI_NAME} directly, message {RUBY_NAME} directly,"
                f" or have me relay your message:",
                reply_markup=_relay_kb()
            )

    # 3) Callbacks: start relay (identified / anonymous) to Roni
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

    @app.on_callback_query(filters.regex("^dmf_relay_cancel$"))
    async def cb_relay_cancel(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        _awaiting_relay.pop(uid, None)
        await cq.answer("Relay canceled.", show_alert=False)
        try:
            await cq.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    # 4) Admin/manual DM-ready toggle (reply or self)
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
                await _notify_admins(client, f"🔔 DM-ready: {u.mention} (<code>{target_id}</code>) — set by admin", reply_uid=target_id)
            except Exception:
                await _notify_admins(client, f"🔔 DM-ready: <code>{target_id}</code> — set by admin", reply_uid=target_id)

    # 5) List global DM-ready
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

    # 6) Admin nudge
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
