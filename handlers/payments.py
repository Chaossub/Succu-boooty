# payments.py
from __future__ import annotations

import json
import calendar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
PAYMENTS_FILE = DATA_DIR / "stripe_payments.json"


@dataclass
class Payment:
    telegram_id: int
    model_id: str
    purchase_type: str  # e.g. "game", "content", "tip"
    amount_cents: int
    created_at: datetime

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Payment":
        return cls(
            telegram_id=int(d["telegram_id"]),
            model_id=str(d.get("model_id") or ""),
            purchase_type=str(d.get("purchase_type") or "unknown"),
            amount_cents=int(d.get("amount_cents") or 0),
            created_at=datetime.fromisoformat(d["created_at"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "telegram_id": self.telegram_id,
            "model_id": self.model_id,
            "purchase_type": self.purchase_type,
            "amount_cents": self.amount_cents,
            "created_at": self.created_at.isoformat(),
        }


def _load_all() -> List[Payment]:
    if not PAYMENTS_FILE.exists():
        return []
    try:
        raw = json.loads(PAYMENTS_FILE.read_text("utf-8"))
        return [Payment.from_dict(item) for item in raw]
    except Exception:
        # if file is corrupted, don't crash the bot
        return []


def _save_all(payments: List[Payment]) -> None:
    data = [p.to_dict() for p in payments]
    PAYMENTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_payment(
    telegram_id: int,
    model_id: str,
    purchase_type: str,
    amount_cents: int,
    created_at: datetime | None = None,
) -> None:
    """
    Append a successful payment. Call this from your Stripe webhook handler once
    a payment is confirmed (e.g. checkout.session.completed).
    """
    created_at = created_at or datetime.utcnow()
    payments = _load_all()
    payments.append(
        Payment(
            telegram_id=telegram_id,
            model_id=model_id,
            purchase_type=purchase_type,
            amount_cents=amount_cents,
            created_at=created_at,
        )
    )
    _save_all(payments)


def _same_month(dt: datetime, year: int, month: int) -> bool:
    return dt.year == year and dt.month == month


def get_monthly_progress(
    telegram_id: int, year: int | None = None, month: int | None = None
) -> Tuple[float, int]:
    """
    Returns (total_game_dollars, distinct_models_count) for the given user
    in the given year/month (defaults to current UTC month).

    - total_game_dollars: only payments where purchase_type == "game"
    - distinct_models_count: any purchase_type counts for the model list
    """
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    payments = _load_all()
    total_game_cents = 0
    model_ids = set()

    for p in payments:
        if p.telegram_id != telegram_id:
            continue
        if not _same_month(p.created_at, year, month):
            continue

        # For "game" purchases, add to the dollar total
        if p.purchase_type == "game":
            total_game_cents += p.amount_cents

        # Any purchase type counts toward "has bought from this model"
        if p.model_id:
            model_ids.add(p.model_id)

    total_game_dollars = total_game_cents / 100.0
    return total_game_dollars, len(model_ids)


def has_met_requirements(
    telegram_id: int,
    year: int | None = None,
    month: int | None = None,
    min_game_dollars: float = 20.0,
    min_models: int = 2,
) -> bool:
    total_game_dollars, model_count = get_monthly_progress(telegram_id, year, month)
    return total_game_dollars >= min_game_dollars and model_count >= min_models


def days_left_in_month(now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    last_day = calendar.monthrange(now.year, now.month)[1]
    end_date = datetime(now.year, now.month, last_day).date()
    return max((end_date - now.date()).days, 0)
