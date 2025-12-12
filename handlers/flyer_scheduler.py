# handlers/flyer_scheduler.py
import asyncio
import os
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient, ASCENDING
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611") or "6964994611"))

# ────────────── Logging helper ──────────────

def log_debug(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[FLYERSCHED][{ts}] {msg}", flush=True)


# ────────────── Timezone & scheduler ──────────────

LA_TZ = pytz.timezone("America/Los_Angeles")
scheduler = BackgroundScheduler(timezone=LA_TZ)
MAIN_LOOP = None  # set by main.py
JOBS = {}  # job_id -> job


def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop
    log_debug("MAIN_LOOP set by set_main_loop()")


# ────────────── Mongo ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI must be set for flyer_scheduler")

mongo = MongoClient(MONGO_URI)
db = mongo["Succubot"]
flyers_coll = db["flyers"]
scheduled_coll = db["scheduled_flyers"]
scheduled_coll.create_index([("run_at", ASCENDING)])
scheduled_coll.create_index([("status", ASCENDING)])


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def resolve_group_name(group: str) -> str:
    """
    Same behavior as schedulemsg: allow env shortcuts
    like SUCCUBUS_SANCTUARY, MODELS_CHAT, etc.
    """
    group = group.strip()
    if group.startswith("-") or group.startswith("@"):
        return group
    val = os.environ.get(group)
    if val:
        return val.split(",")[0].strip()
    return group


# ────────────── Core posting helpers ──────────────

async def post_flyer(client: Client, target: str, flyer_name: str, job_id: str):
    log_debug(f"post_flyer CALLED for {target} flyer={flyer_name} job_id={job_id}")
    norm = _normalize_name(flyer_name)
    doc = flyers_coll.find_one({"name": norm})
    if not doc:
        log_debug(f"post_flyer: flyer {flyer_name} not found in DB")
        scheduled_coll.update_one(
            {"_id": job_id}, {"$set": {"status": "error", "error": "flyer not found"}}
        )
        JOBS.pop(job_id, None)
        return

    try:
        await client.send_photo(
            target,
            doc["file_id"],
            caption=doc.get("caption") or "",
        )
        log_debug(f"Flyer {flyer_name} posted to {target} (job_id={job_id})")
        scheduled_coll.update_one(
            {"_id": job_id},
            {"$set": {"status": "sent", "sent_at": datetime.now(LA_TZ)}},
        )
    except Exception as e:
        log_debug(f"Failed to post scheduled flyer ({job_id}): {e}")
        scheduled_coll.update_one(
            {"_id": job_id},
            {"$set": {"status": "error", "error": str(e)}},
        )

    JOBS.pop(job_id, None)


def run_post_flyer(client: Client, target: str, flyer_name: str, job_id: str):
    log_debug(f"run_post_flyer CALLED for {target} flyer={flyer_name} job_id={job_id}")
    global MAIN_LOOP
    if MAIN_LOOP is None:
        log_debug("ERROR: MAIN_LOOP is not set!")
        return
    try:
        asyncio.run_coroutine_threadsafe(
            post_flyer(client, target, flyer_name, job_id), MAIN_LOOP
        )
        log_debug("asyncio.run_coroutine_threadsafe called for post_flyer")
    except Exception as exc:
        log_debug(f"ERROR in run_post_flyer: {exc}")


def _schedule_db_doc(client: Client, doc: dict):
    """
    Given a scheduled_flyers doc, actually schedule it in APScheduler.
    """
    job_id = str(doc["_id"])
    target = doc["target_resolved"] or doc["target"]
    run_at = doc["run_at"]
    job = scheduler.add_job(
        func=run_post_flyer,
        trigger="date",
        run_date=run_at,
        args=[client, target, doc["flyer_name"], job_id],
        id=job_id,
        replace_existing=True,
    )
    JOBS[job_id] = job
    log_debug(f"Scheduled job {job_id} for {run_at} to {target} flyer={doc['flyer_name']}")


def _reload_pending_jobs(client: Client):
    now = datetime.now(LA_TZ)
    pending = list(
        scheduled_coll.find(
            {"status": "pending", "run_at": {"$gte": now}}
        ).sort("run_at", ASCENDING)
    )
    log_debug(f"Reloading {len(pending)} pending flyer jobs from Mongo")
    for doc in pending:
        _schedule_db_doc(client, doc)


# ────────────── Command handlers ──────────────

async def scheduleflyer_handler(client: Client, message: Message):
    """
    /scheduleflyer <YYYY-MM-DD HH:MM> <group> <flyer_name>
    """
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.reply_text("Only the owner can schedule flyers.")
        return

    parts = (message.text or "").split(maxsplit=4)
    # /scheduleflyer date time group name
    if len(parts) < 5:
        await message.reply_text(
            "Usage:\n"
            "<code>/scheduleflyer YYYY-MM-DD HH:MM &lt;group&gt; &lt;flyer_name&gt;</code>\n\n"
            "Example:\n"
            "<code>/scheduleflyer 2025-12-25 18:30 SUCCUBUS_SANCTUARY merry_monday</code>"
        )
        return

    _, date_part, time_part, group_raw, flyer_name = parts
    time_str = f"{date_part} {time_part}"
    group = resolve_group_name(group_raw)
    flyer_name = flyer_name.strip()
    norm = _normalize_name(flyer_name)

    flyer_doc = flyers_coll.find_one({"name": norm})
    if not flyer_doc:
        await message.reply_text(
            f"❌ I couldn't find a flyer named <b>{flyer_name}</b>.\n"
            "Save it first with <code>/addflyer</code>."
        )
        return

    try:
        run_at_local = LA_TZ.localize(datetime.strptime(time_str, "%Y-%m-%d %H:%M"))
    except Exception as e:
        await message.reply_text(f"❌ Invalid time: {e}")
        return

    # store in Mongo so it survives restarts
    doc = {
        "_id": f"{group}|{norm}|{int(run_at_local.timestamp())}",
        "flyer_name": norm,
        "target": group_raw,
        "target_resolved": group,
        "run_at": run_at_local,
        "status": "pending",
        "created_by": message.from_user.id,
        "created_at": datetime.now(LA_TZ),
    }
    scheduled_coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    _schedule_db_doc(client, doc)

    await message.reply_text(
        "✅ Flyer scheduled.\n"
        f"• Flyer: <code>{flyer_name}</code>\n"
        f"• When: <b>{run_at_local.strftime('%Y-%m-%d %H:%M %Z')}</b>\n"
        f"• Where: <code>{group}</code>\n"
        f"• ID: <code>{doc['_id']}</code>\n\n"
        "Use <code>/cancelflyer "
        f"{doc['_id']}</code> to cancel."
    )


async def cancelflyer_handler(_: Client, message: Message):
    """
    /cancelflyer <id>
    """
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.reply_text("Only the owner can cancel scheduled flyers.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage:\n<code>/cancelflyer &lt;id&gt;</code>")
        return

    job_id = parts[1].strip()
    doc = scheduled_coll.find_one({"_id": job_id})
    if not doc:
        await message.reply_text("❌ No scheduled flyer with that ID.")
        return

    # cancel in scheduler
    job = JOBS.pop(job_id, None)
    if job:
        try:
            job.remove()
        except Exception:
            pass

    scheduled_coll.update_one(
        {"_id": job_id},
        {"$set": {"status": "canceled", "canceled_at": datetime.now(LA_TZ)}},
    )

    await message.reply_text(f"✅ Canceled scheduled flyer <code>{job_id}</code>.")


async def listscheduled_handler(_: Client, message: Message):
    """
    /listflyerposts → show upcoming scheduled flyer posts
    """
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.reply_text("Only the owner can list scheduled flyers.")
        return

    now = datetime.now(LA_TZ)
    docs = list(
        scheduled_coll.find(
            {"status": "pending", "run_at": {"$gte": now}}
        ).sort("run_at", ASCENDING)
    )
    if not docs:
        await message.reply_text("No scheduled flyer posts.")
        return

    lines = ["📅 <b>Scheduled flyer posts:</b>"]
    for d in docs:
        run_at = d["run_at"].strftime("%Y-%m-%d %H:%M %Z")
        lines.append(
            f"• <code>{d['_id']}</code>\n"
            f"  Flyer: <code>{d['flyer_name']}</code>\n"
            f"  When: <b>{run_at}</b>\n"
            f"  Where: <code>{d['target_resolved']}</code>"
        )

    await message.reply_text("\n".join(lines))


# ────────────── Register ──────────────

def register(app: Client):
    log_debug("Registering flyer_scheduler handlers")

    app.add_handler(MessageHandler(scheduleflyer_handler, filters.command("scheduleflyer")), group=0)
    app.add_handler(MessageHandler(cancelflyer_handler, filters.command("cancelflyer")), group=0)
    app.add_handler(MessageHandler(listscheduled_handler, filters.command("listflyerposts")), group=0)

    if not scheduler.running:
        scheduler.start()
        log_debug("Scheduler started")

    # After we start the scheduler, reload jobs from Mongo
    _reload_pending_jobs(app)
