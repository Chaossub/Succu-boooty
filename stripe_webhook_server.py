"""
stripe_webhook_server.py

Standalone FastAPI server for Stripe webhooks.

- Runs separately from your Telegram bot (separate Render Web Service).
- Receives Stripe "checkout.session.completed" events.
- Pulls metadata (telegram_id, username, model, note).
- Writes rows into:
    sanctuary_payments
    sanctuary_monthly_stats
  using the same schema as your requirements handlers.

Your bot, running as a worker, will see the data in Mongo and do the
reminders / sweeps exactly as normal.

Nothing here talks to Telegram.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

import stripe
import pytz
from fastapi import FastAPI, Request, Header, HTTPException
from pymongo import MongoClient, ASCENDING

log = logging.getLogger("stripe_webhook_server")
logging.basicConfig(level=logging.INFO)

# ────────────── ENV / CONSTANTS ──────────────

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
if not STRIPE_WEBHOOK_SECRET:
    log.warning("STRIPE_WEBHOOK_SECRET not set – webhooks will fail until you add it.")

stripe.api_key = os.getenv("STRIPE_API_KEY", "")  # optional, not strictly needed for basic webhooks

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"
if not MONGO_URI:
    raise RuntimeError("MONGO_URI / MONGODB_URI is required for stripe_webhook_server")

LA_TZ = pytz.timezone("America/Los_Angeles")

mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]

payments_col = db.get_collection("sanctuary_payments")
monthly_col = db.get_collection("sanctuary_monthly_stats")

# Same group ID env your bot uses
SUCCU_RAW = os.getenv("SUCCUBUS_SANCTUARY")
try:
    SANCTU_GROUP_ID = int(SUCCU_RAW) if SUCCU_RAW else 0
except Exception:
    SANCTU_GROUP_ID = 0

# Requirements – must match the ones in your handlers (only used to compute month stats)
REQUIRED_CENTS = int(os.getenv("REQ2_REQUIRED_CENTS", "2000"))  # $20 default
REQUIRED_MODELS = int(os.getenv("REQ2_REQUIRED_MODELS", "2"))   # 2 models default

# Indexes (idempotent)
payments_col.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
payments_col.create_index([("source", ASCENDING), ("created_at", ASCENDING)])
monthly_col.create_index(
    [("user_id", ASCENDING), ("group_id", ASCENDING), ("month", ASCENDING)],
    unique=True,
)


# ────────────── HELPERS ──────────────

def _now_la() -> datetime:
    return datetime.now(tz=LA_TZ)


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _record_payment_row(
    *,
    user_id: int,
    username: str | None,
    models: List[str],
    amount_cents: int,
    source: str,
    is_game: bool,
    note: str | None,
) -> None:
    """
    Writes into sanctuary_payments + sanctuary_monthly_stats
    with the SAME schema as the requirements_sanctuary_admin handler.
    """
    created_at = datetime.now(timezone.utc)
    now_la = _now_la()
    mkey = _month_key(now_la)

    norm_models = [m.lower().strip() for m in models if m]

    payment_doc: Dict[str, Any] = {
        "user_id": user_id,
        "username": username or "",
        "models": norm_models,
        "amount_cents": int(amount_cents),
        "currency": "usd",
        "source": source,
        "is_game": bool(is_game),
        "note": note or "",
        "group_id": SANCTU_GROUP_ID,
        "created_at": created_at,
        "month": mkey,
    }
    payments_col.insert_one(payment_doc)

    if SANCTU_GROUP_ID:
        monthly_col.update_one(
            {"user_id": user_id, "group_id": SANCTU_GROUP_ID, "month": mkey},
            {
                "$inc": {"total_cents": int(amount_cents)},
                "$addToSet": {"models_supported": {"$each": norm_models}},
            },
            upsert=True,
        )

    log.info(
        "Logged Stripe payment: tg_id=%s models=%s cents=%s month=%s",
        user_id, norm_models, amount_cents, mkey
    )


def _extract_models_from_metadata(model_key: str | None, is_game: bool) -> tuple[list[str], bool]:
    """
    Apply the same logic as your bot:

    - model=game OR is_game=True → counts for BOTH roni & ruby
    - otherwise single model key
    """
    model_key = (model_key or "").lower().strip()
    if is_game or model_key == "game":
        return ["roni", "ruby"], True
    elif model_key:
        return [model_key], False
    else:
        return [], is_game


# ────────────── FASTAPI APP ──────────────

app = FastAPI(title="Succubus Sanctuary Stripe Webhook Server")


@app.get("/")
async def root():
    return {"status": "ok", "msg": "Succu Stripe webhook server running"}


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """
    Main Stripe webhook endpoint.

    Expects `checkout.session.completed` with metadata:
      - telegram_id  (required)
      - username     (optional)
      - model        ("roni", "ruby", "game", etc.)
      - note         (optional)
      - is_game      ("true"/"false" optional, for future uses)

    In Stripe dashboard, configure webhook events from "Your account"
    and include only: checkout.session.completed
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    payload = await request.body()
    sig_header = stripe_signature

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        log.warning("Stripe webhook signature verification failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.get("type")
    session = event.get("data", {}).get("object", {})

    if event_type != "checkout.session.completed":
        # We only care about completed checkout sessions
        log.info("Ignoring Stripe event type: %s", event_type)
        return {"status": "ignored"}

    log.info("Processing checkout.session.completed event")

    # Stripe Checkout Session fields
    amount_total = session.get("amount_total", 0)  # already in cents
    metadata = session.get("metadata", {}) or {}

    tg_id = metadata.get("telegram_id")
    username = metadata.get("username")
    model_key = metadata.get("model")
    note = metadata.get("note")
    is_game_meta = (metadata.get("is_game") or "").lower() == "true"

    if not tg_id:
        log.warning("Stripe session missing telegram_id metadata; skipping.")
        return {"status": "missing_telegram_id"}

    try:
        telegram_id = int(tg_id)
    except ValueError:
        log.warning("Invalid telegram_id in metadata: %r", tg_id)
        return {"status": "invalid_telegram_id"}

    models, is_game_flag = _extract_models_from_metadata(model_key, is_game_meta)
    if not models:
        # If no model specified, you can choose to drop, or log as unknown
        log.warning("No model in metadata – logging as 'unknown'")
        models = ["unknown"]

    _record_payment_row(
        user_id=telegram_id,
        username=username,
        models=models,
        amount_cents=int(amount_total),
        source="stripe",
        is_game=is_game_flag,
        note=note,
    )

    return {"status": "ok"}
