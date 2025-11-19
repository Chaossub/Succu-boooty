# handlers/requirements_sanctuary_admin.py
#
# Succubus Sanctuary - ADMIN SIDE
#
# - Tracks payments (manual + Stripe) in MongoDB
# - Updates per-month stats for the Sanctuary group
# - Lets admins:
#     /logpayment <amount> <model|game> <@user|user_id> [note...]
#     /exemptbuyer <@user|user_id> [reason...]
#     /unexemptbuyer <@user|user_id>
#     /reqstatus [@user|user_id]
#
# This file does NOT run any schedulers.
# Jobs / reminders / kicks live in requirements_sanctuary_jobs.py
#
# To enable it, in main.py:
#     _try_register("requirements_sanctuary_admin")
#

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Iterable

import pytz
from pymongo import MongoClient, ASCENDING
from pyrogram import Client, filters
from pyrogram.types import Message, User

from utils.admin_check import require_admin
from utils.groups import GROUP_SHORTCUTS

log = logging.getLogger("requirements_sanctuary_admin")

# ────────────── ENV / CONSTANTS ──────────────

LA_TZ = pytz.timezone("America/Los_Angeles")

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"

if not MONGO_URI:
    raise RuntimeError("[requirements_sanctuary_admin] Please set MONGO_URI or MONGODB_URI")

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

# Sanctuary group ID (requirements apply here)
_SANCTU_RAW = GROUP_SHORTCUTS.get("SUCCUBUS_SANCTUARY")
SANCTU_GROUP_ID: Optional[int]
try:
    SANCTU_GROUP_ID = int(_SANCTU_RAW) if _SANCTU_RAW else None
except Exception:
    SANCTU_GROUP_ID = None

if not SANCTU_GROUP_ID:
    log.warning(
        "[requirements_sanctuary_admin] SUCCUBUS_SANCTUARY env is not set; "
        "requirement stats will not be tied to a specific group."
    )

# Requirements: $20 and 2 models (game counts as both)
REQUIRED_CENTS = int(os.getenv("REQ2_REQUIRED_CENTS", "2000"))  # default $20
REQUIRED_MODELS = int(os.getenv("REQ2_REQUIRED_MODELS", "2"))   # default 2 models

# ────────────── HELPERS ──────────────

def _now_la() -> datetime:
    return datetime.now(tz=LA_TZ)

def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")

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

def _is_exempt(user_id: int, group_id: int) -> bool:
    doc = exempt_col.find_one({"user_id": user_id, "group_id": group_id})
    return bool(doc)

# ────────────── CORE: RECORDING PAYMENTS ──────────────

def record_sanctuary_payment(
    *,
    user_id: int,
    username: str | None,
    models: List[str],
    amount_cents: int,
    source: str,
    is_game: bool = False,
    note: str | None = None,
    created_at: Optional[datetime] = None,
    group_id: Optional[int] = None,
) -> None:
    """
    Core writer:
    - Writes a payment row into sanctuary_payments
    - Upserts into sanctuary_monthly_stats for the current LA month
    """
    if not SANCTU_GROUP_ID and not group_id:
        log.warning(
            "record_sanctuary_payment called but SUCCUBUS_SANCTUARY is not set."
        )
    gid = group_id or SANCTU_GROUP_ID or 0

    created_at = created_at or datetime.now(timezone.utc)
    now_la = _now_la()
    mkey = _month_key(now_la)

    norm_models = [m.lower().strip() for m in models if m]

    payment_doc = {
        "user_id": user_id,
        "username": username or "",
        "models": norm_models,
        "amount_cents": int(amount_cents),
        "currency": "usd",
        "source": source,
        "is_game": bool(is_game),
        "note": note or "",
        "group_id": gid,
        "created_at": created_at,
        "month": mkey,
    }
    payments_col.insert_one(payment_doc)

    # Upsert monthly bucket
    if gid:
        monthly_col.update_one(
            {"user_id": user_id, "group_id": gid, "month": mkey},
            {
                "$inc": {"total_cents": int(amount_cents)},
                "$addToSet": {"models_supported": {"$each": norm_models}},
            },
            upsert=True,
        )

def record_stripe_payment_from_webhook(
    telegram_id: int,
    username: str | None,
    model_key: str,
    amount_cents: int,
    *,
    is_game: bool = False,
    note: str | None = None,
) -> None:
    """
    Convenience helper to be called from your Stripe webhook handler.

    - telegram_id: Telegram user ID (from Stripe metadata)
    - username: Telegram username (from metadata, optional)
    - model_key: e.g. "roni", "ruby", or "game"
    - amount_cents: Stripe amount_total (in cents)
    - is_game=True or model_key=="game" → counts for BOTH Roni + Ruby
    """
    model_key = (model_key or "").lower().strip()
    if is_game or model_key == "game":
        models = ["roni", "ruby"]
        is_game = True
    else:
        models = [model_key] if model_key else []

    record_sanctuary_payment(
        user_id=telegram_id,
        username=username,
        models=models,
        amount_cents=amount_cents,
        source="stripe",
        is_game=is_game,
        note=note,
    )

# ────────────── ADMIN COMMANDS ──────────────

async def _resolve_user(client: Client, message: Message, token: Optional[str]) -> Optional[User]:
    """
    Resolve a user to log payment for or exempt:
    - If replying, uses the replied-to user
    - Else tries @username or numeric ID in token
    """
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user

    if not token:
        await message.reply_text("You must reply to a user or pass @username / user_id.")
        return None

    token = token.strip()
    try:
        if token.startswith("@"):
            return await client.get_users(token)
        elif token.isdigit():
            return await client.get_users(int(token))
    except Exception as e:
        log.warning("Failed to resolve user %r: %s", token, e)

    await message.reply_text("I couldn't resolve that user. Use @username, numeric ID, or reply to a user.")
    return None

@require_admin
async def _logpayment_cmd(client: Client, message: Message) -> None:
    """
    /logpayment <amount> <model|game> <@user|user_id> [note...]
    - amount: in dollars (e.g. 20 or 25.50)
    - model: slug like roni, ruby, or 'game' to count as both
    """
    if not SANCTU_GROUP_ID:
        await message.reply_text("SUCCUBUS_SANCTUARY is not configured; please set the env var first.")
        return

    parts = message.text.split(maxsplit=4)
    # /logpayment, amount, model, target, [note...]
    if len(parts) < 4 and not message.reply_to_message:
        await message.reply_text(
            "Usage:\n"
            "<code>/logpayment 20 roni @username optional note</code>\n"
            "Or reply to a user with:\n"
            "<code>/logpayment 20 roni</code>\n"
            "Use <code>game</code> as the model to count for both."
        )
        return

    try:
        amount = float(parts[1])
    except Exception:
        await message.reply_text("Amount must be a number in dollars, e.g. 20 or 25.50.")
        return

    model_key = (parts[2] if len(parts) > 2 else "").strip().lower()
    if not model_key:
        await message.reply_text("You must specify a model (e.g. roni, ruby, game).")
        return

    target_token = parts[3] if len(parts) > 3 and not message.reply_to_message else None
    note = parts[4] if len(parts) > 4 else ""

    user = await _resolve_user(client, message, target_token)
    if not user:
        return

    is_game = (model_key == "game")
    if is_game:
        models = ["roni", "ruby"]
    else:
        models = [model_key]

    cents = int(round(amount * 100))
    record_sanctuary_payment(
        user_id=user.id,
        username=user.username or "",
        models=models,
        amount_cents=cents,
        source="manual",
        is_game=is_game,
        note=note,
    )
    await message.reply_text(
        f"✅ Logged payment of <b>${amount:.2f}</b> for {user.mention} "
        f"({', '.join(models) or 'unknown model'})",
        parse_mode="html",
        disable_web_page_preview=True,
    )

@require_admin
async def _exemptbuyer_cmd(client: Client, message: Message) -> None:
    """
    /exemptbuyer <@user|user_id> [reason...]
    Marks a user as exempt from auto-kick + reminders.
    """
    if not SANCTU_GROUP_ID:
        await message.reply_text("SUCCUBUS_SANCTUARY is not configured.")
        return

    parts = message.text.split(maxsplit=2)
    target_token = parts[1] if len(parts) > 1 else None
    reason = parts[2] if len(parts) > 2 else ""

    user = await _resolve_user(client, message, target_token)
    if not user:
        return

    now = datetime.now(timezone.utc)
    exempt_col.update_one(
        {"user_id": user.id, "group_id": SANCTU_GROUP_ID},
        {
            "$set": {
                "user_id": user.id,
                "group_id": SANCTU_GROUP_ID,
                "username": user.username or "",
                "reason": reason,
                "set_by": message.from_user.id if message.from_user else 0,
                "set_at": now,
            }
        },
        upsert=True,
    )
    await message.reply_text(
        f"✅ {user.mention} marked as exempt from Sanctuary requirements.",
        parse_mode="html",
    )

@require_admin
async def _unexemptbuyer_cmd(client: Client, message: Message) -> None:
    """
    /unexemptbuyer <@user|user_id>
    Removes exemption.
    """
    if not SANCTU_GROUP_ID:
        await message.reply_text("SUCCUBUS_SANCTUARY is not configured.")
        return

    parts = message.text.split(maxsplit=1)
    target_token = parts[1] if len(parts) > 1 else None

    user = await _resolve_user(client, message, target_token)
    if not user:
        return

    exempt_col.delete_one({"user_id": user.id, "group_id": SANCTU_GROUP_ID})
    await message.reply_text(
        f"✅ {user.mention} is no longer exempt from Sanctuary requirements.",
        parse_mode="html",
    )

@require_admin
async def _reqstatus_cmd(client: Client, message: Message) -> None:
    """
    /reqstatus [@user|user_id]
    Shows this month's $ + model count for Sanctuary + whether they meet requirements.
    """
    if not SANCTU_GROUP_ID:
        await message.reply_text("SUCCUBUS_SANCTUARY is not configured.")
        return

    parts = message.text.split(maxsplit=1)
    target_token = parts[1] if len(parts) > 1 else None

    if target_token:
        user = await _resolve_user(client, message, target_token)
        if not user:
            return
    else:
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.reply_text("Reply to a user or pass @username / user_id.")
            return
        user = message.reply_to_message.from_user

    now = _now_la()
    mkey = _month_key(now)
    stats = _get_monthly_stats(user.id, SANCTU_GROUP_ID, mkey)
    cents = stats["total_cents"]
    models = stats["models"]
    meets = _meets_requirements(cents, models)

    spent = cents / 100.0
    msg = [
        f"📊 <b>Sanctuary requirements status for {user.mention}</b>",
        f"Month: <code>{mkey}</code>",
        f"Total spent: <b>${spent:.2f}</b>",
        f"Models supported: <b>{len(models)}</b> ({', '.join(models) or 'none'})",
        f"Requirement: <b>${REQUIRED_CENTS/100:.2f}</b> & {REQUIRED_MODELS} models",
        f"Meets requirement: {'✅ YES' if meets else '❌ NO'}",
        f"Exempt: {'✅ YES' if _is_exempt(user.id, SANCTU_GROUP_ID) else '❌ NO'}",
    ]
    await message.reply_text("\n".join(msg), parse_mode="html")

# ────────────── REGISTER ENTRYPOINT ──────────────

def register(app: Client):
    log.info(
        "✅ handlers.requirements_sanctuary_admin registered (SANCTU_GROUP_ID=%s)",
        SANCTU_GROUP_ID,
    )

    @app.on_message(filters.command("logpayment"))
    async def logpayment_handler(client: Client, message: Message):
        await _logpayment_cmd(client, message)

    @app.on_message(filters.command("exemptbuyer"))
    async def exemptbuyer_handler(client: Client, message: Message):
        await _exemptbuyer_cmd(client, message)

    @app.on_message(filters.command("unexemptbuyer"))
    async def unexemptbuyer_handler(client: Client, message: Message):
        await _unexemptbuyer_cmd(client, message)

    @app.on_message(filters.command("reqstatus"))
    async def reqstatus_handler(client: Client, message: Message):
        await _reqstatus_cmd(client, message)
