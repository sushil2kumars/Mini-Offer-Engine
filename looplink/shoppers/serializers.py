"""Input serializers for the shoppers API."""

from __future__ import annotations

from rest_framework import serializers


class RedemptionInputSerializer(serializers.Serializer):
    """Validate a sticker-redemption request payload."""

    shopper_id = serializers.CharField(max_length=255)
    reward_id = serializers.CharField(max_length=64)
