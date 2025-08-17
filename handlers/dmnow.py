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
            is_admin = (member.privileges is not None) or (member.status in ("administrator", "creator"))
        except Exception:
            is_admin = False

        if not is_admin:
            return await m.reply_text("Admins only.")

        # Deep link to this bot's DM /start
        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a public @username to create the DM button.")
        url = f"https://t.me/{me.username}?start=ready"

        # Customizable via env (optional)
        btn_text  = os.getenv("DMNOW_BTN", "💌 DM Now")
        lead_text = os.getenv("DMNOW_TEXT", "Tap the button to DM the bot for menus, rules, games & support.")

        # If the admin typed extra text after /dmnow, use that instead of env text
        # Example: "/dmnow Hey boys — tap to message us" -> uses that caption
        text = lead_text
        if m.text and len(m.text.split(maxsplit=1)) > 1:
            text = m.text.split(maxsplit=1)[1]

        kb = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=url)]])
        await m.reply_text(text, reply_markup=kb, disable_web_page_preview=True)
