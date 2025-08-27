# handlers/bloop.py
from __future__ import annotations
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.admin_check import is_admin

def register(app: Client):

    @app.on_message(filters.command(["bloop"]))
    async def bloop_help(client: Client, m: Message):
        if not m.from_user or not is_admin(m.from_user.id):
            return await m.reply_text("❌ You’re not allowed to use this command.")

        text = """🐰 <b>SuccuBot Command List</b> 🐰

✨ <b>Navigation</b>
  /start – open the portal
  /portal – legacy portal
  /hi – say hi
  /ping – bot ping
  /bloop – show this list (admin only)

🎭 <b>Fun & XP</b>
  /bite – playful bite
  /kiss – playful kiss
  /spank – playful spank
  /tease – playful tease
  /naughtystats – show naughty XP
  /resetxp – reset XP

🛠 <b>Moderation</b>
  /warn – issue warning
  /warns – check warnings
  /mute – mute user
  /unmute – unmute user
  /ban – ban user
  /unban – unban user
  /kick – kick user
  /userinfo – info about a user

🪄 <b>Menus</b>
  /menu – show menu
  /addmenu – add a menu
  /changemenu – change a menu
  /getmenu – get menu
  /listmenus – list menus
  /cancel – cancel menu/summon
  /createmenu – set custom header text (roni|ruby|rin|savy)

👑 <b>Federation</b>
  /createfed – create federation
  /delfed – delete federation
  /fedinfo – federation info
  /fedban – federation ban
  /fedunban – federation unban
  /fedbans – list bans
  /fedadmins – list federation admins
  /addfedadmin – add federation admin
  /removefedadmin – remove federation admin

📋 <b>Requirements</b>
  /reqstatus – check requirement status
  /reqadd – add requirement
  /reqadmins – list req admins
  /reqexempt – exempt a user
  /exemptlist – list exemptions
  /reqnote – add note
  /reqgame – log game
  /reqhelp – help
  /reqexport – export data
  /reqremind – send reminders
  /reqreport – report
  /reqsweep – sweep

🎟 <b>Flyers</b>
  /flyer – post flyer
  /addflyer – add flyer
  /deleteflyer – delete flyer
  /changeflyer – change flyer
  /listflyers – list flyers
  /flyerhelp – flyer help
  /scheduleflyer – schedule flyer
  /listscheduledflyers – list scheduled flyers
  /cancelflyer – cancel flyer
  /cancelallflyers – cancel all flyers
  /textflyer – text flyer

🗓 <b>Scheduling</b>
  /schedulemsg – schedule message
  /listmsgs – list scheduled messages
  /cancelmsg – cancel scheduled message

📣 <b>Summoning</b>
  /summon – summon user
  /summonall – summon all
  /trackall – track all members

💌 <b>DM Tools</b>
  /dmnow – send DM now
  /dmreadylist – list DM-ready users
  /dmreadyclear – clear DM-ready
  /test – DM “test” to DM-ready users missing requirements

📚 <b>Misc</b>
  /warmup – warmup command
  /fun – fun placeholder
  /game – game command
"""
        await m.reply_text(text, disable_web_page_preview=True)
