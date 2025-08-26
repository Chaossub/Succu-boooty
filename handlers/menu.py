# handlers/menu.py
import os
from typing import Dict, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)

# ====== Text from ENV (fallbacks kept minimal) ======
WELCOME_BANNER = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

FIND_MODELS_ELSEWHERE_TEXT = os.getenv("FIND_MODELS_ELSEWHERE_TEXT", "Links coming soon.")
BUYER_RULES_TEXT = os.getenv("BUYER_RULES_TEXT", "Rules coming soon.")
BUYER_REQUIREMENTS_TEXT = os.getenv("BUYER_REQUIREMENTS_TEXT", "Requirements coming soon.")
GAME_RULES_TEXT = os.getenv("GAME_RULES_TEXT", "Games & extras coming soon.")
MEMBER_CMDS_TEXT = os.getenv("MEMBER_CMDS_TEXT", "Member commands coming soon.")

# Admins / owner
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # MUST be set to receive anon/suggestions
RONI_USERNAME = os.getenv("RONI_USERNAME", "")
RUBY_USERNAME = os.getenv("RUBY_USERNAME", "")

# Models: menu text & usernames for DMs
MODELS = [
    {
        "key": "roni",
        "pretty": "💖 Roni",
        "menu_text": os.getenv("RONI_MENU_TEXT", "Roni’s menu coming soon."),
        "username": os.getenv("RONI_USERNAME", ""),
    },
    {
        "key": "ruby",
        "pretty": "💖 Ruby",
        "menu_text": os.getenv("RUBY_MENU_TEXT", "Ruby’s menu coming soon."),
        "username": os.getenv("RUBY_USERNAME", ""),
    },
    {
        "key": "rin",
        "pretty": "💖 Rin",
        "menu_text": os.getenv("RIN_MENU_TEXT", "Rin’s menu coming soon."),
        "username": os.getenv("RIN_USERNAME", ""),
    },
    {
        "key": "savy",
        "pretty": "💖 Savy",
        "menu_text": os.getenv("SAVY_MENU_TEXT", "Savy’s menu coming soon."),
        "username": os.getenv("SAVY_USERNAME", ""),
    },
]

# ====== simple in-memory “awaiting input” states for anon & suggestions ======
# states[user_id] = ("anon" | "suggest_anon" | "suggest_named")
_states: Dict[int, Tuple[str]] = {}

# ====== Keyboards ======
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💕 Menus", callback_data="menus")],
            [InlineKeyboardButton("🔥 Find Our Models Elsewhere ➚", callback_data="find_elsewhere")],
            [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
            [InlineKeyboardButton("❓ Help", callback_data="help")],
        ]
    )

def kb_menus() -> InlineKeyboardMarkup:
    rows = []
    # 2 per row feels nice; adjust if you prefer 1 per row
    for i in range(0, len(MODELS), 2):
        chunk = MODELS[i:i+2]
        row = [
            InlineKeyboardButton(m["pretty"], callback_data=f"model_menu:{m['key']}")
            for m in chunk
        ]
        rows.append(row)
    rows.append([InlineKeyboardButton("💌 Contact Models", callback_data="contact_models")])
    rows.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def kb_contact_models() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(MODELS), 2):
        chunk = MODELS[i:i+2]
        row = []
        for m in chunk:
            if m["username"]:
                row.append(InlineKeyboardButton(
                    f"💌 {m['pretty'].replace('💖 ', '')} ➚",
                    url=f"https://t.me/{m['username']}"
                ))
            else:
                row.append(InlineKeyboardButton(
                    f"💌 {m['pretty'].replace('💖 ', '')}",
                    callback_data="noop"))
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 Back to Menus", callback_data="menus")])
    return InlineKeyboardMarkup(rows)

def kb_admins() -> InlineKeyboardMarkup:
    rows = []
    if RONI_USERNAME:
        rows.append([InlineKeyboardButton("👑 Contact Roni ➚", url=f"https://t.me/{RONI_USERNAME}")])
    if RUBY_USERNAME:
        rows.append([InlineKeyboardButton("👑 Contact Ruby ➚", url=f"https://t.me/{RUBY_USERNAME}")])
    rows.append([InlineKeyboardButton("🕵️ Anonymous Message", callback_data="anon_msg")])
    rows.append([
        InlineKeyboardButton("💡 Suggest (Anonymous)", callback_data="suggest_anon"),
        InlineKeyboardButton("💡 Suggest (With @)", callback_data="suggest_named"),
    ])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def kb_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📜 Buyer Rules", callback_data="help_rules")],
            [InlineKeyboardButton("✅ Buyer Requirements", callback_data="help_requirements")],
            [InlineKeyboardButton("🎮 Game Rules", callback_data="help_games")],
            [InlineKeyboardButton("🆘 Member Commands", callback_data="help_cmds")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
        ]
    )

# ====== Rendering helpers ======
async def show_main_menu(m: Message):
    await m.reply_text(
        WELCOME_BANNER,
        reply_markup=kb_main(),
        disable_web_page_preview=True
    )

async def edit_to_main(q: CallbackQuery):
    # add a tiny invisible change to dodge MESSAGE_NOT_MODIFIED
    await q.message.edit_text(
        WELCOME_BANNER + "\n",  # small harmless change
        reply_markup=kb_main(),
        disable_web_page_preview=True
    )

# ====== Public API for main.py to call, and local wiring for /start & /portal ======
def register(app: Client):
    # /start, /portal
    @app.on_message(filters.command(["start", "portal"]) & filters.private)
    async def _start(_, m: Message):
        # Mark DM-ready note (non-blocking log style)
        try:
            name = (m.from_user.first_name or "").strip()
            await m.reply_text(f"✅ DM-ready — <a href='tg://user?id={m.from_user.id}'>{name or 'User'}</a> just opened the portal.",
                               disable_web_page_preview=True)
        except Exception:
            pass
        await show_main_menu(m)

    # Main buttons
    @app.on_callback_query(filters.regex(r"^back_main$"))
    async def _back_main(_, q: CallbackQuery):
        await edit_to_main(q)
        await q.answer("Back to main")

    @app.on_callback_query(filters.regex(r"^menus$"))
    async def _menus(_, q: CallbackQuery):
        await q.message.edit_text("💕 <b>Menus</b>", reply_markup=kb_menus(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^contact_models$"))
    async def _contact_models(_, q: CallbackQuery):
        await q.message.edit_text("💌 <b>Contact a model directly:</b>", reply_markup=kb_contact_models(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^admins$"))
    async def _admins(_, q: CallbackQuery):
        await q.message.edit_text("👑 <b>Contact Admins:</b>", reply_markup=kb_admins(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^help$"))
    async def _help(_, q: CallbackQuery):
        await q.message.edit_text("❓ <b>Help</b>", reply_markup=kb_help(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^find_elsewhere$"))
    async def _find_elsewhere(_, q: CallbackQuery):
        await q.message.edit_text(FIND_MODELS_ELSEWHERE_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]), disable_web_page_preview=True)
        await q.answer()

    # Help sub-pages
    @app.on_callback_query(filters.regex(r"^help_rules$"))
    async def _help_rules(_, q: CallbackQuery):
        await q.message.edit_text(BUYER_RULES_TEXT, reply_markup=kb_help(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^help_requirements$"))
    async def _help_reqs(_, q: CallbackQuery):
        await q.message.edit_text(BUYER_REQUIREMENTS_TEXT, reply_markup=kb_help(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^help_games$"))
    async def _help_games(_, q: CallbackQuery):
        await q.message.edit_text(GAME_RULES_TEXT, reply_markup=kb_help(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^help_cmds$"))
    async def _help_cmds(_, q: CallbackQuery):
        await q.message.edit_text(MEMBER_CMDS_TEXT, reply_markup=kb_help(), disable_web_page_preview=True)
        await q.answer()

    # Model menus (not DMs)
    @app.on_callback_query(filters.regex(r"^model_menu:(.+)$"))
    async def _model_menu(_, q: CallbackQuery):
        model_key = q.data.split(":", 1)[1]
        model = next((m for m in MODELS if m["key"] == model_key), None)
        if not model:
            await q.answer("Unknown model", show_alert=True)
            return
        text = f"{model['menu_text']}\n\n🔙 Back with the button below."
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔙 Back to Menus", callback_data="menus")]
            ]
        )
        await q.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await q.answer()

    # Admin utilities: anon & suggestions
    @app.on_callback_query(filters.regex(r"^anon_msg$"))
    async def _anon(_, q: CallbackQuery):
        _states[q.from_user.id] = ("anon",)
        await q.message.reply_text("🕵️ Send me the anonymous message now. I’ll forward it to the owner.")
        await q.answer()

    @app.on_callback_query(filters.regex(r"^suggest_anon$"))
    async def _sug_anon(_, q: CallbackQuery):
        _states[q.from_user.id] = ("suggest_anon",)
        await q.message.reply_text("💡 Send your suggestion. I’ll forward it anonymously.")
        await q.answer()

    @app.on_callback_query(filters.regex(r"^suggest_named$"))
    async def _sug_named(_, q: CallbackQuery):
        _states[q.from_user.id] = ("suggest_named",)
        await q.message.reply_text("💡 Send your suggestion. I’ll include your @username.")
        await q.answer()

    # Catch user’s next message for anon/suggestions
    @app.on_message(filters.private & ~filters.command(["start", "portal"]))
    async def _collect_inputs(c: Client, m: Message):
        state = _states.pop(m.from_user.id, None)
        if not state:
            return
        if OWNER_ID == 0:
            await m.reply_text("⚠️ OWNER_ID not set; can’t deliver. Please tell the owner.")
            return

        kind = state[0]
        try:
            if kind == "anon":
                await c.send_message(
                    OWNER_ID,
                    f"🕵️ <b>Anonymous message</b> received:\n\n{m.text or '(non-text)'}",
                    disable_web_page_preview=True,
                )
                await m.reply_text("✅ Sent anonymously to the admins.")
            elif kind == "suggest_anon":
                await c.send_message(
                    OWNER_ID,
                    f"💡 <b>Anonymous suggestion</b> received:\n\n{m.text or '(non-text)'}",
                    disable_web_page_preview=True,
                )
                await m.reply_text("✅ Suggestion sent anonymously.")
            elif kind == "suggest_named":
                from_user = m.from_user
                who = f"@{from_user.username}" if from_user and from_user.username else f"tg://user?id={from_user.id}"
                await c.send_message(
                    OWNER_ID,
                    f"💡 <b>Suggestion</b> from {who}:\n\n{m.text or '(non-text)'}",
                    disable_web_page_preview=True,
                )
                await m.reply_text("✅ Suggestion sent with your name.")
        except Exception as e:
            await m.reply_text(f"❌ Couldn’t deliver: {e}")
