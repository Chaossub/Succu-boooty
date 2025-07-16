from pyrogram import filters
from pyrogram.types import Message, User, Chat, CallbackQuery
from pyrogram import Client

SUPER_ADMIN_ID = 6964994611

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except Exception:
        return False

def register(app: Client):
    @app.on_message(filters.command(["start", "help"]))
    async def help_handler(client: Client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        admin = await is_admin(client, chat_id, user_id)
        lines = ["<b>SuccuBot Commands</b>"]
        lines.append("\n🛠 <b>General</b>")
        lines.append("/start — Initialize the bot")
        lines.append("/help — Show this help message")
        lines.append("/cancel — Cancel the current operation")

        lines.append("\n🔔 <b>Summon</b>")
        if admin: lines.append("/trackall — Track all group members (admin only)")
        lines.append("/summon @username — Summon one user")
        lines.append("/summonall — Summon all tracked users")
        lines.append("/flirtysummon @username — Flirty summon one user")
        lines.append("/flirtysummonall — Flirty summon all users")

        lines.append("\n🎉 <b>Fun</b>")
        lines.append("/bite @user — Playful bite & earn XP")
        lines.append("/spank @user — Playful spank & earn XP")
        lines.append("/tease @user — Playful tease & earn XP")

        lines.append("\n📈 <b>XP & Leaderboard</b>")
        lines.append("/naughtystats — Show your XP")
        lines.append("/leaderboard — Show XP leaderboard")

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

            lines.append("\n🛡 <b>Federation</b>")
            lines.append("/createfed <name> — Create a federation")
            lines.append("/deletefed <fed_id> — Delete federation")
            lines.append("/purgefed <fed_id> — Purge fed ban list")
            lines.append("/renamefed <fed_id> <new_name> — Rename federation")
            lines.append("/addfedadmin <fed_id> <user> — Add fed admin")
            lines.append("/removefedadmin <fed_id> <user> — Remove fed admin")
            lines.append("/fedlist — List federations")
            lines.append("/listfedgroups <fed_id> — List groups in federation")
            lines.append("/fedadmins <fed_id> — List federation admins")
            lines.append("/fedban <user> — Federation ban")
            lines.append("/fedunban <user> — Federation unban")
            lines.append("/fedcheck <user> — Check federation bans")
            lines.append("/togglefedaction <kick|mute|off> — Toggle enforcement")

            lines.append("\n📂 <b>Flyers</b>")
            lines.append("/flyer <name> — Retrieve a flyer")
            lines.append("/listflyers — List all flyers")
            lines.append("/addflyer <name> <caption> — Add flyer (photo or text)")
            lines.append("/changeflyer <name> — Update flyer image (reply to new image)")
            lines.append("/deleteflyer <name> — Delete a flyer")
            lines.append("/scheduleflyer <name> <HH:MM> <group> [daily|once] — Schedule flyer")
            lines.append("/scheduletext <HH:MM> <group> <text> [daily|once] — Schedule text flyer")
            lines.append("/listscheduled — View scheduled flyers")
            lines.append("/cancelflyer <job_id> — Cancel a scheduled post")

        await message.reply("\n".join(lines), disable_web_page_preview=True)

