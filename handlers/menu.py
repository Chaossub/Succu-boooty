# handlers/menu.py
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from .panels import _model_key_from_name, col_model_menus, _is_owner_or_admin

def register(app: Client):

    @app.on_message(filters.command("createmenu") & filters.private)
    async def create_menu(c: Client, m: Message):
        if not m.from_user:
            return

        if not _is_owner_or_admin(m.from_user.id):
            await m.reply_text("⛔ You are not allowed to create menus.")
            return

        # Check if command is in caption or text
        args = []
        if m.caption:
            args = m.caption.split(maxsplit=2)
        elif m.text:
            args = m.text.split(maxsplit=2)

        if len(args) < 2:
            await m.reply_text("Usage:\n`/createmenu <ModelName> <text>` (with or without a photo)", quote=True)
            return

        model_name = args[1]
        model_key = _model_key_from_name(model_name)
        if not model_key:
            await m.reply_text("Unknown model name. Use Roni, Ruby, Rin, or Savy.", quote=True)
            return

        text = ""
        if len(args) >= 3:
            text = args[2]

        photo_id = None
        if m.photo:
            photo_id = m.photo.file_id

        # Save into Mongo
        col_model_menus.update_one(
            {"key": model_key},
            {"$set": {"text": text, "photo_id": photo_id}},
            upsert=True,
        )

        await m.reply_text(f"✅ Saved menu for **{model_name}**.", quote=True)
