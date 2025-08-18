# handlers/dmnow.py
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def register(app: Client):

    @app.on_message(filters.command("dmnow") & ~filters.private)
    async def dmnow_button(client: Client, m):
        """
        Group-only helper: replies with a 'DM Now' deep-link button to this bot.
        Does NOT set dm-ready; users become dm-ready after pressing /start in DM.
        """
        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a @username to make a DM button.")

        url = f"https://t.me/{me.username}?start=ready"
        btn_text = "💌 DM Now"
        line = "Tap to DM for quick support — Contact Admins, Help, and anonymous relay in one click."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=url)]])
        await m.reply_text(line, reply_markup=kb)
