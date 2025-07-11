import os
import json
import asyncio
from pytz import timezone as pytz_timezone
from functools import partial
from pyrogram import Client, filters
from pyrogram.types import Message

# ─── Superuser override ─────────────────────────────────
SUPERUSERS = {6964994611}

# ─── Chat shortcuts from environment ─────────────────────────
CHAT_SHORTCUTS = {}
for name in ["SUCCUBUS_SANCTUARY", "MODELS_CHAT", "TEST_GROUP"]:
    val = os.environ.get(name)
    if val:
        try:
            CHAT_SHORTCUTS[name.lower()] = int(val)
        except ValueError:
            pass

# ─── Storage paths ────────────────────────────────────
FLYER_DIR = "flyers"
SCHEDULE_FILE = "scheduled_flyers.json"

os.makedirs(FLYER_DIR, exist_ok=True)


def flyer_file(chat_id: int) -> str:
    return os.path.join(FLYER_DIR, f"{chat_id}.json")


def load_flyers(chat_id: int) -> dict:
    path = flyer_file(chat_id)
    if os.path.exists(path):
        return json.load(open(path))
    return {}


def save_flyers(chat_id: int, data: dict):
    with open(flyer_file(chat_id), "w") as f:
        json.dump(data, f, indent=2)


def load_scheduled() -> list:
    if os.path.exists(SCHEDULE_FILE):
        return json.load(open(SCHEDULE_FILE))
    return []


def save_scheduled(jobs: list):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(jobs, f, indent=2)

# ─── Admin check ──────────────────────────────────────
async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    if user_id in SUPERUSERS:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except:
        return False

# ─── Helper to resolve chat targets ─────────────────────
def resolve_target(target: str) -> int:
    if target.lstrip('-').isdigit():
        return int(target)
    key = target.lower()
    if key in CHAT_SHORTCUTS:
        return CHAT_SHORTCUTS[key]
    raise ValueError(f"Unknown chat shortcut or invalid ID: {target}")

# ─── Job executors ────────────────────────────────────
async def _send_flyer(client: Client, job: dict):
    flyers = load_flyers(job["origin_chat_id"])
    f = flyers.get(job["name"])
    if f:
        await client.send_photo(job["chat_id"], f["file_id"], caption=f["caption"])

async def _send_text(client: Client, job: dict):
    await client.send_message(job["chat_id"], job["text"])

# ─── Registration ────────────────────────────────────
def register(app: Client, scheduler):
    @app.on_message(filters.command("addflyer") & filters.photo)
    async def addflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")
        if not message.caption or len(message.caption.split()) < 2:
            return await message.reply("❌ Usage: send photo with `/addflyer <name>` in caption.")
        name = message.caption.split(None, 1)[1].strip()
        flyers = load_flyers(message.chat.id)
        if name in flyers:
            return await message.reply(f"❌ Flyer “{name}” already exists.")
        flyers[name] = {"file_id": message.photo.file_id, "caption": name}
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer “{name}” added.")

    @app.on_message(filters.command("changeflyer") & filters.photo)
    async def changeflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can change flyers.")
        if not message.caption or len(message.caption.split()) < 2:
            return await message.reply("❌ Usage: send photo with `/changeflyer <name>` in caption.")
        name = message.caption.split(None, 1)[1].strip()
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply(f"❌ No flyer “{name}” found.")
        flyers[name]["file_id"] = message.photo.file_id
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer “{name}” updated.")

    @app.on_message(filters.command("flyer"))
    async def flyer_handler(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = message.command[1]
        flyers = load_flyers(message.chat.id)
        f = flyers.get(name)
        if not f:
            return await message.reply("❌ Flyer not found.")
        await client.send_photo(message.chat.id, f["file_id"], caption=f["caption"])

    @app.on_message(filters.command("listflyers"))
    async def listflyers_handler(client, message: Message):
        flyers = load_flyers(message.chat.id)
        if not flyers:
            return await message.reply("❌ No flyers.")
        text = "<b>📌 Flyers:</b>\n" + "\n".join(f"• <code>{n}</code>" for n in flyers)
        await message.reply(text)

    @app.on_message(filters.command("deleteflyer"))
    async def deleteflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = message.command[1]
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply(f"❌ No flyer “{name}”.")
        del flyers[name]
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer “{name}” deleted.")

    # ─── Scheduling commands ─────────────────────────
    @app.on_message(filters.command("scheduleflyer"))
    async def scheduleflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        cmd=message.command
        if len(cmd)!=4:
            return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <chat>")
        name,time_str,target=cmd[1],cmd[2],cmd[3]
        try:
            h,m=map(int,time_str.split(':'))
            dest=resolve_target(target)
        except Exception as e:
            return await message.reply(f"❌ {e}")
        flyers=load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply(f"❌ No flyer “{name}”.")
        job={"type":"flyer","name":name,"time":time_str,"chat_id":dest,"origin_chat_id":message.chat.id}
        data=load_scheduled()+[job]
        save_scheduled(data)
        scheduler.add_job(lambda j=job: asyncio.create_task(_send_flyer(app, j)),
                          trigger="cron",hour=h,minute=m,
                          timezone=pytz_timezone(os.environ.get("SCHEDULER_TZ","US/Pacific")))
        await message.reply(f"✅ Scheduled flyer “{name}” at {time_str} → <code>{dest}</code>.")

    @app.on_message(filters.command("scheduletext"))
    async def scheduletext_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule text.")
        cmd=message.command
        if len(cmd)<4:
            return await message.reply("❌ Usage: /scheduletext <HH:MM> <chat> <text>")
        time_str,target=cmd[1],cmd[2]
        text=" ".join(cmd[3:])
        try:
            h,m=map(int,time_str.split(':'))
            dest=resolve_target(target)
        except Exception as e:
            return await message.reply(f"❌ {e}")
        job={"type":"text","time":time_str,"chat_id":dest,"text":text}
        data=load_scheduled()+[job]
        save_scheduled(data)
        scheduler.add_job(lambda j=job: asyncio.create_task(_send_text(app, j)),
                          trigger="cron",hour=h,minute=m,
                          timezone=pytz_timezone(os.environ.get("SCHEDULER_TZ","US/Pacific")))
        await message.reply(f"✅ Scheduled text at {time_str} → <code>{dest}</code>.")

    @app.on_message(filters.command("listscheduled"))
    async def list_scheduled_handler(client, message: Message):
        data=load_scheduled()
        if not data:
            return await message.reply("❌ No scheduled posts.")
        lines=[]
        for i,j in enumerate(data,1):
            if j["type"]=="flyer":
                lines.append(f"{i}. Flyer '{j['name']}' @ {j['time']} to {j['chat_id']}")
            else:
                lines.append(f"{i}. Text @ {j['time']} to {j['chat_id']}")
        await message.reply("\n".join(lines))

    @app.on_message(filters.command("cancelflyer"))
    async def cancel_flyer_handler(client, message: Message):
        cmd=message.command
        if len(cmd)!=2 or not cmd[1].isdigit():
            return await message.reply("❌ Usage: /cancelflyer <index>")
        idx=int(cmd[1])-1
        data=load_scheduled()
        if idx<0 or idx>=len(data):
            return await message.reply("❌ Invalid index.")
        job=data.pop(idx)
        save_scheduled(data)
        await message.reply(f"✅ Canceled scheduled post #{idx+1}.")

    # ─── Reschedule existing jobs on startup ─────────
    for job in load_scheduled():
        h,m=map(int,job['time'].split(':'))
        if job['type']=='flyer':
            scheduler.add_job(lambda j=job: asyncio.create_task(_send_flyer(app, j)),
                              trigger='cron',hour=h,minute=m,
                              timezone=pytz_timezone(os.environ.get('SCHEDULER_TZ','US/Pacific')))
        else:
            scheduler.add_job(lambda j=job: asyncio.create_task(_send_text(app, j)),
                              trigger='cron',hour=h,minute=m,
                              timezone=pytz_timezone(os.environ.get('SCHEDULER_TZ','US/Pacific')))
