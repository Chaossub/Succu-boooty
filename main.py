import os
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes
)

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ENV CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

SUPER_ADMINS = list(map(int, os.getenv("SUPER_ADMINS", "8087941938,6964994611").split(",")))
MODELS = list(map(int, os.getenv("MODELS", "5650388514,6307783399").split(",")))

# --- Role helpers ---
def is_super(user_id: int) -> bool:
    return user_id in SUPER_ADMINS

def is_model(user_id: int) -> bool:
    return user_id in MODELS

# --- Menus ---
def main_menu(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("Help", callback_data="help")],
        [InlineKeyboardButton("Portal", callback_data="portal")],
        [InlineKeyboardButton("Find Models Elsewhere", callback_data="links")],
    ]
    return InlineKeyboardMarkup(buttons)

def help_menu(user_id: int) -> InlineKeyboardMarkup:
    buttons = []

    # Member commands
    buttons.append([InlineKeyboardButton("📜 Member Commands", callback_data="member_cmds")])
    # Model commands
    if is_model(user_id) or is_super(user_id):
        buttons.append([InlineKeyboardButton("💃 Model Commands", callback_data="model_cmds")])
    # Admin commands
    if is_super(user_id):
        buttons.append([InlineKeyboardButton("🛠 Admin Commands", callback_data="admin_cmds")])

    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)

def member_cmds_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("Buyer Requirements", callback_data="buyer_reqs")],
        [InlineKeyboardButton("Buyer Rules", callback_data="buyer_rules")],
        [InlineKeyboardButton("Game Rules", callback_data="game_rules")],
        [InlineKeyboardButton("Menus", callback_data="menus")],
        [InlineKeyboardButton("⬅️ Back", callback_data="help")],
    ]
    return InlineKeyboardMarkup(buttons)

def model_cmds_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("Flyers", callback_data="flyers")],
        [InlineKeyboardButton("Manage Menus", callback_data="manage_menus")],
        [InlineKeyboardButton("⬅️ Back", callback_data="help")],
    ]
    return InlineKeyboardMarkup(buttons)

def admin_cmds_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("Exemption List", callback_data="exemptions")],
        [InlineKeyboardButton("⬅️ Back", callback_data="help")],
    ]
    return InlineKeyboardMarkup(buttons)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        "🔥 Welcome to SuccuBot 🔥\n"
        "I’m your naughty little helper inside the Sanctuary — "
        "here to keep things fun, flirty, and flowing.\n\n"
        "Use the buttons below to explore.",
        reply_markup=main_menu(user_id),
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "help":
        await query.edit_message_text(
            "ℹ️ Help Menu", reply_markup=help_menu(user_id)
        )
    elif data == "portal":
        await query.edit_message_text(
            "🚪 The portal connects you to everything inside the Sanctuary."
        )
    elif data == "links":
        await query.edit_message_text(
            "✨ Find our models elsewhere:\n"
            "• Ruby Ransoms: https://allmylinks.com/rubyransoms\n"
            "• Roni: Coming soon!"
        )
    elif data == "back_main":
        await query.edit_message_text(
            "Back to main menu:", reply_markup=main_menu(user_id)
        )
    elif data == "member_cmds":
        await query.edit_message_text(
            "📜 Member Commands", reply_markup=member_cmds_menu()
        )
    elif data == "model_cmds":
        await query.edit_message_text(
            "💃 Model Commands", reply_markup=model_cmds_menu()
        )
    elif data == "admin_cmds":
        await query.edit_message_text(
            "🛠 Admin Commands", reply_markup=admin_cmds_menu()
        )
    elif data == "buyer_reqs":
        await query.edit_message_text(
            "🔥 Buyer Requirements 🔥\n\n"
            "To stay in the group, you must:\n"
            "• Spend $20+ each month OR\n"
            "• Join 4+ games."
        )
    elif data == "buyer_rules":
        await query.edit_message_text(
            "📜 Buyer Rules 📜\n\n"
            "1. Respect the models.\n"
            "2. No freeloading — support at least two models.\n"
            "3. No harassment or guilt-tripping."
        )
    elif data == "game_rules":
        await query.edit_message_text(
            "🎮 Game Rules 🎮\n\n"
            "Each tip gets you into a game.\n"
            "Minimum tip: $5.\n"
            "Prizes include content from our models!"
        )
    elif data == "menus":
        await query.edit_message_text("🍽 Menus — choose a model’s menu from the list.")
    elif data == "flyers":
        await query.edit_message_text("📢 Flyers — manage and post flyers here.")
    elif data == "manage_menus":
        await query.edit_message_text("📋 Manage Menus — update or add your menu.")
    elif data == "exemptions":
        await query.edit_message_text("🛡 Exemption List — view who is exempt and why.")
    else:
        await query.edit_message_text("⚠️ Unknown option.")

# --- Main ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()

