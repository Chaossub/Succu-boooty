@app.on_message(filters.command("mute") & filters.group)
async def mute_user(client, message: Message):
    chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if not is_admin(chat_member, message.from_user.id):
        await message.reply("Only admins can mute users.")
        return

    user = await get_target_user(client, message)
    if not user:
        return

    if user.is_bot:
        await message.reply("Cannot mute a bot.")
        return

    if user.id == message.from_user.id:
        await message.reply("You cannot mute yourself.")
        return

    if user.id == OWNER_ID:
        await message.reply("You cannot mute the bot owner.")
        return

    try:
        logging.debug(f"Muting user: {user.id} - {user.first_name}")
        await client.restrict_chat_member(
            message.chat.id,
            user.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            ),
            until_date=None
        )
        await message.reply(f"{user.mention} has been muted.")
    except Exception as e:
        logging.error(f"Failed to mute user {user.id}: {e}", exc_info=True)
        await message.reply(f"Failed to mute: {e}")
