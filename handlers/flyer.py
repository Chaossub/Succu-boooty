import os
import json
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from utils.check_admin import is_admin

FLYER_STORAGE = "flyers.json"
SCHEDULE_STORAGE = "scheduled_flyers.json"


# ─── Utilities ─────────────────────────────────────────────────────────────

def load_flyers():
    if not os.path.exists(FLYER_STORAGE):
        return {}
    with open(FLYER_STORAGE, "r") as f:
        return json.load(f)


def save_flyers(data):
    with open(FLYER_STORAGE, "w") as f:
        json.dump(data, f, indent=2)


def load_schedules():
    if not os.path.exists(SCHEDULE_STORAGE):
        return []
    with open(SCHEDULE_STORAGE, "r") as f:
        return json.load(f)


def save_schedules(data):
    with open(SCHEDULE_STORAGE, "w") as f:
        json.dump(data, f, indent=2)


# ─── Commands ──────────────────────────────────────────────────────────────

@Client.on_message(filters.command("addflyer") & filters.group)
async def add_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can create flyers.")

    if not message.photo or len(message.command) < 2:
        return await message.reply("Please attach a photo and use the format: /addflyer <name> <optional caption>")

    flyer_name = message.command[1].strip()
    caption = " ".join(message.command[2:]) if len(message.command) > 2 else ""
    file_id = message.photo.file_id

    flyers = load_flyers()
    flyers[flyer_name] = {"file_id": file_id, "caption": caption}
    save_flyers(flyers)

    await message.reply(f"✅ Flyer '{flyer_name}' has been saved!")


@Client.on_message(filters.command("changeflyer") & filters.reply & filters.group)
async def change_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can update flyers.")

    if not message.reply_to_message.photo or len(message.command) < 2:
        return await message.reply("Reply to a new flyer image with: /changeflyer <name>")

    flyer_name = message.command[1].strip()
    flyers = load_flyers()

    if flyer_name not in flyers:
        return await message.reply("❌ Flyer not found.")

    flyers[flyer_name]["file_id"] = message.reply_to_message.photo.file_id
    save_flyers(flyers)

    await message.reply(f"✅ Flyer '{flyer_name}' updated!")


@Client.on_message(filters.command("flyer") & filters.group)
async def send_flyer(client: Client, message: Message):
    flyers = load_flyers()
    if len(message.command) < 2:
        return await message.reply("Usage: /flyer <name>")

    flyer_name = message.command[1].strip()
    flyer = flyers.get(flyer_name)

    if not flyer:
        return await message.reply("❌ Flyer not found.")

    await message.reply_photo(flyer["file_id"], caption=flyer["caption"])


@Client.on_message(filters.command("listflyers") & filters.group)
async def list_flyers(client: Client, message: Message):
    flyers = load_flyers()
    if not flyers:
        return await message.reply("No flyers found.")

    reply = "📌 <b>Available Flyers:</b>\n" + "\n".join(f"• {name}" for name in flyers)
    await message.reply(reply)


@Client.on_message(filters.command("deleteflyer") & filters.group)
async def delete_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can delete flyers.")

    if len(message.command) < 2:
        return await message.reply("Usage: /deleteflyer <name>")

    flyer_name = message.command[1].strip()
    flyers = load_flyers()

    if flyer_name not in flyers:
        return await message.reply("❌ Flyer not found.")

    del flyers[flyer_name]
    save_flyers(flyers)

    await message.reply(f"✅ Flyer '{flyer_name}' deleted.")


@Client.on_message(filters.command("scheduleflyer") & filters.group)
async def schedule_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can schedule flyers.")

    parts = message.text.split(" ", 4)
    if len(parts) < 5:
        return await message.reply("Usage: /scheduleflyer <name> <day_of_week> <HH:MM> <target_chat_id>")

    name, day, time_str, target = parts[1], parts[2], parts[3], parts[4]

    hour, minute = map(int, time_str.split(":"))
    job = {
        "name": name,
        "chat_id": int(target),
        "day": day,
        "hour": hour,
        "minute": minute,
        "type": "image"
    }

    jobs = load_schedules()
    jobs.append(job)
    save_schedules(jobs)

    await message.reply(f"📅 Scheduled flyer '{name}' to post every {day} at {time_str} in {target}")


@Client.on_message(filters.command("scheduletext") & filters.group)
async def schedule_text(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can schedule text.")

    try:
        parts = message.text.split(" ", 4)
        day, time_str, target, text = parts[1], parts[2], parts[3], parts[4]

        hour, minute = map(int, time_str.split(":"))
        job = {
            "chat_id": int(target),
            "day": day,
            "hour": hour,
            "minute": minute,
            "text": text,
            "type": "text"
        }

        jobs = load_schedules()
        jobs.append(job)
        save_schedules(jobs)

        await message.reply(f"📅 Scheduled text for {day} at {time_str} in {target}")
    except:
        await message.reply("Usage: /scheduletext <day_of_week> <HH:MM> <chat_id> <text>")


@Client.on_message(filters.command("listscheduled") & filters.group)
async def list_scheduled(client: Client, message: Message):
    jobs = load_schedules()
    if not jobs:
        return await message.reply("No scheduled posts.")

    reply = "📅 <b>Scheduled Posts:</b>\n"
    for job in jobs:
        reply += f"• {job['type'].title()} — {job.get('name', job.get('text')[:15]+'...')} to {job['chat_id']} on {job['day']} at {job['hour']:02}:{job['minute']:02}\n"

    await message.reply(reply)


@Client.on_message(filters.command("cancelflyer") & filters.group)
async def cancel_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🚫 Only admins can cancel scheduled flyers.")

    if len(message.command) < 2:
        return await message.reply("Usage: /cancelflyer <name or text prefix>")

    to_cancel = message.command[1].strip()
    jobs = load_schedules()
    updated = [job for job in jobs if job.get("name", "") != to_cancel and not job.get("text", "").startswith(to_cancel)]
    save_schedules(updated)

    await message.reply("🗑️ Scheduled post(s) removed.")


# ─── Scheduler Jobs ────────────────────────────────────────────────────────

def schedule_jobs(scheduler: BackgroundScheduler, client: Client):
    jobs = load_schedules()
    for job in jobs:
        trigger = CronTrigger(day_of_week=job["day"], hour=job["hour"], minute=job["minute"])
        if job["type"] == "image":
            scheduler.add_job(send_scheduled_flyer, trigger, args=[client, job])
        elif job["type"] == "text":
            scheduler.add_job(send_scheduled_text, trigger, args=[client, job])


async def send_scheduled_flyer(client: Client, job):
    flyers = load_flyers()
    flyer = flyers.get(job["name"])
    if flyer:
        await client.send_photo(job["chat_id"], flyer["file_id"], caption=flyer["caption"])


async def send_scheduled_text(client: Client, job):
    await client.send_message(job["chat_id"], job["text"])


# ─── Admin Test ────────────────────────────────────────────────────────────

@Client.on_message(filters.command("testadmin"))
async def test_admin_status(client: Client, message: Message):
    admin = await is_admin(client, message.chat.id, message.from_user.id)
    await message.reply(f"✅ Admin status: <b>{admin}</b>")


# ─── Register ──────────────────────────────────────────────────────────────

def register(app: Client, scheduler: BackgroundScheduler):
    app.add_handler(add_flyer)
    app.add_handler(change_flyer)
    app.add_handler(send_flyer)
    app.add_handler(list_flyers)
    app.add_handler(delete_flyer)
    app.add_handler(schedule_flyer)
    app.add_handler(schedule_text)
    app.add_handler(list_scheduled)
    app.add_handler(cancel_flyer)
    app.add_handler(test_admin_status)

    schedule_jobs(scheduler, app)
