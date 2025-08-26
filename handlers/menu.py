# handlers/menu.py
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
import os
import html

# ---- Config pulled from ENV ----
FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "No external links have been set yet.")
BUYER_RULES      = os.getenv("BUYER_RULES_TEXT", "No rules configured.")
BUYER_REQS       = os.getenv("BUYER_REQS_TEXT", "No requirements configured.")
GAME_RULES       = os.getenv("GAME_RULES_TEXT", "No game rules configured.")
OWNER_ID         = int(os.getenv("OWNER_ID", "0"))

RONI_USERNAME    = os.getenv("RONI_USERNAME", "RoniJane")
RUBY_USERNAME    = os.getenv("RUBY_USERNAME", "RubyDoe")

# Models registry (menus come from your per-model handlers/commands)
MODELS = [
    ("Roni", "model_menu:roni", os.getenv("RONI_USERNAME", "RoniJane")),
    ("Ruby", "model_menu:ruby", os.getenv("RUBY_USERNAME", "RubyDoe")),
    ("Rin",  "model_menu:rin",  os.getenv("RIN_USERNAME",  "RinUser")),
    ("Savy", "model_menu:savy", os.getenv("SAVY_USERNAME", "SavyUser")),
]

WELCOME_COPY = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

# Simple in-memory “did we DM-ready this user recently” flag
_dm_ready_once = set()

def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="contact_admins")],
        [InlineKeyboardButton("💞 Contact Models", callback_data="contact_models_open")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="ext_links")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ])

def _kb_menus() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(MODELS), 2):
        row = []
        for name, cb, _ in MODELS[i:i+2]:
            row.append(InlineKeyboardButton(f"💗 {name}", callback_data=cb))
        rows.append(row)
    rows.append([InlineKeyboardButton("💌 Contact Models", callback_data="contact_models_open")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def _kb_contact_models() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(MODELS), 2):
        row = []
        for name, _, username in MODELS[i:i+2]:
            row.append(InlineKeyboardButton(f"💗 {name}", url=f"https://t.me/{username}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 Back to Menus", callback_data="menus")])
    return InlineKeyboardMarkup(rows)

def _kb_contact_admins() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 DM Roni", url=f"https://t.me/{RONI_USERNAME}")],
        [InlineKeyboardButton("👑 DM Ruby", url=f"https://t.me/{RUBY_USERNAME}")],
        [InlineKeyboardButton("🕵️ Anonymous Message", callback_data="anon")],
        [InlineKeyboardButton("💡 Suggestion Box", callback_data="suggest")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ])

def _kb_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="buyer_rules")],
        [InlineKeyboardButton("✅ Buyer Requirements", callback_data="buyer_reqs")],
        [InlineKeyboardButton("🧰 Member Commands", callback_data="member_cmds")],
        [InlineKeyboardButton("🎮 Game Rules", callback_data="game_rules")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ])

def _kb_back_to_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Help", callback_data="help")]])

def _kb_back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])

def wire(app: Client):
    @app.on_message(filters.command(["start", "portal"]) & filters.private)
    async def _start(client: Client, m: types.Message):
        if m.from_user and m.from_user.id not in _dm_ready_once:
            _dm_ready_once.add(m.from_user.id)
            await m.reply_text(f"✅ DM-ready — {m.from_user.mention} just opened the portal.")
        await m.reply_text(WELCOME_COPY, reply_markup=_kb_main(),
                           disable_web_page_preview=True, parse_mode="html")

    @app.on_callback_query(filters.regex("^menus$"))
    async def _menus(client: Client, q: types.CallbackQuery):
        await q.message.edit_text("💕 <b>Menu</b>\n\nChoose a model menu or open the contact list.",
                                  reply_markup=_kb_menus(), parse_mode="html")

    @app.on_callback_query(filters.regex("^back_main$"))
    async def _back_main(client: Client, q: types.CallbackQuery):
        await q.message.edit_text(WELCOME_COPY, reply_markup=_kb_main(),
                                  disable_web_page_preview=True, parse_mode="html")

    @app.on_callback_query(filters.regex("^contact_models_open$"))
    async def _contact_models_open(client: Client, q: types.CallbackQuery):
        await q.message.edit_text("Contact a model directly:", reply_markup=_kb_contact_models())

    @app.on_callback_query(filters.regex("^contact_admins$"))
    async def _contact_admins(client: Client, q: types.CallbackQuery):
        await q.message.edit_text("Contact Admins:", reply_markup=_kb_contact_admins())

    # Anonymous & Suggestions (forward to OWNER_ID)
    @app.on_callback_query(filters.regex("^anon$"))
    async def _anon(client: Client, q: types.CallbackQuery):
        await q.message.edit_text("🕵️ Send your anonymous message. I’ll forward it to the owner.",
                                  reply_markup=_kb_back_to_main())
        await client.send_message(q.from_user.id, "Reply to this message with your anonymous note:",
                                  reply_markup=ForceReply(selective=True))

    @app.on_callback_query(filters.regex("^suggest$"))
    async def _suggest(client: Client, q: types.CallbackQuery):
        await q.message.edit_text("💡 Send your suggestion (anonymous or include your @).",
                                  reply_markup=_kb_back_to_main())
        await client.send_message(q.from_user.id, "Reply to this message with your suggestion:",
                                  reply_markup=ForceReply(selective=True))

    @app.on_message(filters.private & filters.reply)
    async def _collector(client: Client, m: types.Message):
        try:
            if OWNER_ID:
                who = m.from_user.mention if m.from_user else "Unknown"
                text = m.text or m.caption or ""
                body = f"📥 <b>New user submission</b>\nFrom: {who}\n\n{html.escape(text)}"
                await client.send_message(OWNER_ID, body, parse_mode="html")
                await m.reply_text("✅ Got it! I’ve sent that along.")
        except Exception:
            await m.reply_text("I couldn’t deliver that just now—please try again.")

    # Help
    @app.on_callback_query(filters.regex("^help$"))
    async def _help(client: Client, q: types.CallbackQuery):
        await q.message.edit_text("❓ Help", reply_markup=_kb_help())

    @app.on_callback_query(filters.regex("^buyer_rules$"))
    async def _buyer_rules(client: Client, q: types.CallbackQuery):
        await q.message.edit_text(BUYER_RULES, reply_markup=_kb_back_to_help(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^buyer_reqs$"))
    async def _buyer_reqs(client: Client, q: types.CallbackQuery):
        await q.message.edit_text(BUYER_REQS, reply_markup=_kb_back_to_help(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^member_cmds$"))
    async def _member_cmds(client: Client, q: types.CallbackQuery):
        text = (
            "🧰 <b>Member Commands</b>\n"
            "• /menu — open the menu\n"
            "• /portal — same as /start\n"
            "• /help — show help\n"
        )
        await q.message.edit_text(text, reply_markup=_kb_back_to_help(), parse_mode="html")

    @app.on_callback_query(filters.regex("^game_rules$"))
    async def _game_rules(client: Client, q: types.CallbackQuery):
        await q.message.edit_text(GAME_RULES, reply_markup=_kb_back_to_help(), disable_web_page_preview=True)

    # NEW: Find Our Models Elsewhere (from ENV text)
    @app.on_callback_query(filters.regex("^ext_links$"))
    async def _ext_links(client: Client, q: types.CallbackQuery):
        await q.message.edit_text(FIND_MODELS_TEXT, reply_markup=_kb_back_to_main(), disable_web_page_preview=True)

    # Per-model menu entry: delegates to your per-model handlers
    @app.on_callback_query(filters.regex(r"^model_menu:(.+)$"))
    async def _open_model_menu(client: Client, q: types.CallbackQuery):
        key = q.matches[0].group(1)  # roni/ruby/rin/savy
        await client.send_message(q.from_user.id, f"/menu_{key}")
