import os
import logging
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable not set")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["succubot"]  # use lowercase db name
feds = db["federations"]
groups = db["groups"]

SUPER_ADMIN_ID = 6964994611

def is_fed_admin(user_id, fed_id):
    fed = feds.find_one({"fed_id": fed_id})
    if not fed:
        return False
    if user_id == fed["owner_id"]:
        return True
    if user_id in fed.get("admins", []):
        return True
    if user_id == SUPER_ADMIN_ID:
        return True
    return False

def register(app):

    @app.on_message(filters.command("createfed") & filters.group)
    async def create_fed(client, message: Message):
        logging.info(f"Received /createfed command from user {message.from_user.id} in chat {message.chat.id}")
        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not args[1].strip():
            await message.reply("Usage: /createfed <name>")
            return
        fed_name = args[1].strip()
        fed_id = f"fed-{message.chat.id}"
        if feds.find_one({"fed_id": fed_id}):
            await message.reply("This group already has a federation.")
            return
        try:
            feds.insert_one({
                "fed_id": fed_id,
                "name": fed_name,
                "owner_id": message.from_user.id,
                "admins": [],
                "bans": []
            })
        except Exception as e:
            await message.reply(f"Database error:\n<code>{e}</code>")
            logging.error(f"Failed to insert federation: {e}")
            return
        await message.reply(f"✅ Federation <b>{fed_name}</b> created!\nFedID: <code>{fed_id}</code>")

    @app.on_message(filters.command("fedlist") & filters.group)
    async def fed_list(client, message: Message):
        logging.info(f"Received /fedlist command from user {message.from_user.id} in chat {message.chat.id}")
        fed_list = list(feds.find({}))
        if not fed_list:
            await message.reply("No federations found.")
            return
        text = "<b>Federations:</b>\n"
        for fed in fed_list:
            text += f"- <code>{fed['fed_id']}</code>: {fed.get('name', 'No name')}\n"
        await message.reply(text)

    @app.on_message(filters.command("delfed") & filters.group)
    async def delete_fed(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /delfed <fed_id>")
            return
        fed_id = args[1].strip()
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            await message.reply("No federation found with that ID.")
            return
        if message.from_user.id != fed["owner_id"] and message.from_user.id != SUPER_ADMIN_ID:
            await message.reply("Only the federation owner or super admin can delete this federation.")
            return
        feds.delete_one({"fed_id": fed_id})
        groups.update_many({"fed_id": fed_id}, {"$unset": {"fed_id": ""}})
        await message.reply(f"✅ Federation <b>{fed_id}</b> deleted and unlinked from all groups.")

    @app.on_message(filters.command("joinfed") & filters.group)
    async def join_fed(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /joinfed <fed_id>")
            return
        fed_id = args[1].strip()
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            await message.reply("No federation found with that ID.")
            return
        groups.update_one({"chat_id": message.chat.id}, {"$set": {"fed_id": fed_id}}, upsert=True)
        await message.reply(f"✅ Group linked to federation <b>{fed_id}</b>.")

    @app.on_message(filters.command("leavefed") & filters.group)
    async def leave_fed(client, message: Message):
        groups.update_one({"chat_id": message.chat.id}, {"$unset": {"fed_id": ""}})
        await message.reply("✅ Group unlinked from its federation.")

    @app.on_message(filters.command("fedban") & filters.group)
    async def fedban_user(client, message: Message):
        group_doc = groups.find_one({"chat_id": message.chat.id})
        fed_id = group_doc.get("fed_id") if group_doc else None
        if not fed_id:
            await message.reply("This group is not part of a federation.")
            return
        if not is_fed_admin(message.from_user.id, fed_id):
            await message.reply("Only federation admins/owner/superadmin can fedban.")
            return
        user = None
        reason = ""
        if message.reply_to_message:
            user = message.reply_to_message.from_user
            args = message.text.split(maxsplit=1)
            reason = args[1] if len(args) > 1 else ""
        else:
            args = message.text.split(maxsplit=2)
            if len(args) < 2:
                await message.reply("Reply to a user or use /fedban @username or user_id [reason]")
                return
            mention = args[1]
            reason = args[2] if len(args) > 2 else ""
            try:
                if mention.startswith("@"):
                    user = await client.get_users(mention)
                else:
                    user = await client.get_users(int(mention))
            except Exception as e:
                await message.reply(f"Invalid user! Use /fedban as reply, /fedban @username, or /fedban user_id.\n\n<code>{e}</code>")
                return
        if not user:
            await message.reply("Couldn't find user to fedban.")
            return
        user_id = user.id
        fed = feds.find_one({"fed_id": fed_id})
        if any(b['user_id'] == user_id for b in fed.get("bans", [])):
            await message.reply("User is already fedbanned.")
            return
        ban_entry = {"user_id": user_id, "reason": reason}
        feds.update_one({"fed_id": fed_id}, {"$push": {"bans": ban_entry}})
        reason_text = f"\n<b>Reason:</b> {reason}" if reason else ""
        await message.reply(f"✅ {user.mention} has been federationally banned!{reason_text}")

    @app.on_message(filters.command("fedunban") & filters.group)
    async def fedunban_user(client, message: Message):
        group_doc = groups.find_one({"chat_id": message.chat.id})
        fed_id = group_doc.get("fed_id") if group_doc else None
        if not fed_id:
            await message.reply("This group is not part of a federation.")
            return
        if not is_fed_admin(message.from_user.id, fed_id):
            await message.reply("Only federation admins/owner/superadmin can fedunban.")
            return
        if message.reply_to_message:
            user = message.reply_to_message.from_user
        else:
            args = message.text.split()
            if len(args) < 2:
                await message.reply("Reply to a user or use /fedunban @username or user_id")
                return
            mention = args[1]
            try:
                if mention.startswith("@"):
                    user = await client.get_users(mention)
                else:
                    user = await client.get_users(int(mention))
            except Exception as e:
                await message.reply(f"Invalid user! Use /fedunban as reply, /fedunban @username, or /fedunban user_id.\n\n<code>{e}</code>")
                return
        if not user:
            await message.reply("Couldn't find user to fedunban.")
            return
        user_id = user.id
        fed = feds.find_one({"fed_id": fed_id})
        if not any(b['user_id'] == user_id for b in fed.get("bans", [])):
            await message.reply("User is not fedbanned.")
            return
        feds.update_one({"fed_id": fed_id}, {"$pull": {"bans": {"user_id": user_id}}})
        await message.reply(f"✅ {user.mention} has been federationally unbanned!")

    @app.on_message(filters.command("fedbans") & filters.group)
    async def fedbans_list(client, message: Message):
        group_doc = groups.find_one({"chat_id": message.chat.id})
        fed_id = group_doc.get("fed_id") if group_doc else None
        if not fed_id:
            await message.reply("This group is not part of a federation.")
            return
        fed = feds.find_one({"fed_id": fed_id})
        ban_list = fed.get("bans", [])
        if not ban_list:
            await message.reply("No users are fedbanned in this federation.")
            return
        ban_text = "\n".join([
            f"<code>{ban['user_id']}</code>" + (f" — {ban['reason']}" if ban.get("reason") else "")
            for ban in ban_list
        ])
        await message.reply(f"🚫 Fedbanned users in <b>{fed_id}</b>:\n{ban_text}")

    @app.on_message(filters.command("addfedadmin") & filters.group)
    async def add_fed_admin(client, message: Message):
        args = message.text.split()
        if len(args) < 3:
            await message.reply("Usage: /addfedadmin <fed_id> <@username or user_id>")
            return
        fed_id = args[1]
        mention = args[2]
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            await message.reply("No federation found with that ID.")
            return
        if message.from_user.id != fed["owner_id"] and message.from_user.id != SUPER_ADMIN_ID:
            await message.reply("Only the federation owner or super admin can add federation admins.")
            return
        try:
            if mention.startswith("@"):
                user = await client.get_users(mention)
            else:
                user = await client.get_users(int(mention))
        except Exception as e:
            await message.reply(f"Could not find that user.\n\n<code>{e}</code>")
            return
        if user.id in fed.get("admins", []):
            await message.reply("User is already a federation admin.")
            return
        feds.update_one({"fed_id": fed_id}, {"$push": {"admins": user.id}})
        await message.reply(f"✅ {user.mention} has been added as a federation admin!")

    @app.on_message(filters.command("removefedadmin") & filters.group)
    async def remove_fed_admin(client, message: Message):
        args = message.text.split()
        if len(args) < 3:
            await message.reply("Usage: /removefedadmin <fed_id> <@username or user_id>")
            return
        fed_id = args[1]
        mention = args[2]
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            await message.reply("No federation found with that ID.")
            return
        if message.from_user.id != fed["owner_id"] and message.from_user.id != SUPER_ADMIN_ID:
            await message.reply("Only the federation owner or super admin can remove federation admins.")
            return
        try:
            if mention.startswith("@"):
                user = await client.get_users(mention)
            else:
                user = await client.get_users(int(mention))
        except Exception as e:
            await message.reply(f"Could not find that user.\n\n<code>{e}</code>")
            return
        if user.id not in fed.get("admins", []):
            await message.reply("User is not a federation admin.")
            return
        feds.update_one({"fed_id": fed_id}, {"$pull": {"admins": user.id}})
        await message.reply(f"✅ {user.mention} has been removed as a federation admin!")

    @app.on_message(filters.command("fedadmins") & filters.group)
    async def fed_admins(client, message: Message):
        args = message.text.split()
        if len(args) < 2:
            await message.reply("Usage: /fedadmins <fed_id>")
            return
        fed_id = args[1]
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            await message.reply("No federation found with that ID.")
            return
        admin_ids = fed.get("admins", [])
        owner_id = fed["owner_id"]
        text = f"<b>Owner:</b> <code>{owner_id}</code>\n<b>Admins:</b>\n"
        if not admin_ids:
            text += "No federation admins have been set."
        else:
            for admin_id in admin_ids:
                try:
                    user = await client.get_users(admin_id)
                    text += f"- {user.mention} (<code>{admin_id}</code>)\n"
                except Exception:
                    text += f"- <code>{admin_id}</code>\n"
        await message.reply(text)
