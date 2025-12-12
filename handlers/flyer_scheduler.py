# handlers/flyer_scheduler.py
import os
import asyncio
import logging
from datetime import datetime
from typing import Dict

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient, ASCENDING
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

log = logging.getLogger(__name__)

OWNER_ID = int(
    os.getenv("OWNER_ID")
    or os.getenv("BOT_OWNER_ID")
    or "6964994611"
)

# ────────────── Scheduler globals ──────────────

scheduler = BackgroundScheduler()
MAIN_LOOP = None  # set by main.py

# msg_id -> job (same pattern as schedulemsg)
SCHEDULED_FLYERS: Dict[str, object] = {}

# ────────────── DB ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI must be set for flyer_scheduler")

mongo = MongoClient(MONGO_URI)
db = mongo["Succubot"]

flyers_coll = db["flyers"]
jobs_coll = db["flyer_jobs"]
jobs_coll.create_index([("msg_id", ASCENDING)], unique=True)

# ────────────── Helpers ──────────────


def fs_log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[FLYERSCHED][{ts}] {msg}", flush=True)


def resolve_group_name(group: str) -> str:
    """
    Same pattern as schedulemsg:
    - If group looks like an ID or @username, use it directly
    - Otherwise treat it as an ENV key (e.g. SUCCUBUS_SANCTUARY)
    """
    group = group.strip()
    if group.startswith("-") or group.startswith("@"):
        return group

    val = os.getenv(group)
    if val:
        return val.split(",")[0].strip()
    return group


def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop
    fs_log("MAIN_LOOP set by set_main_loop()")


async def _post_flyer(
    client: Client,
    group: str,
    file_id: str,
    caption: str,
    msg_id: str,
):
    fs_log(f"_post_flyer CALLED for {group} (msg_id={msg_id})")
    try:
        await client.send_photo(group, file_id, caption=caption)
        fs_log(f"Flyer posted to {group} (msg_id={msg_id})")
    except Exception as e:
        fs_log(f"Failed to post scheduled flyer: {e}")

    # Remove from in-memory and DB
    SCHEDULED_FLYERS.pop(msg_id, None)
    try:
        jobs_coll.delete_one({"msg_id": msg_id})
    except Exception as e:
        fs_log(f"Failed to delete job doc for {msg_id}: {e}")


def _run_post_flyer(
    client: Client,
    group: str,
    file_id: str,
    caption: str,
    msg_id: str,
):
    fs_log(f"_run_post_flyer CALLED for {group} (msg_id={msg_id})")
    global MAIN_LOOP
    if MAIN_LOOP is None:
        fs_log("ERROR: MAIN_LOOP is not set!")
        return
    try:
        asyncio.run_coroutine_threadsafe(
            _post_flyer(client, group, file_id, caption, msg_id),
            MAIN_LOOP,
        )
        fs_log("asyncio.run_coroutine_threadsafe called for _post_flyer")
    except Exception as exc:
        fs_log(f"ERROR in _run_post_flyer: {exc}")


def _reload_jobs(client: Client):
    """
    On startup, reload any jobs stored in Mongo.
    """
    fs_log("Reloading pending flyer jobs from Mongo")
    now = datetime.now(tz=pytz.timezone("America/Los_Angeles"))
    count = 0

    for doc in jobs_coll.find():
        job_time = doc.get("run_at")
        if not job_time:
            continue

        # If the time is in the past, drop it
        if job_time < now:
            jobs_coll.delete_one({"_id": doc["_id"]})
            continue

        msg_id = doc["msg_id"]
        group = doc["group"]
        file_id = doc["file_id"]
        caption = doc.get("caption") or ""

        job = scheduler.add_job(
            func=_run_post_flyer,
            trigger="date",
            run_date=job_time,
            args=[client, group, file_id, caption, msg_id],
            id=msg_id,
            replace_existing=True,
        )
        SCHEDULED_FLYERS[msg_id] = job
        count += 1

    fs_log(f"Reloading {count} pending flyer jobs from Mongo")


# ────────────── Commands ──────────────


async def scheduleflyer_handler(client: Client, m: Message):
    """
    /scheduleflyer <YYYY-MM-DD HH:MM> <group> <flyer_name>

    Example:
    /scheduleflyer 2025-12-24 18:30 SUCCUBUS_SANCTUARY monday
    """
    if not m.from_user or m.from_user.id != OWNER_ID:
        await m.reply_text("Only Roni can schedule flyers 💋")
        return

    parts = (m.text or "").split(maxsplit=4)
    if len(parts) < 5:
        await m.reply_text(
            "Usage:\n"
            "<code>/scheduleflyer &lt;YYYY-MM-DD HH:MM&gt; &lt;group&gt; &lt;flyer_name&gt;</code>\n\n"
            "Example:\n"
            "<code>/scheduleflyer 2025-12-24 18:30 SUCCUBUS_SANCTUARY monday</code>"
        )
        return

    date_part = parts[1]
    time_part = parts[2]
    group_raw = parts[3]
    flyer_name = parts[4].strip().lower()

    group = resolve_group_name(group_raw)
    time_str = f"{date_part} {time_part}"

    # Look up flyer by name
    flyer_doc = flyers_coll.find_one({"name": flyer_name})
    if not flyer_doc:
        await m.reply_text(
            f"❌ I couldn't find a flyer named <code>{flyer_name}</code>.\n"
            "Use <code>/flyerlist</code> to see all saved flyers."
        )
        return

    file_id = flyer_doc.get("file_id")
    caption = flyer_doc.get("caption") or ""

    if not file_id:
        await m.reply_text("That flyer is missing its image. Try recreating it with /addflyer.")
        return

    try:
        local_tz = pytz.timezone("America/Los_Angeles")
        run_at = local_tz.localize(datetime.strptime(time_str, "%Y-%m-%d %H:%M"))
    except Exception as e:
        await m.reply_text(f"❌ Invalid time: <code>{e}</code>")
        return

    msg_id = f"{group}|{flyer_name}|{int(run_at.timestamp())}"

    # Create job in scheduler
    job = scheduler.add_job(
        func=_run_post_flyer,
        trigger="date",
        run_date=run_at,
        args=[client, group, file_id, caption, msg_id],
        id=msg_id,
        replace_existing=True,
    )
    SCHEDULED_FLYERS[msg_id] = job

    # Persist job in Mongo
    jobs_coll.update_one(
        {"msg_id": msg_id},
        {
            "$set": {
                "msg_id": msg_id,
                "group": group,
                "flyer_name": flyer_name,
                "file_id": file_id,
                "caption": caption,
                "run_at": run_at,
                "created_by": m.from_user.id,
            }
        },
        upsert=True,
    )

    await m.reply_text(
        "✅ Flyer scheduled.\n\n"
        f"• Flyer: <code>{flyer_name}</code>\n"
        f"• Group: <code>{group}</code>\n"
        f"• Time: <code>{run_at.strftime('%Y-%m-%d %H:%M %Z')}</code>\n"
        f"• ID: <code>{msg_id}</code>"
    )
    fs_log(f"Flyer scheduled: {msg_id}")


async def cancelflyer_handler(client: Client, m: Message):
    """
    /cancelflyer <msg_id>
    """
    if not m.from_user or m.from_user.id != OWNER_ID:
        await m.reply_text("Only Roni can cancel scheduled flyers 💋")
        return

    parts = (m.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await m.reply_text("Usage: <code>/cancelflyer &lt;msg_id&gt;</code>")
        return

    msg_id = parts[1].strip()

    job = SCHEDULED_FLYERS.get(msg_id)
    if job:
        try:
            job.remove()
        except Exception:
            pass
        SCHEDULED_FLYERS.pop(msg_id, None)

    jobs_coll.delete_one({"msg_id": msg_id})
    await m.reply_text(f"✅ Scheduled flyer <code>{msg_id}</code> canceled.")
    fs_log(f"Canceled scheduled flyer: {msg_id}")


async def listflyersched_handler(client: Client, m: Message):
    """
    /listflyersched – owner only
    """
    if not m.from_user or m.from_user.id != OWNER_ID:
        await m.reply_text("Only Roni can view scheduled flyers 💋")
        return

    docs = list(jobs_coll.find().sort("run_at", 1))
    if not docs:
        await m.reply_text("No scheduled flyers.")
        return

    lines = ["📅 <b>Scheduled flyers:</b>"]
    for d in docs:
        msg_id = d["msg_id"]
        group = d["group"]
        flyer_name = d["flyer_name"]
        run_at = d["run_at"]
        run_str = run_at.strftime("%Y-%m-%d %H:%M %Z") if hasattr(run_at, "strftime") else str(run_at)
        lines.append(
            f"• <code>{flyer_name}</code> → <code>{group}</code> at <i>{run_str}</i>\n"
            f"  ID: <code>{msg_id}</code>"
        )

    await m.reply_text("\n".join(lines))


# ────────────── Register ──────────────


def register(app: Client):
    fs_log("Registering flyer_scheduler handlers")

    app.add_handler(
        MessageHandler(
            scheduleflyer_handler,
            filters.command("scheduleflyer", prefixes=["/", "!"]),
        ),
        group=0,
    )
    app.add_handler(
        MessageHandler(
            cancelflyer_handler,
            filters.command("cancelflyer", prefixes=["/", "!"]),
        ),
        group=0,
    )
    app.add_handler(
        MessageHandler(
            listflyersched_handler,
            filters.command("listflyersched", prefixes=["/", "!"]),
        ),
        group=0,
    )

    if not scheduler.running:
        scheduler.start()
        fs_log("Scheduler started")

    # Reload jobs from Mongo
    _reload_jobs(app)
