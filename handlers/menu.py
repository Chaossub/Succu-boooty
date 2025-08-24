# handlers/menu.py

import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# -------- ENV CONTENT --------
FIND_ELSEWHERE_TEXT      = os.getenv("FIND_ELSEWHERE_TEXT", "No links configured.")
BUYER_RULES_TEXT         = os.getenv("BUYER_RULES_TEXT", "No Buyer Rules configured.")
BUYER_REQUIREMENTS_TEXT  = os.getenv("BUYER_REQUIREMENTS_TEXT", "No Buyer Requirements configured.")
GAME_RULES_TEXT          = os.getenv("GAME_RULES_TEXT", "No Game Rules configured.")
MEMBER_COMMANDS_TEXT     = os.getenv("MEMBER_COMMANDS_TEXT", "No member commands listed.")

# Admin DM targets
OWNER_ID       = int(os.getenv("OWNER_ID", "0") or 0)
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0") or 0)

# --------- KEYBOARDS ----------
def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Menus", callback_data="menus")],
        [InlineKeyboardButton("Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("Find Our Models Elsewhere", callback_data="find_elsewhere")],
        [InlineKeyboardButton("Help", callback_data="help")],
    ])

def _kb_menus() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Roni", callback_data="menu_roni"),
         InlineKeyboardButton("Ruby", callback_data="menu_ruby")],
        [InlineKeyboardButton("Rin", callback_data="menu_rin"),
         InlineKeyboardButton("Savy", callback_data="menu_savy")],
        [InlineKeyboardButton("Contact Models", callback_data="contact_models_all")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ])

def _kb_admins() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Message Roni", callback_data="dm_admin_roni")],
        [InlineKeyboardButton("Message Ruby", callback_data="dm_admin_ruby")],
        [InlineKeyboardButton("Send Anonymous Message", callback_data="anon_admin")],
        [InlineKeyboardButton("Suggestions (Anon or Named)", callback_data="suggest_admin")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ])

def _kb_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Buyer Rules", callback_data="help_buyer_rules")],
        [InlineKeyboardButton("Buyer Requirements", callback_data="help_buyer_requirements")],
        [InlineKeyboardButton("Member Commands", callback_data="help_member_cmds")],
        [InlineKeyboardButton("Game Rules", callback_data="help_game_rules")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ])

def _kb_doc_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Help", callback_data="help")]])

def _kb_find_elsewhere_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]])

# Example model menus (hook up to your existing per-model handlers)
def _kb_model_menu(name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Book {name}", callback_data=f"book_{name.lower()}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menus")],
    ])

# --------- UTIL: SAFE EDIT ----------
async def safe_edit(msg: Message, new_text: str, new_kb: InlineKeyboardMarkup):
    """Edit text only if it changed; else try updating only markup."""
    try:
        if msg.text != new_text:
            await msg.edit_text(new_text, reply_markup=new_kb, disable_web_page_preview=True)
        else:
            # Text is identical—only update markup (may also be identical; Telegram ignores silently)
            await msg.edit_reply_markup(new_kb)
    except Exception:
        # As a last resort (e.g., message too old to edit), send a new one
        await msg.reply_text(new_text, reply_markup=new_kb, disable_web_page_preview=True)

# --------- REGISTER ----------
def register(app: Client):

    # Main Menu entry points
    @app.on_callback_query(filters.regex("^back_main$"))
    async def _back_main(_, q: CallbackQuery):
        await q.answer()
        await safe_edit(q.message, "Main Menu", _kb_main())

    @app.on_callback_query(filters.regex("^menus$"))
    async def _menus(_, q: CallbackQuery):
        await q.answer()
        await safe_edit(q.message, "Menus", _kb_menus())

    @app.on_callback_query(filters.regex("^admins$"))
    async def _admins(_, q: CallbackQuery):
        await q.answer()
        await safe_edit(q.message, "Contact Admins", _kb_admins())

    # --- Admin actions: open DMs, anonymous & suggestions -> send to OWNER ---
    @app.on_callback_query(filters.regex("^dm_admin_roni$"))
    async def _dm_roni(client: Client, q: CallbackQuery):
        await q.answer("Opening DM with Roni…", show_alert=False)
        await client.send_message(q.from_user.id, "Tap here to DM Roni: @RoniJane")  # update handle

    @app.on_callback_query(filters.regex("^dm_admin_ruby$"))
    async def _dm_ruby(client: Client, q: CallbackQuery):
        await q.answer("Opening DM with Ruby…", show_alert=False)
        await client.send_message(q.from_user.id, "Tap here to DM Ruby: @RubyHandle")  # update handle

    @app.on_callback_query(filters.regex("^anon_admin$"))
    async def _anon_admin(client: Client, q: CallbackQuery):
        await q.answer()
        await client.send_message(q.from_user.id, "Send me the anonymous message for admins. I’ll forward it.")
        # Next user message will be forwarded by your generic message router if you have it.
        # Minimal inline implementation:
        # (Left to your existing flow to capture next text and forward to OWNER)

    @app.on_callback_query(filters.regex("^suggest_admin$"))
    async def _suggest_admin(client: Client, q: CallbackQuery):
        await q.answer()
        await client.send_message(q.from_user.id, "Send your suggestion (I’ll include your @name unless you say 'anon').")

    # --- Menus: example per-model stubs ---
    for model in ("roni", "ruby", "rin", "savy"):
        @app.on_callback_query(filters.regex(f"^menu_{model}$"))
        async def _model_menu(_, q: CallbackQuery, model=model):
            await q.answer()
            await safe_edit(q.message, f"{model.capitalize()} Menu", _kb_model_menu(model.capitalize()))

    # Contact Models (full list → external DMs)
    @app.on_callback_query(filters.regex("^contact_models_all$"))
    async def _contact_all(client: Client, q: CallbackQuery):
        await q.answer()
        # Build a grid of names → deep links or @handles
        rows = [
            [InlineKeyboardButton("Roni", url="https://t.me/RoniJane")],
            [InlineKeyboardButton("Ruby", url="https://t.me/RubyHandle")],
            [InlineKeyboardButton("Rin",  url="https://t.me/RinHandle")],
            [InlineKeyboardButton("Savy", url="https://t.me/SavyHandle")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menus")],
        ]
        await safe_edit(q.message, "Contact a Model Directly:", InlineKeyboardMarkup(rows))

    # Find Elsewhere: show the text blob from ENV (like before)
    @app.on_callback_query(filters.regex("^find_elsewhere$"))
    async def _find_elsewhere(_, q: CallbackQuery):
        await q.answer()
        await safe_edit(q.message, FIND_ELSEWHERE_TEXT, _kb_find_elsewhere_back())

    # Help bucket
    @app.on_callback_query(filters.regex("^help$"))
    async def _help(_, q: CallbackQuery):
        await q.answer()
        await safe_edit(q.message, "Help", _kb_help())

    @app.on_callback_query(filters.regex("^help_buyer_rules$"))
    async def _help_buyer_rules(_, q: CallbackQuery):
        await q.answer()
        await safe_edit(q.message, BUYER_RULES_TEXT, _kb_doc_back())

    @app.on_callback_query(filters.regex("^help_buyer_requirements$"))
    async def _help_buyer_req(_, q: CallbackQuery):
        await q.answer()
        await safe_edit(q.message, BUYER_REQUIREMENTS_TEXT, _kb_doc_back())

    @app.on_callback_query(filters.regex("^help_member_cmds$"))
    async def _help_member_cmds(_, q: CallbackQuery):
        await q.answer()
        await safe_edit(q.message, MEMBER_COMMANDS_TEXT, _kb_doc_back())

    @app.on_callback_query(filters.regex("^help_game_rules$"))
    async def _help_game_rules(_, q: CallbackQuery):
        await q.answer()
        await safe_edit(q.message, GAME_RULES_TEXT, _kb_doc_back())
