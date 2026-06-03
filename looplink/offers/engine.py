"""Pure, side-effect-free promotion evaluation engine.

The engine takes a transaction payload and a list of offer definitions and
returns an :class:`EngineOutput` describing the discounts and stickers that
apply. It performs no database access or I/O so it can be unit-tested in
isolation and reused from any context (views, batch jobs, simulations).
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
CENTS = Decimal("0.01")
PERCENT_BASE = Decimal("100")
STICKER_EARN_DIVISOR = Decimal("10")


class OfferType:
    """Canonical identifiers for the supported promotion types."""

    PRODUCT_PERCENT_DISCOUNT = "PRODUCT_PERCENT_DISCOUNT"
    BOGO = "BOGO"
    CART_FIXED_DISCOUNT = "CART_FIXED_DISCOUNT"
    STICKER_EARN = "STICKER_EARN"
    STICKER_CAMPAIGN = "STICKER_CAMPAIGN"


EVALUATION_ORDER = (
    OfferType.PRODUCT_PERCENT_DISCOUNT,
    OfferType.BOGO,
    OfferType.CART_FIXED_DISCOUNT,
    OfferType.STICKER_EARN,
    OfferType.STICKER_CAMPAIGN,
)


@dataclass
class OfferResult:
    """Outcome of evaluating a single offer against a transaction."""

    offer_id: str
    offer_type: str
    offer_name: str
    discount_amount: Decimal
    stickers_earned: int
    detail: dict[str, Any]


@dataclass
class EngineOutput:
    """Aggregated result of evaluating every offer against a transaction."""

    basket_total: Decimal
    total_discount: Decimal
    final_total: Decimal
    stickers_earned: int
    applied_offers: list[OfferResult] = field(default_factory=list)
    processed_items: list[dict] = field(default_factory=list)


def _to_decimal(value: Any) -> Decimal:
    """Convert an arbitrary numeric/string value to ``Decimal`` safely."""
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    """Round a monetary ``Decimal`` to two decimal places."""
    return value.quantize(CENTS)


def _line_total(item: dict) -> Decimal:
    """Return the price for a single line item (unit price * quantity)."""
    return _to_decimal(item["unit_price"]) * Decimal(int(item["quantity"]))


def _build_result(offer: dict, discount: Decimal, stickers: int, detail: dict) -> OfferResult:
    """Construct an :class:`OfferResult` from an offer definition."""
    return OfferResult(
        offer_id=offer["offer_id"],
        offer_type=offer["type"],
        offer_name=offer["name"],
        discount_amount=discount,
        stickers_earned=stickers,
        detail=detail,
    )


def apply_product_percent(items: list[dict], offer: dict) -> OfferResult:
    """Apply a percentage discount to every line item matching the offer SKU.

    The matching line items are mutated in place so their effective
    ``unit_price`` reflects the discount, allowing subsequent offers to stack
    against the already-discounted value.
    """
    details = offer["details"]
    sku = details["sku"]
    percent = _to_decimal(details["percent"])

    total_discount = ZERO
    total_qty = 0

    for item in items:
        if item["sku"] != sku:
            continue

        qty = int(item["quantity"])
        item_total = _line_total(item)
        discount = min(item_total * percent / PERCENT_BASE, item_total)

        total_discount += discount
        total_qty += qty

        new_item_total = item_total - discount
        item["unit_price"] = str(new_item_total / Decimal(qty)) if qty > 0 else "0.00"
        item.setdefault("_discounts", []).append({
            "offer_id": offer["offer_id"],
            "offer_name": offer["name"],
            "discount_amount": str(_money(discount)),
        })

    return _build_result(
        offer,
        discount=_money(total_discount),
        stickers=0,
        detail={"affected_skus": [sku], "units": total_qty},
    )


def apply_bogo(items: list[dict], offer: dict) -> OfferResult:
    """Apply a Buy-One-Get-One offer to the matching SKU.

    For ``q`` matching units the cheapest ``floor(q / 2)`` units are free. The
    discount is spread proportionately across the matching line items so the
    effective ``unit_price`` is reduced for subsequent offers.
    """
    sku = offer["details"]["sku"]

    sku_items = [item for item in items if item["sku"] == sku]
    unit_prices: list[Decimal] = []
    for item in sku_items:
        unit_prices.extend(_to_decimal(item["unit_price"]) for _ in range(int(item["quantity"])))

    unit_prices.sort()
    free_units = len(unit_prices) // 2
    total_discount = sum(unit_prices[:free_units], ZERO)

    if total_discount > 0:
        total_sku_value = sum((_line_total(item) for item in sku_items), ZERO)
        if total_sku_value > 0:
            for item in sku_items:
                qty = int(item["quantity"])
                if qty <= 0:
                    continue
                item_total = _line_total(item)
                item_discount = total_discount * (item_total / total_sku_value)
                new_item_total = item_total - item_discount
                item["unit_price"] = str(new_item_total / Decimal(qty))
                item.setdefault("_discounts", []).append({
                    "offer_id": offer["offer_id"],
                    "offer_name": offer["name"],
                    "discount_amount": str(_money(item_discount)),
                })

    return _build_result(
        offer,
        discount=_money(total_discount),
        stickers=0,
        detail={"affected_skus": [sku], "free_units": free_units},
    )


def apply_cart_fixed(basket_total: Decimal, offer: dict) -> OfferResult:
    """Apply a fixed cart-level subsidy once the basket meets the threshold."""
    details = offer["details"]
    threshold = _to_decimal(details["threshold"])
    discount = _to_decimal(details["discount"])

    if basket_total >= threshold:
        return _build_result(
            offer,
            discount=discount,
            stickers=0,
            detail={"threshold": str(threshold), "basket_total": str(basket_total)},
        )

    return _build_result(
        offer,
        discount=ZERO,
        stickers=0,
        detail={"reason": f"Basket total {basket_total} below threshold {threshold}"},
    )


def apply_sticker_earn(items: list[dict], basket_total: Decimal, offer: dict) -> OfferResult:
    """Award stickers based on basket value plus optional promo-SKU bonuses.

    Stickers are earned against the pre-discount basket total so rewards stay
    predictable regardless of which monetary offers applied.
    """
    details = offer["details"]
    rate_per_10 = int(details.get("rate_per_10", 1))
    promo_skus = details.get("promo_skus", [])
    promo_bonus = int(details.get("promo_bonus", 0))
    max_per_tx_raw = details.get("max_per_transaction")
    max_per_tx = int(max_per_tx_raw) if max_per_tx_raw is not None else None

    base = int(basket_total // STICKER_EARN_DIVISOR) * rate_per_10

    bonus = sum(int(item["quantity"]) * promo_bonus for item in items if item["sku"] in promo_skus)

    total = base + bonus
    if max_per_tx is not None:
        total = min(total, max_per_tx)

    return _build_result(
        offer,
        discount=ZERO,
        stickers=total,
        detail={
            "base_earn": base,
            "bonus_earn": bonus,
            "total": total,
            "max_per_transaction": max_per_tx,
            "earn_rate": rate_per_10,
        },
    )


def apply_sticker_campaign(
    items: list[dict],
    basket_total: Decimal,
    store_id: str,
    timestamp: datetime,
    offer: dict,
) -> OfferResult:
    """Award campaign stickers based on weekday multipliers and store eligibility."""
    details = offer["details"]
    weekday_bonus = details.get("weekday_bonus", {})
    min_basket = _to_decimal(details.get("min_basket", "0"))
    store_ids = details.get("store_ids", [])
    bonus_stickers = int(details.get("bonus_stickers", 0))

    if basket_total < min_basket:
        return _build_result(
            offer,
            discount=ZERO,
            stickers=0,
            detail={"reason": f"Basket {basket_total} below minimum {min_basket}"},
        )

    if store_ids and store_id not in store_ids:
        return _build_result(
            offer,
            discount=ZERO,
            stickers=0,
            detail={"reason": f"Store {store_id} not in campaign stores"},
        )

    weekday_name = timestamp.strftime("%A").lower()
    multiplier = weekday_bonus.get(weekday_name, 1)

    if multiplier == 1 and bonus_stickers == 0:
        return _build_result(
            offer,
            discount=ZERO,
            stickers=0,
            detail={"reason": f"No bonus active on {weekday_name}"},
        )

    base_earn = int(basket_total // STICKER_EARN_DIVISOR)
    total_earn = base_earn * multiplier + bonus_stickers

    return _build_result(
        offer,
        discount=ZERO,
        stickers=total_earn,
        detail={
            "weekday": weekday_name,
            "multiplier": multiplier,
            "bonus_stickers": bonus_stickers,
            "base_earn": base_earn,
            "total": total_earn,
        },
    )


def _evaluate_offer(
    offer: dict,
    items: list[dict],
    basket_total: Decimal,
    current_total: Decimal,
    store_id: str,
    timestamp: datetime | None,
) -> OfferResult | None:
    """Dispatch a single offer to its processor, returning ``None`` if unknown.

    ``CART_FIXED_DISCOUNT`` is evaluated against the running ``current_total``
    (post product/BOGO discounts); all other offers evaluate against the
    pre-discount ``basket_total``.
    """
    offer_type = offer["type"]

    if offer_type == OfferType.PRODUCT_PERCENT_DISCOUNT:
        return apply_product_percent(items, offer)
    if offer_type == OfferType.BOGO:
        return apply_bogo(items, offer)
    if offer_type == OfferType.CART_FIXED_DISCOUNT:
        return apply_cart_fixed(current_total, offer)
    if offer_type == OfferType.STICKER_EARN:
        return apply_sticker_earn(items, basket_total, offer)
    if offer_type == OfferType.STICKER_CAMPAIGN:
        return apply_sticker_campaign(items, basket_total, store_id, timestamp, offer)

    logger.warning("Skipping offer %s with unknown type %r", offer.get("offer_id"), offer_type)
    return None


def _deduplicate_campaign_base(applied_offers: list[OfferResult]) -> int:
    """Remove redundant base earnings double-counted across sticker campaigns.

    Returns the number of stickers removed from the running total. Each
    campaign's ``base_earn`` overlaps with the standard ``STICKER_EARN`` base,
    so only one instance of the base is retained while bonuses are preserved.
    """
    campaigns = [o for o in applied_offers if o.offer_type == OfferType.STICKER_CAMPAIGN]
    has_standard_earn = any(o.offer_type == OfferType.STICKER_EARN for o in applied_offers)

    removed = 0
    for index, campaign in enumerate(campaigns):
        if index == 0 and not has_standard_earn:
            continue

        base_to_remove = campaign.detail.get("base_earn", 0)
        to_subtract = min(base_to_remove, campaign.stickers_earned)
        if to_subtract > 0:
            campaign.stickers_earned -= to_subtract
            removed += to_subtract

    return removed


def evaluate(transaction: dict, offers: list[dict]) -> EngineOutput:
    """Evaluate every applicable offer against ``transaction``.

    Offers are processed in a deterministic order so monetary discounts stack
    predictably and never reduce the basket below zero. The input transaction
    is not mutated; a deep copy of its items is used as the working ledger.
    """
    items = copy.deepcopy(transaction["items"])
    store_id = transaction.get("store_id", "")
    timestamp = transaction.get("timestamp")

    original_prices = [str(_to_decimal(it["unit_price"])) for it in items]

    basket_total = sum((_line_total(item) for item in items), ZERO)

    applied_offers: list[OfferResult] = []
    total_discount = ZERO
    total_stickers = 0
    current_total = basket_total

    for offer_type in EVALUATION_ORDER:
        for offer in offers:
            if offer["type"] != offer_type:
                continue

            result = _evaluate_offer(offer, items, basket_total, current_total, store_id, timestamp)
            if result is None:
                continue

            if result.discount_amount <= 0 and result.stickers_earned <= 0:
                continue

            capped_discount = min(result.discount_amount, current_total)
            result.discount_amount = _money(capped_discount)

            applied_offers.append(result)
            total_discount += capped_discount
            current_total -= capped_discount
            total_stickers += result.stickers_earned

    total_stickers -= _deduplicate_campaign_base(applied_offers)

    final_total = max(ZERO, basket_total - total_discount)

    processed_items = []
    for i, item in enumerate(items):
        qty = int(item["quantity"])
        orig = _to_decimal(original_prices[i])
        final = _to_decimal(item["unit_price"])
        discounts = item.pop("_discounts", [])
        processed_items.append({
            "sku": item["sku"],
            "name": item.get("name", item["sku"]),
            "quantity": qty,
            "category": item.get("category", ""),
            "original_unit_price": str(orig),
            "final_unit_price": str(final),
            "line_original": str(_money(orig * qty)),
            "line_final": str(_money(final * qty)),
            "discounts": discounts,
        })

    return EngineOutput(
        basket_total=_money(basket_total),
        total_discount=_money(total_discount),
        final_total=_money(final_total),
        stickers_earned=total_stickers,
        applied_offers=applied_offers,
        processed_items=processed_items,
    )
