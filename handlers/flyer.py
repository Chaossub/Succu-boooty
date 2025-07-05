import json
from pyrogram import filters
from pyrogram.types import Message

FLYERS_PATH = "data/flyers.json"
SUPER_ADMIN_ID = 6964994611

def load_flyers():
    try:
        with open(FLYERS_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

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

def extract_file_id(msg):
    if msg.photo:
        return msg.photo.file_id
    if msg.document:
        return msg.document.file_id
    return None

def get_flyer_name(content):
    # For command in caption or text, returns the flyer name or None
    if not content:
        return None
    parts = content.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    return parts[1].strip().lower()

def register(app):

    @app.on_message(filters.group)
    async def flyer_commands(client, message: Message):
        content = message.text or message.caption
        if not content:
            return

        lower_content = content.lower()
        # CREATE
        if lower_content.startswith("/createflyer") or lower_content.startswith("!createflyer"):
            if not is_admin(client, message.from_user.id, message.chat.id):
                return await message.reply("Only admins can add flyers.")
            flyer_name = get_flyer_name(content)
            if not flyer_name:
                return await message.reply("Usage: /createflyer <name> (send with image/file as caption or reply)")
            file_id = extract_file_id(message)
            if not file_id and message.reply_to_message:
                file_id = extract_file_id(message.reply_to_message)
            if not file_id:
                return await message.reply("Attach a photo/file, or reply to one, with this command!")
            data = load_flyers()
            chat_id = str(message.chat.id)
            if chat_id not in data:
                data[chat_id] = {}
            if flyer_name in data[chat_id]:
                return await message.reply("A flyer with that name already exists! Use /changeflyer to update it.")
            data[chat_id][flyer_name] = file_id
            save_flyers(data)
            return await message.reply(f"✅ Flyer '{flyer_name}' saved!")

        # CHANGE
        if lower_content.startswith("/changeflyer") or lower_content.startswith("!changeflyer"):
            if not is_admin(client, message.from_user.id, message.chat.id):
                return await message.reply("Only admins can change flyers.")
            flyer_name = get_flyer_name(content)
            if not flyer_name:
                return await message.reply("Usage: /changeflyer <name> (send with image/file as caption or reply)")
            file_id = extract_file_id(message)
            if not file_id and message.reply_to_message:
                file_id = extract_file_id(message.reply_to_message)
            if not file_id:
                return await message.reply("Attach a photo/file, or reply to one, with this command!")
            data = load_flyers()
            chat_id = str(message.chat.id)
            if chat_id not in data or flyer_name not in data[chat_id]:
                return await message.reply("No flyer with that name. Use /createflyer first.")
            data[chat_id][flyer_name] = file_id
            save_flyers(data)
            return await message.reply(f"✅ Flyer '{flyer_name}' updated!")

        # DELETE
        if lower_content.startswith("/delflyer") or lower_content.startswith("!delflyer"):
            if not is_admin(client, message.from_user.id, message.chat.id):
                return await message.reply("Only admins can delete flyers.")
            args = content.split(maxsplit=1)
            if len(args) < 2:
                return await message.reply("Usage: /delflyer <name>")
            flyer_name = args[1].strip().lower()
            data = load_flyers()
            chat_id = str(message.chat.id)
            if chat_id not in data or flyer_name not in data[chat_id]:
                return await message.reply("No flyer with that name.")
            del data[chat_id][flyer_name]
            save_flyers(data)
            return await message.reply("✅ Flyer deleted!")

        # PIN
        if lower_content.startswith("/pinflyer") or lower_content.startswith("!pinflyer"):
            if not is_admin(client, message.from_user.id, message.chat.id):
                return await message.reply("Only admins can pin flyers.")
            args = content.split(maxsplit=1)
            if len(args) < 2:
                return await message.reply("Usage: /pinflyer <name>")
            flyer_name = args[1].strip().lower()
            data = load_flyers()
            chat_id = str(message.chat.id)
            if chat_id not in data or flyer_name not in data[chat_id]:
                return await message.reply("No flyer with that name.")
            file_id = data[chat_id][flyer_name]
            try:
                sent = await message.reply_photo(file_id)
            except Exception:
                sent = await message.reply_document(file_id)
            try:
                await client.pin_chat_message(chat_id, sent.id, disable_notification=True)
            except Exception as e:
                return await message.reply(f"Could not pin flyer: {e}")
            return await message.reply(f"📌 Flyer '{flyer_name}' pinned!")

        # UNPIN
        if lower_content.startswith("/unpinflyer") or lower_content.startswith("!unpinflyer"):
            if not is_admin(client, message.from_user.id, message.chat.id):
                return await message.reply("Only admins can unpin flyers.")
            try:
                await client.unpin_chat_message(message.chat.id)
                return await message.reply("📍 Unpinned the current pinned message!")
            except Exception as e:
                return await message.reply(f"Could not unpin: {e}")

        # FLYERLIST
        if lower_content.startswith("/flyerlist") or lower_content.startswith("!flyerlist"):
            data = load_flyers()
            chat_id = str(message.chat.id)
            if chat_id not in data or not data[chat_id]:
                return await message.reply("No flyers saved in this group yet!")
            flyers = "\n".join([f"- <b>{f}</b>" for f in data[chat_id].keys()])
            return await message.reply(f"📄 Flyers in this group:\n{flyers}")

        # GET FLYER
        if lower_content.startswith("/flyer") or lower_content.startswith("!flyer"):
            args = content.split(maxsplit=1)
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
