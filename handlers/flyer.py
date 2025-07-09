
db = client[MONGO_DB]

LA_TIMEZONE = pytz.timezone("America/Los_Angeles")

# Example: /addflyer <name> <caption>
@flyer_db.on_message(filters.command("addflyer") & filters.group)
@admin_only
async def add_flyer_command(client, message: Message):
    if not message.photo:
        return await message.reply("❌ Please attach an image with your flyer.")

    try:
        name_caption = message.text.split(maxsplit=2)
        if len(name_caption) < 3:
            return await message.reply("❌ Usage: /addflyer <name> <caption>")

        name = name_caption[1].strip().lower()
        caption = name_caption[2].strip()
        file_id = message.photo.file_id

        await add_flyer(db, message.chat.id, name, file_id, caption)
        await message.reply(f"✅ Flyer '{name}' added successfully!")
    except Exception as e:
        logging.exception(e)
        await message.reply("❌ Failed to add flyer.")

# Change flyer image (reply to new image)
@flyer_db.on_message(filters.command("changeflyer") & filters.reply & filters.group)
@admin_only
async def change_flyer_command(client, message: Message):
    if not message.reply_to_message.photo:
        return await message.reply("❌ Reply to a photo to change the flyer image.")

    try:
        name = message.text.split(maxsplit=1)[1].strip().lower()
        file_id = message.reply_to_message.photo.file_id
        await change_flyer_image(db, message.chat.id, name, file_id)
        await message.reply(f"✅ Flyer '{name}' image updated.")
    except Exception as e:
        logging.exception(e)
        await message.reply("❌ Failed to update flyer image.")

# /deleteflyer <name>
@flyer_db.on_message(filters.command("deleteflyer") & filters.group)
@admin_only
async def delete_flyer_command(client, message: Message):
    try:
        name = message.text.split(maxsplit=1)[1].strip().lower()
        await delete_flyer(db, message.chat.id, name)
        await message.reply(f"🗑️ Flyer '{name}' deleted.")
    except Exception as e:
        logging.exception(e)
        await message.reply("❌ Failed to delete flyer.")

# /listflyers
@flyer_db.on_message(filters.command("listflyers") & filters.group)
async def list_flyers_command(client, message: Message):
    try:
        flyers = await list_flyers(db, message.chat.id)
        if not flyers:
            await message.reply("📭 No flyers added yet.")
            return

        msg = "📋 <b>Flyers in this group:</b>\n"
        for flyer in flyers:
            msg += f"- {flyer['name']}\n"

        await message.reply(msg)
    except Exception as e:
        logging.exception(e)
        await message.reply("❌ Failed to fetch flyers.")

# /flyer <name>
@flyer_db.on_message(filters.command("flyer") & filters.group)
async def get_flyer_command(client, message: Message):
    try:
        name = message.text.split(maxsplit=1)[1].strip().lower()
        flyer = await get_flyer(db, message.chat.id, name)

        if not flyer:
            return await message.reply("❌ Flyer not found.")

        await message.reply_photo(flyer['file_id'], caption=flyer['caption'])
    except Exception as e:
        logging.exception(e)
        await message.reply("❌ Could not retrieve flyer.")

# /scheduleflyer <name> <time> <target_group>
@flyer_db.on_message(filters.command("scheduleflyer") & filters.group)
@admin_only
async def schedule_flyer_command(client, message: Message):
    try:
        args = message.text.split(maxsplit=3)
        if len(args) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <target_group_id>")

        name = args[1].strip().lower()
        post_time_str = args[2]
        target_group = int(args[3])

        now = datetime.now(LA_TIMEZONE)
        post_time = datetime.strptime(post_time_str, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day, tzinfo=LA_TIMEZONE
        )

        if post_time < now:
            post_time = post_time.replace(day=now.day + 1)

        await schedule_flyer(db, message.chat.id, name, target_group, post_time)
        await message.reply(f"📅 Scheduled flyer '{name}' to post in group {target_group} at {post_time.strftime('%H:%M %Z')}.")
    except Exception as e:
        logging.exception(e)
        await message.reply("❌ Failed to schedule flyer.")

# Register function
def register(app, scheduler):
    pass  # Registration is handled by decorators above
