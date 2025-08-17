# handlers/dmnow.py
# /dmnow — post a deep-link button for members to open the bot DM.
# - In groups: admins only
# - In private: restricted to OWNER / SUPER_ADMINS (optional)
# - Does NOT touch DM-ready. User must press /start in DM to become ready.

import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0"))
SUPER_ADMINS = {
    int(x) for x in os.getenv("SUPER_ADMINS", "").replace(";", ",").split(",") if x.strip().isdigit()
}

# Defaults (overridable by env)
DMNOW_BTN  = os.getenv("DMNOW_BTN", "💌 DM Now")
DMNOW_TEXT = os.getenv("DMNOW_TEXT", "Tap to DM the team.")

async def _is_group_admin(app: Client, chat_id: int, user_id: int) -> bool:
    try:
        m = await app.get_chat_member(chat_id, user_id)
        return (m.privileges is not None) or (m.status in ("administrator", "creator"))
    except Exception:
        return False

def _is_high_priv(uid: int) -> bool:
    return uid in SUPER_ADMINS or uid in {OWNER_ID, SUPER_ADMIN_ID}

def register(app: Client):

    @app.on_message(filters.command("dmnow"))
    async def dmnow(client: Client, m: Message):
        # Permission gate
        if m.chat and m.chat.type != "private":
            if not await _is_group_admin(client, m.chat.id, m.from_user.id):
                return await m.reply_text("Admins only.")
        else:
            if not _is_high_priv(m.from_user.id):
                return await m.reply_text("Only admins can use this here.")

        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a public @username to create a DM button.")

        # Build deep-link to bot
        # Use ?start=ready so the first message pre-fills a parameter (your /start already handles it gracefully)
        url = f"https://t.me/{me.username}?start=ready"

        # Allow optional custom label/text: /dmnow <label>|<text>
        label, text = DMNOW_BTN, DMNOW_TEXT
        if len(m.command) > 1:
            arg = " ".join(m.command[1:]).strip()
            if "|" in arg:
                a, b = arg.split("|", 1)
                if a.strip(): label = a.strip()
                if b.strip(): text  = b.strip()
            else:
                # single token overrides label only
                if arg: label = arg

        kb = InlineKeyboardMarkup([[InlineKeyboardButton(label, url=url)]])

        # If replying to a message, put the button as a short follow-up so you can place it "at the end".
        if m.reply_to_message:
            return await m.reply_text(text, reply_markup=kb, disable_web_page_preview=True)

        # Otherwise just post the button & text in chat.
        await m.reply_text(text, reply_markup=kb, disable_web_page_preview=True)
