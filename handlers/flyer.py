import json
from pyrogram import filters
from pyrogram.types import Message

FLYERS_PATH = "data/flyers.json"
SUPER_ADMIN_ID = 6964994611

def load_flyers():
    with open(FLYERS_PATH, "r") as f:
        return json.load(f)

def save_flyers(data):
    with open(FLYERS_PATH, "w") as f:
        json.dump(data, f)

def is_admin(app, user_id, chat_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = app.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

def register(app):

    @app.on_message(filters.command("createflyer") & filters.reply & filters.group)
    async def create_flyer(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can add flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: /createflyer <name> (reply to an image)")
        flyer_name = args[1].strip().lower()
        if not message.reply_to_message or not (message.reply_to_message.photo or message.reply_to_message.document):
            return await message.reply("Reply to a photo or file to save as a flyer!")
        flyer_file_id = (message.reply_to_message.photo or message.reply_to_message.document).file_id
        data = load_flyers()
        chat_id = str(message.chat.id)
        if chat_id not in data:
            data[chat_id] = {}
        if flyer_name in data[chat_id]:
            return await message.reply("A flyer with that name already exists! Use /changeflyer to update it.")
        data[chat_id][flyer_name] = flyer_file_id
        save_flyers(data)
        await message.reply(f"✅ Flyer '{flyer_name}' saved!")

    @app.on_message(filters.command("changeflyer") & filters.reply & filters.group)
    async def change_flyer(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can change flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: /changeflyer <name> (reply to an image)")
        flyer_name = args[1].strip().lower()
        if not message.reply_to_message or not (message.reply_to_message.photo or message.reply_to_message.document):
            return await message.reply("Reply to a photo or file to save as a flyer!")
        flyer_file_id = (message.reply_to_message.photo or message.reply_to_message.document).file_id
        data = load_flyers()
        chat_id = str(message.chat.id)
        if chat_id not in data or flyer_name not in data[chat_id]:
            return await message.reply("No flyer with that name. Use /createflyer first.")
        data[chat_id][flyer_name] = flyer_file_id
        save_flyers(data)
        await message.reply(f"✅ Flyer '{flyer_name}' updated!")

    @app.on_message(filters.command("flyerlist") & filters.group)
    async def flyer_list(_, message: Message):
        data = load_flyers()
        chat_id = str(message.chat.id)
        if chat_id not in data or not data[chat_id]:
            return await message.reply("No flyers saved in this group yet!")
        flyers = "\n".join([f"- {f}" for f in data[chat_id].keys()])
        await message.reply(f"📄 Flyers in this group:\n{flyers}")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: /flyer <name>")
        flyer_name = args[1].strip().lower()
        data = load_flyers()
        chat_id = str(message.chat.id)
        if chat_id not in data or flyer_name not in data[chat_id]:
            return await message.reply("No flyer with that name.")
        file_id = data[chat_id][flyer_name]
        try:
            await message.reply_photo(file_id)
        except Exception:
            await message.reply_document(file_id)

    @app.on_message(filters.command("delflyer") & filters.group)
    async def del_flyer(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can delete flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: /delflyer <name>")
        flyer_name = args[1].strip().lower()
        data = load_flyers()
        chat_id = str(message.chat.id)
        if chat_id not in data or flyer_name not in data[chat_id]:
            return await message.reply("No flyer with that name.")
        del data[chat_id][flyer_name]
        save_flyers(data)
        await message.reply("✅ Flyer deleted!")
