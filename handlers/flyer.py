# handlers/flyer.py
import os
import json
from pytz import timezone as pytz_timezone
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message

# ─── Storage paths ────────────────────────────────────
FLYER_DIR     = "flyers"
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
    member = await client.get_chat_member(chat_id, user_id)
    return member.status in ("creator", "administrator")

# ─── Scheduled job executors ──────────────────────────
async def _send_flyer(client: Client, job: dict):
    origin = job["origin_chat_id"]
    flyers = load_flyers(origin)
    f = flyers.get(job["name"])
    if f:
        await client.send_photo(job["chat_id"], f["file_id"], caption=f["caption"])

async def _send_text(client: Client, job: dict):
    await client.send_message(job["chat_id"], job["text"])

def _schedule_existing(scheduler: BackgroundScheduler, client: Client):
    for job in load_scheduled():
        h, m = map(int, job["time"].split(":"))
        trigger = dict(
            trigger="cron",
            hour=h,
            minute=m,
            timezone=pytz_timezone(os.environ.get("SCHEDULER_TZ", "US/Pacific"))
        )
        if job["type"] == "flyer":
            scheduler.add_job(_send_flyer, **trigger, args=[client, job])
        else:
            scheduler.add_job(_send_text,  **trigger, args=[client, job])

# ─── Registration ────────────────────────────────────
def register(app: Client, scheduler: BackgroundScheduler):
    # bind all handlers to this `app` instance:
    @app.on_message(filters.command("addflyer") & filters.photo)
    async def addflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")
        if not message.caption or len(message.caption.split()) < 2:
            return await message.reply("❌ Usage: send photo with `/addflyer <name>` in caption.")
        name = message.caption.split(None, 1)[1].strip()
        flyers = load_flyers(message.chat.id)
        if name in flyers:
            return await message.reply("❌ A flyer named “%s” already exists." % name)
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
            return await message.reply("❌ No flyer named “%s” found." % name)
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
            return await message.reply("❌ No flyers in this group.")
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
            return await message.reply("❌ No flyer named “%s”." % name)
        del flyers[name]
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer “{name}” deleted.")

    @app.on_message(filters.command("scheduleflyer"))
    async def scheduleflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        cmd = message.command
        if len(cmd) != 4:
            return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <chat_id>")
        name, time_str, target = cmd[1], cmd[2], cmd[3]
        try:
            h, m = map(int, time_str.split(":"))
            dest = int(target)
        except:
            return await message.reply("❌ Invalid time or chat_id.")
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply("❌ Flyer “%s” not found." % name)
        job = {
            "type":           "flyer",
            "name":           name,
            "time":           time_str,
            "chat_id":        dest,
            "origin_chat_id": message.chat.id
        }
        data = load_scheduled() + [job]
        save_scheduled(data)
        scheduler.add_job(
            _send_flyer,
            trigger="cron",
            hour=h, minute=m,
            timezone=pytz_timezone(os.environ.get("SCHEDULER_TZ", "US/Pacific")),
            args=[client, job]
        )
        await message.reply(f"✅ Scheduled flyer “{name}” at {time_str} → <code>{dest}</code>.")

    @app.on_message(filters.command("scheduletext"))
    async def scheduletext_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule text.")
        cmd = message.command
        if len(cmd) < 4:
            return await message.reply("❌ Usage: /scheduletext <HH:MM> <chat_id> <text…>")
        time_str, target = cmd[1], cmd[2]
        text = " ".join(cmd[3:])
        try:
            h, m = map(int, time_str.split(":"))
            dest = int(target)
        except:
            return await message.reply("❌ Invalid time or chat_id.")
        job = {"type":"text","time":time_str,"chat_id":dest,"text":text}
        data = load_scheduled() + [job]
        save_scheduled(data)
        scheduler.add_job(
            _send_text,
            trigger="cron",
            hour=h, minute=m,
            timezone=pytz_timezone(os.environ.get("SCHEDULER_TZ", "US/Pacific")),
            args=[client, job]
        )
        await message.reply(f"✅ Scheduled text at {time_str} → <code>{dest}</code>.")

    @app.on_message(filters.command("listscheduled"))
    async def listscheduled_handler(client, message: Message):
        data = load_scheduled()
        if not data:
            return await message.reply("❌ No scheduled posts.")
        text = "<b>⏰ Scheduled Posts:</b>\n"
        for i, j in enumerate(data, 1):
            if j["type"] == "flyer":
                text += (f"{i}. Flyer “{j['name']}” @ {j['time']} → "
                         f"<code>{j['chat_id']}</code>\n")
            else:
                text += f"{i}. Text @ {j['time']} → <code>{j['chat_id']}</code>\n"
        await message.reply(text)

    @app.on_message(filters.command("cancelflyer"))
    async def cancelflyer_handler(client, message: Message):
        cmd = message.command
        if len(cmd) != 2 or not cmd[1].isdigit():
            return await message.reply("❌ Usage: /cancelflyer <index>")
        idx = int(cmd[1]) - 1
        data = load_scheduled()
        if idx < 0 or idx >= len(data):
            return await message.reply("❌ Invalid index.")
        job = data.pop(idx)
        save_scheduled(data)
        await message.reply(f"✅ Canceled scheduled post #{idx+1}: {job}")

    # finally, re-schedule any saved jobs on startup
    _schedule_existing(scheduler, app)
