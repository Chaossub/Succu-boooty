# dm_foolproof.py
# Foolproof DM onboarding + safer reminders + /dmnudge mentions.
# Requires req_store.py functions: dm_mark_ready, dm_mark_unready, list_dm_not_ready, next_reminder_index.

import os, json
from typing import Set, List
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import req_store as store

OWNER_ID = 6964994611
ADMINS_PATH = os.getenv("REQ_ADMINS_PATH", "data/requirements/req_admins.json")

def _load_admins() -> Set[int]:
    os.makedirs(os.path.dirname(ADMINS_PATH), exist_ok=True)
    if not os.path.exists(ADMINS_PATH):
        _save_admins({OWNER_ID})
    try:
        with open(ADMINS_PATH, "r", encoding="utf-8") as f:
            ids = set(int(x) for x in json.load(f).get("admins", []))
            ids.add(OWNER_ID)
            return ids
    except Exception:
        return {OWNER_ID}

def _save_admins(admins: Set[int]) -> None:
    os.makedirs(os.path.dirname(ADMINS_PATH), exist_ok=True)
    with open(ADMINS_PATH, "w", encoding="utf-8") as f:
        json.dump({"admins": sorted(admins)}, f, ensure_ascii=False, indent=2)

ADMINS: Set[int] = _load_admins()

def _is_admin(uid: int) -> bool:
    return uid == OWNER_ID or uid in ADMINS

def _admin_only(func):
    async def wrapper(client: Client, message: Message):
        uid = message.from_user.id if message.from_user else 0
        if not _is_admin(uid):
            return
        return await func(client, message)
    return wrapper

SANCTUARY_GROUP_LINK = os.getenv("SANCTUARY_GROUP_LINK", "")  # optional
DM_NOTIFY_OWNER_ON_START = os.getenv("DM_NOTIFY_OWNER_ON_START", "true").lower() in ("1","true","yes")

REMINDER_TEMPLATES = [
    "Hey handsome 😏 You haven’t hit your **$20 or 4 games** yet this month. Don’t make me pout… come be a good boy 💋",
    "Psst… we’re waiting to spoil you 😈 Tip a little, play a little, meet your monthly — it keeps our naughty vibes flowing.",
    "We love a lurker… but we adore a **spender**. Hit your $20 or 4 games and we’ll make it worth your while 🔥",
    "Tick-tock, baby ⏳ Meet your **$20 / 4 games** so we can keep spoiling you properly 😏"
]

async def _name_for(client: Client, user_id: int) -> str:
    try:
        u = await client.get_users(user_id)
        return f"@{u.username}" if getattr(u, "username", None) else f'<a href="tg://user?id={user_id}">{(u.first_name or "Member")}</a>'
    except Exception:
        return f'<a href="tg://user?id={user_id}">Member</a>'

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def priv_start(client: Client, message: Message):
        uid = message.from_user.id
        store.dm_mark_ready(uid)
        kb = None
        if SANCTUARY_GROUP_LINK:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Back to the Sanctuary", url=SANCTUARY_GROUP_LINK)]])
        await message.reply_text("Hi! You’re all set — I can DM you about games, reminders, and rewards 😈", reply_markup=kb)
        if DM_NOTIFY_OWNER_ON_START:
            who = f"@{message.from_user.username}" if message.from_user.username else f"ID:{uid}"
            try:
                await client.send_message(OWNER_ID, f"✅ DM-ready: {who}")
            except Exception:
                pass

    @app.on_message(filters.command("dmsetup"))
    @_admin_only
    async def dmsetup(client: Client, message: Message):
        me = await client.get_me()
        bot_username = me.username or ""
        url = f"https://t.me/{bot_username}?start=sanctuary" if bot_username else "https://t.me/"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 Enable DMs (tap Start)", url=url)]])
        text = (
            "To receive game reminders and rewards directly, tap the button and press <b>Start</b> in my DM.\n"
            "If you don’t Start the bot, I can’t message you privately."
        )
        await message.reply_text(text, reply_markup=kb)

    @app.on_message(filters.command("dmstatus"))
    @_admin_only
    async def dmstatus(client: Client, message: Message):
        all_users = store.list_all()
        not_ready = store.list_dm_not_ready()
        ready = len(all_users) - len(not_ready)
        total = len(all_users)
        lines: List[str] = []
        for u in not_ready[:25]:
            lines.append("• " + await _name_for(client, u["user_id"]))
        msg = f"DM-ready: {ready}/{total}\nNot ready ({len(not_ready)}):\n" + ("\n".join(lines) if lines else "• None")
        await message.reply_text(msg)

    @app.on_message(filters.command("remindnow"))
    @_admin_only
    async def remindnow(client: Client, message: Message):
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
        failed_ids: List[int] = []
        for u in behind:
            uid = u["user_id"]
            try:
                await client.send_message(uid, tpl)
                store.dm_mark_ready(uid)
                sent += 1
            except Exception:
                store.dm_mark_unready(uid)
                failed += 1
                failed_ids.append(uid)
        fail_lines: List[str] = []
        for uid in failed_ids[:25]:
            fail_lines.append("• " + await _name_for(client, uid))
        summary = f"📬 Reminders sent: {sent} (failed: {failed}) using template #{idx}"
        if failed:
            summary += "\n\nThese users need to tap <b>Start</b> (use /dmsetup):\n" + ("\n".join(fail_lines) if fail_lines else "• (unable to resolve)")
        summary += f"\n\nTemplate preview:\n“{tpl}”"
        await message.reply_text(summary)

    @app.on_message(filters.command("id"))
    async def cmd_id(client: Client, message: Message):
        if message.reply_to_message and message.reply_to_message.from_user:
            target = message.reply_to_message.from_user
            who = f"@{target.username}" if target.username else target.first_name
            return await message.reply_text(f"{who} — ID: `{target.id}`")
        u = message.from_user
        who = f"@{u.username}" if u.username else u.first_name
        await message.reply_text(f"{who} — ID: `{u.id}`")

    @app.on_message(filters.command("dmnudge"))
    @_admin_only
    async def dmnudge(client: Client, message: Message):
        """
        /dmnudge
        /dmnudge <limit>
        /dmnudge <limit> <custom text...>
        /dmnudge <custom text...>
        """
        default_limit = 25
        parts = message.command[1:]
        limit = default_limit
        custom_text = ""
        if parts:
            try:
                limit = max(1, int(parts[0]))
                custom_text = " ".join(parts[1:]).strip()
            except ValueError:
                custom_text = " ".join(parts).strip()
        if not custom_text:
            custom_text = (
                "Hey loves! To receive game reminders, reward drops, and special invites, "
                "please tap the button below and press <b>Start</b> in my DM. "
                "If you don’t Start the bot, I can’t message you privately. 💌"
            )
        not_ready = store.list_dm_not_ready()
        if not not_ready:
            return await message.reply_text("✨ Everyone is already DM-ready. Nothing to nudge!")

        me = await client.get_me()
        bot_username = me.username or ""
        deep_link = f"https://t.me/{bot_username}?start=sanctuary" if bot_username else "https://t.me/"

        targets = not_ready[:limit]
        mentions = [await _name_for(client, u["user_id"]) for u in targets]

        base_header = custom_text + "\n\n" + "Please tap <b>Start</b> here: " + deep_link + "\n\n"
        chunk, chunks, current_len = [], [], len(base_header)
        for m in mentions:
            piece = m + " "
            if current_len + len(piece) > 3500:
                chunks.append(base_header + "".join(chunk))
                chunk, current_len = [piece], len(base_header) + len(piece)
            else:
                chunk.append(piece)
                current_len += len(piece)
        if chunk:
            chunks.append(base_header + "".join(chunk))

        sent = 0
        for text in chunks:
            await message.reply_text(text, disable_web_page_preview=True)
            sent += 1

        remaining = max(0, len(not_ready) - len(targets))
        tail = f"\n\n…and {remaining} more not ready." if remaining else ""
        await message.reply_text(f"📣 Nudge sent in {sent} message(s). Targeted {len(targets)} user(s).{tail}")
