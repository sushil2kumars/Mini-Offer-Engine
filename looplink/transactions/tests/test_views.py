import json
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from django.urls import reverse

from looplink.offers.engine import EngineOutput, OfferResult
from looplink.shoppers.models import ShopperProfile
from looplink.transactions.models import AppliedOffer, Transaction


def _make_tx_payload(overrides=None):
    payload = {
        "transaction_id": "tx-1001",
        "shopper_id": "shopper-123",
        "store_id": "store-001",
        "timestamp": "2026-06-02T10:00:00Z",
        "items": [
            {"sku": "SKU-MILK", "name": "Whole Milk", "quantity": 2, "unit_price": "3.50", "category": "dairy"},
        ],
    }
    if overrides:
        payload.update(overrides)
    return payload


class TestTransactionIngest(TestCase):
    def setUp(self):
        self.url = reverse("ingest_transaction")

    @patch("looplink.transactions.views.load_offers")
    def test_valid_transaction_returns_201(self, mock_load_offers):
        mock_load_offers.return_value = []
        payload = _make_tx_payload()
        response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 201
        data = response.json()
        assert data["transaction_id"] == "tx-1001"
        assert data["shopper_id"] == "shopper-123"
        assert data["basket_total"] == "7.00"
        assert data["total_discount"] == "0.00"
        assert data["final_total"] == "7.00"
        assert data["stickers_earned"] == 0
        assert data["applied_offers"] == []
        assert data["idempotent"] is False

    @patch("looplink.transactions.views.load_offers")
    def test_duplicate_transaction_returns_200(self, mock_load_offers):
        mock_load_offers.return_value = []
        payload = _make_tx_payload()
        response1 = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response1.status_code == 201

        response2 = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response2.status_code == 200
        data = response2.json()
        assert data["transaction_id"] == "tx-1001"
        assert data["idempotent"] is True

    @patch("looplink.transactions.views.load_offers")
    def test_engine_results_in_response(self, mock_load_offers):
        mock_load_offers.return_value = [
            {
                "offer_id": "OFFER10PCT-MILK",
                "type": "PRODUCT_PERCENT_DISCOUNT",
                "name": "10% off Milk",
                "details": {"sku": "SKU-MILK", "percent": 10},
            }
        ]
        payload = _make_tx_payload()
        response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 201
        data = response.json()
        assert data["basket_total"] == "7.00"
        assert data["total_discount"] == "0.70"
        assert data["final_total"] == "6.30"
        assert len(data["applied_offers"]) == 1
        assert data["applied_offers"][0]["offer_id"] == "OFFER10PCT-MILK"
        assert data["applied_offers"][0]["discount_amount"] == "0.70"

    def test_missing_shopper_id_returns_400(self):
        payload = _make_tx_payload({"shopper_id": None})
        response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 400

    def test_negative_unit_price_returns_400(self):
        payload = _make_tx_payload({"items": [
            {"sku": "SKU-MILK", "name": "Milk", "quantity": 1, "unit_price": "-1.00", "category": "dairy"},
        ]})
        response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 400

    def test_zero_quantity_returns_400(self):
        payload = _make_tx_payload({"items": [
            {"sku": "SKU-MILK", "name": "Milk", "quantity": 0, "unit_price": "3.50", "category": "dairy"},
        ]})
        response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 400

    @patch("looplink.transactions.views.load_offers")
    def test_unknown_offer_skus_returns_no_applied_offers(self, mock_load_offers):
        mock_load_offers.return_value = [
            {"offer_id": "OFFER10PCT-MILK", "type": "PRODUCT_PERCENT_DISCOUNT",
             "name": "10% off Milk", "details": {"sku": "SKU-MILK", "percent": 10}},
        ]
        payload = _make_tx_payload({"items": [
            {"sku": "SKU-UNKNOWN", "name": "Unknown", "quantity": 1, "unit_price": "5.00", "category": "other"},
        ]})
        response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 201
        data = response.json()
        assert data["applied_offers"] == []

    @patch("looplink.transactions.views.load_offers")
    def test_shopper_profile_created(self, mock_load_offers):
        mock_load_offers.return_value = []
        payload = _make_tx_payload()
        self.client.post(self.url, data=json.dumps(payload), content_type="application/json")

        from looplink.shoppers.models import ShopperProfile
        shopper = ShopperProfile.objects.get(shopper_id="shopper-123")
        assert shopper.sticker_balance == 0
        assert shopper.shopper_id == "shopper-123"

    @patch("looplink.transactions.views.load_offers")
    def test_sticker_balance_updated(self, mock_load_offers):
        mock_load_offers.return_value = [
            {
                "offer_id": "OFFER-STICKER-EARN",
                "type": "STICKER_EARN",
                "name": "Stickers",
                "details": {"rate_per_10": 1, "promo_skus": [], "promo_bonus": 0, "max_per_transaction": 5},
            }
        ]
        payload = _make_tx_payload({"items": [
            {"sku": "SKU-MILK", "name": "Milk", "quantity": 5, "unit_price": "10.00", "category": "dairy"},
        ]})
        self.client.post(self.url, data=json.dumps(payload), content_type="application/json")

        from looplink.shoppers.models import ShopperProfile
        shopper = ShopperProfile.objects.get(shopper_id="shopper-123")
        assert shopper.sticker_balance == 5

    @patch("looplink.transactions.views.load_offers")
    def test_empty_items_returns_400(self, mock_load_offers):
        mock_load_offers.return_value = []
        payload = _make_tx_payload({"items": []})
        response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 400

    def test_missing_transaction_id_returns_400(self):
        payload = _make_tx_payload({"transaction_id": None})
        response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 400

    def test_missing_store_id_returns_400(self):
        payload = _make_tx_payload({"store_id": None})
        response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 400

    @patch("looplink.transactions.views.load_offers")
    def test_duplicate_returns_original_data(self, mock_load_offers):
        mock_load_offers.return_value = [
            {
                "offer_id": "OFFER10PCT-MILK",
                "type": "PRODUCT_PERCENT_DISCOUNT",
                "name": "10% off Milk",
                "details": {"sku": "SKU-MILK", "percent": 10},
            }
        ]
        first = _make_tx_payload({"transaction_id": "tx-dup"})
        response1 = self.client.post(self.url, data=json.dumps(first), content_type="application/json")
        assert response1.status_code == 201
        data1 = response1.json()
        assert data1["total_discount"] == "0.70"

        second = _make_tx_payload({
            "transaction_id": "tx-dup",
            "items": [{"sku": "SKU-UNKNOWN", "name": "X", "quantity": 1, "unit_price": "99.00", "category": "other"}],
        })
        response2 = self.client.post(self.url, data=json.dumps(second), content_type="application/json")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["total_discount"] == "0.70"
        assert data2["basket_total"] == "7.00"
        assert data2["idempotent"] is True

    @patch("looplink.transactions.views.load_offers")
    def test_stickers_not_doubled_on_duplicate(self, mock_load_offers):
        mock_load_offers.return_value = [
            {
                "offer_id": "OFFER-STICKER-EARN",
                "type": "STICKER_EARN",
                "name": "Stickers",
                "details": {"rate_per_10": 1, "promo_skus": [], "promo_bonus": 0, "max_per_transaction": 5},
            }
        ]
        payload = _make_tx_payload({"transaction_id": "tx-sticky"})
        self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.client.post(self.url, data=json.dumps(payload), content_type="application/json")

        from looplink.shoppers.models import ShopperProfile
        shopper = ShopperProfile.objects.get(shopper_id="shopper-123")
        assert shopper.sticker_balance == 0

    @patch("looplink.transactions.views.load_offers")
    def test_multiple_transactions_accumulate_stickers(self, mock_load_offers):
        mock_load_offers.return_value = [
            {
                "offer_id": "OFFER-STICKER-EARN",
                "type": "STICKER_EARN",
                "name": "Stickers",
                "details": {"rate_per_10": 1, "promo_skus": [], "promo_bonus": 0, "max_per_transaction": 5},
            }
        ]
        tx1 = _make_tx_payload({"transaction_id": "tx-a", "items": [
            {"sku": "SKU-MILK", "name": "Milk", "quantity": 1, "unit_price": "20.00", "category": "dairy"},
        ]})
        self.client.post(self.url, data=json.dumps(tx1), content_type="application/json")

        tx2 = _make_tx_payload({"transaction_id": "tx-b", "items": [
            {"sku": "SKU-MILK", "name": "Milk", "quantity": 1, "unit_price": "30.00", "category": "dairy"},
        ]})
        self.client.post(self.url, data=json.dumps(tx2), content_type="application/json")

        from looplink.shoppers.models import ShopperProfile
        shopper = ShopperProfile.objects.get(shopper_id="shopper-123")
        assert shopper.sticker_balance == 5

    @patch("looplink.transactions.views.load_offers")
    def test_applied_offer_records_created(self, mock_load_offers):
        mock_load_offers.return_value = [
            {
                "offer_id": "OFFER10PCT-MILK",
                "type": "PRODUCT_PERCENT_DISCOUNT",
                "name": "10% off Milk",
                "details": {"sku": "SKU-MILK", "percent": 10},
            }
        ]
        payload = _make_tx_payload()
        self.client.post(self.url, data=json.dumps(payload), content_type="application/json")

        tx = Transaction.objects.get(transaction_id="tx-1001")
        offers = tx.applied_offers.all()
        assert len(offers) == 1
        assert offers[0].offer_id == "OFFER10PCT-MILK"
        assert offers[0].discount_amount == Decimal("0.70")
        assert offers[0].offer_type == "PRODUCT_PERCENT_DISCOUNT"
        assert offers[0].detail["affected_skus"] == ["SKU-MILK"]

    @patch("looplink.transactions.views.load_offers")
    def test_transaction_stores_correct_discount(self, mock_load_offers):
        mock_load_offers.return_value = [
            {
                "offer_id": "OFFER10PCT-MILK",
                "type": "PRODUCT_PERCENT_DISCOUNT",
                "name": "10% off Milk",
                "details": {"sku": "SKU-MILK", "percent": 10},
            }
        ]
        payload = _make_tx_payload()
        response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 201

        tx = Transaction.objects.get(transaction_id="tx-1001")
        assert tx.basket_total == Decimal("7.00")
        assert tx.total_discount == Decimal("0.70")
        assert tx.final_total == Decimal("6.30")
        assert tx.status == Transaction.STATUS_PROCESSED


class TestTransactionStats(TestCase):
    def setUp(self):
        self.url = reverse("transaction_stats")

    def test_stats_empty_db(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        data = response.json()
        assert data["total_transactions_processed"] == 0
        assert data["total_shoppers"] == 0
        assert data["total_stickers_awarded"] == 0
        assert data["total_discount_given"] == "0.00"
        assert data["stickers_per_store"] == []
        assert data["discount_per_offer"] == []

    def test_stats_with_transactions(self):
        tx1 = Transaction.objects.create(
            transaction_id="s-tx1", shopper_id="s1", store_id="store-a",
            timestamp="2026-06-03T00:00:00Z", items=[],
            basket_total=100, total_discount=10, final_total=90, stickers_earned=5,
        )
        tx2 = Transaction.objects.create(
            transaction_id="s-tx2", shopper_id="s1", store_id="store-a",
            timestamp="2026-06-03T01:00:00Z", items=[],
            basket_total=50, total_discount=5, final_total=45, stickers_earned=3,
        )
        tx3 = Transaction.objects.create(
            transaction_id="s-tx3", shopper_id="s2", store_id="store-b",
            timestamp="2026-06-03T02:00:00Z", items=[],
            basket_total=200, total_discount=20, final_total=180, stickers_earned=10,
        )
        AppliedOffer.objects.create(
            transaction=tx1, offer_id="O1", offer_type="PCT", offer_name="10% off",
            discount_amount=10.00, stickers_earned=0, detail={},
        )
        AppliedOffer.objects.create(
            transaction=tx2, offer_id="O1", offer_type="PCT", offer_name="10% off",
            discount_amount=5.00, stickers_earned=0, detail={},
        )
        AppliedOffer.objects.create(
            transaction=tx3, offer_id="O2", offer_type="FIXED", offer_name="$5 off",
            discount_amount=20.00, stickers_earned=0, detail={},
        )

        ShopperProfile.objects.create(shopper_id="s1", sticker_balance=8)
        ShopperProfile.objects.create(shopper_id="s2", sticker_balance=10)

        response = self.client.get(self.url)
        assert response.status_code == 200
        data = response.json()

        assert data["total_transactions_processed"] == 3
        assert data["total_shoppers"] == 2
        assert data["total_stickers_awarded"] == 18
        assert Decimal(data["total_discount_given"]) == Decimal("35.00")

        store_map = {s["store_id"]: s["stickers_awarded"] for s in data["stickers_per_store"]}
        assert store_map["store-a"] == 8
        assert store_map["store-b"] == 10

        offer_map = {o["offer_id"]: o for o in data["discount_per_offer"]}
        assert Decimal(offer_map["O1"]["total_discount"]) == Decimal("15.00")
        assert offer_map["O1"]["times_applied"] == 2
        assert Decimal(offer_map["O2"]["total_discount"]) == Decimal("20.00")
        assert offer_map["O2"]["times_applied"] == 1
