# handlers/menu.py — use wire(app, mongo)
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def wire(app, mongo_client=None):
    env = getattr(app, "_succubot_env", {})
    FIND_URL = env.get("FIND_URL", "https://t.me/SuccuBot")
    BUYER_RULES = env.get("BUYER_RULES", "No rules found.")
    BUYER_REQS  = env.get("BUYER_REQS", "No requirements found.")
    GAME_RULES  = env.get("GAME_RULES", "No game rules found.")
    MODEL_USERNAMES = env.get("MODEL_USERNAMES", {})
    RONI = env.get("RONI", "RoniJane")
    RUBY = env.get("RUBY", "RubySanc")
    OWNER_ID = env.get("OWNER_ID", 0)

    # --- keyboards ---
    def kb_main():  # matches dm_foolproof.kb_main layout
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💕 Menu", callback_data="menus")],
            [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
            [InlineKeyboardButton("💞 Contact Models", callback_data="contact_models")],
            [InlineKeyboardButton("🔥 Find Our Models Elsewhere", url=FIND_URL)],
            [InlineKeyboardButton("❓ Help", callback_data="help")],
        ])

    def kb_menus():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("Roni", callback_data="menu_model:Roni")],
            [InlineKeyboardButton("Ruby", callback_data="menu_model:Ruby")],
            [InlineKeyboardButton("Rin",  callback_data="menu_model:Rin")],
            [InlineKeyboardButton("Savy", callback_data="menu_model:Savy")],
            [InlineKeyboardButton("💌 Contact Models", callback_data="contact_models")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
        ])

    def kb_contact_models():
        rows = [[InlineKeyboardButton(f"💌 {name}", url=f"https://t.me/{uname}")]
                for name, uname in MODEL_USERNAMES.items()]
        rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menus")])
        return InlineKeyboardMarkup(rows)

    def kb_admins():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 Message Roni", url=f"https://t.me/{RONI}")],
            [InlineKeyboardButton("👑 Message Ruby", url=f"https://t.me/{RUBY}")],
            [InlineKeyboardButton("🙈 Send Anonymous Message", callback_data="anon_msg")],
            [InlineKeyboardButton("💡 Suggestions", callback_data="suggest_msg")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
        ])

    def kb_help():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 Buyer Rules", callback_data="help_rules")],
            [InlineKeyboardButton("✅ Buyer Requirements", callback_data="help_reqs")],
            [InlineKeyboardButton("🆘 Member Commands", callback_data="help_cmds")],
            [InlineKeyboardButton("🎮 Game Rules", callback_data="help_games")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
        ])

    def kb_model_menu(name: str):
        uname = MODEL_USERNAMES.get(name)
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📖 {name}'s Menu", callback_data=f"noop:{name}")],
            [InlineKeyboardButton("📅 Book Model", url=f"https://t.me/{uname}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menus")],
        ])

    # --- navigation: edit only the keyboard so welcome text stays ---
    @app.on_callback_query(filters.regex("^menus$"))
    async def _menus(_, q):
        await q.message.edit_reply_markup(reply_markup=kb_menus()); await q.answer()

    @app.on_callback_query(filters.regex("^back_main$"))
    async def _back(_, q):
        await q.message.edit_reply_markup(reply_markup=kb_main()); await q.answer()

    @app.on_callback_query(filters.regex("^admins$"))
    async def _admins(_, q):
        await q.message.edit_reply_markup(reply_markup=kb_admins()); await q.answer()

    @app.on_callback_query(filters.regex("^contact_models$"))
    async def _contact_models(_, q):
        await q.message.edit_reply_markup(reply_markup=kb_contact_models()); await q.answer()

    @app.on_callback_query(filters.regex("^help$"))
    async def _help(_, q):
        await q.message.edit_reply_markup(reply_markup=kb_help()); await q.answer()

    # Help subpages — send as new messages
    @app.on_callback_query(filters.regex("^help_rules$"))
    async def _help_rules(_, q):
        await q.answer(); await q.message.reply_text(BUYER_RULES, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^help_reqs$"))
    async def _help_reqs(_, q):
        await q.answer(); await q.message.reply_text(BUYER_REQS, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^help_cmds$"))
    async def _help_cmds(_, q):
        txt = (
            "🆘 <b>Member Commands</b>\n"
            "• /start or /portal — open the portal\n"
            "• /dmready — mark yourself DM-ready\n"
            "• /dmreadylist — list recent DM-ready (staff)\n"
        )
        await q.answer(); await q.message.reply_text(txt, parse_mode=ParseMode.HTML)

    @app.on_callback_query(filters.regex("^help_games$"))
    async def _help_games(_, q):
        await q.answer(); await q.message.reply_text(GAME_RULES, disable_web_page_preview=True)

    # Model menus
    @app.on_callback_query(filters.regex(r"^menu_model:(.+)$"))
    async def _model_menu(_, q):
        name = q.data.split(":", 1)[1]
        await q.message.edit_reply_markup(reply_markup=kb_model_menu(name)); await q.answer()

    @app.on_callback_query(filters.regex(r"^noop:"))
    async def _noop(_, q):
        await q.answer("Open the model’s menu with the buttons below.")

    # Anonymous + Suggestions → DM owner
    @app.on_callback_query(filters.regex("^anon_msg$"))
    async def _anon(_, q):
        await q.answer()
        await q.message.reply_text("Send the anonymous message for the admins. I’ll forward it privately.")
        g = 991

        @app.on_message(filters.private & ~filters.bot, group=g)
        async def once(_, m):
            if OWNER_ID:
                text = f"📩 <b>Anonymous admin message</b>\n\n{m.text or '(no text)'}"
                await app.send_message(OWNER_ID, text, parse_mode=ParseMode.HTML)
                await m.reply_text("Sent anonymously to the admins. 💌")
            app.remove_handler(once, group=g)

    @app.on_callback_query(filters.regex("^suggest_msg$"))
    async def _suggest(_, q):
        await q.answer()
        await q.message.reply_text("Send your suggestion. I’ll forward it privately (with your username).")
        g = 992

        @app.on_message(filters.private & ~filters.bot, group=g)
        async def once_s(_, m):
            if OWNER_ID:
                u = m.from_user
                text = f"💡 <b>Suggestion</b> from @{u.username or u.id}\n\n{m.text or '(no text)'}"
                await app.send_message(OWNER_ID, text, parse_mode=ParseMode.HTML)
                await m.reply_text("Thanks! Your suggestion was sent. 🙏")
            app.remove_handler(once_s, group=g)
