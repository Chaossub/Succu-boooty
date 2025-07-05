import os
import asyncio
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

SUPER_ADMIN_ID = 6964994611  # Your Telegram ID

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["succubot"]
feds = db["federations"]

def is_fed_admin(user_id, fed_id):
    fed = feds.find_one({"fed_id": fed_id})
    if not fed:
        return False
    if user_id == SUPER_ADMIN_ID:
        return True
    return user_id in fed.get("admins", []) or user_id == fed.get("owner_id")

def get_fed_by_group(chat_id):
    return feds.find_one({"groups": chat_id})

def register(app):

    @app.on_message(filters.command("createfed") & filters.group)
    async def create_fed(_, message: Message):
        user_id = message.from_user.id
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: /createfed <fed_name>")
        fed_name = args[1].strip()
        if feds.find_one({"name": fed_name}):
            return await message.reply("A federation with that name already exists!")
        fed_id = str(abs(hash(fed_name + str(user_id))) % (10 ** 9))
        feds.insert_one({
            "fed_id": fed_id,
            "name": fed_name,
            "owner_id": user_id,
            "admins": [],
            "groups": [message.chat.id],
            "bans": []
        })
        await message.reply(f"✅ Federation '{fed_name}' created!\nID: <code>{fed_id}</code>")

    @app.on_message(filters.command("delfed") & filters.group)
    async def delete_fed(_, message: Message):
        user_id = message.from_user.id
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("Usage: /delfed <fed_id>")
        fed_id = args[1].strip()
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            return await message.reply("No federation found with that ID.")
        if user_id != fed.get("owner_id") and user_id != SUPER_ADMIN_ID:
            return await message.reply("Only the federation owner or bot owner can delete this federation.")
        feds.delete_one({"fed_id": fed_id})
        await message.reply("❌ Federation deleted.")

    @app.on_message(filters.command("renamefed") & filters.group)
    async def rename_fed(_, message: Message):
        user_id = message.from_user.id
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply("Usage: /renamefed <fed_id> <new_name>")
        fed_id = args[1].strip()
        new_name = args[2].strip()
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            return await message.reply("No federation found with that ID.")
        if user_id != fed.get("owner_id") and user_id != SUPER_ADMIN_ID:
            return await message.reply("Only the federation owner or bot owner can rename this federation.")
        feds.update_one({"fed_id": fed_id}, {"$set": {"name": new_name}})
        await message.reply(f"✅ Federation renamed to '{new_name}'.")

    @app.on_message(filters.command("addfedadmin") & filters.group)
    async def add_fed_admin(_, message: Message):
        user_id = message.from_user.id
        args = message.text.split()
        if len(args) < 3:
            return await message.reply("Usage: /addfedadmin <fed_id> <@user>")
        fed_id = args[1].strip()
        mention = args[2].strip()
        if mention.startswith('@'):
            target_user = await app.get_users(mention)
        else:
            try:
                target_user = await app.get_users(int(mention))
            except Exception:
                return await message.reply("Invalid user.")
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            return await message.reply("No federation found with that ID.")
        if user_id != fed.get("owner_id") and user_id != SUPER_ADMIN_ID:
            return await message.reply("Only the federation owner or bot owner can add admins.")
        if target_user.id in fed.get("admins", []):
            return await message.reply("User is already an admin.")
        feds.update_one({"fed_id": fed_id}, {"$addToSet": {"admins": target_user.id}})
        await message.reply(f"✅ {target_user.mention} added as federation admin.")

    @app.on_message(filters.command("delfedadmin") & filters.group)
    async def del_fed_admin(_, message: Message):
        user_id = message.from_user.id
        args = message.text.split()
        if len(args) < 3:
            return await message.reply("Usage: /delfedadmin <fed_id> <@user>")
        fed_id = args[1].strip()
        mention = args[2].strip()
        if mention.startswith('@'):
            target_user = await app.get_users(mention)
        else:
            try:
                target_user = await app.get_users(int(mention))
            except Exception:
                return await message.reply("Invalid user.")
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            return await message.reply("No federation found with that ID.")
        if user_id != fed.get("owner_id") and user_id != SUPER_ADMIN_ID:
            return await message.reply("Only the federation owner or bot owner can remove admins.")
        feds.update_one({"fed_id": fed_id}, {"$pull": {"admins": target_user.id}})
        await message.reply(f"✅ {target_user.mention} removed from federation admins.")

    @app.on_message(filters.command("linkgroup") & filters.group)
    async def link_group(_, message: Message):
        user_id = message.from_user.id
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("Usage: /linkgroup <fed_id>")
        fed_id = args[1].strip()
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            return await message.reply("No federation found with that ID.")
        if user_id != fed.get("owner_id") and user_id != SUPER_ADMIN_ID:
            return await message.reply("Only the federation owner or bot owner can link groups.")
        if message.chat.id in fed.get("groups", []):
            return await message.reply("This group is already linked to that federation.")
        feds.update_one({"fed_id": fed_id}, {"$addToSet": {"groups": message.chat.id}})
        await message.reply("✅ Group linked to federation.")

    @app.on_message(filters.command("unlinkgroup") & filters.group)
    async def unlink_group(_, message: Message):
        user_id = message.from_user.id
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("Usage: /unlinkgroup <fed_id>")
        fed_id = args[1].strip()
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            return await message.reply("No federation found with that ID.")
        if user_id != fed.get("owner_id") and user_id != SUPER_ADMIN_ID:
            return await message.reply("Only the federation owner or bot owner can unlink groups.")
        feds.update_one({"fed_id": fed_id}, {"$pull": {"groups": message.chat.id}})
        await message.reply("✅ Group unlinked from federation.")

    @app.on_message(filters.command("fedban") & filters.group)
    async def fed_ban(_, message: Message):
        user_id = message.from_user.id
        args = message.text.split()
        if len(args) < 3:
            return await message.reply("Usage: /fedban <fed_id> <@user> [reason]")
        fed_id = args[1].strip()
        mention = args[2].strip()
        reason = " ".join(args[3:]) if len(args) > 3 else ""
        if mention.startswith('@'):
            target_user = await app.get_users(mention)
        else:
            try:
                target_user = await app.get_users(int(mention))
            except Exception:
                return await message.reply("Invalid user.")
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            return await message.reply("No federation found with that ID.")
        if not is_fed_admin(user_id, fed_id):
            return await message.reply("You are not a federation admin or owner.")
        if target_user.id == fed.get("owner_id"):
            return await message.reply("You can't fedban the federation owner.")
        if target_user.id in fed.get("bans", []):
            return await message.reply("User is already banned in this federation.")
        feds.update_one({"fed_id": fed_id}, {"$addToSet": {"bans": target_user.id}})
        await message.reply(
            f"🚫 {target_user.mention} has been federation banned!\nReason: <i>{reason or 'No reason given.'}</i>"
        )

    @app.on_message(filters.command("fedunban") & filters.group)
    async def fed_unban(_, message: Message):
        user_id = message.from_user.id
        args = message.text.split()
        if len(args) < 3:
            return await message.reply("Usage: /fedunban <fed_id> <@user>")
        fed_id = args[1].strip()
        mention = args[2].strip()
        if mention.startswith('@'):
            target_user = await app.get_users(mention)
        else:
            try:
                target_user = await app.get_users(int(mention))
            except Exception:
                return await message.reply("Invalid user.")
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            return await message.reply("No federation found with that ID.")
        if not is_fed_admin(user_id, fed_id):
            return await message.reply("You are not a federation admin or owner.")
        feds.update_one({"fed_id": fed_id}, {"$pull": {"bans": target_user.id}})
        await message.reply(f"✅ {target_user.mention} has been federation unbanned.")

    @app.on_message(filters.command("fedlist") & filters.group)
    async def fed_list(_, message: Message):
        user_id = message.from_user.id
        user_feds = feds.find({"owner_id": user_id})
        fed_list_text = "Your Federations:\n"
        found = False
        for fed in user_feds:
            fed_list_text += f"• <b>{fed['name']}</b> (<code>{fed['fed_id']}</code>)\n"
            found = True
        if not found:
            fed_list_text = "You don't own any federations."
        await message.reply(fed_list_text)

    @app.on_message(filters.command("fedinfo") & filters.group)
    async def fed_info(_, message: Message):
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("Usage: /fedinfo <fed_id>")
        fed_id = args[1].strip()
        fed = feds.find_one({"fed_id": fed_id})
        if not fed:
            return await message.reply("No federation found with that ID.")
        admins = fed.get("admins", [])
        bans = fed.get("bans", [])
        groups = fed.get("groups", [])
        await message.reply(
            f"<b>Federation:</b> {fed['name']}\n"
            f"<b>ID:</b> <code>{fed['fed_id']}</code>\n"
            f"<b>Owner:</b> <code>{fed['owner_id']}</code>\n"
            f"<b>Admins:</b> {', '.join([str(a) for a in admins])}\n"
            f"<b>Bans:</b> {len(bans)} users\n"
            f"<b>Groups Linked:</b> {len(groups)}"
        )

    @app.on_message(filters.command("fedcheck") & filters.group)
    async def fed_check(_, message: Message):
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("Usage: /fedcheck <@user>")
        mention = args[1].strip()
        if mention.startswith('@'):
            target_user = await app.get_users(mention)
        else:
            try:
                target_user = await app.get_users(int(mention))
            except Exception:
                return await message.reply("Invalid user.")
        fed = get_fed_by_group(message.chat.id)
        if not fed:
            return await message.reply("This group is not linked to a federation.")
        if target_user.id in fed.get("bans", []):
            return await message.reply(f"🚫 {target_user.mention} is federation banned in this group.")
        else:
            return await message.reply(f"{target_user.mention} is <b>not</b> federation banned in this group.")
