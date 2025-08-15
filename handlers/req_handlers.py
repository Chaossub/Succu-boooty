import math
from io import BytesIO
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message

from req_store import ReqStore, _month_key

STORE = ReqStore()

# ---------------- utilities ----------------
async def is_admin(app: Client, chat_id: int, user_id: int) -> bool:
    if user_id in STORE.list_admins():
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.privileges is not None or member.status in ("administrator", "creator")
    except Exception:
        return False

def parse_amount(s: str) -> Optional[float]:
    try:
        s = s.replace("$", "")
        return float(s)
    except Exception:
        return None

# --------------- registration --------------
def register(app: Client):
    # Admin management
    @app.on_message(filters.command("reqadmins") & ~filters.scheduled)
    async def reqadmins(client: Client, m: Message):
        if len(m.command) == 1:
            admins = ", ".join(map(str, STORE.list_admins())) or "(none yet)"
            return await m.reply_text(f"<b>Req Admins</b>\n{admins}")

        if not await is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")

        sub = m.command[1].lower()
        target = m.from_user.id
        if m.reply_to_message and m.reply_to_message.from_user:
            target = m.reply_to_message.from_user.id
        elif len(m.command) > 2 and m.command[2].isdigit():
            target = int(m.command[2])

        if sub == "add":
            ok = STORE.add_admin(target)
            return await m.reply_text("Added ✅" if ok else "Already an admin")
        elif sub == "remove":
            ok = STORE.remove_admin(target)
            return await m.reply_text("Removed ✅" if ok else "Not an admin")
        else:
            return await m.reply_text("Usage: /reqadmins [add|remove] (reply or user_id)")

    # Add a purchase amount ($)
    @app.on_message(filters.command("reqadd") & ~filters.scheduled)
    async def reqadd(client: Client, m: Message):
        if not await is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        if len(m.command) < 2:
            return await m.reply_text("Usage: /reqadd <amount> [@user|reply]")
        amt = parse_amount(m.command[1])
        if amt is None or math.isnan(amt) or amt < 0:
            return await m.reply_text("Amount must be a number (e.g., 20 or $5).")
        target = m.from_user.id
        if m.reply_to_message and m.reply_to_message.from_user:
            target = m.reply_to_message.from_user.id
        mk, u = STORE.add_purchase(target, amt)
        await m.reply_text(f"🧾 Recorded ${amt:.2f} for <code>{target}</code> [{mk}] • Total: ${u.purchases:.2f}")

    # Increment games count
    @app.on_message(filters.command("reqgame") & ~filters.scheduled)
    async def reqgame(client: Client, m: Message):
        if not await is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        target = m.from_user.id
        if m.reply_to_message and m.reply_to_message.from_user:
            target = m.reply_to_message.from_user.id
        mk, u = STORE.add_game(target)
        await m.reply_text(f"🎲 Logged a game for <code>{target}</code> [{mk}] • Games: {u.games}")

    # Set a note on a user (this month)
    @app.on_message(filters.command("reqnote") & ~filters.scheduled)
    async def reqnote(client: Client, m: Message):
        if not await is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        if len(m.command) < 2 and not (m.reply_to_message and m.reply_to_message.text):
            return await m.reply_text("Usage: /reqnote <text> (or reply with text)")
        note = " ".join(m.command[1:]) if len(m.command) > 1 else m.reply_to_message.text
        target = m.from_user.id
        if m.reply_to_message and m.reply_to_message.from_user:
            target = m.reply_to_message.from_user.id
        mk, u = STORE.set_note(target, note)
        await m.reply_text(f"📝 Note set for <code>{target}</code> [{mk}].")

    # Anyone can check their status; admins can check others via reply/user_id
    @app.on_message(filters.command("reqstatus") & ~filters.scheduled)
    async def reqstatus(client: Client, m: Message):
        target = m.from_user.id
        month_key = _month_key()
        # If admin, allow target switching
        if await is_admin(client, m.chat.id, m.from_user.id):
            if m.reply_to_message and m.reply_to_message.from_user:
                target = m.reply_to_message.from_user.id
            elif len(m.command) > 1 and m.command[1].isdigit():
                target = int(m.command[1])
        mk, u = STORE.get_status(target)
        needed_text = (
            "✅ Requirement met"
            if (u.purchases >= 20.0) or (u.games >= 4)
            else "❌ Not met (needs $20 total OR 4+ games)"
        )
        await m.reply_text(
            f"<b>Status for</b> <code>{target}</code> [{month_key}]\n"
            f"• Purchases: ${u.purchases:.2f}\n"
            f"• Games: {u.games}\n"
            f"• DM-Ready: {'Yes' if u.dm_ready else 'No'}\n"
            f"• Notes: {u.notes or '(none)'}\n"
            f"— {needed_text}"
        )

    # CSV export for this month
    @app.on_message(filters.command("reqexport") & ~filters.scheduled)
    async def reqexport(client: Client, m: Message):
        if not await is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        mk = _month_key()
        csv_text = STORE.export_csv(mk)
        bio = BytesIO(csv_text.encode("utf-8"))
        bio.name = f"requirements-{mk}.csv"
        await m.reply_document(bio, caption=f"Requirements export for {mk}")

    # Quick help
    @app.on_message(filters.command("reqhelp") & ~filters.scheduled)
    async def reqhelp(client: Client, m: Message):
        await m.reply_text(
            "<b>Requirements Tracker Commands</b>\n"
            "• /reqstatus — your status (admins: /reqstatus <user_id> or reply)\n"
            "• /reqadd <amt> — add purchase (reply to user or self)\n"
            "• /reqgame — add one game (reply to user or self)\n"
            "• /reqnote <text> — set note (reply or text)\n"
            "• /reqexport — CSV for this month\n"
            "• /reqadmins — list\n"
            "• /reqadmins add (reply/user_id)\n"
            "• /reqadmins remove (reply/user_id)\n"
        )
