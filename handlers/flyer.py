import os
from pymongo import MongoClient
from pyrogram import filters

MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME") or "succubot"
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyer_coll = mongo['flyers']

def is_admin(user_id, chat_id, client):
    # You can improve this for owner/admin
    member = client.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")

def register(app):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer(client, message):
        if not is_admin(message.from_user.id, message.chat.id, client):
            return await message.reply("❌ Admins only.")
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("Reply to a photo with /addflyer <name> <caption>")
        try:
            _, name, *caption = message.text.split(maxsplit=2)
            caption = caption[0] if caption else ""
            flyer_coll.update_one(
                {"chat_id": message.chat.id, "name": name},
                {"$set": {
                    "file_id": message.reply_to_message.photo.file_id,
                    "caption": caption,
                    "chat_id": message.chat.id,
                    "name": name
                }},
                upsert=True
            )
            await message.reply(f"✅ Flyer '{name}' added.")
        except Exception as e:
            await message.reply(f"❌ Error: {e}")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def listflyers(client, message):
        flyers = list(flyer_coll.find({"chat_id": message.chat.id}))
        if not flyers:
            await message.reply("No flyers in this group.")
        else:
            msg = "Flyers:\n" + "\n".join(f"• {f['name']}" for f in flyers)
            await message.reply(msg)

    @app.on_message(filters.command("flyer") & filters.group)
    async def getflyer(client, message):
        try:
            _, name = message.text.split(maxsplit=1)
        except:
            return await message.reply("Usage: /flyer <name>")
        flyer = flyer_coll.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ Not found.")
        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def changeflyer(client, message):
        if not is_admin(message.from_user.id, message.chat.id, client):
            return await message.reply("❌ Admins only.")
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("Reply to a photo with /changeflyer <name>")
        try:
            _, name = message.text.split(maxsplit=1)
            flyer = flyer_coll.find_one({"chat_id": message.chat.id, "name": name})
            if not flyer:
                return await message.reply("❌ Not found.")
            flyer_coll.update_one(
                {"chat_id": message.chat.id, "name": name},
                {"$set": {"file_id": message.reply_to_message.photo.file_id}}
            )
            await message.reply(f"✅ Flyer '{name}' updated.")
        except Exception as e:
            await message.reply(f"❌ Error: {e}")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def deleteflyer(client, message):
        if not is_admin(message.from_user.id, message.chat.id, client):
            return await message.reply("❌ Admins only.")
        try:
            _, name = message.text.split(maxsplit=1)
            flyer = flyer_coll.find_one_and_delete({"chat_id": message.chat.id, "name": name})
            if not flyer:
                return await message.reply("❌ Not found.")
            await message.reply(f"✅ Flyer '{name}' deleted.")
        except Exception as e:
            await message.reply(f"❌ Error: {e}")
