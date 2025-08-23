# dm_foolproof.py (root level)
import os
import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from req_store import ReqStore

log = logging.getLogger("dm_foolproof")

store = ReqStore()

# ENV for contacts
RONI_ID = os.getenv("RONI_ID")
RUBY_ID = os.getenv("RUBY_ID")
OWNER_ID = os.getenv("OWNER_ID")
SUPER_ADMIN_ID = os.getenv("SUPER_ADMIN_ID")

# Welcome text
WELCOME_TEXT = (
    "🔥 <b>Welcome to Succubus Sanctuary!</b> 🔥\n\n"
    "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)

# -------------------------------
# Keyboards
# -------------------------------
def _welcome_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📜 Help", callback_data="help_menu")],
            [InlineKeyboardButton("📖 Menu", callback_data="menu_main")],
            [InlineKeyboardButton("🛡 Contact Admins", callback_data="contact_admins")],
            [InlineKeyboardButton("💋 Contact Models", callback_data="contact_models")],
        ]
    )


def _contact_models_kb():
    btns = []
    if RONI_ID:
        btns.append([InlineKeyboardButton("Roni ❤️", url=f"tg://user?id={RONI_ID}")])
    if RUBY_ID:
        btns.append([InlineKeyboardButton("Ruby 😈", url=f"tg://user?id={RUBY_ID}")])
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back_home")])
    return InlineKeyboardMarkup(btns)


def _contact_admins_kb():
    btns = []
    if OWNER_ID:
        btns.append([InlineKeyboardButton("Owner 👑", url=f"tg://user?id={OWNER_ID}")])
    if SUPER_ADMIN_ID:
        btns.append([InlineKeyboardButton("Ruby (Admin) 😇", url=f"tg://user?id={SUPER_ADMIN_ID}")])
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back_home")])
    return InlineKeyboardMarkup(btns)


# -------------------------------
# Handlers
# -------------------------------
def register(app: Client):
    @app.on_message(filters.command("start"))
    async def start_cmd(c: Client, m: Message):
        uid = m.from_user.id
        uname = m.from_user.mention

        # Mark DM-ready only once
        if not store.is_dm_ready_global(uid):
            store.set_dm_ready_global(uid, True)
            # Notify owner once
            if OWNER_ID:
                try:
                    await c.send_message(
                        int(OWNER_ID),
                        f"✅ {uname} is now DM ready!",
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as e:
                    log.warning("Failed to notify owner: %s", e)

        await m.reply_text(
            WELCOME_TEXT,
            reply_markup=_welcome_kb(),
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML,
        )

    # Menu navigation
    @app.on_callback_query()
    async def cb_nav(c, q):
        if q.data == "help_menu":
            await q.message.edit_text(
                "❓ <b>Help Menu</b>\n\nChoose a category:",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("📌 Buyer Requirements", callback_data="buyer_req")],
                        [InlineKeyboardButton("📖 Buyer Rules", callback_data="buyer_rules")],
                        [InlineKeyboardButton("🎲 Game Rules", callback_data="game_rules")],
                        [InlineKeyboardButton("⬅️ Back", callback_data="back_home")],
                    ]
                ),
                parse_mode=ParseMode.HTML,
            )
        elif q.data == "menu_main":
            await q.message.edit_text(
                "🍷 <b>SuccuBot Menu</b>\n\nSelect an option:",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("💋 Contact Models", callback_data="contact_models")],
                        [InlineKeyboardButton("🛡 Contact Admins", callback_data="contact_admins")],
                        [InlineKeyboardButton("⬅️ Back", callback_data="back_home")],
                    ]
                ),
                parse_mode=ParseMode.HTML,
            )
        elif q.data == "contact_models":
            await q.message.edit_text(
                "💋 <b>Contact a Model</b>",
                reply_markup=_contact_models_kb(),
                parse_mode=ParseMode.HTML,
            )
        elif q.data == "contact_admins":
            await q.message.edit_text(
                "🛡 <b>Contact Admins</b>",
                reply_markup=_contact_admins_kb(),
                parse_mode=ParseMode.HTML,
            )
        elif q.data == "back_home":
            await q.message.edit_text(
                WELCOME_TEXT,
                reply_markup=_welcome_kb(),
                parse_mode=ParseMode.HTML,
            )

    # Command to list DM-ready users
    @app.on_message(filters.command("dmreadylist"))
    async def dm_ready_list(c: Client, m: Message):
        dm_users = store.list_dm_ready_global()
        if not dm_users:
            await m.reply_text("⚠️ No users are marked as DM ready.")
            return

        lines = []
        for uid in dm_users.keys():
            try:
                u = await c.get_users(int(uid))
                lines.append(f"• {u.mention}")
            except Exception:
                lines.append(f"• {uid}")

        await m.reply_text("✅ <b>DM Ready Users</b>:\n" + "\n".join(lines), parse_mode=ParseMode.HTML)

