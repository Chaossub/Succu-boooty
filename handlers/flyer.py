import os
import json
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from utils.check_admin import is_admin

FLYERS_PATH = "data/flyers.json"
SCHEDULE_PATH = "data/scheduled_posts.json"

os.makedirs("data", exist_ok=True)
if not os.path.exists(FLYERS_PATH):
    with open(FLYERS_PATH, "w") as f:
        json.dump({}, f)
if not os.path.exists(SCHEDULE_PATH):
    with open(SCHEDULE_PATH, "w") as f:
        json.dump([], f)

def load_flyers():
    with open(FLYERS_PATH, "r") as f:
        return json.load(f)

def save_flyers(data):
    with open(FLYERS_PATH, "w") as f:
        json.dump(data, f, indent=2)

def load_scheduled():
    with open(SCHEDULE_PATH, "r") as f:
        return json.load(f)

def save_scheduled(data):
    with open(SCHEDULE_PATH, "w") as f:
        json.dump(data, f, indent=2)

async def add_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can create flyers.")
    if not message.photo:
        return await message.reply("📸 Please send a photo with the caption: /addflyer <name> <caption>")
    try:
        parts = message.caption.split(" ", 2)
        name = parts[1].strip().lower()
        caption = parts[2] if len(parts) > 2 else ""
    except Exception:
        return await message.reply("❌ Usage: /addflyer <name> <caption>")
    flyers = load_flyers()
    flyers[name] = {
        "file_id": message.photo.file_id,
        "caption": caption
    }
    save_flyers(flyers)
    await message.reply(f"✅ Flyer '{name}' added!")

async def change_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can update flyers.")
    if not message.reply_to_message or not message.photo:
        return await message.reply("❌ Reply to the new image with /changeflyer <name>")
    try:
        name = message.text.split(" ", 1)[1].strip().lower()
    except:
        return await message.reply("❌ Usage: /changeflyer <name>")
    flyers = load_flyers()
    if name not in flyers:
        return await message.reply("❌ Flyer not found.")
    flyers[name]["file_id"] = message.photo.file_id
    save_flyers(flyers)
    await message.reply(f"✅ Flyer '{name}' updated!")

async def delete_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can delete flyers.")
    try:
        name = message.text.split(" ", 1)[1].strip().lower()
    except:
        return await message.reply("❌ Usage: /deleteflyer <name>")
    flyers = load_flyers()
    if name not in flyers:
        return await message.reply("❌ Flyer not found.")
    del flyers[name]
    save_flyers(flyers)
    await message.reply(f"✅ Flyer '{name}' deleted.")

async def list_flyers(client: Client, message: Message):
    flyers = load_flyers()
    if not flyers:
        return await message.reply("📭 No flyers found.")
    flyer_list = "\n".join([f"• {name}" for name in flyers])
    await message.reply(f"📂 Available Flyers:\n{flyer_list}")

async def get_flyer(client: Client, message: Message):
    try:
        name = message.text.split(" ", 1)[1].strip().lower()
    except:
        return await message.reply("❌ Usage: /flyer <name>")
    flyers = load_flyers()
    if name not in flyers:
        return await message.reply("❌ Flyer not found.")
    flyer = flyers[name]
    await client.send_photo(
        chat_id=message.chat.id,
        photo=flyer["file_id"],
        caption=flyer["caption"]
    )

async def schedule_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can schedule flyers.")
    try:
        _, flyer_name, target_group, post_time = message.text.split(" ", 3)
        flyer_name = flyer_name.lower().strip()
    except:
        return await message.reply("❌ Usage: /scheduleflyer <flyer_name> <target_group_id> <YYYY-MM-DD HH:MM>")
    flyers = load_flyers()
    if flyer_name not in flyers:
        return await message.reply("❌ Flyer not found.")
    schedule = load_scheduled()
    schedule.append({
        "type": "flyer",
        "name": flyer_name,
        "group_id": int(target_group),
        "time": post_time
    })
    save_scheduled(schedule)
    await message.reply(f"✅ Flyer '{flyer_name}' scheduled for {post_time} in {target_group}!")

async def schedule_text(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can schedule text posts.")
    try:
        _, group_id, post_time, text = message.text.split(" ", 3)
    except:
        return await message.reply("❌ Usage: /scheduletext <group_id> <YYYY-MM-DD HH:MM> <text>")
    schedule = load_scheduled()
    schedule.append({
        "type": "text",
        "group_id": int(group_id),
        "time": post_time,
        "text": text
    })
    save_scheduled(schedule)
    await message.reply(f"✅ Text post scheduled for {post_time} in {group_id}!")

async def post_scheduled(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Admins only.")
    await post_due(client)

async def post_due(client: Client):
    schedule = load_scheduled()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    remaining = []
    for item in schedule:
        if item["time"] == now:
            if item["type"] == "flyer":
                flyers = load_flyers()
                flyer = flyers.get(item["name"])
                if flyer:
                    await client.send_photo(
                        chat_id=item["group_id"],
                        photo=flyer["file_id"],
                        caption=flyer["caption"]
                    )
            elif item["type"] == "text":
                await client.send_message(
                    chat_id=item["group_id"],
                    text=item["text"]
                )
        else:
            remaining.append(item)
    save_scheduled(remaining)

def register(app, scheduler):
    app.add_handler(filters.command("addflyer")(add_flyer))
    app.add_handler(filters.command("changeflyer")(change_flyer))
    app.add_handler(filters.command("deleteflyer")(delete_flyer))
    app.add_handler(filters.command("listflyers")(list_flyers))
    app.add_handler(filters.command("flyer")(get_flyer))
    app.add_handler(filters.command("scheduleflyer")(schedule_flyer))
    app.add_handler(filters.command("scheduletext")(schedule_text))
    app.add_handler(filters.command("postnow")(post_scheduled))
    scheduler.add_job(lambda: app.loop.create_task(post_due(app)), "interval", minutes=1)
    scheduler.start()
