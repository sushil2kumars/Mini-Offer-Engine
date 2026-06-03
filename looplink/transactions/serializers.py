"""Input serializers for the transactions API."""

from __future__ import annotations

from rest_framework import serializers


class TransactionItemSerializer(serializers.Serializer):
    """Validate a single line item within a transaction payload."""

    sku = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    category = serializers.CharField(max_length=255)


class TransactionInputSerializer(serializers.Serializer):
    """Validate a full transaction ingest request payload.

    ``items`` must contain at least one line item, enforced by ``min_length=1``.
    """

    transaction_id = serializers.CharField(max_length=255)
    shopper_id = serializers.CharField(max_length=255)
    store_id = serializers.CharField(max_length=255)
    timestamp = serializers.DateTimeField()
    items = TransactionItemSerializer(many=True, min_length=1)
