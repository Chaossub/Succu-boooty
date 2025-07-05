from pyrogram import filters
from pyrogram.types import Message

SUPER_ADMIN_ID = 6964994611

def is_admin(app, user_id, chat_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = app.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

GENERAL_CMDS = [
    ("/naughty [reply]", "Check your or another's naughty XP"),
    ("/leaderboard", "See the top 10 naughtiest users"),
]

FUN_CMDS = [
    ("/bite [reply]", "Give someone a naughty bite (+3 XP)"),
    ("/spank [reply]", "Give someone a naughty spank (+2 XP)"),
    ("/tease [reply]", "Give someone a playful tease (+1 XP)"),
]

FLYER_CMDS = [
    ("/flyer <name>", "View a flyer by name"),
    ("/flyerlist", "See all flyers in this group"),
]

SUMMON_CMDS = [
    ("/summon @user", "Summon a specific user"),
    ("/summonall", "Summon all tracked users"),
    ("/flirtysummon @user", "Flirty summon a specific user"),
    ("/flirtysummonall", "Flirty summon all tracked users"),
]

MOD_CMDS = [
    ("/warn [reply]", "Warn a user (auto-mute at 3/6 warns)"),
    ("/warns [reply]", "Check warns for a user"),
    ("/resetwarns [reply]", "Reset warns for a user"),
    ("/mute [reply] [minutes]", "Mute a user (optionally timed)"),
    ("/unmute [reply]", "Unmute a user"),
    ("/flirtywarn [reply]", "Give a flirty warning"),
    ("/ban [reply]", "Ban a user from the group"),
    ("/unban [reply]", "Unban a user from the group"),
    ("/kick [reply]", "Kick a user from the group"),
]

TRACK_CMDS = [
    ("/trackall", "Track all group members for summons"),
]

FED_CMDS = [
    ("/createfed <name>", "Create a new federation"),
    ("/delfed <fed_id>", "Delete a federation"),
    ("/renamefed <fed_id> <new_name>", "Rename a federation"),
    ("/addfedadmin <fed_id> <@user>", "Add federation admin"),
    ("/delfedadmin <fed_id> <@user>", "Remove federation admin"),
    ("/linkgroup <fed_id>", "Link this group to a federation"),
    ("/unlinkgroup <fed_id>", "Unlink this group from a federation"),
    ("/fedban <fed_id> <@user> [reason]", "Federation-ban a user"),
    ("/fedunban <fed_id> <@user>", "Remove federation-ban"),
    ("/fedlist", "List federations you own"),
    ("/fedinfo <fed_id>", "Show federation details"),
    ("/fedcheck <@user>", "Check a user's fedban status"),
]

FLYER_ADMIN_CMDS = [
    ("/createflyer <name> [reply]", "Add a flyer (reply to photo/file)"),
    ("/changeflyer <name> [reply]", "Change a flyer (reply to photo/file)"),
    ("/delflyer <name>", "Delete a flyer by name"),
]

def register(app):

    @app.on_message(filters.command("help") & filters.group)
    async def help_command(client, message: Message):
        is_user_admin = is_admin(client, message.from_user.id, message.chat.id)
        text = "😈 <b>SuccuBot Commands</b> 😈\n\n"

        text += "✨ <b>General</b>\n"
        for cmd, desc in GENERAL_CMDS:
            text += f"  <code>{cmd}</code> — {desc}\n"

        text += "\n🍑 <b>Fun & Naughty</b>\n"
        for cmd, desc in FUN_CMDS:
            text += f"  <code>{cmd}</code> — {desc}\n"

        text += "\n📄 <b>Flyers</b>\n"
        for cmd, desc in FLYER_CMDS:
            text += f"  <code>{cmd}</code> — {desc}\n"

        text += "\n📣 <b>Summon & Tracking</b>\n"
        for cmd, desc in SUMMON_CMDS:
            text += f"  <code>{cmd}</code> — {desc}\n"

        if is_user_admin:
            text += "\n🛡️ <b>Moderation</b>\n"
            for cmd, desc in MOD_CMDS:
                text += f"  <code>{cmd}</code> — {desc}\n"

            text += "\n🗂️ <b>Tracking (Admin)</b>\n"
            for cmd, desc in TRACK_CMDS:
                text += f"  <code>{cmd}</code> — {desc}\n"

            text += "\n🎨 <b>Flyers (Admin)</b>\n"
            for cmd, desc in FLYER_ADMIN_CMDS:
                text += f"  <code>{cmd}</code> — {desc}\n"

            text += "\n👑 <b>Federation</b>\n"
            for cmd, desc in FED_CMDS:
                text += f"  <code>{cmd}</code> — {desc}\n"

        text += "\n❌ <code>/cancel</code> — Cancel multi-step commands"

        await message.reply(text)
