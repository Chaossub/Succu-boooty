# handlers/menu.py
# (If you’re wiring handlers separately.) This minimal file exposes Menu tabs & per-model view.

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, CommandHandler, Application
from telegram import Update
from telegram.ext import ContextTypes

def menu_tabs_text() -> str:
    return "💕 <b>Model Menus</b>\nChoose a name:"

def menu_tabs_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Roni", callback_data="menu_open:roni"),
         InlineKeyboardButton("Ruby", callback_data="menu_open:ruby")],
        [InlineKeyboardButton("Rin",  callback_data="menu_open:rin"),
         InlineKeyboardButton("Savy", callback_data="menu_open:savy")],
        [InlineKeyboardButton("⬅️ Back to Start", callback_data="back_home")],
    ])

def model_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_tabs")],
        [InlineKeyboardButton("🏠 Start", callback_data="back_home")],
    ])

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)

async def cb_menu_tabs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)

async def cb_menu_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    model = q.data.split(":", 1)[1].strip().lower()
    title = model.capitalize()
    await q.message.edit_text(f"💖 <b>{title} Menu</b>\n(Your {title} menu content goes here)",
                              reply_markup=model_kb(), disable_web_page_preview=True)

def register(app: Application):
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(cb_menu_tabs, pattern=r"^menu_tabs$"))
    app.add_handler(CallbackQueryHandler(cb_menu_open, pattern=r"^menu_open:.+$"))
