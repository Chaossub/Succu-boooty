# handlers/help_cmd.py

from pyrogram import Client, filters
from pyrogram.types import Message

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
    @app.on_message(filters.command(["start", "help"]) & (filters.private | filters.group))
    async def help_handler(client: Client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        admin = await is_admin(client, chat_id, user_id)

        lines = ["<b>SuccuBot Commands</b>"]

        # General
        lines.append("\n🛠 <b>General</b>")
        lines.append("/start — Initialize the bot")
        lines.append("/help — Show this help message")
        lines.append("/cancel — Cancel the current operation")

        # Summon
        lines.append("\n🔔 <b>Summon</b>")
        if admin:
            lines.append("/trackall — Track all group members (admin only)")
        lines.append("/summon <code>@username</code> — Summon one user")
        lines.append("/summonall — Summon all tracked users")
        lines.append("/flirtysummon <code>@username</code> — Flirty summon one user")
        lines.append("/flirtysummonall — Flirty summon all users")

        # Fun
        lines.append("\n🎉 <b>Fun</b>")
        lines.append("/bite <code>@username</code> — Playful bite & earn XP")
        lines.append("/spank <code>@username</code> — Playful spank & earn XP")
        lines.append("/tease <code>@username</code> — Playful tease & earn XP")

        # XP & Leaderboard
        lines.append("\n📈 <b>XP & Leaderboard</b>")
        lines.append("/naughty — Show your XP")
        lines.append("/leaderboard — Show the XP leaderboard")

        # Moderation
        if admin:
            lines.append("\n⚒ <b>Moderation</b>")
            lines.append("/warn <user> [reason] — Issue a warning")
            lines.append("/warns <user> — Check warnings")
            lines.append("/resetwarns <user> — Reset warns")
            lines.append("/flirtywarn <user> — Flirty warning (no count)")
            lines.append("/mute <user> [min] — Mute a user")
            lines.append("/unmute <user> — Unmute a user")
            lines.append("/kick <user> — Kick a user")
            lines.append("/ban <user> — Ban a user")
            lines.append("/unban <user> — Unban a user")
            lines.append("/userinfo <user> — View user info")

            # Federation
            lines.append("\n🛡 <b>Federation</b>")
            lines.append("/createfed <name> — Create a federation")
            lines.append("/deletefed <fed_id> — Delete a federation")
            lines.append("/purgefed <fed_id> — Purge fed ban list")
            lines.append("/renamefed <fed_id> <new_name> — Rename federation")
            lines.append("/addfedadmin <fed_id> <user> — Add fed admin")
            lines.append("/removefedadmin <fed_id> <user> — Remove fed admin")
            lines.append("/listfeds — List federations")
            lines.append("/listfedgroups <fed_id> — List groups in federation")
            lines.append("/listfedadmins <fed_id> — List federation admins")
            lines.append("/fedban <fed_id> <user> — Federation ban")
            lines.append("/fedunban <fed_id> <user> — Federation unban")
            lines.append("/fedcheck <user> — Check federation bans")
            lines.append("/togglefedaction <fed_id> <kick|mute|off> — Toggle enforcement")

            # Flyers
            lines.append("\n📂 <b>Flyers (Text & Photo)</b>")
            lines.append("/flyer <name> — Retrieve a flyer (text or photo)")
            lines.append("/listflyers — List all flyers in this group")
            lines.append("")
            lines.append("Add text flyer: /addflyer <name> <text>")
            lines.append("Add photo flyer: send photo with caption '/addflyer <name> <caption>'")
            lines.append("Update flyer: /changeflyer <name> <text> (or send photo with new caption)")
            lines.append("/deleteflyer <name> — Delete a flyer")
            lines.append("")
            lines.append("Schedule flyer: /scheduleflyer <name> <group> <HH:MM> <day|once>")
            lines.append("• <b>Group</b>: alias <code>MODELS_CHAT</code>, <code>TEST_GROUP</code>, <code>SUCCUBUS_SANCTUARY</code> or group ID.")
            lines.append("• <b>Day</b>: <code>mon</code>, <code>tue</code>, <code>wed</code>, <code>thu</code>, <code>fri</code>, <code>sat</code>, <code>sun</code>, <code>once</code>")
            lines.append("/cancelflyer <name> — Cancel scheduled flyer")

        await message.reply_text(
            "\n".join(lines),
            parse_mode="html",
            disable_web_page_preview=True
        )
