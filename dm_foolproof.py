import json, os, time
from pyrogram import filters
from pyrogram.types import Message

DATA_FILE = "dm_ready.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def human_time_ago(ts: float) -> str:
    delta = int(time.time() - ts)
    days, rem = divmod(delta, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours}h ago"
    elif hours > 0:
        return f"{hours}h {minutes}m ago"
    else:
        return f"{minutes}m ago"

def register(app):
    @app.on_message(filters.command("start"))
    async def start_handler(client, message: Message):
        data = load_data()
        uid = str(message.from_user.id)

        if uid not in data:
            data[uid] = {
                "id": message.from_user.id,
                "name": message.from_user.first_name,
                "username": f"@{message.from_user.username}" if message.from_user.username else "(no username)",
                "since": time.time()
            }
            save_data(data)
            await message.reply_text(f"✅ DM-ready — {data[uid]['name']} {data[uid]['username']}")

        await message.reply_text(
            "🔥 Welcome to SuccuBot 🔥\n"
            "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
            "✨ Use the menu below to navigate!",
            reply_markup=client.get_panel("main")
        )

    @app.on_message(filters.command("dmreadylist"))
    async def dmready_list(client, message: Message):
        data = load_data()
        if not data:
            await message.reply_text("No one is DM-ready yet.")
            return

        lines = []
        for entry in data.values():
            since = human_time_ago(entry["since"])
            lines.append(f"✅ {entry['name']} {entry['username']} — `{entry['id']}` (since {since})")

        await message.reply_text("\n".join(lines))

