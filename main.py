# handlers/menu.py
import os
import logging
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, ForceReply
)
from pyrogram.errors import MessageNotModified

load_dotenv()
log = logging.getLogger(__name__)

# --- Owner / routing for anon + suggestions (DM to you) -----------------------
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# --- Text blocks from ENV (exactly as you keep them) --------------------------
def _txt(key: str, default: str = "") -> str:
    v = os.getenv(key, "").strip()
    return v if v else default

WELCOME_BANNER = _txt("WELCOME_BANNER",
    "🔥 *Welcome to SuccuBot* 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ *Use the menu below to navigate!*"
)

WHAT_CAN_THIS_BOT_DO = _txt("WHAT_CAN_THIS_BOT_DO",
    "*What can this bot do?*\n"
    "🔥 *Welcome to SuccuBot* 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
    "😈 If you ever need to know exactly what I can do, just press the Help button and I’ll spill all my secrets… 💋"
)

MODELS_ELSEWHERE_TEXT    = _txt("MODELS_ELSEWHERE_TEXT", "Links coming soon.")
BUYER_RULES_TEXT         = _txt("BUYER_RULES_TEXT", "Rules coming soon.")
BUYER_REQUIREMENTS_TEXT  = _txt("BUYER_REQUIREMENTS_TEXT", "Requirements coming soon.")
GAME_RULES_TEXT          = _txt("GAME_RULES_TEXT", "Games & extras coming soon.")

# --- Models (names, emojis, usernames, per-model menus from ENV) --------------
MODELS = [
    {
        "key": "roni",
        "label": "Roni",
        "emoji": "💗",
        "username": os.getenv("RONI_USERNAME", "").lstrip("@"),
        "menu": _txt("RONI_MENU", "Roni’s menu is coming soon ✨"),
    },
    {
        "key": "ruby",
        "label": "Ruby",
        "emoji": "💖",
        "username": os.getenv("RUBY_USERNAME", "").lstrip("@"),
        "menu": _txt("RUBY_MENU", "Ruby’s menu is coming soon ✨"),
    },
    {
        "key": "rin",
        "label": "Rin",
        "emoji": "💞",
        "username": os.getenv("RIN_USERNAME", "").lstrip("@"),
        "menu": _txt("RIN_MENU", "Rin’s menu is coming soon ✨"),
    },
    {
        "key": "savy",
        "label": "Savy",
        "emoji": "💓",
        "username": os.getenv("SAVY_USERNAME", "").lstrip("@"),
        "menu": _txt("SAVY_MENU", "Savy’s menu is coming soon ✨"),
    },
]

# --- Local state for anon/suggestion collection --------------------------------
_pending_input: Dict[int, Dict[str, Any]] = {}  # user_id -> {"type": "anon" | "suggest"}

# --- Keyboards -----------------------------------------------------------------
def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💕 Menus", callback_data="menus")],
            [InlineKeyboardButton("💞 Contact Models", callback_data="contact_models")],
            [InlineKeyboardButton("👑 Contact Admins", callback_data="contact_admins")],
            [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="find_elsewhere")],
            [InlineKeyboardButton("❓ Help", callback_data="help_root")],
        ]
    )

def _kb_menus() -> InlineKeyboardMarkup:
    rows = []
    # Model menus (open menu text — NOT DMs)
    for m in MODELS:
        rows.append([InlineKeyboardButton(f"{m['emoji']} {m['label']}", callback_data=f"model_menu:{m['key']}")])
    # Contact models list (DM links)
    rows.append([InlineKeyboardButton("💌 Contact Models", callback_data="contact_models")])
    rows.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def _kb_contact_models() -> InlineKeyboardMarkup:
    rows = []
    for m in MODELS:
        if m["username"]:
            rows.append([InlineKeyboardButton(f"{m['emoji']} {m['label']} ↗", url=f"https://t.me/{m['username']}")])
        else:
            rows.append([InlineKeyboardButton(f"{m['emoji']} {m['label']} (DM unavailable)", callback_data="noop")])
    rows.append([InlineKeyboardButton("⬅️ Back to Menus", callback_data="menus")])
    return InlineKeyboardMarkup(rows)

def _kb_contact_admins() -> InlineKeyboardMarkup:
    roni_user = next((m["username"] for m in MODELS if m["key"] == "roni"), "")
    ruby_user = next((m["username"] for m in MODELS if m["key"] == "ruby"), "")
    rows = []
    if roni_user:
        rows.append([InlineKeyboardButton("👑 Message Roni", url=f"https://t.me/{roni_user}")])
    if ruby_user:
        rows.append([InlineKeyboardButton("👑 Message Ruby", url=f"https://t.me/{ruby_user}")])
    rows.append([InlineKeyboardButton("🕵️ Anonymous Message", callback_data="anon")])
    rows.append([InlineKeyboardButton("💡 Suggestion Box", callback_data="suggest")])
    rows.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def _kb_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📜 Buyer Rules", callback_data="help_rules")],
            [InlineKeyboardButton("✅ Buyer Requirements", callback_data="help_requirements")],
            [InlineKeyboardButton("🎮 Game Rules", callback_data="help_games")],
            [InlineKeyboardButton("🧰 Member Commands", callback_data="help_member_cmds")],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")],
        ]
    )

# --- Helpers ------------------------------------------------------------------
async def _safe_edit(msg: Message, text: str, kb: Optional[InlineKeyboardMarkup] = None):
    try:
        await msg.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except MessageNotModified:
        if kb:
            try:
                await msg.edit_reply_markup(kb)
            except MessageNotModified:
                pass

def _member_commands_text() -> str:
    return (
        "🧰 *Member Commands*\n\n"
        "`/menu` — open the main menu\n"
        "`/portal` — same as /start\n"
        "`/help` — open the Help panel\n"
        "Interact with the inline buttons for everything else."
    )

# --- Public attach() to wire handlers into your Client -------------------------
def attach(app: Client):
    log.info("Registering menu handlers")

    # /menu (keeps the welcome banner text as the main menu body)
    @app.on_message(filters.command("menu"))
    async def _open_menu(_, m: Message):
        await m.reply_text(WELCOME_BANNER, reply_markup=_kb_main(), disable_web_page_preview=True)

    # Optional: let /help drop directly into the help panel
    @app.on_message(filters.command("help"))
    async def _help_cmd(_, m: Message):
        await m.reply_text("❓ *Help*", reply_markup=_kb_help())

    # Callback navigation (single entrypoint)
    @app.on_callback_query()
    async def _cb(_, q: CallbackQuery):
        data = q.data or ""

        # Main nav
        if data == "menus":
            await _safe_edit(q.message, "💕 *Menus*", _kb_menus())
            await q.answer()
            return

        if data == "contact_models":
            await _safe_edit(q.message, "Contact a model directly:", _kb_contact_models())
            await q.answer()
            return

        if data == "contact_admins":
            await _safe_edit(q.message, "Contact Admins:", _kb_contact_admins())
            await q.answer()
            return

        if data == "find_elsewhere":
            # Use ENV text; back returns to main (keeping banner feel)
            await _safe_edit(q.message, MODELS_ELSEWHERE_TEXT, _kb_main())
            await q.answer()
            return

        if data == "help_root":
            await _safe_edit(q.message, "❓ *Help*", _kb_help())
            await q.answer()
            return

        # Help subsections
        if data == "help_rules":
            await _safe_edit(q.message, BUYER_RULES_TEXT, _kb_help())
            await q.answer()
            return

        if data == "help_requirements":
            await _safe_edit(q.message, BUYER_REQUIREMENTS_TEXT, _kb_help())
            await q.answer()
            return

        if data == "help_games":
            await _safe_edit(q.message, GAME_RULES_TEXT, _kb_help())
            await q.answer()
            return

        if data == "help_member_cmds":
            await _safe_edit(q.message, _member_commands_text(), _kb_help())
            await q.answer()
            return

        # Per-model menus (NOT DMs)
        if data.startswith("model_menu:"):
            key = data.split(":", 1)[1]
            model = next((m for m in MODELS if m["key"] == key), None)
            if model:
                # Show the model menu text + a Book Model DM link + back
                buttons = []
                if model["username"]:
                    buttons.append([InlineKeyboardButton("💌 Book Model", url=f"https://t.me/{model['username']}")])
                buttons.append([InlineKeyboardButton("⬅️ Back to Menus", callback_data="menus")])
                await _safe_edit(q.message, model["menu"], InlineKeyboardMarkup(buttons))
            await q.answer()
            return

        # Back to main (keep banner)
        if data == "back_main":
            await _safe_edit(q.message, WELCOME_BANNER, _kb_main())
            await q.answer()
            return

        # Anon / Suggestion flows ➜ prompt with ForceReply
        if data == "anon":
            _pending_input[q.from_user.id] = {"type": "anon"}
            await q.message.reply_text(
                "🕵️ Send your *anonymous* message now. I’ll deliver it privately to the admins.",
                reply_markup=ForceReply(selective=True)
            )
            await q.answer("Waiting for your anonymous message…")
            return

        if data == "suggest":
            _pending_input[q.from_user.id] = {"type": "suggest"}
            await q.message.reply_text(
                "💡 Send your *suggestion* now. I can include your @username in the forward.",
                reply_markup=ForceReply(selective=True)
            )
            await q.answer("Waiting for your suggestion…")
            return

        if data == "noop":
            await q.answer()
            return

    # Capture replies for anon/suggestions and forward to OWNER_ID
    @app.on_message(filters.private & ~filters.command(["start", "portal", "menu", "help"]))
    async def _collect_inputs(client: Client, m: Message):
        st = _pending_input.pop(m.from_user.id, None)
        if not st:
            return
        if not OWNER_ID:
            await m.reply_text("Sorry, admin inbox isn’t configured yet (OWNER_ID missing).")
            return

        if st["type"] == "anon":
            header = "🕵️ *Anonymous Message*"
            body = m.text or "(no text)"
            await client.send_message(OWNER_ID, f"{header}\n\n{body}")
            await m.reply_text("✅ Sent anonymously to the admins. Thank you!")
            return

        if st["type"] == "suggest":
            uname = f"@{m.from_user.username}" if m.from_user and m.from_user.username else "Anonymous"
            header = "💡 *Suggestion*"
            body = m.text or "(no text)"
            await client.send_message(OWNER_ID, f"{header}\n\nFrom: {uname}\n\n{body}")
            await m.reply_text("✅ Suggestion delivered. Thank you!")
            return
