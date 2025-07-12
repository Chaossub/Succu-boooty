```python
import os
import json
import logging
from pytz import timezone as tz
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.check_admin import is_admin

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

FLYER_DIR = "flyers"
SCHEDULE_FILE = "scheduled_flyers.json"

os.makedirs(FLYER_DIR, exist_ok=True)


def flyer_file(chat_id):
    return os.path.join(FLYER_DIR, f"{chat_id}.json")


def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except Exception:
        logger.exception("❌ Failed to load JSON from %s", path)
    return default


def save_json(path, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        logger.exception("❌ Failed to save JSON to %s", path)


def load_flyers(chat_id):
    flyers = load_json(flyer_file(chat_id), {})
    logger.debug("🔁 Loaded %d flyers for chat %s", len(flyers), chat_id)
    return flyers


def save_flyers(chat_id, flyers):
    save_json(flyer_file(chat_id), flyers)
    logger.debug("💾 Saved %d flyers for chat %s", len(flyers), chat_id)


def load_scheduled():
    data = load_json(SCHEDULE_FILE, [])
    logger.debug("🔄 Loaded %d scheduled jobs", len(data))
    return data


def save_scheduled(data):
    save_json(SCHEDULE_FILE, data)
    logger.debug("💾 Persisted %d scheduled jobs", len(data))


# ─── Flyer Management Commands ─────────────────────────────────
@Client.on_message(filters.command("addflyer") & filters.photo)
async def add_flyer(client: Client, message: Message):
    logger.debug("/addflyer invoked by %s in %s", message.from_user.id, message.chat.id)
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can add flyers.")
    parts = message.caption.split(None, 1) if message.caption else []
    if len(parts) < 2:
        return await message.reply("❌ Usage: /addflyer <name>")
    name = parts[1].strip()
    flyers = load_flyers(message.chat.id)
    if name in flyers:
        return await message.reply("❌ Flyer with that name already exists.")
    flyers[name] = {"file_id": message.photo.file_id,
                    "caption": message.caption or name}
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' added.")


@Client.on_message(filters.command("changeflyer") & filters.photo)
async def change_flyer(client: Client, message: Message):
    logger.debug("/changeflyer invoked by %s in %s", message.from_user.id, message.chat.id)
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can update flyers.")
    parts = message.caption.split(None, 1) if message.caption else []
    if len(parts) < 2:
        return await message.reply("❌ Usage: /changeflyer <name>")
    name = parts[1].strip()
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        return await message.reply("❌ No flyer found with that name.")
    flyers[name]['file_id'] = message.photo.file_id
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' image updated.")


@Client.on_message(filters.command("deleteflyer"))
async def delete_flyer(client: Client, message: Message):
    logger.debug("/deleteflyer invoked: %s", message.text)
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


@Client.on_message(filters.command("flyer"))
async def send_flyer(client: Client, message: Message):
    logger.debug("/flyer invoked: %s", message.text)
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("❌ Usage: /flyer <name>")
    name = parts[1]
    flyers = load_flyers(message.chat.id)
    data = flyers.get(name)
    if not data:
        return await message.reply("❌ Flyer not found.")
    await client.send_photo(message.chat.id, data['file_id'], caption=data['caption'])


@Client.on_message(filters.command("listflyers"))
async def list_flyers(client: Client, message: Message):
    flyers = load_flyers(message.chat.id)
    if not flyers:
        return await message.reply("❌ No flyers in this chat.")
    lines = ["📂 <b>Available Flyers:</b>"]
    for name in flyers:
        lines.append(f"• <code>{name}</code>")
    await message.reply("\n".join(lines))


# ─── Scheduling Commands ─────────────────────────────
@Client.on_message(filters.command("scheduleflyer"))
async def schedule_flyer_cmd(client: Client, message: Message):
    logger.debug("/scheduleflyer invoked: %s", message.text)
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can schedule flyers.")
    parts = message.text.split()
    if len(parts) < 5:
        return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <day(s)> <chat_id>")
    _, name, timestr, dayspec, target = parts[:5]
    try:
        hour, minute = map(int, timestr.split(':'))
    except ValueError:
        return await message.reply("❌ Time must be HH:MM")
    dow = '*' if dayspec.lower() in ('daily', '*') else dayspec.lower()
    try:
        chat_id = int(target)
    except ValueError:
        return await message.reply("❌ Invalid chat_id.")
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        return await message.reply(f"❌ Flyer '{name}' not found.")
    job = {
        'type': 'flyer',
        'name': name,
        'time': timestr,
        'day_of_week': dow,
        'origin_chat': message.chat.id,
        'target_chat': chat_id,
    }
    data = load_scheduled()
    data.append(job)
    save_scheduled(data)
    await message.reply(f"✅ Scheduled flyer '{name}' at {timestr} ({dow}) → {chat_id}")


@Client.on_message(filters.command("listscheduled"))
async def list_scheduled(client: Client, message: Message):
    data = load_scheduled()
    if not data:
        return await message.reply("❌ No scheduled posts.")
    lines = ["⏰ <b>Scheduled Flyers:</b>"]
    for i, j in enumerate(data, 1):
        lines.append(f"{i}. <code>{j['name']}</code> at {j['time']} ({j['day_of_week']}) → {j['target_chat']}")
    await message.reply("\n".join(lines))


@Client.on_message(filters.command("cancelflyer"))
async def cancel_flyer(client: Client, message: Message):
    logger.debug("/cancelflyer invoked: %s", message.text)
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("❌ Usage: /cancelflyer <index>")
    idx = int(parts[1]) - 1
    data = load_scheduled()
    if idx < 0 or idx >= len(data):
        return await message.reply("❌ Invalid index.")
    job = data.pop(idx)
    save_scheduled(data)
    await message.reply(f"✅ Canceled scheduled flyer '{job['name']}'")


# ─── Internal Scheduler Wiring ────────────────────────
def _send_flyer(client: Client, job):
    logger.info("🏷 Running flyer job %s", job)
    try:
        flyers = load_flyers(job['origin_chat'])
        data = flyers.get(job['name'])
        if not data:
            logger.error("❌ Flyer '%s' not found in origin %s", job['name'], job['origin_chat'])
            return
        msg = client.send_photo(
            job['target_chat'],
            data['file_id'],
            caption=data['caption']
        )
        logger.info("✅ Flyer sent msg_id=%s → %s", getattr(msg, 'message_id', '?'), job['target_chat'])
    except Exception:
        logger.exception("❌ Failed to send flyer %s", job)


def register(app: Client, scheduler: BackgroundScheduler):
    # Re-schedule saved jobs on startup
    jobs = load_scheduled()
    logger.info("🔁 Re-scheduling %d jobs", len(jobs))
    for job in jobs:
        h, m = map(int, job['time'].split(':'))
        scheduler.add_job(
            _send_flyer,
            trigger='cron',
            hour=h,
            minute=m,
            day_of_week=job.get('day_of_week', '*'),
            timezone=tz(os.environ.get('SCHEDULER_TZ', 'UTC')),
            args=[app, job]
        )
    # Attach handlers
    app.add_handler(add_flyer)
    app.add_handler(change_flyer)
    app.add_handler(delete_flyer)
    app.add_handler(send_flyer)
    app.add_handler(list_flyers)
    app.add_handler(schedule_flyer_cmd)
    app.add_handler(list_scheduled)
    app.add_handler(cancel_flyer)
```
