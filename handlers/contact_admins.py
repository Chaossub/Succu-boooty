# handlers/contact_admins.py
# Contact Admins panel:
#  - Buttons to DM Roni / Ruby directly
#  - Anonymous message to admins (owner can reply anonymously)
#  - Suggestions (identified or anonymous)
# All with back buttons to portal.

import os, secrets
from typing import Dict, Optional, List

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import RPCError, FloodWait

OWNER_ID       = int(os.getenv("OWNER_ID", "0"))
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0"))
RUBY_ID        = int(os.getenv("RUBY_ID", "0"))

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

CONTACT_TEXT = "How would you like to reach us?"

# Simple state for anon threads: token ↔ user_id; admin_id ↔ pending token
_anon_threads: Dict[str, int] = {}
_admin_pending_reply: Dict[int, str] = {}

def build_admins_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    row1 = []
    if OWNER_ID:
        row1.append(InlineKeyboardButton(f"💌 Message {RONI_NAME}", url=f"tg://user?id={OWNER_ID}"))
    if RUBY_ID:
        row1.append(InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
    if row1: rows.append(row1)
    rows.append([InlineKeyboardButton("🙈 Send anonymous message to admins", callback_data="adm_anon")])
    rows.append([InlineKeyboardButton("💡 Send a suggestion", callback_data="adm_suggest")])
    rows.append([InlineKeyboardButton("◀️ Back to Start", callback_data="dmf_home")])
    return InlineKeyboardMarkup(rows)

def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancel", callback_data="adm_cancel")]])

def _suggest_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Suggest (with your @)", callback_data="adm_suggest_ident")],
        [InlineKeyboardButton("🙈 Suggest anonymously", callback_data="adm_suggest_anon")],
        [InlineKeyboardButton("◀️ Back", callback_data="dmf_open_admins")],
    ])

def register(app: Client):

    # Owner reply mode (anonymous back to sender)
    @app.on_callback_query(filters.regex(r"^adm_anon_reply:"))
    async def on_anon_reply(client: Client, cq: CallbackQuery):
        token = cq.data.split(":", 1)[1]
        if cq.from_user.id != OWNER_ID:
            return await cq.answer("Only the owner can reply anonymously.", show_alert=True)
        if token not in _anon_threads:
            return await cq.answer("That anonymous thread has expired.", show_alert=True)
        _admin_pending_reply[cq.from_user.id] = token
        await cq.message.reply_text("Reply mode enabled. Type your reply now — it will be sent anonymously. Use /cancel to exit.")
        await cq.answer("Reply with your message to send anonymously.")

    # Handle owner DM message while in reply mode
    @app.on_message(filters.private & ~filters.command(["start", "menu", "help"]))
    async def on_owner_reply(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if uid != OWNER_ID:
            return
        token = _admin_pending_reply.pop(uid, None)
        if not token:
            return
        target_uid = _anon_threads.get(token)
        if not target_uid:
            return await m.reply_text("This anonymous thread has expired.")
        try:
            await client.send_message(target_uid, f"📮 Message from {RONI_NAME}:")
            await client.copy_message(chat_id=target_uid, from_chat_id=m.chat.id, message_id=m.id)
            await m.reply_text("Sent anonymously ✅")
        except RPCError:
            await m.reply_text("Could not deliver message.")

    # Open panel (wired from dm_portal)
    @app.on_callback_query(filters.regex(r"^dmf_open_admins$"))
    async def on_admins_root(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(CONTACT_TEXT, reply_markup=build_admins_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(CONTACT_TEXT, reply_markup=build_admins_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Anonymous message flow
    _pending_kind: Dict[int, str] = {}  # user_id -> "anon"|"sug_ident"|"sug_anon"

    @app.on_callback_query(filters.regex(r"^adm_anon$"))
    async def on_anon_begin(client: Client, cq: CallbackQuery):
        _pending_kind[cq.from_user.id] = "anon"
        await cq.message.reply_text("You're anonymous. Type the message you want me to send to the admins.", reply_markup=_cancel_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^adm_suggest$"))
    async def on_suggest_panel(client: Client, cq: CallbackQuery):
        await cq.message.reply_text("How would you like to send your suggestion?", reply_markup=_suggest_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^adm_suggest_ident$"))
    async def on_suggest_ident(client: Client, cq: CallbackQuery):
        _pending_kind[cq.from_user.id] = "sug_ident"
        await cq.message.reply_text("Great! Type your suggestion and I’ll send it to the admins.", reply_markup=_cancel_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^adm_suggest_anon$"))
    async def on_suggest_anon(client: Client, cq: CallbackQuery):
        _pending_kind[cq.from_user.id] = "sug_anon"
        await cq.message.reply_text("You're anonymous. Type your suggestion for the admins.", reply_markup=_cancel_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^adm_cancel$"))
    async def on_cancel(client: Client, cq: CallbackQuery):
        _pending_kind.pop(cq.from_user.id, None)
        await cq.answer("Canceled.")
        try:
            await cq.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    # Message capture for anon/suggestions
    @app.on_message(filters.private & ~filters.command(["start", "menu", "help"]))
    async def on_private_msg(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        kind = _pending_kind.pop(uid, None)
        if not kind:
            return

        targets = [x for x in (OWNER_ID, SUPER_ADMIN_ID) if x]
        if not targets:
            return await m.reply_text("No admins configured.")

        if kind == "anon":
            token = secrets.token_urlsafe(8)
            _anon_threads[token] = uid
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Reply anonymously", callback_data=f"adm_anon_reply:{token}")]])
            for admin in targets:
                try:
                    await client.send_message(admin, "📨 Anonymous message")
                    await client.copy_message(admin, m.chat.id, m.id, reply_markup=kb)
                except FloodWait as e:
                    await asyncio.sleep(int(getattr(e, "value", 1)) or 1)
                except RPCError:
                    continue
            return await m.reply_text("Sent anonymously ✅")

        if kind == "sug_ident":
            header = f"💡 Suggestion from {m.from_user.mention} (<code>{uid}</code>)"
            for admin in targets:
                try:
                    await client.send_message(admin, header)
                    await client.copy_message(admin, m.chat.id, m.id)
                except RPCError:
                    continue
            return await m.reply_text("Thanks! Your suggestion was sent ✅")

        if kind == "sug_anon":
            token = secrets.token_urlsafe(8)
            _anon_threads[token] = uid
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Reply anonymously", callback_data=f"adm_anon_reply:{token}")]])
            for admin in targets:
                try:
                    await client.send_message(admin, "💡 Anonymous suggestion")
                    await client.copy_message(admin, m.chat.id, m.id, reply_markup=kb)
                except RPCError:
                    continue
            return await m.reply_text("Suggestion sent anonymously ✅")
