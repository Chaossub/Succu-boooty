import os
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import RPCError, FloodWait, UserIsBlocked, PeerIdInvalid

from req_store import ReqStore

_store = ReqStore()
_OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # optional: single owner to ping

async def _is_admin(app: Client, chat_id: int, user_id: int) -> bool:
    if user_id in _store.list_admins():
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.privileges is not None or member.status in ("administrator", "creator")
    except Exception:
        return False

async def _notify_admins(app: Client, text: str):
    targets = [_OWNER_ID] if _OWNER_ID > 0 else _store.list_admins()
    for uid in targets:
        try:
            await app.send_message(uid, text)
        except Exception:
            pass

def register(app: Client):
    # 1) ADMIN: drop a deep-link button in chat so users can DM the bot to auto-opt in
    @app.on_message(filters.command("dmsetup") & ~filters.scheduled)
    async def dmsetup(client: Client, m: Message):
        if not await _is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a username set to create a DM button.")
        url = f"https://t.me/{me.username}?start=ready"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("💌 Open DM with the bot", url=url)]]
        )
        await m.reply_text(
            "Tap the button to open a DM with me. Send any message there and you'll be marked DM-ready automatically.",
            reply_markup=kb
        )

    # 2) AUTO-READY: any private message marks the user DM-ready forever (+ ping admins)
    @app.on_message(filters.private & ~filters.scheduled)
    async def auto_ready_on_private(client: Client, m: Message):
        if not m.from_user:
            return
        uid = m.from_user.id
        # Already ready? skip ping spam
        first_time = not _store.is_dm_ready_global(uid)
        _store.set_dm_ready_global(uid, True, by_admin=False)

        if first_time:
            await _notify_admins(
                client,
                f"🔔 DM-ready: {m.from_user.mention} (<code>{uid}</code>) — via private chat"
            )

    # 3) Admin/manual toggles (reply or self)
    @app.on_message(filters.command(["dmready", "dmunready"]) & ~filters.scheduled)
    async def dm_ready_toggle(client: Client, m: Message):
        ready = m.command[0].lower() == "dmready"
        target_id = m.from_user.id
        if m.reply_to_message and m.reply_to_message.from_user:
            # only admins can change others
            if not await _is_admin(client, m.chat.id, m.from_user.id):
                return await m.reply_text("Admins only for toggling others.")
            target_id = m.reply_to_message.from_user.id

        # set global
        _store.set_dm_ready_global(target_id, ready, by_admin=(target_id != m.from_user.id))
        status = "✅ DM-ready (global)" if ready else "❌ Not DM-ready"
        who = "you" if target_id == m.from_user.id else f"<code>{target_id}</code>"
        await m.reply_text(f"{status} set for {who}.")

        if ready:
            # ping owner/admins
            try:
                u = await client.get_users(target_id)
                await _notify_admins(client, f"🔔 DM-ready: {u.mention} (<code>{target_id}</code>) — set by admin")
            except Exception:
                await _notify_admins(client, f"🔔 DM-ready: <code>{target_id}</code> — set by admin")

    # 4) List global DM-ready
    @app.on_message(filters.command("dmreadylist") & ~filters.scheduled)
    async def dmreadylist(client: Client, m: Message):
        dm = _store.list_dm_ready_global()
        if not dm:
            return await m.reply_text("No one is marked DM-ready (global) yet.")
        lines = []
        # prevent huge spam
        for uid_str in list(dm.keys())[:200]:
            uid = int(uid_str)
            try:
                u = await client.get_users(uid)
                lines.append(f"• {u.mention} (<code>{uid}</code>)")
            except Exception:
                lines.append(f"• <code>{uid}</code>")
        await m.reply_text("<b>DM-ready (global):</b>\n" + "\n".join(lines))

    # 5) Optional: Admin nudge
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
