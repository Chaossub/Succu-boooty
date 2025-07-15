import os
import logging
import asyncio
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

log = logging.getLogger(__name__)

# ---- ALIAS LOADING ----
def load_aliases():
    aliases = {}
    for key, val in os.environ.items():
        if key.isupper() and (
            key.endswith("_CHAT") or key.endswith("_GROUP") or key.endswith("_SANCTUARY")
        ):
            try:
                aliases[key.upper()] = int(val)
            except Exception as e:
                log.warning(f"Alias {key} could not be converted to int: {val} ({e})")
    log.info(f"Loaded group aliases: {aliases}")
    return aliases

ALIASES = load_aliases()

def resolve_group(alias: str):
    if not alias:
        raise ValueError("Group alias missing.")
    alias = alias.strip().upper()
    if alias in ALIASES:
        return ALIASES[alias]
    raise ValueError(
        f"❌ Invalid group/alias: '{alias}' (available: {list(ALIASES)})"
    )

# ---- MONGO SETUP ----
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME") or os.getenv("MONGO_DB_NAME")
mongo = MongoClient(MONGO_URI)[MONGO_DBNAME]

# ---- ADMIN CHECK ----
SUPER_ADMIN_ID = 6964994611

async def is_admin(client, chat_id, user_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

# ---- REGISTRATION ----
def register(app, scheduler):
    log.info("📢 flyer.register() called")

    # -- Add Flyer --
    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can add flyers.")
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply("❌ Usage: /addflyer <name> <caption> (attach photo if needed)")

        name, caption = args[1], args[2]
        flyer = {"name": name.lower(), "caption": caption, "type": "text"}
        if message.photo:
            flyer["type"] = "photo"
            flyer["file_id"] = message.photo.file_id
        elif message.document and message.document.mime_type.startswith("image/"):
            flyer["type"] = "photo"
            flyer["file_id"] = message.document.file_id

        if mongo.flyers.find_one({"name": flyer["name"]}):
            return await message.reply("❌ Flyer already exists.")
        mongo.flyers.insert_one(flyer)
        await message.reply(
            f"✅ {'Photo' if flyer['type']=='photo' else 'Text'} flyer '{name}' added."
        )

    # -- List Flyers --
    @app.on_message(filters.command("listflyers"))
    async def list_flyers(client, message: Message):
        flyers = list(mongo.flyers.find())
        if not flyers:
            return await message.reply("No flyers available.")
        txt = "<b>Flyers:</b>\n" + "\n".join(
            [f"- <b>{f['name']}</b> ({f['type']})" for f in flyers]
        )
        await message.reply(txt)

    # -- Send Flyer Now --
    @app.on_message(filters.command("flyer"))
    async def get_flyer(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        flyer = mongo.flyers.find_one({"name": args[1].strip().lower()})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if flyer["type"] == "photo":
            await message.reply_photo(flyer["file_id"], caption=flyer["caption"])
        else:
            await message.reply(flyer["caption"])

    # -- Delete Flyer --
    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can delete flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = args[1].strip().lower()
        if not mongo.flyers.find_one({"name": name}):
            return await message.reply("❌ Flyer not found.")
        mongo.flyers.delete_one({"name": name})
        await message.reply(f"✅ Flyer '{name}' deleted.")

    # -- Schedule Flyer --
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can schedule flyers.")
        args = message.text.split(maxsplit=4)
        if len(args) < 5:
            return await message.reply(
                "❌ Usage: /scheduleflyer <name> <HH:MM> <group_alias> <once|daily>"
            )
        name, timestr, group_alias, freq = args[1], args[2], args[3], args[4]
        name = name.strip().lower()
        freq = freq.lower()
        try:
            group_id = resolve_group(group_alias)
        except Exception as e:
            return await message.reply(str(e))

        flyer = mongo.flyers.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        import datetime
        now = datetime.datetime.now()
        hour, minute = map(int, timestr.split(":"))
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_time < now:
            run_time += datetime.timedelta(days=1)

        job_id = f"flyer_{name}_{group_id}_{run_time.timestamp()}"
        job_kwargs = dict(
            flyer=flyer,
            group_id=group_id,
            app=client,
            job_id=job_id,
        )

        def flyer_job(flyer, group_id, app, job_id):
            asyncio.run(post_flyer(app, flyer, group_id, job_id))
        if freq == "once":
            scheduler.add_job(
                flyer_job,
                "date",
                run_date=run_time,
                kwargs=job_kwargs,
                id=job_id,
            )
        elif freq == "daily":
            scheduler.add_job(
                flyer_job,
                "cron",
                hour=hour,
                minute=minute,
                kwargs=job_kwargs,
                id=job_id,
            )
        else:
            return await message.reply("❌ Frequency must be 'once' or 'daily'.")

        await message.reply(
            f"✅ Scheduled flyer '{name}' to {group_alias} at {hour:02}:{minute:02} ({freq}).\nTime zone: {os.getenv('SCHEDULER_TZ','America/Los_Angeles')}"
        )

    # -- List Scheduled Flyers --
    @app.on_message(filters.command("listscheduled"))
    async def list_scheduled(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("No flyers scheduled.")
        lines = ["<b>Scheduled Flyers:</b>"]
        for job in jobs:
            data = job.kwargs
            lines.append(
                f"- {data['flyer']['name']} to {data['group_id']} at {str(job.next_run_time)} [job_id: {job.id}]"
            )
        await message.reply("\n".join(lines))

    # -- Cancel Scheduled Flyer --
    @app.on_message(filters.command("cancelflyer") & filters.group)
    async def cancel_flyer(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can cancel flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /cancelflyer <job_id>")
        job_id = args[1].strip()
        job = scheduler.get_job(job_id)
        if not job:
            return await message.reply("❌ No such scheduled flyer/job.")
        scheduler.remove_job(job_id)
        await message.reply(f"✅ Flyer/job {job_id} cancelled.")

# -- Util: Actually post flyer --
async def post_flyer(app, flyer, group_id, job_id):
    log.info(f"Posting flyer '{flyer['name']}' to {group_id}")
    try:
        if flyer["type"] == "photo":
            await app.send_photo(group_id, flyer["file_id"], caption=flyer["caption"])
        else:
            await app.send_message(group_id, flyer["caption"])
        log.info(f"Posted flyer '{flyer['name']}' to {group_id}")
    except Exception as e:
        log.error(f"Failed to post flyer: {e}")


