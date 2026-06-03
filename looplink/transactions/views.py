"""API views for ingesting purchase transactions and reporting statistics."""

import logging
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, F, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from looplink.offers.config import load_offers
from looplink.offers.engine import EngineOutput, evaluate
from looplink.shoppers.models import ShopperProfile, StickerRedemption

from .models import AppliedOffer, Transaction
from .serializers import TransactionInputSerializer

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
CENTS = Decimal("0.01")


def _serialize_applied_offer(applied_offer: AppliedOffer) -> dict:
    """Serialize a single applied offer for API output."""
    return {
        "offer_id": applied_offer.offer_id,
        "offer_name": applied_offer.offer_name,
        "discount_amount": str(applied_offer.discount_amount),
        "stickers_earned": applied_offer.stickers_earned,
        "detail": applied_offer.detail,
    }


def _serialize_transaction(tx: Transaction, idempotent: bool = False) -> dict:
    """Serialize a transaction together with its applied offers."""
    return {
        "transaction_id": tx.transaction_id,
        "shopper_id": tx.shopper_id,
        "basket_total": str(tx.basket_total),
        "total_discount": str(tx.total_discount),
        "final_total": str(tx.final_total),
        "stickers_earned": tx.stickers_earned,
        "applied_offers": [_serialize_applied_offer(ao) for ao in tx.applied_offers.all()],
        "idempotent": idempotent,
    }


def _normalize_items(items: list[dict]) -> list[dict]:
    """Normalize validated line items into JSON-serializable storage form."""
    return [
        {
            "sku": item["sku"],
            "name": item["name"],
            "quantity": item["quantity"],
            "unit_price": str(item["unit_price"]),
            "category": item["category"],
        }
        for item in items
    ]


def _credit_shopper_stickers(shopper_id: str, stickers_earned: int) -> None:
    """Atomically add earned stickers to a shopper, creating the profile if needed.

    Uses an update-first strategy to avoid races: attempt the increment, and
    only fall back to creating the profile when no row was updated. A nested
    savepoint plus ``IntegrityError`` retry handles concurrent creation.
    """
    updated = ShopperProfile.objects.filter(shopper_id=shopper_id).update(
        sticker_balance=F("sticker_balance") + stickers_earned,
        updated_at=timezone.now(),
    )
    if updated:
        return

    try:
        with transaction.atomic():
            ShopperProfile.objects.create(shopper_id=shopper_id, sticker_balance=stickers_earned)
    except IntegrityError:
        ShopperProfile.objects.filter(shopper_id=shopper_id).update(
            sticker_balance=F("sticker_balance") + stickers_earned,
            updated_at=timezone.now(),
        )


def _persist_transaction(data: dict, result: EngineOutput) -> Transaction:
    """Persist the transaction, its applied offers and the shopper sticker credit."""
    with transaction.atomic():
        tx = Transaction.objects.create(
            transaction_id=data["transaction_id"],
            shopper_id=data["shopper_id"],
            store_id=data["store_id"],
            timestamp=data["timestamp"],
            items=_normalize_items(data["items"]),
            basket_total=result.basket_total,
            total_discount=result.total_discount,
            final_total=result.final_total,
            stickers_earned=result.stickers_earned,
            status=Transaction.STATUS_PROCESSED,
            processed_items=result.processed_items,
        )

        AppliedOffer.objects.bulk_create(
            [
                AppliedOffer(
                    transaction=tx,
                    offer_id=offer.offer_id,
                    offer_type=offer.offer_type,
                    offer_name=offer.offer_name,
                    discount_amount=offer.discount_amount,
                    stickers_earned=offer.stickers_earned,
                    detail=offer.detail,
                )
                for offer in result.applied_offers
            ]
        )

        _credit_shopper_stickers(data["shopper_id"], result.stickers_earned)

    return tx


@api_view(["POST"])
@permission_classes([AllowAny])
def ingest_transaction(request: Request) -> Response:
    """Ingest a purchase transaction, evaluate offers and store the results.

    Ingestion is idempotent on ``transaction_id``: duplicates return the
    previously stored result with HTTP 200 and ``idempotent: true`` without
    re-processing.
    """
    serializer = TransactionInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    tx_id = data["transaction_id"]
    existing = Transaction.objects.filter(transaction_id=tx_id).first()
    if existing is not None:
        logger.info(
            "[TRACE:%s] Idempotent hit — returning stored result for shopper=%s",
            tx_id,
            existing.shopper_id,
        )
        return Response(_serialize_transaction(existing, idempotent=True), status=status.HTTP_200_OK)

    offers = load_offers()
    logger.info(
        "[TRACE:%s] Evaluating transaction shopper=%s store=%s items=%d offers_loaded=%s",
        tx_id,
        data["shopper_id"],
        data["store_id"],
        len(data["items"]),
        len(offers),
    )
    result = evaluate(data, offers)
    logger.info(
        "[TRACE:%s] Evaluation complete discount=%s final_total=%s stickers=%s applied=%s",
        tx_id,
        result.total_discount,
        result.final_total,
        result.stickers_earned,
        [o.offer_id for o in result.applied_offers],
    )

    try:
        tx = _persist_transaction(data, result)
    except IntegrityError:
        existing = Transaction.objects.get(transaction_id=data["transaction_id"])
        return Response(_serialize_transaction(existing, idempotent=True), status=status.HTTP_200_OK)

    logger.info(
        "[TRACE:%s] Persisted transaction for shopper=%s discount=%s final_total=%s stickers=%s",
        tx.transaction_id,
        tx.shopper_id,
        result.total_discount,
        result.final_total,
        result.stickers_earned,
    )
    return Response(_serialize_transaction(tx), status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def transaction_stats(request: Request) -> Response:
    """Return system-wide transaction, discount, sticker and redemption statistics."""
    tx_count = Transaction.objects.count()
    shopper_count = ShopperProfile.objects.count()

    total_stickers = Transaction.objects.aggregate(total=Sum("stickers_earned"))["total"] or 0

    stickers_per_store = (
        Transaction.objects.values("store_id")
        .annotate(total=Sum("stickers_earned"))
        .order_by("-total")
    )

    total_discount_agg = (
        AppliedOffer.objects.aggregate(total=Sum("discount_amount"))["total"] or ZERO
    ).quantize(CENTS)

    discount_per_offer = (
        AppliedOffer.objects.values("offer_id", "offer_name")
        .annotate(total_discount=Sum("discount_amount"), times_applied=Count("id"))
        .order_by("-total_discount")
    )

    redemption_count = StickerRedemption.objects.count()
    stickers_redeemed = StickerRedemption.objects.aggregate(total=Sum("stickers_cost"))["total"] or 0

    avg_discount_per_tx = (total_discount_agg / tx_count).quantize(CENTS) if tx_count else ZERO
    avg_stickers_per_tx = round(total_stickers / tx_count, 2) if tx_count else 0

    return Response(
        {
            "total_transactions_processed": tx_count,
            "total_shoppers": shopper_count,
            "total_stickers_awarded": total_stickers,
            "total_discount_given": str(total_discount_agg),
            "average_discount_per_transaction": str(avg_discount_per_tx),
            "average_stickers_per_transaction": avg_stickers_per_tx,
            "total_redemptions": redemption_count,
            "total_stickers_redeemed": stickers_redeemed,
            "stickers_per_store": [
                {"store_id": s["store_id"], "stickers_awarded": s["total"]}
                for s in stickers_per_store
            ],
            "discount_per_offer": [
                {
                    "offer_id": o["offer_id"],
                    "offer_name": o["offer_name"],
                    "total_discount": str(o["total_discount"].quantize(CENTS)),
                    "times_applied": o["times_applied"],
                }
                for o in discount_per_offer
            ],
        }
    )
