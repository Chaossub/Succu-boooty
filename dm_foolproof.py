# dm_foolproof.py — /start: DM-ready that only announces when persisted in Mongo
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError

from req_store import ReqStore
from handlers.panels import render_main

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_only").lower().strip()

STORE = ReqStore()  # knows whether it's using Mongo or file

def _fmt(u):
    return f"{u.first_name or 'Someone'}" + (f" @{u.username}" if u.username else "")

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        u = m.from_user

        # Mark DM-ready; True means "state changed" (first time or reset->set)
        changed = STORE.set_dm_ready_global(u.id, True)

        # Announce **only** if we have persistent backend (Mongo) and this is first time
        if changed and STORE.uses_mongo():
            try:
                await m.reply_text(f"✅ DM-ready — {_fmt(u)}")
            except RPCError:
                pass
            if OWNER_ID and DM_READY_NOTIFY_MODE in ("first_only", "always"):
                try:
                    await c.send_message(
                        OWNER_ID,
                        f"✅ DM-ready NEW user\n• {u.first_name or ''} @{u.username or ''}\n• id: <code>{u.id}</code>"
                    )
                except Exception:
                    pass

        # Render main panel (single placeholder edited in place)
        ph = await m.reply_text("…")
        await render_main(ph)

    # ---- Status & admin tools ----
    @app.on_message(filters.private & filters.command("dmready_status"))
    async def _status(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        if STORE.uses_mongo():
            await m.reply_text("✅ DM-ready storage: <b>Mongo (persistent)</b>")
        else:
            await m.reply_text("⚠️ DM-ready storage: <b>JSON (ephemeral)</b>\n"
                               "Add MONGO_URI/MONGO_DB_NAME/DM_READY_COLLECTION to make it persistent.")

    @app.on_message(filters.private & filters.command("dmready_count"))
    async def _count(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        await m.reply_text(f"📊 DM-ready unique users: <b>{len(STORE.list_dm_ready_global())}</b>")

    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def _list_all(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        dm = STORE.list_dm_ready_global()
        items = sorted(dm.items(), key=lambda kv: kv[1].get("since", 0), reverse=True)
        lines = [f"• <code>{uid}</code> — since {int(meta.get('since', 0))}" for uid, meta in items]
        text = "🗂 <b>DM-ready (all)</b>\n" + ("\n".join(lines) if lines else "(empty)")
        await m.reply_text(text)

    @app.on_message(filters.private & filters.command("dmready_reset"))
    async def _reset(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            return await m.reply_text("Usage: /dmready_reset <user_id>")
        try:
            target = int(parts[1])
        except ValueError:
            return await m.reply_text("Provide a numeric user_id.")
        ok = STORE.set_dm_ready_global(target, False)
        await m.reply_text("🔁 Reset." if ok else "No change.")
