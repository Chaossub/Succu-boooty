import os
from typing import Optional
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ENV
RONI_ID  = os.getenv("RONI_ID")
RUBY_ID  = os.getenv("RUBY_ID")
RONI_NAME= os.getenv("RONI_NAME", "Roni")
RUBY_NAME= os.getenv("RUBY_NAME", "Ruby")
RONI_UN  = os.getenv("RONI_USERNAME")  # e.g. Chaossub283 (no @)
RUBY_UN  = os.getenv("RUBY_USERNAME")

# Fallbacks (so Roni never disappears)
OWNER_ID = os.getenv("OWNER_ID")
OWNER_USERNAME = os.getenv("OWNER_USERNAME")

# Links + Help: comma-separated pairs "Label|URL"
# Example: MODELS_LINKS="AllMyLinks|https://allmylinks.com/sanctuary, Fansly|https://fans.ly/..."
MODELS_LINKS = os.getenv("MODELS_LINKS", "").strip()
HELP_LINKS   = os.getenv("HELP_LINKS", "").strip()

def _btn(text, data): 
    return InlineKeyboardButton(text, callback_data=data)

def _back_main(): 
    return [[_btn("⬅️ Back to Main", "nav:main")]]

def _user_url(username: Optional[str], numeric_id: Optional[str]) -> Optional[str]:
    if username:
        return f"https://t.me/{username.lstrip('@')}"
    if numeric_id:
        return f"https://t.me/user?id={int(numeric_id)}"
    return None

def _pairs_to_buttons(csv: str):
    rows = []
    if not csv:
        return rows
    for raw in csv.split(","):
        item = raw.strip()
        if not item:
            continue
        if "|" in item:
            label, url = [p.strip() for p in item.split("|", 1)]
            if label and url:
                rows.append([InlineKeyboardButton(label, url=url)])
    return rows

async def render_main(msg: Message):
    rows = [
        [_btn("💕 Menu", "nav:menu")],
        [_btn("👑 Contact Admins", "nav:contact")],
        [_btn("🔥 Find Our Models Elsewhere", "nav:links")],
        [_btn("❓ Help", "nav:help")],
    ]
    kb = InlineKeyboardMarkup(rows)
    await msg.edit_text(
        "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
        "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
        "✨ <i>Use the menu below to navigate!</i>",
        reply_markup=kb
    )

async def render_menu(msg: Message):
    rows = [
        [_btn("💘 Roni", "menu:roni"), _btn("💘 Ruby", "menu:ruby")],
        [_btn("💘 Rin", "menu:rin"), _btn("💘 Savy", "menu:savy")],
    ] + _back_main()
    await msg.edit_text("💕 <b>Menus</b>\nPick a model whose menu is saved.", reply_markup=InlineKeyboardMarkup(rows))

async def render_contact(msg: Message):
    rows = []
    roni_url = _user_url(RONI_UN or OWNER_USERNAME, RONI_ID or OWNER_ID)
    ruby_url = _user_url(RUBY_UN, RUBY_ID)
    if roni_url:
        rows.append([InlineKeyboardButton(f"👑 Contact {RONI_NAME}", url=roni_url)])
    if ruby_url:
        rows.append([InlineKeyboardButton(f"👑 Contact {RUBY_NAME}", url=ruby_url)])
    rows.append([_btn("🕵️ Anonymous Message", "contact:anon")])
    rows += _back_main()
    await msg.edit_text(
        "👑 <b>Contact Admins</b>\n\n• Tag an admin in chat\n• Or send an anonymous message via the bot.",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def render_help(msg: Message):
    rows = _pairs_to_buttons(HELP_LINKS) + _back_main()
    await msg.edit_text("❓ <b>Help</b>\nTap a button below, or ping an admin if you’re stuck.", reply_markup=InlineKeyboardMarkup(rows))

async def render_links(msg: Message):
    rows = _pairs_to_buttons(MODELS_LINKS) + _back_main()
    await msg.edit_text("🔥 <b>Find Our Models Elsewhere</b>", reply_markup=InlineKeyboardMarkup(rows))

def register(app: Client):
    @app.on_callback_query(filters.regex("^nav:main$"))
    async def _go_main(c, cq): await render_main(cq.message)

    @app.on_callback_query(filters.regex("^nav:menu$"))
    async def _go_menu(c, cq): await render_menu(cq.message)

    @app.on_callback_query(filters.regex("^nav:contact$"))
    async def _go_contact(c, cq): await render_contact(cq.message)

    @app.on_callback_query(filters.regex("^nav:help$"))
    async def _go_help(c, cq): await render_help(cq.message)

    @app.on_callback_query(filters.regex("^nav:links$"))
    async def _go_links(c, cq): await render_links(cq.message)

    # Optional: expose commands that open the same panels
    @app.on_message(filters.private & filters.command("menu"))
    async def _cmd_menu(c, m):
        ph = await m.reply_text("…"); await render_menu(ph)

    @app.on_message(filters.private & filters.command("contact"))
    async def _cmd_contact(c, m):
        ph = await m.reply_text("…"); await render_contact(ph)

    @app.on_message(filters.private & filters.command("help"))
    async def _cmd_help(c, m):
        ph = await m.reply_text("…"); await render_help(ph)
