import os
import json
from pytz import timezone as pytz_timezone
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

# ─── Resolve chat shortcuts or numeric IDs ─────────────
def resolve_target(target: str) -> int:
    if target.lstrip('-').isdigit():
        return int(target)
    key = target.lower()
    if key in CHAT_SHORTCUTS:
        return CHAT_SHORTCUTS[key]
    raise ValueError(f"Unknown chat shortcut or invalid ID: {target}")

# ─── Job executors ────────────────────────────────────
async def _send_flyer(client: Client, job: dict):
    # send to forum thread if provided
    kwargs = {}
    if job.get("thread_id") is not None:
        kwargs["message_thread_id"] = job["thread_id"]
    flyers = load_flyers(job["origin_chat_id"])
    f = flyers.get(job["name"])
    if f:
        await client.send_photo(job["chat_id"], f["file_id"], caption=f["caption"], **kwargs)

async def _send_text(client: Client, job: dict):
    kwargs = {}
    if job.get("thread_id") is not None:
        kwargs["message_thread_id"] = job["thread_id"]
    await client.send_message(job["chat_id"], job["text"], **kwargs)

# ─── Registration ────────────────────────────────────
def register(app: Client, scheduler):
    # ... your CRUD handlers here ...

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        cmd = message.command
        if len(cmd) not in (4, 5):
            return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <chat> [<thread_id>]")
        name, time_str, target = cmd[1], cmd[2], cmd[3]
        thread_id = int(cmd[4]) if len(cmd) == 5 else None
        try:
            hour, minute = map(int, time_str.split(':'))
            dest = resolve_target(target)
        except Exception as e:
            return await message.reply(f"❌ {e}")
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply(f"❌ Flyer '{name}' not found.")
        job = {"type":"flyer","name":name,"time":time_str,
               "chat_id":dest,"origin_chat_id":message.chat.id,
               "thread_id":thread_id}
        data = load_scheduled() + [job]
        save_scheduled(data)
        scheduler.add_job(
            _send_flyer,
            trigger="cron",
            hour=hour,
            minute=minute,
            timezone=pytz_timezone(os.environ.get("SCHEDULER_TZ", "US/Pacific")),
            args=[app, job]
        )
        await message.reply(f"✅ Scheduled flyer '{name}' at {time_str} → {dest} (thread={thread_id}).")

    @app.on_message(filters.command("scheduletext") & filters.group)
    async def scheduletext_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule text.")
        cmd = message.command
        if len(cmd) < 4:
            return await message.reply("❌ Usage: /scheduletext <HH:MM> <chat> [<thread_id>] <text>")
        time_str, target = cmd[1], cmd[2]
        idx = 3
        thread_id = None
        if cmd[3].isdigit():
            thread_id = int(cmd[3])
            idx = 4
        text = " ".join(cmd[idx:])
        try:
            hour, minute = map(int, time_str.split(':'))
            dest = resolve_target(target)
        except Exception as e:
            return await message.reply(f"❌ {e}")
        job = {"type":"text","time":time_str,
               "chat_id":dest,"text":text,
               "thread_id":thread_id}
        data = load_scheduled() + [job]
        save_scheduled(data)
        scheduler.add_job(
            _send_text,
            trigger="cron",
            hour=hour,
            minute=minute,
            timezone=pytz_timezone(os.environ.get("SCHEDULER_TZ", "US/Pacific")),
            args=[app, job]
        )
        await message.reply(f"✅ Scheduled text at {time_str} → {dest} (thread={thread_id}).")

    @app.on_message(filters.command("listscheduled") & filters.group)
    async def list_scheduled_handler(client, message: Message):
        data = load_scheduled()
        if not data:
            return await message.reply("❌ No scheduled posts.")
        lines = []
        for i, j in enumerate(data, 1):
            thread_info = f" thread={j.get('thread_id')}" if j.get('thread_id') else ''
            if j["type"] == "flyer":
                lines.append(f"{i}. Flyer '{j['name']}' @ {j['time']} → {j['chat_id']}{thread_info}")
            else:
                lines.append(f"{i}. Text @ {j['time']} → {j['chat_id']}{thread_info}: {j['text']}")
        await message.reply("\n".join(lines))

    @app.on_message(filters.command("cancelflyer") & filters.group)
    async def cancel_flyer_handler(client, message: Message):
        cmd = message.command
        if len(cmd) != 2 or not cmd[1].isdigit():
            return await message.reply("❌ Usage: /cancelflyer <index>")
        idx = int(cmd[1]) - 1
        data = load_scheduled()
        if idx < 0 or idx >= len(data):
            return await message.reply("❌ Invalid index.")
        data.pop(idx)
        save_scheduled(data)
        await message.reply(f"✅ Canceled scheduled post #{idx+1}.")

    # Reschedule existing jobs on startup
    for job in load_scheduled():
        hour, minute = map(int, job['time'].split(':'))
        fn = _send_flyer if job['type'] == 'flyer' else _send_text
        scheduler.add_job(
            fn,
            trigger='cron',
            hour=hour,
            minute=minute,
            timezone=pytz_timezone(os.environ.get('SCHEDULER_TZ', 'US/Pacific')),
            args=[app, job]
        )
