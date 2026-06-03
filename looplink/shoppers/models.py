"""Domain models for shopper profiles and sticker reward redemptions."""

from __future__ import annotations

from django.db import models

REWARDS: dict[str, dict] = {
    "MUG": {"name": "Mug", "cost": 10},
    "TOTE_BAG": {"name": "Tote Bag", "cost": 20},
}


def get_rewards() -> dict[str, dict]:
    """Return a copy of the available reward catalogue.

    Returns a shallow copy so callers cannot mutate the global registry.
    """
    return dict(REWARDS)


class ShopperProfile(models.Model):
    """Denormalised per-shopper record holding the live sticker balance.

    The balance is updated atomically via ``F()`` expressions on every
    transaction ingest and sticker redemption, making it race-condition safe
    under concurrent requests.
    """

    shopper_id = models.CharField(max_length=255, unique=True, primary_key=True)
    sticker_balance = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"ShopperProfile({self.shopper_id}, balance={self.sticker_balance})"


class StickerRedemption(models.Model):
    """Immutable audit record created each time a shopper redeems stickers."""

    shopper_id = models.CharField(max_length=255, db_index=True)
    reward_id = models.CharField(max_length=64)
    reward_name = models.CharField(max_length=255)
    stickers_cost = models.IntegerField()
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-redeemed_at"]

    def __str__(self) -> str:
        return f"StickerRedemption({self.shopper_id}, reward={self.reward_id}, cost={self.stickers_cost})"
