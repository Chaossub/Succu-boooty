import os
import json
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler

FLYERS_FILE = "data/flyers.json"
os.makedirs("data", exist_ok=True)

def load_flyers():
    if not os.path.isfile(FLYERS_FILE):
        return {}
    with open(FLYERS_FILE, "r") as f:
        return json.load(f)

def save_flyers(flyers):
    with open(FLYERS_FILE, "w") as f:
        json.dump(flyers, f, indent=2)

def register(app, scheduler: BackgroundScheduler):

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(_, msg: Message):
        if not msg.photo:
            return await msg.reply("❌ Please attach a photo.")
        try:
            name = msg.command[1]
            caption = " ".join(msg.command[2:])
        except IndexError:
            return await msg.reply("Usage: /addflyer <name> <caption>")
        flyers = load_flyers()
        flyers[name] = {
            "file_id": msg.photo.file_id,
            "caption": caption,
        }
        save_flyers(flyers)
        await msg.reply(f"✅ Flyer '{name}' saved.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(_, msg: Message):
        try:
            name = msg.command[1]
        except IndexError:
            return await msg.reply("Usage: /flyer <name>")
        flyers = load_flyers()
        flyer = flyers.get(name)
        if not flyer:
            return await msg.reply("❌ Flyer not found.")
        await msg.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("changeflyer") & filters.reply & filters.group)
    async def change_flyer(_, msg: Message):
        if not msg.reply_to_message.photo:
            return await msg.reply("❌ Reply must be to a new photo.")
        try:
            name = msg.command[1]
        except IndexError:
            return await msg.reply("Usage: /changeflyer <name>")
        flyers = load_flyers()
        if name not in flyers:
            return await msg.reply("❌ Flyer not found.")
        flyers[name]["file_id"] = msg.reply_to_message.photo.file_id
        save_flyers(flyers)
        await msg.reply(f"✅ Flyer '{name}' image updated.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(_, msg: Message):
        try:
            name = msg.command[1]
        except IndexError:
            return await msg.reply("Usage: /deleteflyer <name>")
        flyers = load_flyers()
        if name not in flyers:
            return await msg.reply("❌ Flyer not found.")
        flyers.pop(name)
        save_flyers(flyers)
        await msg.reply(f"🗑️ Deleted flyer '{name}'.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(_, msg: Message):
        flyers = load_flyers()
        if not flyers:
            return await msg.reply("No flyers found.")
        names = "\n".join(f"• {n}" for n in flyers.keys())
        await msg.reply(f"📌 Saved Flyers:\n{names}")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(_, msg: Message):
        try:
            name = msg.command[1]
            date_str = msg.command[2]
            time_str = msg.command[3]
            target_group = int(msg.command[4])
        except (IndexError, ValueError):
            return await msg.reply("Usage:\n/scheduleflyer <name> <YYYY-MM-DD> <HH:MM> <target_group_id>")
        flyers = load_flyers()
        flyer = flyers.get(name)
        if not flyer:
            return await msg.reply("❌ Flyer not found.")
        dt_str = f"{date_str} {time_str}"
        try:
            post_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return await msg.reply("Invalid date/time format.")
        
        async def post_flyer():
            await app.send_photo(
                target_group,
                flyer["file_id"],
                caption=flyer["caption"]
            )

        scheduler.add_job(post_flyer, trigger="date", run_date=post_time)
        await msg.reply(f"📅 Flyer '{name}' scheduled for {post_time.strftime('%Y-%m-%d %H:%M')} in {target_group}.")
