# help_menu.py
from __future__ import annotations
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, CommandHandler

BUYER_REQUIREMENTS_TEXT = (
    "🔥 *Buyer Requirements* 🔥\n\n"
    "Each month do *one*:\n"
    "• Spend $20+ total (tips, games, content)\n"
    "• OR join 4+ games ($5+ each)\n\n"
    "Please support at least *two* different models.\n\n"
    "_Struggling this month? Limited exemption available once every 6 months — ask Roni._"
)

BUYER_RULES_TEXT = (
    "📜 *Buyer Rules* 📜\n\n"
    "1) Be respectful — no harassment, guilt-tripping, or haggling.\n"
    "2) Don’t DM models unless you’re payment ready.\n"
    "3) No leaking/piracy — instant ban.\n"
    "4) Keep chat on-topic and fun; no drama.\n"
    "5) Follow Telegram ToS and our guidelines."
)

MEMBER_COMMANDS_TEXT = (
    "🛠️ *Member Commands You Can Use*\n\n"
    "/portal — quick links & contacts\n"
    "/anon — send an anonymous note to Roni\n"
    "/requirements — show buyer requirements\n"
    "/games — today’s games & how to play\n"
    "/menu — browse model menus (if enabled)\n"
    "\n(You’ll only see admin-only options if you have permission.)"
)

def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Buyer Requirements", callback_data="help:reqs")],
        [InlineKeyboardButton("Buyer Rules", callback_data="help:rules")],
        [InlineKeyboardButton("Member Commands", callback_data="help:cmds")],
        [InlineKeyboardButton("Anonymous Message", callback_data="help:anon")],
        [InlineKeyboardButton("⬅️ Back", callback_data="help:back")],
    ])

async def help_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q:
        await q.answer()
        await q.edit_message_text("❓ *Help Menu*\n\nPick a topic:", parse_mode="Markdown", reply_markup=help_keyboard())
    else:
        await update.effective_chat.send_message("❓ *Help Menu*\n\nPick a topic:", parse_mode="Markdown", reply_markup=help_keyboard())

async def help_requirements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(BUYER_REQUIREMENTS_TEXT, parse_mode="Markdown", reply_markup=help_keyboard())

async def help_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(BUYER_RULES_TEXT, parse_mode="Markdown", reply_markup=help_keyboard())

async def help_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(MEMBER_COMMANDS_TEXT, parse_mode="Markdown", reply_markup=help_keyboard())

async def help_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # “Back” returns to the root Help text + menu
    await help_open(update, context)

def register_help_menu(app: Application) -> None:
    # Optional: /helpbtn for testing from chat
    app.add_handler(CommandHandler("helpbtn", help_open))
    app.add_handler(CallbackQueryHandler(help_open, pattern=r"^help:open$"))
    app.add_handler(CallbackQueryHandler(help_requirements, pattern=r"^help:reqs$"))
    app.add_handler(CallbackQueryHandler(help_rules, pattern=r"^help:rules$"))
    app.add_handler(CallbackQueryHandler(help_cmds, pattern=r"^help:cmds$"))
    app.add_handler(CallbackQueryHandler(help_back, pattern=r"^help:back$"))
