import json
import os
from pyrogram import filters
from pyrogram.types import Message

XP_FILE = "xp_data.json"

if os.path.exists(XP_FILE):
    with open(XP_FILE, "r") as f:
        xp_data = json.load(f)
else:
    xp_data = {}

def save_xp():
    with open(XP_FILE, "w") as f:
        json.dump(xp_data, f, indent=4)

def add_xp(chat_id: str, user_id: str, amount: int):
    chat_str = str(chat_id)
    user_str = str(user_id)
    if chat_str not in xp_data:
        xp_data[chat_str] = {}
    if user_str not in xp_data[chat_str]:
        xp_data[chat_str][user_str] = 0
    xp_data[chat_str][user_str] += amount
    save_xp()

def get_xp(chat_id: str, user_id: str) -> int:
    chat_str = str(chat_id)
    user_str = str(user_id)
    return xp_data.get(chat_str, {}).get(user_str, 0)

def get_leaderboard(chat_id: str):
    chat_str = str(chat_id)
    if chat_str not in xp_data:
        return []
    return sorted(xp_data[chat_str].items(), key=lambda x: x[1], reverse=True)

def register(app):
    @app.on_message(filters.command("naughty") & filters.group)
    async def show_xp(client, message: Message):
        user = message.from_user
        if not user:
            return
        xp = get_xp(message.chat.id, user.id)
        await message.reply(f"😈 {user.mention}, your naughty XP is: <b>{xp}</b>!")

    @app.on_message(filters.command("xpboard") & filters.group)
    async def leaderboard(client, message: Message):
        lb = get_leaderboard(message.chat.id)
        if not lb:
            await message.reply("No naughty XP recorded in this chat yet.")
            return
        text = "🔥 <b>Naughty XP Leaderboard</b> 🔥\n\n"
        for i, (user_id, xp) in enumerate(lb[:10], start=1):
            try:
                user = await client.get_users(int(user_id))
                mention = user.mention
            except Exception:
                mention = f"<code>{user_id}</code>"
            text += f"{i}. {mention} — {xp} XP\n"
        await message.reply(text)
