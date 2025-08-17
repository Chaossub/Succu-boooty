# handlers/announce_and_dm_button.py
# python-telegram-bot v20+
from __future__ import annotations
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# 🔹 Load announcement text from environment
# If nothing is set in the environment, it shows a default warning text
MEN_ANNOUNCEMENT = os.getenv(
    "MEN_ANNOUNCEMENT",
    "⚠️ No announcement text set. Please configure MEN_ANNOUNCEMENT in your environment."
)

# ---------- Utilities ----------
def build_dm_deep_link(bot_username: str | None) -> str:
    """
    Build a Telegram deep link to open the bot in DM with a start param.
    """
    handle = bot_username or "YourBotUsername"
    return f"https://t.me/{handle}?start=dm"


def dm_button_markup(bot_username: str | None) -> InlineKeyboardMarkup:
    deep_link = build_dm_deep_link(bot_username)
    return InlineKeyboardMarkup([[InlineKeyboardButton("💌 DM Now", url=deep_link)]])


# ---------- Handlers ----------
async def announce_men(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin-run command that posts the men's announcement with a DM Now button.
    Usage: /announce_men
    """
    markup = dm_button_markup(context.bot.username)
    await update.effective_chat.send_message(
        MEN_ANNOUNCEMENT,
        reply_markup=markup,
        disable_web_page_preview=True,
    )


async def dmnow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Button-only helper. Post your own announcement text first,
    then run /dmnow to drop just the DM Now button beneath it.
    Usage: /dmnow
    """
    markup = dm_button_markup(context.bot.username)
    await update.effective_chat.send_message(
        "Click below to DM the bot:",
        reply_markup=markup,
        disable_web_page_preview=True,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Catches /start and recognizes the deep-link param (?start=dm).
    This is what makes users 'DM ready' after they click the button.
    """
    args = context.args or []
    if args and args[0].lower() == "dm":
        await update.message.reply_text(
            "💌 You’re now DM ready with SuccuBot!\n\n"
            "Use the menu to see model menus, buyer rules, game rules, "
            "or message an admin anonymously. 😈"
        )
    else:
        await update.message.reply_text(
            "🔥 Welcome to SuccuBot — your hub for menus, rules, games, and more!"
        )


# ---------- Registration Helper ----------
def register(app: Application) -> None:
    """
    Call this from your main.py after you create the Application.
    Example:
        from handlers.announce_and_dm_button import register as register_ann
        register_ann(app)
    """
    app.add_handler(CommandHandler("announce_men", announce_men))
    app.add_handler(CommandHandler("dmnow", dmnow))
    app.add_handler(CommandHandler("start", start))


# ---------- Optional: Standalone run (for quick local testing) ----------
if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Set BOT_TOKEN env var to run this module directly.")
    app = Application.builder().token(token).build()
    register(app)
    app.run_polling()
