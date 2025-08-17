# main.py
import asyncio
import importlib
import logging
import os
import pkgutil
import sys
from typing import Final, List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------------- Logging ----------------
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("SuccuBot")

# ---------------- Env ----------------
BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN environment variable")

HANDLERS_PACKAGE: Final[str] = os.getenv("HANDLERS_PACKAGE", "handlers").strip()

# =========================================================
# ===============  LEGACY START UI (kept)  ================
# This preserves your existing /start buttons & callbacks.
# You can tweak the texts/labels, but the callback IDs
# match what you had: help, help_reqs, help_rules, help_games,
# menu, menu_tabs, menu_open:<model>, contact_admins, anon,
# suggest, find_models, back_home
# =========================================================

INTRO = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
    "Use the <b>Help</b> button to see how I can help you. Menus, contact, anon messages, and games are one tap away. 😈"
)

HELP_HOME = (
    "<b>Help Center</b>\n"
    "Pick a topic below. You can always go back."
)
HELP_REQS = (
    "<b>Buyer Requirements</b>\n"
    "Each month do ONE:\n"
    "• Spend $20+ (tips, games, content) — or —\n"
    "• Join 4+ games (start at $5)\n"
    "Support at least two active models. If you can’t tip right now, engage in chat — but still meet the requirement by month-end."
)
HELP_RULES = (
    "<b>Buyer Rules</b>\n"
    "• Don’t DM models unless payment-ready\n"
    "• No haggling, guilt-trips, or harassment\n"
    "• Keep chat respectful & on-topic\n"
    "• Follow game instructions; prizes are as stated\n"
    "• Violations can lead to mutes/kicks/bans"
)
HELP_GAMES = (
    "<b>Games</b>\n"
    "We rotate Candle Temptation, Pick a Peach, Dirty Dice, Flash Frenzy, and others. Ask here for today’s lineup and how to enter."
)

MENUS_TEXT = (
    "<b>Model Menus</b>\n"
    "Pick a model to view her current menu. If a menu is missing, the model can post a photo and use "
    "<code>/addmenu &lt;name&gt; &lt;caption&gt;</code> to register it."
)

CONTACT_TEXT = (
    "<b>Contact</b>\n"
    "Use the buttons to DM a model or contact admins. Prefer privacy? Use Anon Message."
)

ANON_TEXT = (
    "<b>Anonymous Message</b>\n"
    "Use <code>/anon &lt;your message&gt;</code> to privately reach the admin team."
)

SUGGEST_TEXT = (
    "<b>Suggestions</b>\n"
    "Have an idea for games, menus, or features? Send <code>/suggest &lt;text&gt;</code> to drop it with the admins."
)

FIND_MODELS_TEXT = (
    "<b>Find Models</b>\n"
    "Browse active models and jump to their menus or DMs."
)

def kb_home() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("Help", callback_data="help"),
         InlineKeyboardButton("Menus", callback_data="menu")],
        [InlineKeyboardButton("Contact", callback_data="contact_admins"),
         InlineKeyboardButton("Anon Msg", callback_data="anon")],
        [InlineKeyboardButton("Games", callback_data="help_games"),
         InlineKeyboardButton("Find Models", callback_data="find_models")],
    ]
    return InlineKeyboardMarkup(rows)

def kb_help() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Buyer Requirements", callback_data="help_reqs")],
        [InlineKeyboardButton("Buyer Rules", callback_data="help_rules")],
        [InlineKeyboardButton("Games — How to Play", callback_data="help_games")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_home")],
    ]
    return InlineKeyboardMarkup(rows)

def kb_back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="help")],
        [InlineKeyboardButton("🏠 Home", callback_data="back_home")],
    ])

def kb_menus() -> InlineKeyboardMarkup:
    models = ["Roni", "Ruby", "Savage Savy", "Peachy Rin"]
    rows = [[InlineKeyboardButton(m, callback_data=f"menu_open:{m.lower().replace(' ', '')}")] for m in models]
    rows.append([InlineKeyboardButton("Tabs View", callback_data="menu_tabs")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="back_home")])
    return InlineKeyboardMarkup(rows)

def kb_contact() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("DM Roni", url="https://t.me/")],
        [InlineKeyboardButton("DM Ruby", url="https://t.me/")],
        [InlineKeyboardButton("DM Admin", url="https://t.me/")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_home")],
    ]
    return InlineKeyboardMarkup(rows)

async def _reply_or_edit(update: Update, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, reply_markup=kb, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
    else:
        await update.effective_message.reply_html(text, reply_markup=kb, disable_web_page_preview=True)

# ---- /start command (kept) ----
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_or_edit(update, INTRO, kb_home())

# ---- Button router (kept) ----
async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = update.callback_query.data if update.callback_query else ""

    if data == "back_home":
        return await _reply_or_edit(update, INTRO, kb_home())

    if data == "help":
        return await _reply_or_edit(update, HELP_HOME, kb_help())
    if data == "help_reqs":
        return await _reply_or_edit(update, HELP_REQS, kb_back_home())
    if data == "help_rules":
        return await _reply_or_edit(update, HELP_RULES, kb_back_home())
    if data == "help_games":
        return await _reply_or_edit(update, HELP_GAMES, kb_back_home())

    if data == "menu":
        return await _reply_or_edit(update, MENUS_TEXT, kb_menus())
    if data == "menu_tabs":
        # Placeholder; wire your real tabbed view here if you had one.
        txt = "<b>Menus — Tabs View</b>\nSwitch between models easily. (Coming from your previous setup.)"
        return await _reply_or_edit(update, txt, kb_back_home())

    if data.startswith("menu_open:"):
        model_key = data.split(":", 1)[1]
        model_name = {
            "roni": "Roni",
            "ruby": "Ruby",
            "rin": "Peachy Rin",
            "savagesavy": "Savage Savy",
            "savysavage": "Savage Savy",
            "savysavy": "Savage Savy",
        }.get(model_key, model_key.title())
        txt = (
            f"<b>{model_name} — Menu</b>\n"
            "This model’s menu will appear here. Models can update via "
            "<code>/addmenu &lt;name&gt; &lt;caption&gt;</code> while posting a photo."
        )
        return await _reply_or_edit(update, txt, kb_back_home())

    if data == "contact_admins":
        return await _reply_or_edit(update, CONTACT_TEXT, kb_contact())
    if data == "anon":
        return await _reply_or_edit(update, ANON_TEXT, kb_back_home())
    if data == "suggest":
        return await _reply_or_edit(update, SUGGEST_TEXT, kb_back_home())
    if data == "find_models":
        return await _reply_or_edit(update, FIND_MODELS_TEXT, kb_back_home())

    # Fallback → home
    return await _reply_or_edit(update, INTRO, kb_home())

# ---- minimal diagnostics (optional) ----
async def health_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("ok")

async def id_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    c = update.effective_chat
    await update.effective_message.reply_text(
        f"user_id: {getattr(u, 'id', 'unknown')}\nchat_id: {getattr(c, 'id', 'unknown')}"
    )

async def set_base_commands(app: Application) -> None:
    cmds = [
        BotCommand("start", "Start / open the menu"),
        BotCommand("health", "Bot health check"),
        BotCommand("id", "Show your IDs"),
    ]
    try:
        await app.bot.set_my_commands(cmds)
    except Exception:
        log.warning("Could not set commands (non-fatal)", exc_info=True)

# =========================================================
# ===========  Auto-discover PTB handlers  ================
# Looks for a package named 'handlers' (configurable via
# HANDLERS_PACKAGE). Each module may expose either:
#   - register(app: Application)
#   - HANDLERS = [BaseHandler, ...]
# =========================================================

def _ensure_pkg_on_path(package_name: str) -> None:
    try:
        pkg = importlib.import_module(package_name)
        pkg_path = os.path.dirname(pkg.__file__)
        parent = os.path.dirname(pkg_path)
        if parent not in sys.path:
            sys.path.append(parent)
    except Exception:
        pass

def load_and_register_handlers(app: Application, package_name: str = HANDLERS_PACKAGE) -> int:
    loaded = 0
    _ensure_pkg_on_path(package_name)
    try:
        pkg = importlib.import_module(package_name)
    except ModuleNotFoundError as e:
        log.warning("Handlers package '%s' not found; skipping auto-load.", package_name)
        return 0

    if not hasattr(pkg, "__path__"):
        log.warning("'%s' is not a package; skipping auto-load.", package_name)
        return 0

    for modinfo in pkgutil.iter_modules(pkg.__path__):
        mod_name = f"{package_name}.{modinfo.name}"
        try:
            module = importlib.import_module(mod_name)

            if hasattr(module, "register") and callable(getattr(module, "register")):
                module.register(app)
                log.info("Registered handlers via %s.register()", mod_name)
                loaded += 1
                continue

            handlers = getattr(module, "HANDLERS", None)
            if handlers:
                for h in handlers:
                    app.add_handler(h)
                log.info("Registered %d handlers from %s.HANDLERS", len(handlers), mod_name)
                loaded += 1
            else:
                log.info("No register()/HANDLERS found in %s (skipped).", mod_name)
        except Exception:
            log.exception("Failed loading handlers from %s", mod_name)
    return loaded

# ---------------- App runner ----------------
async def main() -> None:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Ensure polling mode
    await app.bot.delete_webhook(drop_pending_updates=False)

    # Keep your legacy Start UI working:
    app.add_handler(CommandHandler("start", cmd_start, block=False))
    app.add_handler(CallbackQueryHandler(on_button, block=False))

    # Diagnostics
    app.add_handler(CommandHandler("health", health_cmd, block=False))
    app.add_handler(CommandHandler("id", id_cmd, block=False))

    # Auto-load additional PTB handlers from handlers/
    count = load_and_register_handlers(app, HANDLERS_PACKAGE)
    log.info("Auto-registered handler modules: %s", count)

    await set_base_commands(app)

    log.info("Starting polling…")
    await app.run_polling(
        poll_interval=2.0,
        allowed_updates=None,
        close_loop=False,
        stop_signals=None,
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutting down…")

