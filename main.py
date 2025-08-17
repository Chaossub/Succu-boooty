import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import telegram  # to log version at boot

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Optional IDs for DM buttons (contact admins)
OWNER_ID = os.getenv("OWNER_ID", "").strip()
RUBY_ID  = os.getenv("RUBY_ID",  "").strip()

# Links used in “Find Our Models Elsewhere”
RONI_LINK = os.getenv("RONI_LINK", "https://allmylinks.com/chaossub283")
RUBY_LINK = os.getenv("RUBY_LINK", "https://allmylinks.com/rubyransoms")
RIN_LINK  = os.getenv("RIN_LINK",  "https://allmylinks.com/peachybunsrin")
SAVY_LINK = os.getenv("SAVY_LINK", "https://allmylinks.com/savannahxsavage")

# ---- Logging ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")

# ---- Text blocks ----
WELCOME_TEXT = (
    "🔥 Welcome to SuccuBot 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
    "Use the buttons below to explore what I can do for you 😏"
)

FIND_MODELS_TEXT = (
    "🔥 Find Our Models Elsewhere 🔥\n\n"
    "👑 Roni Jane (Owner)\n"
    f"{RONI_LINK}\n\n"
    "💎 Ruby Ransom (Co-Owner)\n"
    f"{RUBY_LINK}\n\n"
    "🍑 Peachy Rin\n"
    f"{RIN_LINK}\n\n"
    "⚡ Savage Savy\n"
    f"{SAVY_LINK}"
)

BUYER_RULES_TEXT = (
    "📜 <b>Buyer Rules</b>\n\n"
    "1) Respect the models — no harassment or guilt-tripping.\n"
    "2) No freeloading / begging for free content.\n"
    "3) Follow payment & delivery instructions posted by the team.\n"
)

BUYER_REQUIREMENTS_TEXT = (
    "💸 <b>Buyer Requirements</b>\n\n"
    "To stay in the group each month, complete at least ONE:\n"
    "• Spend $20+ (tips/games/content), or\n"
    "• Join 4+ games.\n"
)

GAME_RULES_TEXT = """🎲 <b>Succubus Sanctuary Game Rules</b>

⸻

🕯️ <b>Candle Temptation Game</b>
• $5 lights a random candle. 3 candles for a model = her spicy surprise.
• All 12 candles by end = special group reward.

⸻

🍑 <b>Pick a Peach</b>
• Pick 1–12 and tip $5. Each number hides a model’s surprise.
• No repeats per model; spread the love.

⸻

💃 <b>Flash Frenzy</b>
• $5 triggers a flash by the chosen girl. Stacks for back-to-back flashes.

⸻

🎰 <b>Dirty Wheel Spins</b>
• $10 per spin. Whatever it lands on is the prize. Add jackpots like “double prize”.

⸻

🎲 <b>Dice Roll Game</b>
• $5 per roll (1–6). Number = prize. Two dice variant for bigger pools.

⸻

🔥 <b>Forbidden Folder Friday</b>
• $80 premium folder (photos + clips), limited-time each Friday.
• Pay Ruby; Roni delivers the Dropbox link. Closes at midnight.
"""

# ---- Keyboards ----
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="contact_admins")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="find_models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

def kb_help_root() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 Buyer Requirements", callback_data="help_reqs")],
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="help_rules")],
        [InlineKeyboardButton("🎮 Game Rules", callback_data="help_games")],
        [InlineKeyboardButton("⬅️ Back to Start", callback_data="back_home")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu")],
    ])

def kb_back_to_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Help", callback_data="help")],
        [InlineKeyboardButton("⬅️ Back to Start", callback_data="back_home")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu")],
    ])

def kb_menu_tabs() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Roni", callback_data="menu_open:roni"),
         InlineKeyboardButton("Ruby", callback_data="menu_open:ruby")],
        [InlineKeyboardButton("Rin", callback_data="menu_open:rin"),
         InlineKeyboardButton("Savy", callback_data="menu_open:savy")],
        [InlineKeyboardButton("⬅️ Back to Start", callback_data="back_home")],
    ])

def kb_model_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_tabs")],
        [InlineKeyboardButton("🏠 Start", callback_data="back_home")],
    ])

def kb_contact_admins() -> InlineKeyboardMarkup:
    rows = []
    row = []
    if OWNER_ID.isdigit():
        row.append(InlineKeyboardButton("💌 Message Roni", url=f"tg://user?id={OWNER_ID}"))
    if RUBY_ID.isdigit():
        row.append(InlineKeyboardButton("💌 Message Ruby", url=f"tg://user?id={RUBY_ID}"))
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🙈 Send anonymous message", callback_data="anon")])
    rows.append([InlineKeyboardButton("💡 Send a suggestion", callback_data="suggest")])
    rows.append([InlineKeyboardButton("⬅️ Back to Start", callback_data="back_home")])
    return InlineKeyboardMarkup(rows)

# ---- Handlers ----
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)
    logging.info("PTB version: %s", getattr(telegram, "__version__", "unknown"))

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "back_home":
        try:
            await q.message.edit_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)
        except Exception:
            await q.message.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    elif data == "help":
        try:
            await q.message.edit_text("❓ <b>Help</b>\nPick a topic:",
                                      reply_markup=kb_help_root(), disable_web_page_preview=True)
        except Exception:
            await q.message.reply_text("❓ <b>Help</b>\nPick a topic:",
                                       reply_markup=kb_help_root(), disable_web_page_preview=True)

    elif data == "help_reqs":
        await q.message.edit_text(BUYER_REQUIREMENTS_TEXT, reply_markup=kb_back_to_help(), disable_web_page_preview=True)

    elif data == "help_rules":
        await q.message.edit_text(BUYER_RULES_TEXT, reply_markup=kb_back_to_help(), disable_web_page_preview=True)

    elif data == "help_games":
        await q.message.edit_text(GAME_RULES_TEXT, reply_markup=kb_back_to_help(), disable_web_page_preview=True)

    elif data == "menu":
        try:
            await q.message.edit_text("💕 <b>Model Menus</b>\nChoose a name:",
                                      reply_markup=kb_menu_tabs(), disable_web_page_preview=True)
        except Exception:
            await q.message.reply_text("💕 <b>Model Menus</b>\nChoose a name:",
                                       reply_markup=kb_menu_tabs(), disable_web_page_preview=True)

    elif data == "menu_tabs":
        try:
            await q.message.edit_text("💕 <b>Model Menus</b>\nChoose a name:",
                                      reply_markup=kb_menu_tabs(), disable_web_page_preview=True)
        except Exception:
            await q.message.reply_text("💕 <b>Model Menus</b>\nChoose a name:",
                                       reply_markup=kb_menu_tabs(), disable_web_page_preview=True)

    elif data.startswith("menu_open:"):
        model = data.split(":", 1)[1].strip().lower()
        title = model.capitalize()
        text = f"💖 <b>{title} Menu</b>\n(Your {title} menu content goes here)"
        try:
            await q.message.edit_text(text, reply_markup=kb_model_back(), disable_web_page_preview=True)
        except Exception:
            await q.message.reply_text(text, reply_markup=kb_model_back(), disable_web_page_preview=True)

    elif data == "contact_admins":
        try:
            await q.message.edit_text("Contact Admins 👑 — how would you like to reach us?",
                                      reply_markup=kb_contact_admins(), disable_web_page_preview=True)
        except Exception:
            await q.message.reply_text("Contact Admins 👑 — how would you like to reach us?",
                                       reply_markup=kb_contact_admins(), disable_web_page_preview=True)

    elif data == "find_models":
        try:
            await q.message.edit_text(
                FIND_MODELS_TEXT,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Back to Start", callback_data="back_home")]]
                ),
                disable_web_page_preview=False,
            )
        except Exception:
            await q.message.reply_text(
                FIND_MODELS_TEXT,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Back to Start", callback_data="back_home")]]
                ),
                disable_web_page_preview=False,
            )

    elif data == "anon":
        await q.message.edit_text(
            "You're anonymous. Type the message you want me to send to the admins.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancel", callback_data="back_home")]]),
        )
    elif data == "suggest":
        await q.message.edit_text(
            "How would you like to send your suggestion?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💡 With your @", callback_data="back_home")],
                [InlineKeyboardButton("🙈 Anonymously", callback_data="back_home")],
                [InlineKeyboardButton("✖️ Cancel", callback_data="back_home")],
            ]),
        )

# ---- Bootstrap (PTB 21) ----
def main():
    if not BOT_TOKEN:
        log.error("Missing BOT_TOKEN in environment. Set BOT_TOKEN and redeploy.")
        raise SystemExit(1)

    log.info("Starting SuccuBot… (PTB %s)", getattr(telegram, "__version__", "unknown"))
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_button))

    app.run_polling(close_loop=False, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
