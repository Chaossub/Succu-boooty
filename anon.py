# anon.py  (python-telegram-bot v20+)
from __future__ import annotations
import os, time, uuid
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, Message,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

# === CONFIG ===
OWNER_ID = 6964994611  # Roni

# States
ASK_MEMBER_MSG, OWNER_REPLY = range(2)

def _new_ticket_id() -> str:
    return uuid.uuid4().hex[:8].upper()

def _owner_reply_kb(ticket: str, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Reply to sender", callback_data=f"anon:reply:{ticket}:{user_id}")
    ]])

async def anon_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_chat.send_message(
        "🕵️ *Anonymous Message*\n\n"
        "Send me the note you want delivered *anonymously* to the owner.\n"
        "You can send text, photos, videos, voice, or files.",
        parse_mode="Markdown"
    )
    return ASK_MEMBER_MSG

async def anon_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    msg: Message = update.effective_message
    ticket = _new_ticket_id()

    # Owner header
    header = (
        f"📨 *New Anonymous Message*\n"
        f"• Ticket: `{ticket}`\n"
        f"• From: anonymous member (user_id hidden)\n\n"
        f"_Tap the button below to reply. Your reply will be sent as **Roni**._"
    )

    # Deliver to owner (copy media when possible so sender isn’t revealed)
    if msg.text:
        sent = await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"{header}\n\n{msg.text}",
            parse_mode="Markdown",
            reply_markup=_owner_reply_kb(ticket, user.id),
        )
    else:
        sent = await msg.copy(
            chat_id=OWNER_ID,
            caption=header,
            parse_mode="Markdown",
            reply_markup=_owner_reply_kb(ticket, user.id),
        )

    await update.effective_chat.send_message(
        "✅ Sent anonymously to the owner. You’ll receive a reply here (as a message from *Roni*) if they respond.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def owner_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Owner taps 'Reply to sender' -> we capture user_id and prompt for message."""
    q = update.callback_query
    await q.answer()
    if update.effective_user.id != OWNER_ID:
        await q.edit_message_reply_markup(reply_markup=None)
        return ConversationHandler.END

    try:
        _, _, ticket, user_id_str = q.data.split(":")
        user_id = int(user_id_str)
    except Exception:
        await q.edit_message_reply_markup(reply_markup=None)
        return ConversationHandler.END

    context.user_data["anon_reply_user_id"] = user_id
    context.user_data["anon_reply_ticket"] = ticket

    await q.message.reply_text(
        f"✍️ Send your reply for ticket `{ticket}`.\n"
        "You can send text or media; it will be delivered as *Roni*.",
        parse_mode="Markdown"
    )
    return OWNER_REPLY

async def owner_send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Owner sends text/media to forward to the original member (revealing Roni)."""
    if update.effective_user.id != OWNER_ID:
        return ConversationHandler.END

    user_id = context.user_data.get("anon_reply_user_id")
    ticket = context.user_data.get("anon_reply_ticket")
    if not user_id or not ticket:
        await update.effective_message.reply_text("Reply session expired. Tap the button again.")
        return ConversationHandler.END

    msg = update.effective_message

    # If text only
    if msg.text and not any([msg.photo, msg.document, msg.video, msg.voice, msg.audio, msg.sticker]):
        header = f"📬 *Message from Roni* — (Reply to ticket `{ticket}`)"
        await context.bot.send_message(user_id, f"{header}\n\n{msg.text}", parse_mode="Markdown")
    else:
        # Copy media with caption that identifies the sender (Roni)
        caption = f"📬 Message from Roni — (Reply to ticket `{ticket}`)"
        await msg.copy(chat_id=user_id, caption=caption, parse_mode="Markdown")

    await msg.reply_text("✅ Sent to the member.")
    # Clear session keys
    context.user_data.pop("anon_reply_user_id", None)
    context.user_data.pop("anon_reply_ticket", None)
    return ConversationHandler.END

def register_anon_handlers(app: Application) -> None:
    app.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler("anon", anon_start),
            CallbackQueryHandler(anon_start, pattern="^help:anon$")
        ],
        states={
            ASK_MEMBER_MSG: [MessageHandler(filters.ALL & ~filters.COMMAND, anon_receive)],
            OWNER_REPLY: [MessageHandler(filters.ALL & ~filters.COMMAND, owner_send_reply)],
        },
        fallbacks=[],
        name="anon_handler",
        persistent=False,
    ))
    app.add_handler(CallbackQueryHandler(owner_reply_button, pattern=r"^anon:reply:"))
