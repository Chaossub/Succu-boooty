# handlers/dm_ready_admin.py
from __future__ import annotations
import os, logging
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import DMReadyStore

log = logging.getLogger(__name__)
store = DMReadyStore()

# ---- auth helpers -----------------------------------------------------------
def _env_owner_and_supers() -> set[str]:
    owner = (os.getenv("OWNER_ID") or "").strip()
    supers = [s.strip() for s in (os.getenv("SUPER_ADMINS") or "").split(",") if s.strip()]
    s: set[str] = set()
    if owner:
        s.add(owner)
    s.update(supers)
    return s

def _is_allowed(uid: int) -> bool:
    # Prefer your project helper if it exists
    try:
        from utils.admin_check import is_admin_or_owner  # type: ignore
        allowed = bool(is_admin_or_owner(uid))
        if allowed:
            return True
    except Exception:
        pass
    return str(uid) in _env_owner_and_supers()

# ---- register ---------------------------------------------------------------
def register(app: Client):

    @app.on_message(filters.command(["dmreadylist", "dmreadys", "dmready_list"]))
    async def dmready_list(client: Client, m: Message):
        try:
            uid = m.from_user.id if m.from_user else 0
            if not _is_allowed(uid):
                return await m.reply_text("❌ You’re not allowed to use this command.")

            users = store.list_all()
            if not users:
                return await m.reply_text("ℹ️ No one is marked DM-ready yet.")

            lines = []
            for i, u in enumerate(users[:300], start=1):
                name = u.get("first_name") or "User"
                uname = ("@" + u["username"]) if u.get("username") else ""
                lines.append(f"{i}. {name} {uname} — <code>{u.get('id')}</code>")
            text = "✅ <b>DM-ready users</b>\n" + "\n".join(lines)
            await m.reply_text(text, disable_web_page_preview=True)
        except Exception as e:
            log.exception("dmreadylist failed")
            await m.reply_text(f"⚠️ dmreadylist error: <code>{e}</code>")

    # Tiny debug endpoint to verify wiring & data (owner/supers only)
    @app.on_message(filters.command(["dmreadydebug", "dmready_dbg"]))
    async def dmready_debug(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _is_allowed(uid):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        path = os.getenv("DMREADY_DB", "data/dm_ready.json")
        users = store.list_all()
        await m.reply_text(
            "🧪 <b>DM-ready debug</b>\n"
            f"• File: <code>{path}</code>\n"
            f"• Count: <code>{len(users)}</code>\n"
            f"• First entry preview: <code>{users[0] if users else '—'}</code>",
            disable_web_page_preview=True
        )

    # Optional maintenance (owner/supers)
    @app.on_message(filters.command("dmreadyremove"))
    async def dmready_remove(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _is_allowed(uid):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        try:
            parts = (m.text or "").split(maxsplit=1)
            if len(parts) < 2:
                return await m.reply_text("Usage: <code>/dmreadyremove &lt;user_id&gt;</code>")
            target = int(parts[1].strip())
            ok = store.remove(target)
            await m.reply_text("✅ Removed." if ok else "ℹ️ That user wasn’t in the list.")
        except Exception as e:
            await m.reply_text(f"⚠️ {e}")

    @app.on_message(filters.command("dmreadyclear"))
    async def dmready_clear(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _is_allowed(uid):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        # simple clear by rewriting the file via new store
        try:
            # brute-force clear: re-init backing file
            path = os.getenv("DMREADY_DB", "data/dm_ready.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("{}")
            # reload store
            globals()["store"] = DMReadyStore()
            await m.reply_text("🧹 Cleared DM-ready list.")
        except Exception as e:
            await m.reply_text(f"⚠️ {e}")
