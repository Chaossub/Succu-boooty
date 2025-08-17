
import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Load ENV
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# -----------------------
# MENU TEXTS
# -----------------------
WELCOME_TEXT = """🔥 Welcome to SuccuBot 🔥
I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.

Use the buttons below to explore what I can do for you 😏
"""

FIND_MODELS_TEXT = """💋 Want to find our models elsewhere?

👉 Ruby: https://allmylinks.com/rubyransoms
👉 Roni: (add link if needed)
👉 Others: (add links)

Support them directly outside the group too 💕
"""

BUYER_RULES_TEXT = """🔥 Succubus Sanctuary Buyer Rules 🔥
1. Respect the models — no guilt-tripping, no free demands.
2. Minimum: $20/month OR 4+ games.
3. Exemptions may be used once every 6 months."""

BUYER_REQUIREMENTS_TEXT = """💸 Buyer Requirements
To stay in the group, you must do at least ONE of the following each month:
- Spend $20+ (tips, games, content).
- OR join 4+ games.
"""

GAME_RULES_TEXT = """🎲 Succubus Sanctuary Game Rules

🕯️ Candle Temptation Game
 - Tip $5 to light candles. 3 candles = model reward.

🍑 Pick a Peach
 - Pick 1–12. Tip $5. Each number = surprise.

💃 Flash Frenzy
 - $5 tip = flash. Stacks for more.

🎰 Dirty Wheel Spins
 - $10 per spin. Random prize.

🎲 Dice Roll Game
 - $5 per roll. 1–6 = prize.

🔥 Forbidden Folder Friday
 - Premium folder. $80 flat. Limited-time only.
"""

# -----------------------
# KEYBOARDS
# -----------------------
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Help", callback_data="help_menu")],
        [InlineKeyboardButton("💋 Find Models", callback_data="find_models")]
    ])

def help_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="buyer_rules")],
        [InlineKeyboardButton("💸 Buyer Requirements", callback_data="buyer_requirements")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="game_rules")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ])

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="help_menu")]
    ])

def back_to_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")]
    ])

# -----------------------
# HANDLERS
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT, reply_markup=main_menu_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help_menu":
        await query.edit_message_text("📖 Help Menu", reply_markup=help_menu_keyboard())

    elif query.data == "buyer_rules":
        await query.edit_message_text(BUYER_RULES_TEXT, reply_markup=back_keyboard())

    elif query.data == "buyer_requirements":
        await query.edit_message_text(BUYER_REQUIREMENTS_TEXT, reply_markup=back_keyboard())

    elif query.data == "game_rules":
        await query.edit_message_text(GAME_RULES_TEXT, reply_markup=back_keyboard())

    elif query.data == "find_models":
        await query.edit_message_text(FIND_MODELS_TEXT, reply_markup=back_to_main_keyboard())

    elif query.data == "back_main":
        await query.edit_message_text(WELCOME_TEXT, reply_markup=main_menu_keyboard())

# -----------------------
# MAIN ENTRY
# -----------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
