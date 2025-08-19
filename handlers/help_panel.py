# handlers/help_panel.py
# Help submenu for the DM portal:
# - "dmf_help"        → opens help submenu
# - "dmf_help_cmds"   → member commands (no self-serve add)
# - "dmf_help_buyer"  → buyer requirements + rules (from env)
# - "dmf_help_games"  → game rules (from env)
# - "dmf_home"        → back to portal (also provided in other files)

import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ------------ Content (env overrides supported) -----------------

# Member commands (no /reqadd or /reqgame)
DEFAULT_MEMBER_COMMANDS = (
    "🧭 <b>Member Commands</b>\n"
    "These work for regular members:\n\n"
    "🛠 <b>General</b>\n"
    "• /start — open the DM portal (Menu / Contact / Links / Help)\n"
    "• /help  — (in DM) opens this Help\n"
    "• /ping  — quick health check\n\n"
    "😈 <b>Fun</b>\n"
    "• /bite @user • /spank @user • /tease @user — playful commands\n\n"
    "📈 <b>XP</b>\n"
    "• /naughtystats — your XP\n"
    "• /leaderboard — server leaderboard\n\n"
    "📋 <b>Requirements</b>\n"
    "• /reqstatus — show your recorded purchases/games and compliance\n"
)

# Buyer requirements & rules (env-driven)
DEFAULT_BUYER_REQ = os.getenv("BUYER_REQUIREMENTS_TEXT", "").strip()
if not DEFAULT_BUYER_REQ:
    DEFAULT_BUYER_REQ = (
        "✨ <b>Buyer Requirements</b>\n\n"
        "To stay in the group, complete <b>one</b> each month:\n"
        "• Spend <b>$20+</b> (tips, games, content, etc.)\n"
        "• <i>or</i> join <b>4+ games</b>\n\n"
        "Miss it → removal at month’s end; re-entry fee <b>$20</b> later."
    )

DEFAULT_RULES = os.getenv("SANCTUARY_RULES_TEXT", "").strip()
if not DEFAULT_RULES:
    DEFAULT_RULES = (
        "‼️ <b>Succubus Sanctuary Rules</b>\n\n"
        "1) Respect models; no haggling/harassment/unsolicited DMs\n"
        "2) Keep it classy; no spam or explicit public posts\n"
        "3) No content theft; screenshots/forwarding = ban\n"
        "4) No begging/scamming; fake payments/chargebacks = ban\n"
        "5) Mods rule; staff actions at their discretion"
    )

# Game rules (env-driven)
DEFAULT_GAME_RULES = os.getenv("GAME_RULES_TEXT", "").strip()
if not DEFAULT_GAME_RULES:
    DEFAULT_GAME_RULES = (
        "🎲 <b>Sanctuary Game Rules</b>\n\n"
        "🕯️ <b>Candle Temptation</b>\n"
        "• Tip $5 to light a random candle\n"
        "• 3 candles for a model = spicy surprise\n"
        "• All 12 lit = group reward\n\n"
        "🍑 <b>Pick a Peach</b>\n"
        "• Tip $5, pick 1–12; each hides a model reward (no repeats)\n\n"
        "💃 <b>Flash Frenzy</b>\n"
        "• Tip $5 to trigger flashes; tips stack for back-to-back\n\n"
        "🎰 <b>Dirty Wheel Spins</b>\n"
        "• Tip $10 per spin; random naughty prize; jackpots possible\n\n"
        "🎲 <b>Dice Roll</b>\n"
        "• Tip $5 to roll; prize by number (doubles = bonus)\n\n"
        "🔥 <b>Forbidden Folder Friday</b>\n"
        "• $80 premium mixed folder drop (pay Ruby; Roni delivers link)"
    )

# ------------ Keyboards -------------------------

def _help_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Member Commands", callback_data="dmf_help_cmds")],
        [InlineKeyboardButton("✨ Buyer Requirements + ‼️ Rules", callback_data="dmf_help_buyer")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="dmf_help_games")],
        [InlineKeyboardButton("◀️ Back to Portal", callback_data="dmf_home")],
    ])

def _back_to_help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="dmf_help")]])

def _portal_kb() -> InlineKeyboardMarkup:
    # Keep aligned with your portal callbacks
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("💌 Contact", callback_data="dmf_contact")],
        [InlineKeyboardButton("🔗 Find our models elsewhere", callback_data="dmf_links")],
        [InlineKeyboardButton("❔ Help", callback_data="dmf_help")],
    ])

# ------------ Utilities -------------------------

async def _edit_or_reply(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        await cq.message.reply_text(text, reply_markup=kb, disable_web_page_preview=True)

# ------------ Handlers --------------------------

def register(app: Client):

    # Open Help submenu
    @app.on_callback_query(filters.regex(r"^dmf_help$"))
    async def on_help_root(client: Client, cq: CallbackQuery):
        await _edit_or_reply(
            cq,
            "❔ <b>Help Center</b>\nChoose a topic:",
            _help_menu_kb()
        )
        await cq.answer()

    # Member commands
    @app.on_callback_query(filters.regex(r"^dmf_help_cmds$"))
    async def on_help_cmds(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, DEFAULT_MEMBER_COMMANDS, _back_to_help_kb())
        await cq.answer()

    # Buyer req + rules
    @app.on_callback_query(filters.regex(r"^dmf_help_buyer$"))
    async def on_help_buyer(client: Client, cq: CallbackQuery):
        text = DEFAULT_BUYER_REQ + "\n\n" + DEFAULT_RULES
        await _edit_or_reply(cq, text, _back_to_help_kb())
        await cq.answer()

    # Game rules
    @app.on_callback_query(filters.regex(r"^dmf_help_games$"))
    async def on_help_games(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, DEFAULT_GAME_RULES, _back_to_help_kb())
        await cq.answer()

    # Back to portal
    @app.on_callback_query(filters.regex(r"^dmf_home$"))
    async def on_home(client: Client, cq: CallbackQuery):
        await _edit_or_reply(
            cq,
            "Welcome to the Sanctuary portal 💋 Choose an option:",
            _portal_kb()
        )
        await cq.answer()
