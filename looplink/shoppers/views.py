"""API views for shopper profiles, transaction history and reward redemption."""

import logging

from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from looplink.transactions.models import AppliedOffer, Transaction

from .models import ShopperProfile, StickerRedemption, get_rewards
from .serializers import RedemptionInputSerializer

logger = logging.getLogger(__name__)


def _serialize_applied_offer(applied_offer: AppliedOffer) -> dict:
    """Serialize a single applied offer for API output."""
    return {
        "offer_id": applied_offer.offer_id,
        "offer_name": applied_offer.offer_name,
        "discount_amount": str(applied_offer.discount_amount),
        "stickers_earned": applied_offer.stickers_earned,
        "detail": applied_offer.detail,
    }


def _serialize_transaction(tx: Transaction) -> dict:
    """Serialize a transaction together with its applied offers."""
    return {
        "transaction_id": tx.transaction_id,
        "store_id": tx.store_id,
        "timestamp": tx.timestamp.isoformat(),
        "basket_total": str(tx.basket_total),
        "total_discount": str(tx.total_discount),
        "final_total": str(tx.final_total),
        "stickers_earned": tx.stickers_earned,
        "applied_offers": [_serialize_applied_offer(ao) for ao in tx.applied_offers.all()],
    }


def _serialize_redemption(redemption: StickerRedemption) -> dict:
    """Serialize a single sticker redemption for API output."""
    return {
        "reward_id": redemption.reward_id,
        "reward_name": redemption.reward_name,
        "stickers_cost": redemption.stickers_cost,
        "redeemed_at": redemption.redeemed_at.isoformat(),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def shopper_detail(request: Request, shopper_id: str) -> Response:
    """Return a shopper's profile, transaction history and redemptions."""
    shopper = get_object_or_404(ShopperProfile, shopper_id=shopper_id)

    transactions = Transaction.objects.filter(shopper_id=shopper_id).prefetch_related("applied_offers")
    redemptions = StickerRedemption.objects.filter(shopper_id=shopper_id)

    return Response(
        {
            "shopper_id": shopper.shopper_id,
            "sticker_balance": shopper.sticker_balance,
            "transactions": [_serialize_transaction(tx) for tx in transactions],
            "redemptions": [_serialize_redemption(r) for r in redemptions],
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def redeem_stickers(request: Request) -> Response:
    """Redeem stickers for a reward, atomically debiting the shopper's balance."""
    serializer = RedemptionInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    shopper_id = serializer.validated_data["shopper_id"]
    reward_id = serializer.validated_data["reward_id"]

    rewards = get_rewards()
    reward = rewards.get(reward_id)
    if reward is None:
        return Response(
            {"success": False, "error": f"Unknown reward: {reward_id}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            shopper = ShopperProfile.objects.select_for_update().get(shopper_id=shopper_id)

            if shopper.sticker_balance < reward["cost"]:
                return Response(
                    {
                        "success": False,
                        "error": (
                            f"Insufficient stickers. Required: {reward['cost']}, "
                            f"Available: {shopper.sticker_balance}"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            redemption = StickerRedemption.objects.create(
                shopper_id=shopper_id,
                reward_id=reward_id,
                reward_name=reward["name"],
                stickers_cost=reward["cost"],
            )

            ShopperProfile.objects.filter(shopper_id=shopper_id).update(
                sticker_balance=F("sticker_balance") - reward["cost"],
                updated_at=timezone.now(),
            )
    except ShopperProfile.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    shopper.refresh_from_db()
    logger.info("Shopper %s redeemed reward %s for %s stickers", shopper_id, reward_id, reward["cost"])

    return Response(
        {
            "success": True,
            "shopper_id": shopper.shopper_id,
            "reward_id": reward_id,
            "reward_name": reward["name"],
            "stickers_cost": reward["cost"],
            "new_sticker_balance": shopper.sticker_balance,
            "redeemed_at": redemption.redeemed_at.isoformat(),
        }
    )
