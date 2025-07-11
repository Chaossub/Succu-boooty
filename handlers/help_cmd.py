# handlers/help_cmd.py

from pyrogram import Client, filters
from pyrogram.types import Message

# Your super‐admin override
SUPER_ADMIN_ID = 6964994611

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False


def register(app: Client):
    @app.on_message(
        filters.command(["start", "help"]) & (filters.private | filters.group)
    )
    async def help_cmd(client: Client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        admin = await is_admin(client, chat_id, user_id)

        sections = []
        sections.append("<b>🛠 General Commands</b>")
        sections.append("• /start — Initialize the bot")
        sections.append("• /help — Show this help message")
        sections.append("• /cancel — Cancel the current operation\n")

        sections.append("<b>🔔 Summon Commands</b>")
        if admin:
            sections.append("• /trackall — Track all group members (admin only)")
        sections.append("• /summon <username> — Summon one user")
        sections.append("• /summonall — Summon all tracked users")
        sections.append("• /flirtysummon <username> — Flirty summon one")
        sections.append("• /flirtysummonall — Flirty summon all\n")

        sections.append("<b>🎉 Fun Commands</b>")
        sections.append("• /bite <username> — Playful bite & earn XP")
        sections.append("• /spank <username> — Playful spank & earn XP")
        sections.append("• /tease <username> — Playful tease & earn XP\n")

        sections.append("<b>📈 XP Commands</b>")
        sections.append("• /naughty — Show your XP")
        sections.append("• /leaderboard — Show the XP leaderboard\n")

        if admin:
            sections.append("<b>⚒ Moderation Commands</b>")
            sections.append("• /warn <user> [reason] — Issue a warning")
            sections.append("• /warns <user> — Check warnings")
            sections.append("• /resetwarns <user> — Reset warns")
            sections.append("• /flirtywarn <user> — Flirty warning (no count)")
            sections.append("• /mute <user> [min] — Mute a user")
            sections.append("• /unmute <user> — Unmute a user")
            sections.append("• /kick <user> — Kick a user")
            sections.append("• /ban <user> — Ban a user")
            sections.append("• /unban <user> — Unban a user")
            sections.append("• /userinfo <user> — View user info\n")

        if admin:
            sections.append("<b>🛡 Federation Commands</b>")
            sections.append("• /createfed <name> — Create a federation")
            sections.append("• /deletefed <fed_id> — Delete a federation")
            sections.append("• /purgefed <fed_id> — Purge federation ban list")
            sections.append("• /renamefed <fed_id> <new_name> — Rename federation")
            sections.append("• /addfedadmin <fed_id> <user> — Add fed admin")
            sections.append("• /removefedadmin <fed_id> <user> — Remove fed admin")
            sections.append("• /listfeds — List federations")
            sections.append("• /listfedgroups <fed_id> — List groups in federation")
            sections.append("• /listfedadmins <fed_id> — List federation admins")
            sections.append("• /fedban <fed_id> <user> — Federation ban")
            sections.append("• /fedunban <fed_id> <user> — Federation unban")
            sections.append("• /fedcheck <user> — Check federation bans")
            sections.append("• /togglefedaction <fed_id> <kick|mute|off> — Toggle enforcement\n")

        if admin:
            sections.append("<b>📂 Flyer Commands</b>")
            sections.append("• /flyer <name> — Retrieve a flyer")
            sections.append("• /listflyers — List all flyers")
            sections.append("• /addflyer <name> — Add a flyer (photo + caption)")
            sections.append("• /changeflyer <name> — Update flyer image")
            sections.append("• /deleteflyer <name> — Delete a flyer")
            sections.append("• /scheduleflyer <name> <HH:MM> <chat> — Schedule flyer")
            sections.append("• /scheduletext <HH:MM> <chat> <text> — Schedule text")
            sections.append("• /listscheduled — View scheduled posts")
            sections.append("• /cancelflyer <index> — Cancel a scheduled post\n")

        await message.reply_text(
            "\n".join(sections),
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
