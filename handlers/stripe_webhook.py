# handlers/stripe_webhook.py
#
# Handles incoming Stripe webhook payment events.
#
# This connects directly into your Sanctuary requirements system by calling:
#   record_stripe_payment_from_webhook(app, ...)
#
# YOU DO NOT EDIT ANY OTHER FILES.
#

import os
import json
import stripe
import logging
from aiohttp import web

from pyrogram import Client

from handlers.requirements_sanctuary_admin import record_stripe_payment_from_webhook

log = logging.getLogger("stripe_webhook")

# ────────────── ENV ──────────────
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
if not STRIPE_WEBHOOK_SECRET:
    log.warning("[stripe_webhook] STRIPE_WEBHOOK_SECRET is not set! Webhooks will fail.")

# ────────────── WEB SERVER SETUP ──────────────
#
# Railway or Render will expose a public URL for your bot.
# You point Stripe → Webhooks → that URL.
#
# Example webhook URL:
#   https://your-app.up.railway.app/stripe/webhook
#
# This file adds that route.


async def stripe_webhook_handler(request: web.Request):
    """
    Receives Stripe webhook events, verifies, and processes payment_intent.succeeded.
    """
    payload = await request.text()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        log.warning("[stripe_webhook] Signature verification failed: %s", e)
        return web.Response(status=400, text="Invalid signature")

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    # We only care about successful payments
    if event_type == "checkout.session.completed":
        log.info("[stripe_webhook] checkout.session.completed received")

        try:
            # Stripe Checkout Session structure
            amount_total = data.get("amount_total", 0)
            metadata = data.get("metadata", {}) or {}

            # Metadata from Stripe link
            tg_id = metadata.get("telegram_id")
            username = metadata.get("username")
            model = metadata.get("model")   # roni / ruby / game / etc.
            note = metadata.get("note")

            if not tg_id:
                log.warning("[stripe_webhook] No telegram_id in metadata, skipping.")
                return web.Response(status=200)

            if not model:
                model = "unknown"

            # Stripe gives cents already
            amount_cents = amount_total

            # Run through sanctuary system
            from bot_instance import app  # this is created below in register()

            await record_stripe_payment_from_webhook(
                app,
                user_id=int(tg_id),
                username=username,
                amount_cents=amount_cents,
                model=model,
                note=note,
            )

            log.info(
                "[stripe_webhook] Successfully logged payment: tg_id=%s model=%s amount=%s",
                tg_id, model, amount_cents
            )
        except Exception as e:
            log.error("[stripe_webhook] Error processing payment: %s", e)

    return web.Response(status=200, text="OK")


# ────────────── REGISTER ROUTE ──────────────

def register(app: Client):
    """
    Registers the webhook server route into AIOHTTP that Pyrogram is running.
    """
    try:
        # Pyrogram exposes app.web (aiohttp Application)
        web_app = app.web

        web_app.router.add_post("/stripe/webhook", stripe_webhook_handler)

        log.info("✅ Registered Stripe webhook route: /stripe/webhook")
    except Exception as e:
        log.warning("Failed to register Stripe webhook: %s", e)
