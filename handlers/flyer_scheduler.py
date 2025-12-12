# handlers/flyer_scheduler.py
import logging
import os
import asyncio
from datetime import datetime, timezone
from typing import Optional, Set

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient, ASCENDING
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

log = logging.getLogger(__name__)

# ────────────── GLOBALS ──────────────

scheduler = BackgroundScheduler()
MAIN_LOOP = None  # set by main.py via set_main_loop()
SCHEDULE_COLLECTION_NAME = "flyer_schedules"

# ────────────── MONGO SETUP ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI must be set for flyer_scheduler")

mongo = MongoClient(MONGO_URI)
db_name = os.getenv("MONGO_DBNAME") or "Succubot"
db = mongo[db_name]

flyers_coll = db["flyers"]
schedules_coll = db[SCHEDULE_COLLECTION_NAME]
schedules_coll.create_index([("job_id", ASCENDING)], unique=True)

# ────────────── PERMISSIONS ──────────────

OWNER_ID = int(
    os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611") or "6964994611")
)

_super_admins_env = os.getenv("SUPER_ADMINS", "")
SUPER_ADMINS: Set[int] = set()
for part in _super_admins_env.split(","):
    part = part.strip()
    if not part:
        continue
    try:
        SUPER_ADMINS.add(int(part))
    except ValueError:
        log.warning("flyer_scheduler.py: invalid SUPER_ADMINS entry %r", part)

SUPER_ADMINS.add(OWNER_ID)

LA_TZ = pytz.timezone("America/Los_Angeles")


def log_debug(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[FLYER_SCHED][{ts}] {msg}", flush=True)


async def _is_flyer_admin(client: Client, m: Message) -> bool:
    if not m.from_user:
        return False
    uid = m.from_user.id
    if uid == OWNER_ID or uid in SUPER_ADMINS:
        return True

    try:
        member = await client.get_chat_member(m.chat.id, uid)
        if member.status in ("administrator", "creator"):
            return True
    except Exception:
        pass

    return False


def _resolve_group_name(group: str) -> str:
    """
    Accept:
      • '-100123...' (numeric id as string)
      • '@username'
      • ENV shortcut like SUCCUBUS_SANCTUARY -> '-100123...'
    """
    if group.startswith("-") or group.startswith("@"):
        return group

    val = os.environ.get(group)
    if val:
        return val.split(",")[0].strip()

    return group


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def set_main_loop(loop) -> None:
    global MAIN_LOOP
    MAIN_LOOP = loop
    log_debug("MAIN_LOOP set by set_main_loop()")


# ────────────── POSTING LOGIC ──────────────

async def _post_flyer(client: Client, chat_id: int, flyer_name: str, job_id: str):
    log_debug(f"_post_flyer CALLED job_id={job_id} flyer={flyer_name} chat_id={chat_id}")

    doc = schedules_coll.find_one({"job_id": job_id})
    if not doc:
        log_debug(f"_post_flyer: schedule {job_id} missing in DB, skipping")
        return

    if doc.get("status") != "pending":
        log_debug(f"_post_flyer: schedule {job_id} status={doc.get('status')}, skipping")
        return

    flyer = flyers_coll.find_one({"name": flyer_name})
    if not flyer:
        log_debug(f"_post_flyer: flyer {flyer_name} not found, marking missed")
        schedules_coll.update_one(
            {"job_id": job_id},
            {"$set": {"status": "missed", "updated_at": _now_utc()}},
        )
        return

    file_id = flyer.get("file_id")
    caption = flyer.get("caption") or ""

    try:
        await client.send_photo(chat_id, file_id, caption=caption)
        log_debug(f"_post_flyer: posted flyer {flyer_name} to {chat_id}")
        schedules_coll.update_one(
            {"job_id": job_id},
            {"$set": {"status": "sent", "sent_at": _now_utc(), "updated_at": _now_utc()}},
        )
    except Exception as e:
        log_debug(f"_post_flyer: failed to post flyer {flyer_name} to {chat_id}: {e}")
        schedules_coll.update_one(
            {"job_id": job_id},
            {"$set": {"status": "error", "error": str(e), "updated_at": _now_utc()}},
        )


def _run_post_flyer(client: Client, chat_id: int, flyer_name: str, job_id: str):
    log_debug(f"_run_post_flyer CALLED job_id={job_id} flyer={flyer_name} chat_id={chat_id}")
    global MAIN_LOOP
    if MAIN_LOOP is None:
        log_debug("ERROR: MAIN_LOOP is not set, cannot post flyer")
        return

    try:
        fut = asyncio.run_coroutine_threadsafe(
            _post_flyer(client, chat_id, flyer_name, job_id), MAIN_LOOP
        )
        log_debug(f"_run_post_flyer: coroutine submitted: {fut}")
    except Exception as exc:
        log_debug(f"_run_post_flyer ERROR: {exc}")


# ────────────── COMMANDS ──────────────

async def scheduleflyer_cmd(client: Client, m: Message):
    if not await _is_flyer_admin(client, m):
        await m.reply_text("Only admins and superadmins can schedule flyers.")
        return

    text = (m.text or "").strip()
    parts = text.split(maxsplit=5)
    # /scheduleflyer YYYY-MM-DD HH:MM GROUP FLYER_NAME
    if len(parts) < 5:
        await m.reply_text(
            "Usage:\n"
            "<code>/scheduleflyer &lt;YYYY-MM-DD&gt; &lt;HH:MM&gt; &lt;group&gt; &lt;flyer_name&gt;</code>\n\n"
            "Example:\n"
            "<code>/scheduleflyer 2025-12-15 18:00 SUCCUBUS_SANCTUARY monday</code>"
        )
        return

    date_str = parts[1]
    time_str = parts[2]
    group_raw = parts[3]
    flyer_name = parts[4].strip()

    flyer_name_norm = flyer_name.strip().lower()

    # Resolve group
    group_resolved = _resolve_group_name(group_raw)

    # Convert to datetime in LA, then UTC
    try:
        naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        local_dt = LA_TZ.localize(naive)
        run_at_utc = local_dt.astimezone(timezone.utc)
    except Exception as e:
        await m.reply_text(f"❌ Invalid date/time: <code>{e}</code>")
        return

    if run_at_utc <= _now_utc():
        await m.reply_text("❌ Time must be in the future.")
        return

    # Verify flyer exists
    flyer = flyers_coll.find_one({"name": flyer_name_norm})
    if not flyer:
        await m.reply_text(f"❌ No flyer named <b>{flyer_name_norm}</b>.")
        return

    # chat_id may be numeric string or @username; we store as-is in DB, and let
    # pyrogram resolve it later.
    target_chat = group_resolved

    # Build job_id
    job_id = f"flyer|{flyer_name_norm}|{target_chat}|{int(run_at_utc.timestamp())}"

    # Save in DB
    schedules_coll.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "job_id": job_id,
                "flyer_name": flyer_name_norm,
                "chat": target_chat,
                "run_at": run_at_utc,
                "tz": "America/Los_Angeles",
                "status": "pending",
                "created_by": m.from_user.id if m.from_user else None,
                "created_at": _now_utc(),
                "updated_at": _now_utc(),
            }
        },
        upsert=True,
    )

    # Schedule in APScheduler
    try:
        scheduler.add_job(
            _run_post_flyer,
            "date",
            run_date=run_at_utc,
            args=[client, target_chat, flyer_name_norm, job_id],
            id=job_id,
            replace_existing=True,
        )
        log_debug(f"scheduleflyer_cmd: scheduled {job_id} at {run_at_utc.isoformat()}")
    except Exception as e:
        log_debug(f"scheduleflyer_cmd: failed to add scheduler job {job_id}: {e}")
        await m.reply_text(f"❌ Failed to schedule flyer: <code>{e}</code>")
        return

    # Pretty display in LA time
    display_time = local_dt.strftime("%Y-%m-%d %H:%M %Z")
    await m.reply_text(
        f"✅ Flyer <b>{flyer_name_norm}</b> scheduled for {display_time} in <code>{target_chat}</code>.\n"
        f"ID: <code>{job_id}</code>"
    )


async def listflyersched_cmd(client: Client, m: Message):
    if not await _is_flyer_admin(client, m):
        await m.reply_text("Only admins and superadmins can view flyer schedules.")
        return

    now = _now_utc()
    docs = list(
        schedules_coll.find(
            {"status": "pending", "run_at": {"$gt": now}}
        ).sort("run_at", ASCENDING)
    )

    if not docs:
        await m.reply_text("No scheduled flyers.")
        return

    lines = ["Scheduled flyer posts:"]
    for d in docs:
        flyer_name = d.get("flyer_name")
        chat = d.get("chat")
        run_at_utc = d.get("run_at")
        try:
            run_local = run_at_utc.astimezone(LA_TZ)
            run_str = run_local.strftime("%Y-%m-%d %H:%M %Z")
        except Exception:
            run_str = str(run_at_utc)

        job_id = d.get("job_id")
        lines.append(
            f"• <b>{flyer_name}</b> → <code>{chat}</code> at <i>{run_str}</i> — "
            f"id: <code>{job_id}</code>"
        )

    await m.reply_text("\n".join(lines))


async def cancelflyer_cmd(client: Client, m: Message):
    if not await _is_flyer_admin(client, m):
        await m.reply_text("Only admins and superadmins can cancel flyer schedules.")
        return

    text = (m.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await m.reply_text("Usage: <code>/cancelflyer &lt;job_id&gt;</code>")
        return

    job_id = parts[1].strip()
    doc = schedules_coll.find_one({"job_id": job_id})
    if not doc:
        await m.reply_text("❌ No such scheduled flyer job.")
        return

    schedules_coll.update_one(
        {"job_id": job_id},
        {"$set": {"status": "canceled", "updated_at": _now_utc()}},
    )

    # Remove APScheduler job if present
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    await m.reply_text(f"✅ Canceled scheduled flyer <code>{job_id}</code>.")
    log_debug(f"cancelflyer_cmd: canceled {job_id}")


# ────────────── STARTUP RESTORE ──────────────

def _restore_schedules(app: Client):
    """Restore pending future jobs from Mongo on startup."""
    now = _now_utc()
    docs = list(
        schedules_coll.find(
            {"status": "pending", "run_at": {"$gt": now}}
        ).sort("run_at", ASCENDING)
    )
    if not docs:
        log_debug("No pending flyer schedules to restore.")
        return

    for d in docs:
        job_id = d.get("job_id")
        flyer_name = d.get("flyer_name")
        chat = d.get("chat")
        run_at_utc = d.get("run_at")

        if not job_id or not flyer_name or not chat or not run_at_utc:
            continue

        try:
            scheduler.add_job(
                _run_post_flyer,
                "date",
                run_date=run_at_utc,
                args=[app, chat, flyer_name, job_id],
                id=job_id,
                replace_existing=True,
            )
            log_debug(
                f"Restored flyer schedule job_id={job_id} flyer={flyer_name} chat={chat} "
                f"run_at={run_at_utc.isoformat()}"
            )
        except Exception as e:
            log_debug(f"Failed to restore flyer schedule {job_id}: {e}")


# ────────────── REGISTER ──────────────

def register(app: Client):
    log_debug("Registering flyer_scheduler handlers")

    if not scheduler.running:
        scheduler.start()
        log_debug("Scheduler started")

    # Restore schedules from Mongo
    _restore_schedules(app)

    app.add_handler(
        MessageHandler(scheduleflyer_cmd, filters.command("scheduleflyer")),
        group=0,
    )
    app.add_handler(
        MessageHandler(listflyersched_cmd, filters.command("listflyersched")),
        group=0,
    )
    app.add_handler(
        MessageHandler(cancelflyer_cmd, filters.command("cancelflyer")),
        group=0,
    )

    log.info("✅ handlers.flyer_scheduler registered (/scheduleflyer, /listflyersched, /cancelflyer)")
