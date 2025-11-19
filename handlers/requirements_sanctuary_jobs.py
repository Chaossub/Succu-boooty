# handlers/requirements_sanctuary_jobs.py
#
# Succubus Sanctuary - JOBS SIDE
#
# - Uses Mongo data created by requirements_sanctuary_admin
# - Sends randomized DM reminders:
#     • Mid-month (15th @ 11:00 LA)
#     • 3 days before month end (daily @ 11:15, no-ops unless last_day-3)
# - Runs a monthly sweep on the 1st @ 7:00 LA:
#     • Kicks non-exempt users who didn't meet requirements
#     • Kicks even if NOT dm_ready
#     • DMs removal notice to dm_ready users
# - Sends Stripe revenue summary for previous month
# - Commands:
#     /reqtest       → DM-ready test ("this is a test" message)
#     /reqscan_mid   → manual mid-month reminder scan
#     /reqscan_final → manual final-warning scan
#
# To enable it, in main.py:
#     _try_register("requirements_sanctuary_jobs")
#

from __future__ import annotations

import os
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Iterable

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient, ASCENDING
from pyrogram import Client, filters
from pyrogram.types import Message, User

from utils.admin_check import require_admin
from utils.dmready_store import global_store as dmready_store
from utils.groups import GROUP_SHORTCUTS

log = logging.getLogger("requirements_sanctuary_jobs")

# ────────────── ENV / CONSTANTS ──────────────

LA_TZ = pytz.timezone("America/Los_Angeles")

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"

if not MONGO_URI:
    raise RuntimeError("[requirements_sanctuary_jobs] Please set MONGO_URI or MONGODB_URI")

mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]

payments_col = db.get_collection("sanctuary_payments")
monthly_col = db.get_collection("sanctuary_monthly_stats")
exempt_col = db.get_collection("sanctuary_exempt")

# Indexes (safe to call repeatedly)
payments_col.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
payments_col.create_index([("source", ASCENDING), ("created_at", ASCENDING)])
monthly_col.create_index(
    [("user_id", ASCENDING), ("group_id", ASCENDING), ("month", ASCENDING)],
    unique=True,
)
exempt_col.create_index([("user_id", ASCENDING), ("group_id", ASCENDING)], unique=True)

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

# Sanctuary group ID (requirements apply here)
_SANCTU_RAW = GROUP_SHORTCUTS.get("SUCCUBUS_SANCTUARY")
SANCTU_GROUP_ID: Optional[int]
try:
    SANCTU_GROUP_ID = int(_SANCTU_RAW) if _SANCTU_RAW else None
except Exception:
    SANCTU_GROUP_ID = None

if not SANCTU_GROUP_ID:
    log.warning(
        "[requirements_sanctuary_jobs] SUCCUBUS_SANCTUARY env is not set; "
        "jobs will be effectively disabled."
    )

# Optional log group for reports
_LOG_RAW = GROUP_SHORTCUTS.get("SANCTU_LOGS") or os.getenv("SANCTU_LOG_GROUP_ID")
LOG_GROUP_ID: Optional[int]
try:
    LOG_GROUP_ID = int(_LOG_RAW) if _LOG_RAW else None
except Exception:
    LOG_GROUP_ID = None

if not LOG_GROUP_ID:
    log.info(
        "[requirements_sanctuary_jobs] No log group configured; "
        "owner-only DMs will be used for reports."
    )

# Requirements: $20 and 2 models (game counts as both)
REQUIRED_CENTS = int(os.getenv("REQ2_REQUIRED_CENTS", "2000"))  # default $20
REQUIRED_MODELS = int(os.getenv("REQ2_REQUIRED_MODELS", "2"))   # default 2 models

# Scheduler
scheduler = BackgroundScheduler(timezone=LA_TZ)

# ────────────── MESSAGE POOLS (RANDOMIZED) ──────────────

MID_MONTH_MESSAGES = [
    (
        "Hey love 💋 Just a little mid-month check-in...\n\n"
        "Right now you’ve spent <b>${spent:.2f}</b> with <b>{models} model(s)</b> this month.\n"
        "To keep access to Succubus Sanctuary next month, you’ll need:\n"
        "• <b>${required_total:.2f}</b> total\n"
        "• Support from <b>{required_models} different models</b>\n"
        "(Games count for both 😉)"
    ),
    (
        "Hi babe 👀 Your succubus system is doing a quick vibe check.\n\n"
        "You’re currently at <b>${spent:.2f}</b> and <b>{models} model(s)</b> for this month.\n"
        "Requirement to stay in the Sanctuary:\n"
        "• <b>${required_total:.2f}</b> total\n"
        "• <b>{required_models} models</b> (games count for both!)\n\n"
        "Plenty of time to spoil us a little more 💕"
    ),
    (
        "Mid-month reminder from the Sanctuary 😈\n\n"
        "You’ve got <b>${spent:.2f}</b> logged and <b>{models} model(s)</b> supported.\n"
        "To keep access you’ll need at least <b>${required_total:.2f}</b> and "
        "<b>{required_models} different models</b>.\n"
        "Games count for both, so they’re an easy way to hit that mark 🔥"
    ),
    (
        "Hey sweetheart ✨\n\n"
        "You’re not quite at the monthly support level yet.\n"
        "Current: <b>${spent:.2f}</b> across <b>{models} model(s)</b>.\n"
        "Needed to stay in Sanctuary next month:\n"
        "• <b>${required_total:.2f}</b> total\n"
        "• <b>{required_models} models</b> (games count as both)\n\n"
        "Just a soft reminder, not a scolding 💗"
    ),
]

FINAL_WARN_MESSAGES = [
    (
        "🔥 Last call, babe 🔥\n\n"
        "There are only <b>3 days</b> left in this month.\n"
        "You’re currently at <b>${spent:.2f}</b> with <b>{models} model(s)</b>.\n\n"
        "To stay in Succubus Sanctuary next month you still need:\n"
        "• At least <b>${required_total:.2f}</b> this month\n"
        "• Support from <b>{required_models} different models</b>\n"
        "(Remember: games count for both 😈)"
    ),
    (
        "Hey love, gentle but serious reminder 🖤\n\n"
        "We’re <b>3 days</b> from the end of the month and you haven’t met requirements yet.\n"
        "Current: <b>${spent:.2f}</b>, <b>{models} model(s)</b>.\n\n"
        "Needed:\n"
        "• <b>${required_total:.2f}</b> total\n"
        "• <b>{required_models} models</b>\n\n"
        "I don’t want the bot to kick you out on the 1st, so don’t forget us 😘"
    ),
    (
        "🕒 Countdown time, pretty thing.\n\n"
        "In 3 days the month resets and the bot will remove anyone who hasn’t:\n"
        "• Spent <b>${required_total:.2f}</b> this month\n"
        "• Supported <b>{required_models}</b> different models (games count for both)\n\n"
        "You’re at <b>${spent:.2f}</b> and <b>{models} model(s)</b>.\n"
        "If you want to stay in Sanctuary, now’s the time to show some love 💕"
    ),
]

KICK_MESSAGES = [
    (
        "Hey love… 💔\n\n"
        "You didn’t meet this month’s support requirements for Succubus Sanctuary, "
        "so the bot automatically removed your access.\n\n"
        "You’re always welcome to come back in the future when you’re ready to support again 💕"
    ),
    (
        "Hi sweetheart — just letting you know the system removed you from Succubus Sanctuary "
        "because this month’s requirements weren’t met.\n\n"
        "If and when you’re ready, you’re absolutely welcome to rejoin and play with us again 🖤"
    ),
    (
        "Your access to Succubus Sanctuary has expired for this month due to not meeting the "
        "support requirements.\n\n"
        "No hard feelings — you can always come back when it makes sense for you ❤️"
    ),
]

# ────────────── HELPERS ──────────────

def _now_la() -> datetime:
    return datetime.now(tz=LA_TZ)

def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")

def _prev_month_key(dt: datetime) -> str:
    year = dt.year
    month = dt.month
    if month == 1:
        year -= 1
        month = 12
    else:
        month -= 1
    return f"{year:04d}-{month:02d}"

def _last_day_of_month(dt: datetime) -> int:
    year = dt.year
    month = dt.month
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=dt.tzinfo)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=dt.tzinfo)
    last = (next_month - timedelta(days=1)).day
    return last

def _is_dm_ready(user_id: int) -> bool:
    try:
        return dmready_store.get(user_id) is not None
    except Exception as e:
        log.error("DMReadyStore.get failed for %s: %s", user_id, e)
        return False

def _is_exempt(user_id: int, group_id: int) -> bool:
    doc = exempt_col.find_one({"user_id": user_id, "group_id": group_id})
    return bool(doc)

def _format_random(pool: List[str], **kwargs) -> str:
    tmpl = random.choice(pool)
    return tmpl.format(**kwargs)

def _get_monthly_stats(user_id: int, group_id: int, month_key: str) -> Dict[str, Any]:
    doc = monthly_col.find_one(
        {"user_id": user_id, "group_id": group_id, "month": month_key}
    ) or {}
    total_cents = int(doc.get("total_cents") or 0)
    models = doc.get("models_supported") or []
    uniq_models = sorted(set(models))
    return {
        "total_cents": total_cents,
        "models": uniq_models,
    }

def _meets_requirements(total_cents: int, models: Iterable[str]) -> bool:
    cents_ok = total_cents >= REQUIRED_CENTS
    model_count = len(set(m.lower() for m in models))
    models_ok = model_count >= REQUIRED_MODELS
    return cents_ok and models_ok

async def _send_log_message(
    client: Client,
    text: str,
    *,
    parse_mode: str = "html",
    disable_web_page_preview: bool = True,
) -> None:
    """
    Sends a log-style message to:
    - OWNER_ID (if set)
    - LOG_GROUP_ID (if set)
    """
    targets = []
    if OWNER_ID:
        targets.append(OWNER_ID)
    if LOG_GROUP_ID:
        targets.append(LOG_GROUP_ID)

    for cid in targets:
        try:
            await client.send_message(
                cid,
                text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
        except Exception as e:
            log.warning("Failed to send log message to %s: %s", cid, e)

# ────────────── TEST DM-READY SCAN ──────────────

async def _send_dmready_test(client: Client) -> None:
    """
    Sends a simple test DM to everyone who is:
    - In Succubus Sanctuary
    - Marked dm_ready
    (Exempt or not doesn’t matter here, this is just a DM test.)
    Also logs a summary to owner/log group.
    """
    if not SANCTU_GROUP_ID:
        log.warning("DM-ready test: SANCTU_GROUP_ID not set; skipping.")
        return

    now = _now_la()
    mkey = _month_key(now)

    log.info("[requirements_sanctuary_jobs] Running DM-ready test scan for %s", mkey)

    checked = 0
    sent = 0
    skipped_not_dmready = 0
    skipped_bots = 0

    async for member in client.get_chat_members(SANCTU_GROUP_ID):
        user: User = member.user
        if not user:
            continue
        if user.is_bot:
            skipped_bots += 1
            continue

        uid = user.id
        checked += 1

        if not _is_dm_ready(uid):
            skipped_not_dmready += 1
            continue

        text = (
            "This is a test message from SuccuBot to confirm I can DM you about "
            "Succubus Sanctuary requirements and updates. 💕\n\n"
            "No action needed — if you received this, everything is working."
        )
        try:
            await client.send_message(uid, text, disable_web_page_preview=True)
            sent += 1
        except Exception as e:
            log.warning("Failed to DM test message to %s: %s", uid, e)

    summary = [
        "🧪 <b>Sanctuary DM-ready test run</b>",
        f"Month: <code>{mkey}</code>",
        f"Checked members: <b>{checked}</b>",
        f"Test DMs sent: <b>{sent}</b>",
        f"Bots (skipped): <b>{skipped_bots}</b>",
        f"Not dm_ready (skipped): <b>{skipped_not_dmready}</b>",
    ]
    await _send_log_message(client, "\n".join(summary))

# ────────────── REMINDER & SWEEP JOBS ──────────────

async def _send_midmonth_reminders(client: Client) -> None:
    """
    Sends mid-month style reminders to:
    - Members of Sanctuary
    - Who are dm_ready
    - Not exempt
    - Have NOT met requirements
    Also logs a summary to owner/log group.
    """
    if not SANCTU_GROUP_ID:
        log.warning("Mid-month: SANCTU_GROUP_ID not set; skipping.")
        return

    now = _now_la()
    mkey = _month_key(now)

    log.info("[requirements_sanctuary_jobs] Running mid-month reminders for %s", mkey)

    sent = 0
    checked = 0
    skipped_met = 0
    skipped_exempt = 0
    skipped_not_dmready = 0

    async for member in client.get_chat_members(SANCTU_GROUP_ID):
        user: User = member.user
        if not user or user.is_bot:
            continue

        uid = user.id
        checked += 1

        # Only DM if dm_ready AND not exempt
        if not _is_dm_ready(uid):
            skipped_not_dmready += 1
            continue
        if _is_exempt(uid, SANCTU_GROUP_ID):
            skipped_exempt += 1
            continue

        stats = _get_monthly_stats(uid, SANCTU_GROUP_ID, mkey)
        cents = stats["total_cents"]
        models = stats["models"]

        # If they already meet requirements, skip
        if _meets_requirements(cents, models):
            skipped_met += 1
            continue

        spent = cents / 100.0
        text = _format_random(
            MID_MONTH_MESSAGES,
            spent=spent,
            models=len(models),
            required_total=REQUIRED_CENTS / 100.0,
            required_models=REQUIRED_MODELS,
        )
        try:
            await client.send_message(uid, text, disable_web_page_preview=True)
            sent += 1
        except Exception as e:
            log.warning("Failed to DM mid-month reminder to %s: %s", uid, e)

    summary = [
        "📬 <b>Sanctuary mid-month reminder run</b>",
        f"Month: <code>{mkey}</code>",
        f"Checked members: <b>{checked}</b>",
        f"Reminders sent: <b>{sent}</b>",
        f"Met requirement (skipped): <b>{skipped_met}</b>",
        f"Exempt (skipped): <b>{skipped_exempt}</b>",
        f"Not dm_ready (skipped): <b>{skipped_not_dmready}</b>",
    ]
    await _send_log_message(client, "\n".join(summary))

async def _send_final_reminders(client: Client, force: bool = False) -> None:
    """
    Sends 3-days-left style reminders.
    - Normal mode: only runs if today is last_day-3.
    - force=True: ignore date and run anyway (used by /reqscan_final).
    """
    if not SANCTU_GROUP_ID:
        log.warning("Final-reminder: SANCTU_GROUP_ID not set; skipping.")
        return

    now = _now_la()
    last_day = _last_day_of_month(now)
    if not force and now.day != last_day - 3:
        # Not the right day; scheduled job will call daily and this no-ops.
        return

    mkey = _month_key(now)
    log.info("[requirements_sanctuary_jobs] Running 3-days-left reminders for %s (force=%s)", mkey, force)

    sent = 0
    checked = 0
    skipped_met = 0
    skipped_exempt = 0
    skipped_not_dmready = 0

    async for member in client.get_chat_members(SANCTU_GROUP_ID):
        user: User = member.user
        if not user or user.is_bot:
            continue
        uid = user.id
        checked += 1

        if not _is_dm_ready(uid):
            skipped_not_dmready += 1
            continue
        if _is_exempt(uid, SANCTU_GROUP_ID):
            skipped_exempt += 1
            continue

        stats = _get_monthly_stats(uid, SANCTU_GROUP_ID, mkey)
        cents = stats["total_cents"]
        models = stats["models"]

        if _meets_requirements(cents, models):
            skipped_met += 1
            continue

        spent = cents / 100.0
        text = _format_random(
            FINAL_WARN_MESSAGES,
            spent=spent,
            models=len(models),
            required_total=REQUIRED_CENTS / 100.0,
            required_models=REQUIRED_MODELS,
        )
        try:
            await client.send_message(uid, text, disable_web_page_preview=True)
            sent += 1
        except Exception as e:
            log.warning("Failed to DM final reminder to %s: %s", uid, e)

    summary = [
        "⚠️ <b>Sanctuary 3-days-left reminder run</b>",
        f"Month: <code>{mkey}</code>",
        f"Force run: <b>{'YES' if force else 'NO'}</b>",
        f"Checked members: <b>{checked}</b>",
        f"Reminders sent: <b>{sent}</b>",
        f"Met requirement (skipped): <b>{skipped_met}</b>",
        f"Exempt (skipped): <b>{skipped_exempt}</b>",
        f"Not dm_ready (skipped): <b>{skipped_not_dmready}</b>",
    ]
    await _send_log_message(client, "\n".join(summary))

async def _run_monthly_sweep_and_report(client: Client) -> None:
    """
    On the 1st (7:00am LA time), checks previous month:
    - Kicks non-exempt members who did not meet requirements
    - Sends removal DMs to dm_ready users
    - Sends Stripe summary + sweep summary to owner/log group
    """
    if not SANCTU_GROUP_ID:
        log.warning("Monthly sweep: SANCTU_GROUP_ID not set; skipping.")
        return

    now = _now_la()
    prev_key = _prev_month_key(now)

    log.info("[requirements_sanctuary_jobs] Running monthly sweep for %s", prev_key)

    kicked: List[int] = []
    failed: List[int] = []

    async for member in client.get_chat_members(SANCTU_GROUP_ID):
        user: User = member.user
        if not user or user.is_bot:
            continue
        uid = user.id

        if _is_exempt(uid, SANCTU_GROUP_ID):
            continue

        stats = _get_monthly_stats(uid, SANCTU_GROUP_ID, prev_key)
        cents = stats["total_cents"]
        models = stats["models"]

        if _meets_requirements(cents, models):
            continue

        # Kick from Sanctuary (even if not dm_ready)
        try:
            await client.ban_chat_member(SANCTU_GROUP_ID, uid)
            await client.unban_chat_member(SANCTU_GROUP_ID, uid)
            kicked.append(uid)
            # DM removal notice if dm_ready
            if _is_dm_ready(uid):
                text = random.choice(KICK_MESSAGES)
                try:
                    await client.send_message(
                        uid, text, disable_web_page_preview=True
                    )
                except Exception as e:
                    log.warning("Failed to DM removal notice to %s: %s", uid, e)
        except Exception as e:
            log.warning("Failed to kick %s from Sanctuary: %s", uid, e)
            failed.append(uid)

    # Stripe summary for previous month
    await _send_owner_stripe_summary(client, prev_key)

    # Sweep summary → owner + optional log group
    lines = [
        f"📅 <b>Sanctuary monthly sweep report</b>",
        f"Month evaluated: <code>{prev_key}</code>",
        f"Kicked: <b>{len(kicked)}</b>",
        f"Failed kicks: <b>{len(failed)}</b>",
    ]
    if kicked:
        lines.append("Kicked user IDs: " + ", ".join(str(x) for x in kicked))
    if failed:
        lines.append("Failed user IDs: " + ", ".join(str(x) for x in failed))

    await _send_log_message(client, "\n".join(lines))

async def _send_owner_stripe_summary(client: Client, month_key: str) -> None:
    """
    Build and log a Stripe-only summary for the given month_key (YYYY-MM).
    """
    if not OWNER_ID and not LOG_GROUP_ID:
        return

    # Filter only Stripe payments in that month
    docs = list(payments_col.find({"month": month_key, "source": "stripe"}))
    if not docs:
        await _send_log_message(
            client,
            f"📊 Stripe summary for <code>{month_key}</code>:\nNo Stripe payments logged.",
        )
        return

    total_cents = sum(int(d.get("amount_cents") or 0) for d in docs)
    total_payments = len(docs)

    # By model (if game counted as multiple models)
    per_model: Dict[str, int] = {}
    for d in docs:
        models = d.get("models") or []
        cents = int(d.get("amount_cents") or 0)
        if not models:
            per_model["_unknown"] = per_model.get("_unknown", 0) + cents
        else:
            for m in set(models):
                key = m.lower()
                per_model[key] = per_model.get(key, 0) + cents

    lines = [
        f"📊 <b>Stripe summary for {month_key}</b>",
        f"Total Stripe revenue: <b>${total_cents/100:.2f}</b>",
        f"Number of payments: <b>{total_payments}</b>",
        "",
        "<b>By model:</b>",
    ]
    for m, cents in sorted(per_model.items(), key=lambda kv: kv[0]):
        label = "Unknown/other" if m == "_unknown" else m
        lines.append(f"• {label}: <b>${cents/100:.2f}</b>")

    await _send_log_message(client, "\n".join(lines))

# ────────────── REGISTER ENTRYPOINT ──────────────

def register(app: Client):
    log.info(
        "✅ handlers.requirements_sanctuary_jobs registered (OWNER_ID=%s, SANCTU_GROUP_ID=%s, LOG_GROUP_ID=%s)",
        OWNER_ID,
        SANCTU_GROUP_ID,
        LOG_GROUP_ID,
    )

    @app.on_message(filters.command("reqscan_mid"))
    @require_admin
    async def reqscan_mid_handler(client: Client, message: Message):
        """
        Manually run mid-month style reminder scan NOW.
        Sends real reminders + logs summary to log group.
        """
        await _send_midmonth_reminders(client)
        await message.reply_text("✅ Ran mid-month requirement scan.")

    @app.on_message(filters.command("reqscan_final"))
    @require_admin
    async def reqscan_final_handler(client: Client, message: Message):
        """
        Manually run 3-days-left style reminder scan NOW (force=True).
        Sends real reminders + logs summary to log group.
        """
        await _send_final_reminders(client, force=True)
        await message.reply_text("✅ Ran final-warning requirement scan (forced).")

    @app.on_message(filters.command("reqtest"))
    @require_admin
    async def reqtest_handler(client: Client, message: Message):
        """
        Manually run a DM-ready test:
        - Sends a simple test message to everyone who is dm_ready in Sanctuary
        - Logs a summary to the log group
        """
        await _send_dmready_test(client)
        await message.reply_text("✅ Ran DM-ready test scan for Sanctuary.")

    # ---- Scheduler setup (background jobs) ----
    try:
        scheduler.start()
    except Exception as e:
        log.warning("requirements_sanctuary_jobs scheduler.start() raised: %s", e)

    import asyncio

    def _run_coro(coro):
        try:
            asyncio.run_coroutine_threadsafe(coro, app.loop)
        except Exception as e:
            log.warning("Error scheduling coroutine: %s", e)

    # Mid-month reminders: 15th at 11:00 LA time
    scheduler.add_job(
        lambda: _run_coro(_send_midmonth_reminders(app)),
        trigger="cron",
        day=15,
        hour=11,
        minute=0,
    )

    # 3-days-left reminders: job runs daily at 11:15; function no-ops unless it's last_day-3
    scheduler.add_job(
        lambda: _run_coro(_send_final_reminders(app, force=False)),
        trigger="cron",
        hour=11,
        minute=15,
    )

    # Monthly sweep & Stripe summary: 1st at 7:00am LA time for previous month
    scheduler.add_job(
        lambda: _run_coro(_run_monthly_sweep_and_report(app)),
        trigger="cron",
        day=1,
        hour=7,
        minute=0,
    )
