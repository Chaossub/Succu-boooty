from typing import List

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError, FloodWait, ChatAdminRequired, UserAdminInvalid

from req_store import ReqStore, _month_key

STORE = ReqStore()

REQUIRED_DOLLARS = 20.0
REQUIRED_GAMES = 4

async def _is_admin(app: Client, chat_id: int, user_id: int) -> bool:
    if user_id in STORE.list_admins():
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.privileges is not None or member.status in ("administrator", "creator")
    except Exception:
        return False

def _meets(u) -> bool:
    return (u.purchases >= REQUIRED_DOLLARS) or (u.games >= REQUIRED_GAMES)

def register(app: Client):
    @app.on_message(filters.command("reqscan") & ~filters.scheduled)
    async def reqscan(client: Client, m: Message):
        if not await _is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")

        mk = _month_key()
        month_users = STORE.state.months.get(mk, {}).get("users", {})
        if not month_users:
            return await m.reply_text(f"No tracked users yet for {mk}.")

        failing: List[int] = []
        exempt: List[int] = []

        async for member in client.get_chat_members(m.chat.id):
            u = member.user
            if u.is_bot:
                continue
            rec = month_users.get(str(u.id))
            if not rec:
                if STORE.is_exempt(u.id, m.chat.id):
                    exempt.append(u.id)
                else:
                    failing.append(u.id)
                continue
            if isinstance(rec, dict):
                from req_store import _as_userreq
                rec = _as_userreq(rec)
            if _meets(rec) or STORE.is_exempt(u.id, m.chat.id):
                if STORE.is_exempt(u.id, m.chat.id):
                    exempt.append(u.id)
                continue
            failing.append(u.id)

        async def fmt(ids):
            out = []
            for uid in ids[:200]:
                try:
                    u = await client.get_users(uid)
                    out.append(f"• {u.mention} (<code>{uid}</code>)")
                except Exception:
                    out.append(f"• <code>{uid}</code>")
            return "\n".join(out) if out else "(none)"

        await m.reply_text(
            f"<b>Requirement scan for {mk}</b>\n\n"
            f"<u>Failing</u>:\n{await fmt(failing)}\n\n"
            f"<u>Exempt</u>:\n{await fmt(exempt)}"
        )

    @app.on_message(filters.command("reqenforce") & ~filters.scheduled)
    async def reqenforce(client: Client, m: Message):
        if not await _is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        try:
            me = await client.get_chat_member(m.chat.id, "me")
            if not (me.privileges and me.privileges.can_restrict_members):
                return await m.reply_text("I need permission to ban/kick members.")
        except Exception:
            pass

        mk = _month_key()
        month_users = STORE.state.months.get(mk, {}).get("users", {})

        kicked = []
        skipped = []
        async for member in client.get_chat_members(m.chat.id):
            u = member.user
            if u.is_bot:
                continue
            if member.status in ("administrator", "creator"):
                continue
            if STORE.is_exempt(u.id, m.chat.id):
                skipped.append(u.id)
                continue
            rec = month_users.get(str(u.id))
            unmet = True
            if rec:
                if isinstance(rec, dict):
                    from req_store import _as_userreq
                    rec = _as_userreq(rec)
                unmet = not _meets(rec)
            if unmet:
                try:
                    await client.ban_chat_member(m.chat.id, u.id)
                    await client.unban_chat_member(m.chat.id, u.id)
                    kicked.append(u.id)
                except (ChatAdminRequired, UserAdminInvalid, FloodWait, RPCError):
                    skipped.append(u.id)

        async def fmt(ids):
            out = []
            for uid in ids[:200]:
                try:
                    u = await client.get_users(uid)
                    out.append(f"• {u.mention} (<code>{uid}</code>)")
                except Exception:
                    out.append(f"• <code>{uid}</code>")
            return "\n".join(out) if out else "(none)"

        await m.reply_text(
            f"<b>Enforcement for {mk}</b>\n"
            f"✅ Kicked:\n{await fmt(kicked)}\n\n"
            f"⏭️ Skipped (exempt/privileged/errors):\n{await fmt(skipped)}"
        )
