# handlers/help_panel.py
# Help submenu for the DM portal:
# - "dmf_help"            → opens help submenu
# - "dmf_help_cmds"       → member commands
# - "dmf_help_buyer"      → buyer requirements + rules
# - "dmf_help_exemptions" → exemptions policy (redeem every 6 months)
# - "dmf_home"            → back to portal (also provided in other files)

import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ------------ Content (env overrides supported) -----------------

DEFAULT_MEMBER_COMMANDS = (
    "🧭 <b>Member Commands</b>\n"
    "These work for regular members:\n\n"
    "🛠 <b>General</b>\n"
    "• /start — open the DM portal (Menu / Contact / Links / Help)\n"
    "• /help  — (in DM) opens this Help\n"
    "• /ping  — quick health check\n\n"
    "💌 <b>DM / Portal</b>\n"
    "• Tap the portal buttons to view model menus, buyer info, rules, links\n\n"
    "😈 <b>Fun</b>\n"
    "• /bite @user • /spank @user • /tease @user — playful commands\n\n"
    "📈 <b>XP</b>\n"
    "• /naughtystats — your XP\n"
    "• /leaderboard — server leaderboard\n\n"
    "🔔 <b>Summon</b>\n"
    "• /summon @user — summon someone (allowed in casual channels)\n"
    "• /summonall — summon all <i>tracked</i> users (if enabled)\n\n"
    "📋 <b>Requirements (self-service)</b>\n"
    "• /reqstatus — show your recorded purchases/games and compliance\n"
    "• /reqgame  — add one game (reply or self)\n"
    "• /reqadd   — add a purchase (reply or self)\n"
)

DEFAULT_BUYER_REQ = os.getenv("BUYER_REQUIREMENTS_TEXT", "").strip()
if not DEFAULT_BUYER_REQ:
    DEFAULT_BUYER_REQ = (
        "✨ <b>Buyer Requirements</b>\n\n"
        "To stay in the group, complete <b>at least one</b> each month:\n"
        "• Spend <b>$20+</b> (tips, games, content, etc.)\n"
        "• <i>or</i> join <b>4+ games</b> (most start at $5)\n\n"
        "Show love: tipping keeps the Sanctuary alive and supports the models 💋\n\n"
        "Fairness:\n"
        "• Support <b>two different models</b> (not just one)\n"
        "• If your inviter left, choose any two models to support\n\n"
        "You still need to meet the monthly requirement to remain in the group.\n"
        "Miss it → removal at month’s end; re-entry fee <b>$20</b> later."
    )

DEFAULT_RULES = os.getenv("SANCTUARY_RULES_TEXT", "").strip()
if not DEFAULT_RULES:
    DEFAULT_RULES = (
        "‼️ <b>Succubus Sanctuary Rules</b>\n\n"
        "1) <b>Respect the Models</b>\n"
        "   • Don’t DM models unless you’re payment-ready\n"
        "   • No haggling or harassment — rates/boundaries stand\n"
        "   • Consent is king; a ‘no’ or silence means stop\n\n"
        "2) <b>Keep It Classy</b>\n"
        "   • No unsolicited explicit spam in public chat\n"
        "   • Roleplay is welcome within consent & respect\n\n"
        "3) <b>No Content Theft</b> — screenshots/forwarding = ban\n\n"
        "4) <b>Stay on Theme</b> — fun & flirt; avoid heavy off-topic\n\n"
        "5) <b>No Begging/Scamming</b> — no fake payments/chargebacks\n\n"
        "6) <b>Mods Rule</b> — warnings/mutes/bans at staff discretion\n\n"
        "By staying you agree to follow these rules. Violations may lead to removal or ban."
    )

DEFAULT_EXEMPTIONS = (
    "🛡 <b>Exemptions & Cool-Offs</b>\n\n"
    "Need a little grace period? You can request a one-time exemption to pause requirement enforcement.\n\n"
    "<b>How it works</b>\n"
    "• An admin can grant an exemption for a short duration (e.g., 72h or 7d)\n"
    "• During that window, you won’t be warned/kicked for requirements\n"
    "• <b>Limit:</b> one exemption <b>every 6 months</b> per member\n"
    "• Exemptions don’t stack; a new one replaces the old if approved\n\n"
    "<b>How to request</b>\n"
    "• DM an admin via the portal’s <b>Contact</b> button and briefly explain your situation\n"
    "• Admins use: <code>/reqexempt add &lt;duration&gt; [; optional note]</code>\n"
    "  Examples: <code>/reqexempt add 72h ; travel</code> or <code>/reqexempt add 7d ; payroll delay</code>\n\n"
    "<b>Notes</b>\n"
    "• Abuse = denial; repeated requests before 6 months may be refused\n"
    "• When the exemption ends, normal enforcement resumes automatically"
)

# ------------ Keyboards -------------------------

def _help_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Member Commands", callback_data="dmf_help_cmds")],
        [InlineKeyboardButton("✨ Buyer Requirements + ‼️ Rules", callback_data="dmf_help_buyer")],
        [InlineKeyboardButton("🛡 Exemptions (every 6 months)", callback_data="dmf_help_exemptions")],
        [InlineKeyboardButton("◀️ Back to Portal", callback_data="dmf_home")],
    ])

def _back_to_help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="dmf_help")]])

def _portal_kb() -> InlineKeyboardMarkup:
    # Same structure you use elsewhere in the portal
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

    # Exemptions (every 6 months)
    @app.on_callback_query(filters.regex(r"^dmf_help_exemptions$"))
    async def on_help_exemptions(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, DEFAULT_EXEMPTIONS, _back_to_help_kb())
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
