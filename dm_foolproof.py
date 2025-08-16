# handlers/help_cmd.py
import os
from pyrogram import Client, filters
from pyrogram.types import Message

SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "6964994611"))

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except Exception:
        return False

def _build_help_text(admin: bool) -> str:
    lines = ["<b>SuccuBot Commands</b>"]

    # General
    lines.append("\n🛠 <b>General</b>")
    lines.append("/help — show this menu")
    lines.append("/hi — say hi")
    lines.append("/ping — quick health check")
    lines.append("/cancel — cancel current action")

    # DM Ready (Foolproof)
    lines.append("\n💌 <b>DM Ready (Foolproof)</b>")
    lines.append("/dmsetup — post button to open DM & auto-opt in")
    lines.append("/dmready — mark yourself ready (reply to set others)")
    lines.append("/dmunready — remove ready (reply to set others)")
    lines.append("/dmreadylist — list DM-ready users (global)")
    lines.append("/dmnudge [@user|id] — DM a nudge (or reply)")

    # Requirements
    lines.append("\n📋 <b>Requirements</b>")
    lines.append("/reqhelp — show requirement commands")
    lines.append("/reqstatus — your status (admins can /reqstatus or reply)")
    lines.append("/reqadd — add purchase (reply or self)")
    lines.append("/reqgame — add one game (reply or self)")
    lines.append("/reqnote — set note (reply or text)")
    lines.append("/reqexport — export this month CSV")
    lines.append("/reqadmins — list/add/remove req admins")

    # Exemptions
    lines.append("\n🛡 <b>Exemptions</b>")
    lines.append("/reqexempt list — show group + global exemptions")
    lines.append("/reqexempt add [72h|7d|global] [; note] — add exemption (reply or id)")
    lines.append("/reqexempt remove [global] — remove exemption (reply or id)")

    # Fun / XP
    lines.append("\n🎉 <b>Fun</b>")
    lines.append("/bite @user — playful bite & earn XP")
    lines.append("/spank @user — playful spank & earn XP")
    lines.append("/tease @user — playful tease & earn XP")

    lines.append("\n📈 <b>XP & Leaderboard</b>")
    lines.append("/naughtystats — show your XP")
    lines.append("/leaderboard — show XP leaderboard")

    if admin:
        # Moderation
        lines.append("\n⚒ <b>Moderation</b>")
        lines.append("/warn <user> [reason] — issue a warning")
        lines.append("/warns <user> — check warnings")
        lines.append("/resetwarns <user> — reset warns")
        lines.append("/flirtywarn <user> — flirty warning (no count)")
        lines.append("/mute <user> [min] — mute a user")
        lines.append("/unmute <user> — unmute a user")
        lines.append("/kick <user> — kick a user")
        lines.append("/ban <user> — ban a user")
        lines.append("/unban <user> — unban a user")
        lines.append("/userinfo <user> — view user info")

        # Federation
        lines.append("\n🛡 <b>Federation</b>")
        lines.append("/createfed <name> — create a federation")
        lines.append("/deletefed <fed_id> — delete federation")
        lines.append("/purgefed <fed_id> — purge fed ban list")
        lines.append("/renamefed <fed_id> <new_name> — rename federation")
        lines.append("/addfedadmin <fed_id> <user> — add fed admin")
        lines.append("/removefedadmin <fed_id> <user> — remove fed admin")
        lines.append("/fedlist — list federations")
        lines.append("/listfedgroups <fed_id> — list groups in federation")
        lines.append("/fedadmins <fed_id> — list federation admins")
        lines.append("/fedban <user> — federation ban")
        lines.append("/fedunban <user> — federation unban")
        lines.append("/fedcheck <user> — check federation bans")
        lines.append("/togglefedaction <kick|mute|off> — toggle enforcement")

        # Flyers / scheduling
        lines.append("\n📂 <b>Flyers</b>")
        lines.append("/flyer <name> — retrieve a flyer")
        lines.append("/listflyers — list all flyers")
        lines.append("/addflyer <name> <caption> — add flyer (photo or text)")
        lines.append("/changeflyer <name> — update flyer image (reply to new image)")
        lines.append("/deleteflyer <name> — delete a flyer")
        lines.append("/scheduleflyer <name> <HH:MM> <group> [daily|once] — schedule flyer")
        lines.append("/scheduletext <HH:MM> <group> <text> [daily|once] — schedule text flyer")
        lines.append("/listscheduled — view scheduled flyers")
        lines.append("/cancelflyer <job_id> — cancel a scheduled post")

        # Tracking
        lines.append("\n📡 <b>Tracking</b>")
        lines.append("/trackall — track all members (admin only)")

    return "\n".join(lines)

def register(app: Client):
    # /help everywhere
    @app.on_message(filters.command("help") & ~filters.scheduled)
    async def help_everywhere(client: Client, message: Message):
        admin = False
        try:
            admin = await is_admin(client, message.chat.id, message.from_user.id)
        except Exception:
            admin = False
        await message.reply(_build_help_text(admin), disable_web_page_preview=True)

    # /start in GROUPS ONLY (so /start in DMs is left to dm_foolproof)
    @app.on_message(filters.command("start") & ~filters.private & ~filters.scheduled)
    async def start_groups(client: Client, message: Message):
        admin = False
        try:
            admin = await is_admin(client, message.chat.id, message.from_user.id)
        except Exception:
            admin = False
        await message.reply(_build_help_text(admin), disable_web_page_preview=True)
