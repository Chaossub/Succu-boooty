import os
import json
import logging
from datetime import datetime, timedelta
from pytz import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.check_admin import is_admin

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ─── Global Scheduler Reference ───────────────────────────────────────────────────
SCHEDULER: BackgroundScheduler = None

# ─── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FLYER_DIR = os.path.join(PROJECT_ROOT, "flyers")
SCHEDULE_FILE = os.path.join(PROJECT_ROOT, "scheduled_flyers.json")
os.makedirs(FLYER_DIR, exist_ok=True)

# ─── JSON Helpers ───────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except Exception:
        logger.exception("Failed to load JSON: %s", path)
    return default

def save_json(path, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        logger.exception("Failed to save JSON: %s", path)

# ─── Flyer Storage ─────────────────────────────────────────────────────────────
def flyer_file(chat_id: int) -> str:
    return os.path.join(FLYER_DIR, f"{chat_id}.json")

def load_flyers(chat_id: int) -> dict:
    flyers = load_json(flyer_file(chat_id), {})
    logger.debug("Loaded %d flyers for chat %s", len(flyers), chat_id)
    return flyers

def save_flyers(chat_id: int, flyers: dict):
    save_json(flyer_file(chat_id), flyers)
    logger.debug("Saved %d flyers for chat %s", len(flyers), chat_id)

# ─── Schedule Storage ──────────────────────────────────────────────────────────
def load_scheduled() -> list:
    jobs = load_json(SCHEDULE_FILE, [])
    logger.debug("Loaded %d scheduled jobs", len(jobs))
    return jobs

def save_scheduled(jobs: list):
    save_json(SCHEDULE_FILE, jobs)
    logger.debug("Persisted %d scheduled jobs", len(jobs))

# ─── Test Command ───────────────────────────────────────────────────────────────
@Client.on_message(filters.command('ping'))
async def ping(client: Client, message: Message):
    await message.reply("pong")

# ─── Flyer Commands ────────────────────────────────────────────────────────────
@Client.on_message(filters.command('addflyer') & filters.photo)
async def add_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can add flyers.")
    parts = (message.caption or "").split(None, 1)
    if len(parts) < 2:
        return await message.reply("❌ Usage: /addflyer <name>")
    name = parts[1].strip()
    flyers = load_flyers(message.chat.id)
    if name in flyers:
        return await message.reply("❌ Flyer already exists.")
    flyers[name] = {"file_id": message.photo.file_id, "caption": message.caption or name}
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' added.")

@Client.on_message(filters.command('changeflyer') & filters.photo)
async def change_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can change flyers.")
    parts = (message.caption or "").split(None, 1)
    if len(parts) < 2:
        return await message.reply("❌ Usage: /changeflyer <name>")
    name = parts[1].strip()
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        return await message.reply("❌ Flyer not found.")
    flyers[name]["file_id"] = message.photo.file_id
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' updated.")

@Client.on_message(filters.command('deleteflyer'))
async def delete_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can delete flyers.")
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("❌ Usage: /deleteflyer <name>")
    name = parts[1]
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        return await message.reply("❌ Flyer not found.")
    del flyers[name]
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' deleted.")

@Client.on_message(filters.command('listflyers'))
async def list_flyers(client: Client, message: Message):
    flyers = load_flyers(message.chat.id)
    if not flyers:
        return await message.reply("❌ No flyers.")
    text = "📂 <b>Flyers in this group:</b>\n" + "\n".join(f"• <code>{n}</code>" for n in flyers)
    await message.reply(text)

@Client.on_message(filters.command('flyer'))
async def send_flyer(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("❌ Usage: /flyer <name>")
    name = parts[1]
    flyers = load_flyers(message.chat.id)
    f = flyers.get(name)
    if not f:
        return await message.reply("❌ Flyer not found.")
    await client.send_photo(message.chat.id, f['file_id'], caption=f['caption'])

# ─── Scheduling Handlers ───────────────────────────────────────────────────────
@Client.on_message(filters.command('scheduleflyer'))
async def schedule_flyer_cmd(client: Client, message: Message):
    logger.debug("[scheduleflyer] got: %s", message.text)
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can schedule flyers.")
    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        return await message.reply("❌ Usage: /scheduleflyer <HH:MM> [daily] <chat_id|ENV_VAR> <name>")
    time_str = parts[1]
    try:
        hour, minute = map(int, time_str.split(':'))
    except ValueError:
        return await message.reply("❌ Invalid time format. Use HH:MM.")
    tz = timezone(os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))
    if parts[2].lower() == "daily":
        repeat = True
        if len(parts) < 4:
            return await message.reply("❌ After \"daily\", provide <chat_id> and <name>.")
        rest = parts[3]
    else:
        repeat = False
        rest = " ".join(parts[2:])
    target, sep, flyer_name = rest.partition(" ")
    if not sep or not flyer_name.strip():
        return await message.reply("❌ Usage: /scheduleflyer <HH:MM> [daily] <chat_id|ENV_VAR> <name>")
    try:
        chat_id = int(target)
    except ValueError:
        env_val = os.getenv(target)
        if env_val and env_val.lstrip('-').isdigit():
            chat_id = int(env_val)
        else:
            return await message.reply("❌ Invalid chat ID or unknown shortcut.")
    flyers = load_flyers(message.chat.id)
    if flyer_name not in flyers:
        return await message.reply(f"❌ Flyer '{flyer_name}' not found.")
    jobs = load_scheduled()
    if repeat:
        job = {'type':'flyer','time':time_str,'day_of_week':'*','origin_chat':message.chat.id,'target_chat':chat_id,'name':flyer_name}
        jobs.append(job)
        save_scheduled(jobs)
        SCHEDULER.add_job(_send_flyer, trigger='cron', hour=hour, minute=minute, day_of_week='*', timezone=tz, args=[client,job])
        logger.debug("[scheduleflyer] scheduler jobs now: %s", SCHEDULER.get_jobs())
        return await message.reply(f"✅ Flyer '{flyer_name}' scheduled daily at {time_str} → {chat_id}")
    now = datetime.now(tz)
    run_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if run_date <= now:
        run_date += timedelta(days=1)
    job = {'type':'flyer','run_date':run_date.isoformat(),'origin_chat':message.chat.id,'target_chat':chat_id,'name':flyer_name}
    jobs.append(job)
    save_scheduled(jobs)
    SCHEDULER.add_job(_send_flyer, trigger='date', run_date=run_date, args=[client,job])
    logger.debug("[scheduleflyer] scheduler jobs now: %s", SCHEDULER.get_jobs())
    await message.reply(f"✅ Flyer '{flyer_name}' scheduled once for {run_date.strftime('%Y-%m-%d %H:%M')} → {chat_id}")

@Client.on_message(filters.command('scheduletext'))
async def schedule_text_cmd(client: Client, message: Message):
    logger.debug("[scheduletext] got: %s", message.text)
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can schedule text.")
    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        return await message.reply("❌ Usage: /scheduletext <HH:MM> [daily] <chat_id|ENV_VAR> <text>")
    time_str = parts[1]
    try:
        hour, minute = map(int, time_str.split(':'))
    except ValueError:
        return await message.reply("❌ Invalid time format. Use HH:MM.")
    tz = timezone(os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))
    if parts[2].lower() == "daily":
        repeat = True
        if len(parts) < 4:
            return await message.reply("❌ After \"daily\", provide <chat_id> and <text>.")
        rest = parts[3]
    else:
        repeat = False
        rest = " ".join(parts[2:])
    target, sep, text_body = rest.partition(" ")
    if not sep or not text_body.strip():
        return await message.reply("❌ Usage: /scheduletext <HH:MM> [daily] <chat_id|ENV_VAR> <text>")
    try:
        chat_id = int(target)
    except ValueError:
        if target.startswith('@'):
            chat_id = target
        else:
            env_val = os.getenv(target)
            try:
                chat_id = int(env_val)
            except Exception:
                return await message.reply("❌ Invalid chat ID, unknown shortcut, or username.")
    # debug echo
    await message.reply(
        "🔧 Debug:\n"
        f" • time: {time_str}\n"
        f" • chat_id: {chat_id}\n"
        f" • daily: {repeat}\n"
        f" • text: {text_body[:50]}…"
    )
    jobs = load_scheduled()
    if repeat:
        job = {'type':'text','time':time_str,'day_of_week':'*','origin_chat':message.chat.id,'target_chat':chat_id,'text':text_body}
        jobs.append(job)
        save_scheduled(jobs)
        SCHEDULER.add_job(_send_text, trigger='cron', hour=hour, minute=minute, day_of_week='*', timezone=tz, args=[client,job])
        logger.debug("[scheduletext] scheduler jobs now: %s", SCHEDULER.get_jobs())
        return await message.reply(f"✅ Text scheduled daily at {time_str} → {chat_id}")
    now = datetime.now(tz)
    run_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if run_date <= now:
        run_date += timedelta(days=1)
    job = {'type':'text','run_date':run_date.isoformat(),'origin_chat':message.chat.id,'target_chat':chat_id,'text':text_body}
    jobs.append(job)
    save_scheduled(jobs)
    SCHEDULER.add_job(_send_text, trigger='date', run_date=run_date, args=[client,job])
    logger.debug("[scheduletext] scheduler jobs now: %s", SCHEDULER.get_jobs())
    await message.reply(f"✅ Text scheduled once for {run_date.strftime('%Y-%m-%d %H:%M')} → {chat_id}")

@Client.on_message(filters.command('debugjobs'))
async def debug_jobs_cmd(client: Client, message: Message):
    persisted = load_scheduled()
    in_memory = []
    for job in SCHEDULER.get_jobs():
        in_memory.append({
            'id': job.id,
            'next_run': str(job.next_run_time),
            'trigger': str(job.trigger)
        })
    persist_str = "📂 Persisted:\n```json\n" + json.dumps(persisted, indent=2) + "\n```"
    mem_str = "\n🧠 In-memory:\n```json\n" + json.dumps(in_memory, indent=2) + "\n```"
    await message.reply(persist_str + mem_str, parse_mode='Markdown')

async def _send_flyer(client: Client, job):
    logger.info("🏷 [FIRE FLYER] %s", job)
    try:
        flyers = load_flyers(job['origin_chat'])
        f = flyers.get(job['name'])
        if not f:
            raise ValueError(f"Missing flyer {job['name']}")
        await client.send_photo(job['target_chat'], f['file_id'], caption=f['caption'])
    except Exception as e:
        logger.exception("Failed to send scheduled flyer: %s", e)
    if 'run_date' in job:
        jobs = load_scheduled()
        jobs = [x for x in jobs if not (x.get('run_date') == job['run_date'] and x['type']=='flyer' and x.get('name')==job['name'])]
        save_scheduled(jobs)
        logger.debug("[FIRE FLYER] cleaned up one-off %s", job)

async def _send_text(client: Client, job):
    logger.info("🏷 [FIRE TEXT] %s", job)
    try:
        await client.send_message(job['target_chat'], job['text'])
    except Exception as e:
        logger.exception("Failed to send scheduled text: %s", e)
    if 'run_date' in job:
        jobs = load_scheduled()
        jobs = [x for x in jobs if not (x.get('run_date') == job['run_date'] and x['type']=='text' and x.get('text')==job['text'])]
        save_scheduled(jobs)
        logger.debug("[FIRE TEXT] cleaned up one-off %s", job)

def register(app: Client, scheduler: BackgroundScheduler):
    global SCHEDULER
    SCHEDULER = scheduler
    jobs = load_scheduled()
    tz = timezone(os.getenv('SCHEDULER_TZ','America/Los_Angeles'))
    logger.info("Rescheduling %d jobs on startup", len(jobs))
    for job in jobs:
        if job['type']=='text':
            if 'run_date' in job:
                rd = datetime.fromisoformat(job['run_date'])
                scheduler.add_job(_send_text, trigger='date', run_date=rd, args=[app,job])
            else:
                h,m = map(int,job['time'].split(':'))
                scheduler.add_job(_send_text, trigger='cron', hour=h, minute=m, day_of_week=job.get('day_of_week','*'), timezone=tz, args=[app,job])
        elif job['type']=='flyer':
            if 'run_date' in job:
                rd = datetime.fromisoformat(job['run_date'])
                scheduler.add_job(_send_flyer, trigger='date', run_date=rd, args=[app,job])
            else:
                h,m = map(int,job['time'].split(':'))
                scheduler.add_job(_send_flyer, trigger='cron', hour=h, minute=m, day_of_week=job.get('day_of_week','*'), timezone=tz, args=[app,job])
