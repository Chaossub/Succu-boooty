import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# Load env variables
SUPER_ADMINS = set(map(int, os.getenv("SUPER_ADMINS", "").split(",")))
MODEL_IDS = set(map(int, os.getenv("MODEL_IDS", "").split(",")))

def register(app: Client):
    @app.on_message(filters.command("help") & filters.private)
    async def help_cmd_handler(client: Client, message: Message):
        await show_help_menu(message)

    @app.on_callback_query(filters.regex(r"^help_menu:(.+)$"))
    async def help_menu_callback(client: Client, query: CallbackQuery):
        data = query.data.split(":")[1]

        if data == "main":
            await show_help_menu(query.message, query)
        elif data == "buyer_requirements":
            await query.message.edit_text(
                "🔥 <b>Buyer Requirements</b> 🔥\n\n"
                "To stay in the group you must do at least one each month:\n"
                "• Spend $20+ (tips, games, content)\n"
                "• OR join 4+ games (min $5 each)\n\n"
                "Support at least TWO different models 💕",
                reply_markup=back_markup()
            )
        elif data == "buyer_rules":
            await query.message.edit_text(
                "📜 <b>Buyer Rules</b> 📜\n\n"
                "1. Respect all models.\n"
                "2. No freeloading — meet requirements.\n"
                "3. No harassment, guilt-tripping, or drama.\n"
                "4. No spamming.\n",
                reply_markup=back_markup()
            )
        elif data == "commands":
            user_id = query.from_user.id
            if user_id in SUPER_ADMINS:
                cmds = (
                    "⚙️ <b>Super Admin Commands</b>\n"
                    "/warn, /resetwarns, /mute, /unmute, /ban, /unban\n"
                    "/fedban, /fedunban, /fedcheck\n"
                    "/kick, /userinfo, /cancel\n"
                    "/addflyer, /changeflyer, /deleteflyer, /listflyers, /flyer\n"
                    "/addmenu, /changemenu, /deletemenu, /listmenus\n"
                )
            elif user_id in MODEL_IDS:
                cmds = (
                    "✨ <b>Model Commands</b>\n"
                    "Includes all Member Commands + the following:\n\n"
                    "/addflyer, /changeflyer, /deleteflyer, /listflyers, /flyer\n"
                    "/addmenu, /changemenu, /deletemenu, /listmenus\n"
                )
            else:
                cmds = (
                    "🙋 <b>Member Commands</b>\n"
                    "/naughty - Check your naughty XP\n"
                    "/leaderboard - See the top naughty members\n"
                    "/bite, /spank, /tease - Fun flirty actions\n"
                    "/summon, /flirtysummon - Call members\n"
                )

            await query.message.edit_text(
                cmds,
                reply_markup=back_markup()
            )

def back_markup():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back", callback_data="help_menu:main")]]
    )

async def show_help_menu(message: Message, query: CallbackQuery = None):
    text = "❓ <b>Help Menu</b> ❓\n\nChoose an option below:"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Buyer Requirements", callback_data="help_menu:buyer_requirements")],
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="help_menu:buyer_rules")],
        [InlineKeyboardButton("⚙️ Commands", callback_data="help_menu:commands")],
    ])

    if query:
        await query.message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)

