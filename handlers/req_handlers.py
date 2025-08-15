import math
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
        # allow placing id at end too
        return int(m.command[-1])
    if len(m.command) > 1 and m.command[1].isdigit():
        return int(m.command[1])
    return m.from_user.id

# ---------- register ----------
def register(app: Client):
    # (existing admin + req commands omitted here for brevity… keep yours as-is)

    # --- EXEMPTIONS: /reqexempt ---
    @app.on_message(filters.command("reqexempt") & ~filters.scheduled)
    async def reqexempt(client: Client, m: Message):
        """
        Usage:
          /reqexempt                      -> help
          /reqexempt list                 -> list group + global exemptions
          /reqexempt add [duration] [global] (reply or user_id) [; note...]
              duration: e.g., 72h, 7d, or blank for indefinite
              'global' keyword -> global scope; otherwise group-only
              You can add a note after a semicolon at the end.
          /reqexempt remove [global] (reply or user_id)
        """
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
            import time
            return await m.reply_text(
                "<b>Exemptions</b>\n\n"
                f"<u>Group</u>:\n{fmt(g)}\n\n"
                f"<u>Global</u>:\n{fmt(glob)}"
            )

        if sub == "add":
            # tokens (after 'add') may include duration (e.g., 72h), 'global' keyword, and optional '; note'
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
                    duration = p  # e.g., 72h or 7d or '12' (hours)

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
            import time
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

    # (keep your existing /reqadd, /reqgame, /reqnote, /reqstatus, /reqexport, /reqadmins handlers unchanged)
