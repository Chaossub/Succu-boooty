from pyrogram import Client, filters

@Client.on_message(filters.command("flyertest"))
async def flyertest(client, message):
    await message.reply("✅ Flyer handler is working!")
