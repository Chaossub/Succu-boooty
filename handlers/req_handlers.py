# req_handlers.py
# Manual admin commands for requirements, reminders, kicks, and admin management.
# Wire in main.py with:
#   from req_handlers import wire_requirements_handlers
#   wire_requirements_handlers(app)

import os
import json
from datetime import datetime
from typing import Optional, Set

from pyrogram import Client, filters
from pyrogram.types import Message

import req_store as store

# ========== OWNER / ADMINS (with persistence) ==========

OWNER_ID = 6964994611  # Roni (hardwired owner, cannot be removed)
# Persistent admins file
ADMINS_PATH = os.getenv("REQ_ADMINS_PATH", "data/requirements/req_admins.json")

def _load_admins() -> Set[int]:
    os.makedirs(os.path.dirname(ADMINS_PATH), exist_ok=True)
    if not os.path.exists(ADMINS_PATH):
        _save_admins({OWNER_ID})  # seed with owner only
    try:
        with open(ADMINS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            ids = {int(x) for x in data.get("admins", [])}
            ids.add(OWNER_ID)
            return ids
    except Exception:
        return {OWNER_ID}

def _save_admins(admins: Set[int]) -> None:
    os.makedirs(os.path.dirname(ADMINS_PATH), exist_ok=True)
    data = {"admins": sorted(admins)}
    with open(ADMINS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

ADMINS: Set[int] = _load_admins()

def _is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in ADMINS

def _admin_only(func):
    async def wrapper(client: Client, message: Message):
        uid = message.from_user.id if message.from_user else 0
        if not _is_admin(uid):
            return
        return await func(client, message)
    return wrapper

# ========== CONFIG ==========

# If set, /kickdefaulters without an arg uses this; else falls back to current chat
DEFAULT_GROUP_ID = None  # e.g., -1001234567890

REMINDER_TEMPLATES = [
    "Hey handsome 😏 You haven’t hit your **$20 or 4 games** yet this month. Don’t make me pout… come be a good boy 💋",
    "Psst… we’re waiting to spoil you 😈 Tip a little, play a little, meet your monthly — it keeps our naughty vibes flowing.",
    "We love a lurker… but we adore a **spender**. Hit your $20 or 4 games and we’ll make it worth your while 🔥",
    "Tick-tock, baby ⏳ Meet your **$20 / 4 games** so we can keep spoiling you properly 😏"
]

# ========== Display helper (live username) ==========

async def fmt_status(client: Client, u: dict) -> str:
    # Live username lookup for display (internal tracking stays by user_id)
    try:
        tg_user = await client.get_users(u["user_id"])
        uname_display = f"@{tg_user.username}" if getattr(tg_user, "username", None) else f"ID:{u['user_id']}"
    except Exception:
        uname_display = f"ID:{u['user_id']}"
    pass_txt = f" (free pass until {u['free_pass_until']})" if u.get("free_pass_until") else ""
    met_txt = "✅ MET" if u.get("met") else "❌ NOT MET"
    return (
        f"{uname_display} — ${u.get('tips_usd',0):.2f} "
        f"({u.get('tip_count',0)} tips), "
        f"{u.get('games',0)} games — {met_txt}{pass_txt}"
    )

HELP_TEXT = (
"**Requirements (Manual) — Admin Commands**\n"
"• /req_start_month [YYYY-MM] — start/initialize month file\n"
"• /reqexport — export CSV for current month\n"
"• /req_archive [YYYY-MM-next] — archive current + optionally start next\n"
"• /req_clear — wipe current month data (fresh start)\n"
"\n"
"**Progress (manual entry)**\n"
"• /marktip <user_id> <amount> [note] — add tip (increments tip_count)\n"
"• /markgame <user_id> <count> — add games\n"
"\n"
"**Status & lists**\n"
"• /reqstatus <user_id> — show one user\n"
"• /reqlist [behind|met|all] — list users by status\n"
"• /reqnote <user_id> <text> — save admin note\n"
"• /reqremove <user_id> — delete user entry this month\n"
"\n"
"**Passes**\n"
"• /grantpass <user_id> <YYYY-MM> — grant pass until month\n"
"• /revokepass <user_id> — revoke pass\n"
"\n"
"**Reminders & kicks**\n"
"• /remindnow [idx] — DM all behind (rotates templates if idx omitted)\n"
"• /kickdefaulters [chat_id] — kick behind users (no pass)\n"
"\n"
"**Admin management**\n"
"• /addreqadmin <user_id> — add an admin (persists)\n"
"• /delreqadmin <user_id> — remove an admin (cannot remove owner)\n"
"• /listreqadmins — list current admins\n"
f"\nOwner: `{OWNER_ID}` is always recognized.\n"
)

# ========== Handlers ==========

def wire_requirements_handlers(app: Client):

    # ---- Help
    @app.on_message(filters.command("reqhelp"))
    @_admin_only
    async def reqhelp(client: Client, message: Message):
        await message.reply_text(HELP_TEXT)

    # ---- Month controls
    @app.on_message(filters.command("req_start_month"))
    @_admin_only
    async def req_start_month(client: Client, message: Message):
        # /req_start_month  (uses current)  OR  /req_start_month 2025-09
        m = None
        if len(message.command) > 1:
            try:
                datetime.strptime(message.command[1], "%Y-%m")
                m = message.command[1]
            except Exception:
                m = None
        m = store.start_month(m or store.month_key())
        await message.reply_text(f"✅ Started month **{m}**. (Fresh JSON created)")

    @app.on_message(filters.command("req_clear"))
    @_admin_only
    async def req_clear(client: Client, message: Message):
        m = store.clear_current_month()
        await message.reply_text(f"🧹 Cleared all data for **{m}**. Starting fresh (rotation reset).")

    @app.on_message(filters.command("reqexport"))
    @_admin_only
    async def reqexport(client: Client, message: Message):
        m = store.month_key()
        path = f"data/requirements/archive_{m}.csv"
        out = store.export_csv(path, m)
        await message.reply_text(f"📤 Exported CSV for **{m}** to `{out}`")

    @app.on_message(filters.command("req_archive"))
    @_admin_only
    async def req_archive(client: Client, message: Message):
        # /req_archive [YYYY-MM-next]
        next_m = None
        if len(message.command) > 1:
            try:
                datetime.strptime(message.command[1], "%Y-%m")
                next_m = message.command[1]
            except Exception:
                next_m = None
        res = store.archive_and_clear(store.month_key(), next_m)
        msg = f"📦 Archived to: `{res['archived_csv']}`"
        if res["next_month_created"]:
            msg += f"\n🆕 Started next: **{res['next_month_created']}**"
        await message.reply_text(msg)

    # ---- Manual progress logging (EXPLICIT ARGS ONLY)
    @app.on_message(filters.command("marktip"))
    @_admin_only
    async def marktip(client: Client, message: Message):
        # /marktip <user_id> <amount> [note]
        if len(message.command) < 3:
            return await message.reply_text("Usage: /marktip <user_id> <amount> [note]")
        try:
            user_id = int(message.command[1])
            amount = float(message.command[2])
        except ValueError:
            return await message.reply_text("User ID must be an integer and amount must be a number.")
        note = " ".join(message.command[3:]) if len(message.command) > 3 else ""
        u = store.add_tip(user_id, amount, note=note)
        await message.reply_text("💸 Tip recorded:\n" + await fmt_status(client, u))

    @app.on_message(filters.command("markgame"))
    @_admin_only
    async def markgame(client: Client, message: Message):
        # /markgame <user_id> <count>
        if len(message.command) < 3:
            return await message.reply_text("Usage: /markgame <user_id> <count>")
        try:
            user_id = int(message.command[1])
            count = int(message.command[2])
        except ValueError:
            return await message.reply_text("User ID and count must be integers.")
        u = store.add_games(user_id, count)
        await message.reply_text("🎯 Games recorded:\n" + await fmt_status(client, u))

    # ---- Status & lists
    @app.on_message(filters.command("reqstatus"))
    @_admin_only
    async def reqstatus(client: Client, message: Message):
        # /reqstatus <user_id>
        if len(message.command) < 2:
            return await message.reply_text("Usage: /reqstatus <user_id>")
        try:
            user_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("User ID must be an integer.")
        u = store.status(user_id)
        await message.reply_text(await fmt_status(client, u))

    @app.on_message(filters.command("reqlist"))
    @_admin_only
    async def reqlist(client: Client, message: Message):
        # /reqlist [all|met|behind]
        mode = message.command[1].lower() if len(message.command) > 1 else "behind"
        if mode == "all":
            rows = store.list_all()
            title = "📋 All"
        elif mode == "met":
            rows = store.list_met()
            title = "✅ Met"
        else:
            rows = store.list_behind()
            title = "❌ Behind"
        if not rows:
            return await message.reply_text(f"{title}: none.")
        lines = []
        for u in rows[:50]:
            lines.append(await fmt_status(client, u))
        await message.reply_text(f"**{title} (showing {len(lines)})**\n" + "\n".join(lines))

    # ---- Passes
    @app.on_message(filters.command("grantpass"))
    @_admin_only
    async def grantpass(client: Client, message: Message):
        # /grantpass <user_id> <YYYY-MM>
        if len(message.command) < 3:
            return await message.reply_text("Usage: /grantpass <user_id> <YYYY-MM>")
        try:
            user_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("User ID must be an integer.")
        until = message.command[2]
        try:
            datetime.strptime(until, "%Y-%m")
        except Exception:
            return await message.reply_text("Format month as YYYY-MM.")
        u = store.set_pass(user_id, until)
        await message.reply_text(f"🎟️ Free pass set until **{until}**:\n" + await fmt_status(client, u))

    @app.on_message(filters.command("revokepass"))
    @_admin_only
    async def revokepass(client: Client, message: Message):
        # /revokepass <user_id>
        if len(message.command) < 2:
            return await message.reply_text("Usage: /revokepass <user_id>")
        try:
            user_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("User ID must be an integer.")
        u = store.revoke_pass(user_id)
        await message.reply_text(f"❎ Pass revoked:\n" + await fmt_status(client, u))

    @app.on_message(filters.command("reqnote"))
    @_admin_only
    async def reqnote(client: Client, message: Message):
        # /reqnote <user_id> <text...>
        if len(message.command) < 3:
            return await message.reply_text("Usage: /reqnote <user_id> <text>")
        try:
            user_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("User ID must be an integer.")
        text = " ".join(message.command[2:])
        u = store.set_note(user_id, text)
        await message.reply_text("📝 Note saved:\n" + await fmt_status(client, u))

    @app.on_message(filters.command("reqremove"))
    @_admin_only
    async def reqremove(client: Client, message: Message):
        # /reqremove <user_id>
        if len(message.command) < 2:
            return await message.reply_text("Usage: /reqremove <user_id>")
        try:
            user_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("User ID must be an integer.")
        ok = store.remove_user(user_id)
        await message.reply_text("🗑️ Removed." if ok else "User not found for this month.")

    # ---- Reminders (DMs)
    @app.on_message(filters.command("remindnow"))
    @_admin_only
    async def remindnow(client: Client, message: Message):
        """
        /remindnow            -> rotates to the next template automatically (persistent)
        /remindnow <idx>      -> forces a specific template index
        """
        if len(message.command) > 1:
            try:
                idx = int(message.command[1])
            except Exception:
                idx = 0
        else:
            idx = store.next_reminder_index(len(REMINDER_TEMPLATES))

        tpl = REMINDER_TEMPLATES[idx % len(REMINDER_TEMPLATES)]
        behind = store.list_behind()
        sent, failed = 0, 0
        for u in behind:
            try:
                await client.send_message(u["user_id"], tpl)
                sent += 1
            except Exception:
                failed += 1
        await message.reply_text(f"📬 Reminders sent: {sent} (failed: {failed}) using template #{idx}")

    # ---- One-off DM
    @app.on_message(filters.command("dmreq"))
    @_admin_only
    async def dmreq(client: Client, message: Message):
        # /dmreq <user_id> <text...>
        if len(message.command) < 3:
            return await message.reply_text("Usage: /dmreq <user_id> <text>")
        try:
            user_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("User ID must be an integer.")
        text = " ".join(message.command[2:])
        try:
            await client.send_message(user_id, text)
            await message.reply_text("✅ DM sent.")
        except Exception as e:
            await message.reply_text(f"❌ DM failed: {e}")

    # ---- Kick sweep (manual)
    @app.on_message(filters.command("kickdefaulters"))
    @_admin_only
    async def kickdefaulters(client: Client, message: Message):
        # /kickdefaulters  OR  /kickdefaulters <chat_id>
        chat_id = None
        if len(message.command) > 1:
            try:
                chat_id = int(message.command[1])
            except Exception:
                chat_id = None
        chat_id = chat_id or DEFAULT_GROUP_ID or (message.chat.id if message.chat else None)
        if not chat_id:
            return await message.reply_text("Provide a chat_id or set DEFAULT_GROUP_ID.")
        behind = store.list_behind()
        kicked, failed = 0, 0
        for u in behind:
            try:
                await client.kick_chat_member(chat_id, u["user_id"])
                await client.unban_chat_member(chat_id, u["user_id"])  # allow rejoin later
                kicked += 1
            except Exception:
                failed += 1
        await message.reply_text(f"🪓 Kick sweep complete — kicked: {kicked}, failed: {failed}")

    # ---- Requirements Admin management (add/remove/list; persisted)
    @app.on_message(filters.command("addreqadmin"))
    @_admin_only
    async def cmd_addreqadmin(client: Client, message: Message):
        # /addreqadmin <user_id>
        if len(message.command) < 2:
            return await message.reply_text("Usage: /addreqadmin <user_id>")
        try:
            new_admin = int(message.command[1])
        except ValueError:
            return await message.reply_text("🚫 Invalid user ID.")
        if new_admin == OWNER_ID:
            return await message.reply_text("✅ Owner is already an admin.")
        if new_admin in ADMINS:
            return await message.reply_text("✅ That user is already a requirements admin.")
        ADMINS.add(new_admin)
        _save_admins(ADMINS)
        await message.reply_text(f"✅ Added {new_admin} as a requirements admin (saved).")

    @app.on_message(filters.command("delreqadmin"))
    @_admin_only
    async def cmd_delreqadmin(client: Client, message: Message):
        # /delreqadmin <user_id>
        if len(message.command) < 2:
            return await message.reply_text("Usage: /delreqadmin <user_id>")
        try:
            target_admin = int(message.command[1])
        except ValueError:
            return await message.reply_text("🚫 Invalid user ID.")
        if target_admin == OWNER_ID:
            return await message.reply_text("🚫 You cannot remove the owner.")
        if target_admin not in ADMINS:
            return await message.reply_text("🚫 That user is not a requirements admin.")
        ADMINS.remove(target_admin)
        _save_admins(ADMINS)
        await message.reply_text(f"✅ Removed {target_admin} from requirements admins (saved).")

    @app.on_message(filters.command("listreqadmins"))
    @_admin_only
    async def cmd_listreqadmins(client: Client, message: Message):
        # Show numeric IDs; (you can look up usernames if you want)
        ids = sorted(list(ADMINS))
        lines = [str(x) + (" (OWNER)" if x == OWNER_ID else "") for x in ids]
        await message.reply_text("👑 Current requirements admins:\n" + "\n".join(lines))

