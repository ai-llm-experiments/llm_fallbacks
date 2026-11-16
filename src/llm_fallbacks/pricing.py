"""Explicit registry zero-price classification shared by catalog consumers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _zero(value: Any) -> bool:
    if type(value) not in (int, float, str):
        return False
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return False
    return amount.is_finite() and amount == 0


def has_explicit_zero_cost(spec: dict[str, Any]) -> bool:
    """Require actual zero price fields and reject unknown or positive charges.

    This classifies registry metadata. Account eligibility, promotional quotas,
    privacy and prevention of paid escalation still need operational evidence.
    """
    mode = spec.get("mode", "")
    text_mode = mode in ("", "chat", "responses", "completion")
    if not text_mode and mode != "embedding":
        # Media and other endpoint pricing schemas need a separate complete
        # pricing contract before automatic free admission is supported.
        return False
    price_evidence = spec.get("pricing_evidence")
    if isinstance(price_evidence, dict) and price_evidence.get("source") == "provider-model-catalog":
        if mode not in ("chat", "responses", "completion", "embedding"):
            return False
        reported = price_evidence.get("reported_prices")
        if not isinstance(reported, dict) or not reported or not all(_zero(value) for value in reported.values()):
            return False
        required = ("prompt", "completion") if text_mode else ("prompt",)
        if not all(key in reported for key in required):
            return False
    costs = {key: value for key, value in spec.items() if "_cost_" in key or key.endswith("_cost")}
    if not costs or not all(_zero(value) for value in costs.values()):
        return False
    if text_mode:
        pairs = (
            ("input_cost_per_token", "output_cost_per_token"),
            ("input_cost_per_character", "output_cost_per_character"),
        )
        return any(all(key in costs for key in pair) for pair in pairs)
    return "input_cost_per_token" in costs or "input_cost_per_character" in costs
