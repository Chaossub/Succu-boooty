import os
import json
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.check_admin import is_admin

FLYER_FILE = "data/flyers.json"
os.makedirs("data", exist_ok=True)

if not os.path.exists(FLYER_FILE):
    with open(FLYER_FILE, "w") as f:
        json.dump({}, f)


def load_flyers():
    with open(FLYER_FILE, "r") as f:
        return json.load(f)


def save_flyers(flyers):
    with open(FLYER_FILE, "w") as f:
        json.dump(flyers, f, indent=2)


@Client.on_message(filters.command("addflyer") & filters.group)
async def add_flyer(client: Client, message: Message):
    # TEMPORARY: print and bypass admin check
    user_id = message.from_user.id
    chat_id = message.chat.id
    print(f"DEBUG: Checking admin status for user {user_id} in chat {chat_id}")
    is_admin_status = await is_admin(client, chat_id, user_id)
    print(f"DEBUG: is_admin returned: {is_admin_status}")
    
    # TEMP BYPASS: Allow owner
    if str(user_id) != "6964994611" and not is_admin_status:
        return await message.reply("🚫 Only admins can create flyers.")

    if not message.photo:
        return await message.reply("❌ Please attach an image with your flyer.")

    if len(message.command) < 2:
        return await message.reply("✏️ Usage: /addflyer <name> <caption>")

    name = message.command[1].lower()
    caption = " ".join(message.command[2:]) or ""

    flyers = load_flyers()
    flyers[name] = {
        "file_id": message.photo.file_id,
        "caption": caption
    }
    save_flyers(flyers)

    await message.reply(f"✅ Flyer <b>{name}</b> added successfully!", quote=True)


@Client.on_message(filters.command("flyer") & filters.group)
async def send_flyer(client: Client, message: Message):
    flyers = load_flyers()
    if len(message.command) < 2:
        return await message.reply("✏️ Usage: /flyer <name>")

    name = message.command[1].lower()
    flyer = flyers.get(name)

    if not flyer:
        return await message.reply("❌ Flyer not found.")

    await client.send_photo(
        chat_id=message.chat.id,
        photo=flyer["file_id"],
        caption=flyer["caption"],
    )


@Client.on_message(filters.command("listflyers") & filters.group)
async def list_flyers(client: Client, message: Message):
    flyers = load_flyers()
    if not flyers:
        return await message.reply("📭 No flyers have been added yet.")
    flyer_list = "\n".join(f"• {name}" for name in flyers)
    await message.reply(f"📌 Current flyers:\n{flyer_list}")


@Client.on_message(filters.command("deleteflyer") & filters.group)
async def delete_flyer(client: Client, message: Message):
    if str(message.from_user.id) != "6964994611" and not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can delete flyers.")
    if len(message.command) < 2:
        return await message.reply("✏️ Usage: /deleteflyer <name>")

    name = message.command[1].lower()
    flyers = load_flyers()

    if name not in flyers:
        return await message.reply("❌ Flyer not found.")

    del flyers[name]
    save_flyers(flyers)
    await message.reply(f"🗑️ Flyer <b>{name}</b> deleted.")


@Client.on_message(filters.command("changeflyer") & filters.group)
async def change_flyer(client: Client, message: Message):
    if str(message.from_user.id) != "6964994611" and not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can update flyers.")

    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("❌ Reply to the new flyer image.")

    if len(message.command) < 2:
        return await message.reply("✏️ Usage: /changeflyer <name> (while replying to a new image)")

    name = message.command[1].lower()
    flyers = load_flyers()

    if name not in flyers:
        return await message.reply("❌ Flyer not found.")

    flyers[name]["file_id"] = message.reply_to_message.photo.file_id
    save_flyers(flyers)

    await message.reply(f"🔄 Flyer <b>{name}</b> updated.")

