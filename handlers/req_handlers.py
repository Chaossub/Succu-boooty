import math
import time
from io import BytesIO
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message

from req_store import ReqStore, _month_key

STORE = ReqStore()

# ---------- helpers ----------
async def is_admin(app: Client, chat_id: int, user_id: int) -> bool:
    if user_id in STORE.list_admins():
        return True
    try:
        m = await app.get_chat_member(chat_id, user_id)
        return m.privileges is not None or m.status in ("administrator", "creator")
    except Exception:
        return False

def parse_amount(s: str) -> Optional[float]:
    try:
        return float(s.replace("$", ""))
    except Exception:
        return None

def _pick_target(m: Message) -> Optional[int]:
    if m.reply_to_message and m.reply_to_message.from_user:
        return m.reply_to_message.from_user.id
    if len(m.command) > 2 and m.command[-1].isdigit():
        return int(m.command[-1])
    if len(m.command) > 1 and m.command[1].isdigit():
        return int(m.command[1])
    return m.from_user.id

# ---------- register ----------
def register(app: Client):
    # Admins list/manage
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

    # Add purchase
    @app.on_message(filters.command("reqadd") & ~filters.scheduled)
    async def reqadd(client: Client, m: Message):
        if not await is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        if len(m.command) < 2:
            return await m.reply_text("Usage: /reqadd <amount> [reply to user or self]")
        amt = parse_amount(m.command[1])
        if amt is None or math.isnan(amt) or amt < 0:
            return await m.reply_text("Amount must be a number (e.g., 20 or $5).")
        target = m.from_user.id
        if m.reply_to_message and m.reply_to_message.from_user:
            target = m.reply_to_message.from_user.id
        mk, u = STORE.add_purchase(target, amt)
        await m.reply_text(f"🧾 Recorded ${amt:.2f} for <code>{target}</code> [{mk}] • Total: ${u.purchases:.2f}")

    # Add game
    @app.on_message(filters.command("reqgame") & ~filters.scheduled)
    async def reqgame(client: Client, m: Message):
        if not await is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        target = m.from_user.id
        if m.reply_to_message and m.reply_to_message.from_user:
            target = m.reply_to_message.from_user.id
        mk, u = STORE.add_game(target)
        await m.reply_text(f"🎲 Logged a game for <code>{target}</code> [{mk}] • Games: {u.games}")

    # Note
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
        mk, _ = STORE.set_note(target, note)
        await m.reply_text(f"📝 Note set for <code>{target}</code> [{mk}].")

    # Status
    @app.on_message(filters.command("reqstatus") & ~filters.scheduled)
    async def reqstatus(client: Client, m: Message):
        target = m.from_user.id
        if await is_admin(client, m.chat.id, m.from_user.id):
            if m.reply_to_message and m.reply_to_message.from_user:
                target = m.reply_to_message.from_user.id
            elif len(m.command) > 1 and m.command[1].isdigit():
                target = int(m.command[1])
        mk, u = STORE.get_status(target)
        met = (u.purchases >= 20.0) or (u.games >= 4)
        needed = "✅ Requirement met" if met else "❌ Not met (needs $20 total OR 4+ games)"
        await m.reply_text(
            f"<b>Status for</b> <code>{target}</code> [{mk}]\n"
            f"• Purchases: ${u.purchases:.2f}\n"
            f"• Games: {u.games}\n"
            f"• DM-Ready (global): {'Yes' if STORE.is_dm_ready_global(target) else 'No'}\n"
            f"• Notes: {u.notes or '(none)'}\n"
            f"— {needed}"
        )

    # Export
    @app.on_message(filters.command("reqexport") & ~filters.scheduled)
    async def reqexport(client: Client, m: Message):
        if not await is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")
        mk = _month_key()
        csv_text = STORE.export_csv(mk)
        bio = BytesIO(csv_text.encode("utf-8"))
        bio.name = f"requirements-{mk}.csv"
        await m.reply_document(bio, caption=f"Requirements export for {mk}")

    # Help
    @app.on_message(filters.command("reqhelp") & ~filters.scheduled)
    async def reqhelp(client: Client, m: Message):
        await m.reply_text(
            "<b>Requirements Tracker</b>\n"
            "• /reqstatus — your status (admins: /reqstatus <user_id> or reply)\n"
            "• /reqadd <amt> — add purchase (reply to user or self)\n"
            "• /reqgame — add one game (reply to user or self)\n"
            "• /reqnote <text> — set note (reply or text)\n"
            "• /reqexport — CSV for this month\n"
            "• /reqadmins — list/add/remove requirement admins\n"
            "— DM Ready (global): /dmsetup /dmready /dmunready /dmreadylist\n"
            "— Exemptions: /reqexempt\n"
        )

    # --------- Exemptions ---------
    @app.on_message(filters.command("reqexempt") & ~filters.scheduled)
    async def reqexempt(client: Client, m: Message):
        if len(m.command) == 1:
            return await m.reply_text(
                "<b>Exemptions</b>\n"
                "• /reqexempt list — show current exemptions\n"
                "• /reqexempt add [72h|7d] [global] (reply or user_id) [; note]\n"
                "• /reqexempt remove [global] (reply or user_id)\n"
                "Indefinite if duration omitted. Use 'global' to apply across all groups."
            )

        if not await is_admin(client, m.chat.id, m.from_user.id):
            return await m.reply_text("Admins only.")

        sub = m.command[1].lower()

        if sub == "list":
            g = STORE.list_exemptions(m.chat.id)
            glob = STORE.list_exemptions(None)
            def fmt(d):
                if not d: return "(none)"
                out = []
                now = int(time.time())
                for uid, rec in d.items():
                    until = rec.get("until")
                    note = rec.get("note") or ""
                    if until is None:
                        out.append(f"• <code>{uid}</code> — indefinite {('— ' + note) if note else ''}")
                    else:
                        mins = max(0, int((until - now) / 60))
                        out.append(f"• <code>{uid}</code> — {mins} min left {('— ' + note) if note else ''}")
                return "\n".join(out)
            return await m.reply_text(
                "<b>Exemptions</b>\n\n"
                f"<u>Group</u>:\n{fmt(g)}\n\n"
                f"<u>Global</u>:\n{fmt(glob)}"
            )

        if sub == "add":
            text = m.text or ""
            after = text.split(None, 2)[2] if len(m.command) > 2 else ""
            note = ""
            if ";" in after:
                after, note = after.split(";", 1)
                note = note.strip()

            pieces = [p.strip() for p in after.split() if p.strip()]
            duration = None
            scope_global = False
            for p in pieces:
                if p.lower() == "global":
                    scope_global = True
                elif p[-1:].lower() in ("h", "d") or p.isdigit():
                    duration = p

            target = _pick_target(m)
            if not target:
                return await m.reply_text("Reply to a user or pass a user_id.")

            rec = STORE.add_exemption(
                user_id=target,
                chat_id=None if scope_global else m.chat.id,
                duration=duration,
                note=note,
            )
            scope = "GLOBAL" if scope_global else f"group <code>{m.chat.id}</code>"
            when = "indefinite" if rec["until"] is None else "until " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(rec["until"]))
            return await m.reply_text(
                f"✅ Exempted <code>{target}</code> in {scope} ({when}){(' — ' + note) if note else ''}"
            )

        if sub == "remove":
            scope_global = any(t.lower() == "global" for t in m.command[2:])
            target = _pick_target(m)
            if not target:
                return await m.reply_text("Reply to a user or pass a user_id.")
            ok = STORE.remove_exemption(target, None if scope_global else m.chat.id)
            if ok:
                return await m.reply_text(f"🗑️ Removed exemption for <code>{target}</code> ({'GLOBAL' if scope_global else 'group'})")
            return await m.reply_text("No exemption found.")

        return await m.reply_text("Unknown subcommand. Use /reqexempt for usage.")
