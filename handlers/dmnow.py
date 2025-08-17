# handlers/dmnow.py
# Group-only helper to append a "DM Now" deep-link button to your message.
# Does NOT modify DM-ready state. Users become DM-ready when they press /start in DM.

import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

def register(app: Client):
    @app.on_message(filters.command("dmnow"))
    async def dmnow(client: Client, m: Message):
        # Must be used in groups by admins
        if not m.chat or m.chat.type == "private":
            return await m.reply_text("Use /dmnow in the group.")
        try:
            member = await client.get_chat_member(m.chat.id, m.from_user.id)
            if (member.privileges is None) and (member.status not in ("administrator", "creator")):
                return await m.reply_text("Admins only.")
        except Exception:
            return await m.reply_text("Admins only.")

        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a @username to build the DM button.")

        # Deep-link to /start — user must tap to DM the bot
        url  = f"https://t.me/{me.username}?start=ready"

        # Customizable via env (optional)
        btn_text  = os.getenv("DMNOW_BTN", "💌 DM Now")
        lead_text = os.getenv("DMNOW_TEXT", "Tap the button to DM the bot for menus, rules, games & support.")

        # If the admin typed a caption with /dmnow, use that text instead of env
        # Example: "Some message here" then add the button
        # (/dmnow command can be on its own line after your message)
        text = lead_text
        if m.text and len(m.text.split(maxsplit=1)) > 1:
            text = m.text.split(maxsplit=1)[1]

        kb = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=url)]])
        await m.reply_text(text, reply_markup=kb, disable_web_page_preview=True)
