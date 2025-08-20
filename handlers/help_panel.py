# handlers/help_panel.py
# Help submenu:
#  - Member Commands (trimmed: only what members can use; requirements: /reqstatus only)
#  - Buyer Requirements
#  - Buyer Rules
#  - Game Rules
#  - Back to Portal

import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ---------- Content (env overrides allowed) ----------

MEMBER_COMMANDS_TEXT = os.getenv("MEMBER_COMMANDS_TEXT", "").strip()
if not MEMBER_COMMANDS_TEXT:
    MEMBER_COMMANDS_TEXT = (
        "🧭 <b>Member Commands</b>\n\n"
        "🛠 <b>General</b>\n"
        "• /start — open the portal (Menu / Contact / Links / Help)\n"
        "• /help  — show Help\n"
        "• /ping  — quick bot check\n\n"
        "😈 <b>Fun</b>\n"
        "• /bite @user • /spank @user • /tease @user\n\n"
        "📈 <b>XP</b>\n"
        "• /naughtystats — your XP\n"
        "• /leaderboard — server leaderboard\n\n"
        "🔔 <b>Summon</b>\n"
        "• /summon @user — summon someone (where allowed)\n"
        "• /summonall — summon all (if enabled)\n\n"
        "📋 <b>Requirements</b>\n"
        "• /reqstatus — see your recorded spend/games & compliance\n"
    )

BUYER_REQUIREMENTS_TEXT = os.getenv("BUYER_REQUIREMENTS_TEXT", "").strip()
if not BUYER_REQUIREMENTS_TEXT:
    BUYER_REQUIREMENTS_TEXT = (
        "✨ <b>Buyer Requirements</b>\n\n"
        "To stay in the group each month, complete <b>at least one</b>:\n"
        "• Spend <b>$20+</b> (tips, games, content, etc.)\n"
        "• <i>or</i> play <b>4+ games</b>\n\n"
        "Support is what keeps the Sanctuary alive and spicy 💋"
    )

BUYER_RULES_TEXT = os.getenv("SANCTUARY_RULES_TEXT", "").strip()
if not BUYER_RULES_TEXT:
    BUYER_RULES_TEXT = (
        "‼️ <b>Succubus Sanctuary Rules</b>\n\n"
        "1) Respect the Models — consent & boundaries always.\n"
        "2) Keep It Classy — no unsolicited explicit spam.\n"
        "3) No Content Theft — sharing/forwarding gets you banned.\n"
        "4) Stay on Theme — keep it fun & flirty.\n"
        "5) No Begging/Scamming — no fake payments or chargebacks.\n"
        "6) Mods Rule — staff discretion applies."
    )

GAME_RULES_TEXT = os.getenv("GAME_RULES_TEXT", "").strip()
if not GAME_RULES_TEXT:
    GAME_RULES_TEXT = (
        "🎲 <b>Succubus Sanctuary Game Rules</b>\n"
        "⸻\n\n"
        "🕯️ <b>Candle Temptation Game</b>\n"
        "• $5 to light a random candle. 12 total, 3 per model.\n"
        "• When a model’s 3 candles are lit, she drops a spicy surprise.\n"
        "• If all 12 are lit: group reward unlocked.\n\n"
        "🍑 <b>Pick a Peach</b>\n"
        "• Pick 1–12 & tip $5. Each hides a model’s reward.\n"
        "• No repeats; make sure everyone gets love.\n\n"
        "💃 <b>Flash Frenzy</b>\n"
        "• $5 triggers a timed flash from a chosen model.\n"
        "• Tips can stack for back-to-back flashes.\n\n"
        "🎰 <b>Dirty Wheel Spins</b>\n"
        "• $10 to spin. Prize is final — no do-overs.\n"
        "• Add jackpot slots like double prize or custom mini-video.\n\n"
        "🎲 <b>Dice Roll Game</b>\n"
        "• $5 to roll (1–6). Number rolled = prize.\n"
        "• Optional: 2 dice (doubles = bonus).\n\n"
        "🔥 <b>Forbidden Folder Friday</b>\n"
        "• $80 unlocks a premium mixed-content folder, Fridays only.\n"
        "• Pay Ruby; Roni delivers the Dropbox link. Limited-time."
    )

def _help_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Member Commands", callback_data="dmf_help_cmds")],
        [InlineKeyboardButton("✨ Buyer Requirements", callback_data="dmf_help_buyer")],
        [InlineKeyboardButton("‼️ Buyer Rules", callback_data="dmf_help_rules")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="dmf_help_games")],
        [InlineKeyboardButton("◀️ Back to Start", callback_data="dmf_home")],
    ])

def _back_to_help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="dmf_help")]])

async def _edit_or_reply(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        await cq.message.reply_text(text, reply_markup=kb, disable_web_page_preview=True)

def register(app: Client):

    @app.on_callback_query(filters.regex(r"^dmf_help$"))
    async def on_help_root(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, "❔ <b>Help Center</b>\nChoose a topic:", _help_menu_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_help_cmds$"))
    async def on_help_cmds(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, MEMBER_COMMANDS_TEXT, _back_to_help_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_help_buyer$"))
    async def on_help_buyer(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, BUYER_REQUIREMENTS_TEXT, _back_to_help_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_help_rules$"))
    async def on_help_rules(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, BUYER_RULES_TEXT, _back_to_help_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_help_games$"))
    async def on_help_games(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, GAME_RULES_TEXT, _back_to_help_kb())
        await cq.answer()
