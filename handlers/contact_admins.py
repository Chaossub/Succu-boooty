# handlers/contact_admins.py
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

RONI_ID   = int(os.getenv("RONI_ID", "0") or "0")
RUBY_ID   = int(os.getenv("RUBY_ID", "0") or "0")
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

BTN_BACK = os.getenv("BTN_BACK", "⬅️ Back to Main")

def _panel_text() -> str:
    return (
        "👑 <b>Contact Admins</b>\n\n"
        "• Tap an admin to open their profile.\n"
        "• Or send feedback or an anonymous message via the bot."
    )

def _kb() -> InlineKeyboardMarkup:
    rows = []
    if RONI_ID:
        rows.append([InlineKeyboardButton(f"💌 DM {RONI_NAME}", url=f"tg://user?id={RONI_ID}")])
    if RUBY_ID:
        rows.append([InlineKeyboardButton(f"💌 DM {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}")])
    rows.append([
        InlineKeyboardButton("💭 Suggestions / Feedback", callback_data="contact_admins_suggest"),
        InlineKeyboardButton("🕵️ Anonymous Message", callback_data="contact_admins_anon"),
    ])
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data="dmf_main")])
    return InlineKeyboardMarkup(rows)

def register(app: Client):

    # Button from main panel
    @app.on_callback_query(filters.regex("^contact_admins_open$"))
    async def open_panel(client: Client, cq: CallbackQuery):
        await cq.message.edit_text(_panel_text(), reply_markup=_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Suggestions flow
    @app.on_callback_query(filters.regex("^contact_admins_suggest$"))
    async def ask_suggest(client: Client, cq: CallbackQuery):
        await cq.answer()
        await cq.message.reply_text(
            "💭 Send me your suggestion/feedback as the next message.\n"
            "I'll forward it to the admins."
        )
        # tag user state by replying; simplest: wait for their next message and forward
        # We’ll use a quick one-shot filter: command-like keyword
        # Users will just type; we detect with reply-to
    @app.on_message(filters.private & filters.reply & ~filters.command(["start","menu","help"]))
    async def catch_reply(client: Client, m: Message):
        if m.reply_to_message and "Suggestions / Feedback" in (m.reply_to_message.text or ""):
            if OWNER_ID:
                await client.send_message(
                    OWNER_ID,
                    f"💭 <b>Suggestion</b> from <a href='tg://user?id={m.from_user.id}'>{m.from_user.first_name}</a>:\n\n{m.text}"
                )
            await m.reply_text("✅ Sent to admins. Thanks!")

    # Anonymous flow
    @app.on_callback_query(filters.regex("^contact_admins_anon$"))
    async def ask_anon(client: Client, cq: CallbackQuery):
        await cq.answer()
        await cq.message.reply_text(
            "🕵️ Send your anonymous message now. I will forward it without your name."
        )

    @app.on_message(filters.private & ~filters.command(["start","menu","help"]))
    async def catch_anon(client: Client, m: Message):
        # detect if they were prompted for anon (best-effort: look at last bot message text)
        last = m.reply_to_message
        if last and last.from_user and last.from_user.is_bot and "anonymous" in (last.text or "").lower():
            if OWNER_ID:
                await client.send_message(OWNER_ID, f"🕵️ <b>Anonymous message</b>:\n\n{m.text}")
            await m.reply_text("✅ Sent anonymously.")
