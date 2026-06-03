"""Domain models for purchase transactions and their applied offers."""

from __future__ import annotations

from django.db import models


class Transaction(models.Model):
    """A fully processed purchase transaction with computed totals.

    Once persisted, a transaction is immutable. Duplicate submissions are
    detected by ``transaction_id`` and short-circuited before any processing
    occurs, ensuring idempotent ingestion.
    """

    STATUS_PENDING = "pending"
    STATUS_PROCESSED = "processed"
    STATUS_DUPLICATE = "duplicate"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_DUPLICATE, "Duplicate"),
    ]

    transaction_id = models.CharField(max_length=255, unique=True)
    shopper_id = models.CharField(max_length=255, db_index=True)
    store_id = models.CharField(max_length=255)
    timestamp = models.DateTimeField()
    items = models.JSONField()
    basket_total = models.DecimalField(max_digits=12, decimal_places=2)
    total_discount = models.DecimalField(max_digits=12, decimal_places=2)
    final_total = models.DecimalField(max_digits=12, decimal_places=2)
    stickers_earned = models.IntegerField(default=0)
    processed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    processed_items = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"Transaction({self.transaction_id}, shopper={self.shopper_id}, total={self.final_total})"


class AppliedOffer(models.Model):
    """Record of a single offer that fired during a transaction's evaluation.

    Each row captures the monetary discount or sticker award produced by one
    offer so the full audit trail can be reconstructed per transaction.
    """

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="applied_offers")
    offer_id = models.CharField(max_length=64)
    offer_type = models.CharField(max_length=64)
    offer_name = models.CharField(max_length=255)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    stickers_earned = models.IntegerField(default=0)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"AppliedOffer({self.offer_id}, tx={self.transaction_id}, discount={self.discount_amount})"
