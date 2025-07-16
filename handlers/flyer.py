import os
from datetime import datetime
from pymongo import MongoClient
from pyrogram import filters
from pyrogram.types import Message

# Mongo setup
MONGO_URI = os.environ.get("MONGO_URI")
mongo = MongoClient(MONGO_URI)
flyers_col = mongo["succubot"]["flyers"]

OWNER_ID = int(os.environ.get("OWNER_ID", "6964994611"))  # Set your Telegram user ID here

async def is_admin(client, message: Message) -> bool:
    """Admins or group owner only."""
    if message.from_user.id == OWNER_ID:
        return True
    chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
    return chat_member.status in ("administrator", "creator")

async def addflyer_handler(client, message: Message):
    # Only admins
    if not await is_admin(client, message):
        return await message.reply("❌ You must be an admin to use this command.")
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.reply("❌ Usage: /addflyer <name> <caption> (as text, or reply to photo with this command)")
    flyer_name = args[1].strip().lower()
    caption = args[2].strip()
    flyer_data = {
        "group_id": message.chat.id,
        "name": flyer_name,
        "caption": caption,
        "created_by": message.from_user.id,
        "created_at": datetime.utcnow()
    }
    # Attach photo if replying to one
    if message.reply_to_message and message.reply_to_message.photo:
        flyer_data["file_id"] = message.reply_to_message.photo.file_id
    elif message.reply_to_message and message.reply_to_message.text:
        flyer_data["caption"] = message.reply_to_message.text

    flyers_col.update_one(
        {"group_id": message.chat.id, "name": flyer_name},
        {"$set": flyer_data},
        upsert=True
    )
    await message.reply("✅ Flyer saved!")

async def flyer_handler(client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("❌ Usage: /flyer <name>")
    flyer_name = args[1].strip().lower()
    flyer = flyers_col.find_one({"group_id": message.chat.id, "name": flyer_name})
    if not flyer:
        return await message.reply("❌ Flyer not found.")
    if flyer.get("file_id"):
        await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))
    else:
        await message.reply(flyer.get("caption", ""))

async def listflyers_handler(client, message: Message):
    flyers = list(flyers_col.find({"group_id": message.chat.id}))
    if not flyers:
        return await message.reply("No flyers saved yet.")
    names = "\n".join([f"• <b>{f['name']}</b>" for f in flyers])
    await message.reply(f"📋 Flyers:\n{names}", parse_mode="html")

async def deleteflyer_handler(client, message: Message):
    if not await is_admin(client, message):
        return await message.reply("❌ You must be an admin to use this command.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("❌ Usage: /deleteflyer <name>")
    flyer_name = args[1].strip().lower()
    res = flyers_col.delete_one({"group_id": message.chat.id, "name": flyer_name})
    if res.deleted_count:
        await message.reply("✅ Flyer deleted.")
    else:
        await message.reply("❌ Flyer not found.")

async def changeflyer_handler(client, message: Message):
    if not await is_admin(client, message):
        return await message.reply("❌ You must be an admin to use this command.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("❌ Usage: /changeflyer <name> (reply to photo/text)")
    flyer_name = args[1].strip().lower()
    flyer = flyers_col.find_one({"group_id": message.chat.id, "name": flyer_name})
    if not flyer:
        return await message.reply("❌ Flyer not found.")
    new_data = {}
    if message.reply_to_message and message.reply_to_message.photo:
        new_data["file_id"] = message.reply_to_message.photo.file_id
        new_data["caption"] = flyer.get("caption", "")
    elif message.reply_to_message and message.reply_to_message.text:
        new_data["caption"] = message.reply_to_message.text
        new_data.pop("file_id", None)
    else:
        return await message.reply("Reply to an image or a text message.")
    flyers_col.update_one(
        {"group_id": message.chat.id, "name": flyer_name},
        {"$set": new_data}
    )
    await message.reply("✅ Flyer updated!")

async def scheduleflyer_handler(client, message: Message):
    if not await is_admin(client, message):
        return await message.reply("❌ You must be an admin to use this command.")
    args = message.text.split(maxsplit=6)
    if len(args) < 6:
        return await message.reply(
            "❌ Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|repeat> <target_group>"
        )
    flyer_name, date_str, time_str, repeat_mode, target_group = args[1:6]
    try:
        run_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return await message.reply("❌ Invalid date/time. Use: YYYY-MM-DD HH:MM")
    if repeat_mode not in ("once", "repeat"):
        return await message.reply("❌ Repeat mode must be 'once' or 'repeat'.")
    # You must implement actual scheduling logic here!
    # This is a placeholder:
    # schedule_flyer_post(flyer_name, run_time, repeat_mode, target_group)
    await message.reply(
        f"✅ Scheduled flyer '{flyer_name}' for {run_time} ({repeat_mode}) in {target_group}."
    )

def register(app):
    app.add_handler(filters.command("addflyer")(addflyer_handler))
    app.add_handler(filters.command("flyer")(flyer_handler))
    app.add_handler(filters.command("listflyers")(listflyers_handler))
    app.add_handler(filters.command("deleteflyer")(deleteflyer_handler))
    app.add_handler(filters.command("changeflyer")(changeflyer_handler))
    app.add_handler(filters.command("scheduleflyer")(scheduleflyer_handler))
