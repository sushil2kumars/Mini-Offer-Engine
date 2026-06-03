import json

from django.test import TestCase
from django.urls import reverse

from looplink.shoppers.models import ShopperProfile, StickerRedemption
from looplink.transactions.models import AppliedOffer, Transaction


class TestShopperDetailAPI(TestCase):
    def setUp(self):
        self.shopper = ShopperProfile.objects.create(shopper_id="test-shopper", sticker_balance=10)
        self.url = reverse("api_shopper_detail", args=["test-shopper"])

    def test_shopper_detail_returns_200(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        data = response.json()
        assert data["shopper_id"] == "test-shopper"
        assert data["sticker_balance"] == 10
        assert data["transactions"] == []

    def test_shopper_not_found_returns_404(self):
        url = reverse("api_shopper_detail", args=["nonexistent"])
        response = self.client.get(url)
        assert response.status_code == 404

    def test_shopper_shows_transactions(self):
        tx = Transaction.objects.create(
            transaction_id="tx-1",
            shopper_id="test-shopper",
            store_id="store-1",
            timestamp="2026-06-03T00:00:00Z",
            items=[],
            basket_total=100.00,
            total_discount=10.00,
            final_total=90.00,
            stickers_earned=5,
        )
        response = self.client.get(self.url)
        data = response.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["transaction_id"] == "tx-1"
        assert data["transactions"][0]["basket_total"] == "100.00"
        assert data["transactions"][0]["final_total"] == "90.00"
        assert data["transactions"][0]["stickers_earned"] == 5

    def test_shopper_shows_applied_offers(self):
        tx = Transaction.objects.create(
            transaction_id="tx-2",
            shopper_id="test-shopper",
            store_id="store-1",
            timestamp="2026-06-03T00:00:00Z",
            items=[],
            basket_total=50.00,
            total_discount=5.00,
            final_total=45.00,
            stickers_earned=2,
        )
        AppliedOffer.objects.create(
            transaction=tx,
            offer_id="OFFER1",
            offer_type="PRODUCT_PERCENT_DISCOUNT",
            offer_name="10% off",
            discount_amount=5.00,
            stickers_earned=0,
            detail={"sku": "SKU-1"},
        )
        response = self.client.get(self.url)
        data = response.json()
        tx_data = data["transactions"][0]
        assert len(tx_data["applied_offers"]) == 1
        assert tx_data["applied_offers"][0]["offer_id"] == "OFFER1"
        assert tx_data["applied_offers"][0]["discount_amount"] == "5.00"

    def test_shopper_balance_reflects_stickers(self):
        response = self.client.get(self.url)
        assert response.json()["sticker_balance"] == 10

    def test_multiple_transactions_ordered_by_timestamp(self):
        Transaction.objects.create(
            transaction_id="tx-old", shopper_id="test-shopper",
            store_id="s1", timestamp="2026-01-01T00:00:00Z",
            items=[], basket_total=10, total_discount=0, final_total=10, stickers_earned=0,
        )
        Transaction.objects.create(
            transaction_id="tx-new", shopper_id="test-shopper",
            store_id="s1", timestamp="2026-06-01T00:00:00Z",
            items=[], basket_total=20, total_discount=0, final_total=20, stickers_earned=0,
        )
        response = self.client.get(self.url)
        tx_ids = [t["transaction_id"] for t in response.json()["transactions"]]
        assert tx_ids == ["tx-new", "tx-old"]

    def test_shopper_detail_includes_redemptions(self):
        StickerRedemption.objects.create(
            shopper_id="test-shopper", reward_id="MUG", reward_name="Mug", stickers_cost=10,
        )
        response = self.client.get(self.url)
        data = response.json()
        assert len(data["redemptions"]) == 1
        assert data["redemptions"][0]["reward_id"] == "MUG"
        assert data["redemptions"][0]["stickers_cost"] == 10


class TestRedemption(TestCase):
    def setUp(self):
        self.url = reverse("api_shopper_redeem")
        self.shopper = ShopperProfile.objects.create(shopper_id="redeem-test", sticker_balance=25)

    def test_redeem_mug_success(self):
        response = self.client.post(self.url, data=json.dumps({
            "shopper_id": "redeem-test", "reward_id": "MUG",
        }), content_type="application/json")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["reward_id"] == "MUG"
        assert data["reward_name"] == "Mug"
        assert data["stickers_cost"] == 10
        assert data["new_sticker_balance"] == 15

    def test_redeem_tote_bag_success(self):
        response = self.client.post(self.url, data=json.dumps({
            "shopper_id": "redeem-test", "reward_id": "TOTE_BAG",
        }), content_type="application/json")
        assert response.status_code == 200
        assert response.json()["new_sticker_balance"] == 5

    def test_redeem_insufficient_stickers(self):
        ShopperProfile.objects.filter(shopper_id="redeem-test").update(sticker_balance=5)
        response = self.client.post(self.url, data=json.dumps({
            "shopper_id": "redeem-test", "reward_id": "MUG",
        }), content_type="application/json")
        assert response.status_code == 400
        assert response.json()["success"] is False
        assert "Insufficient" in response.json()["error"]

    def test_redeem_unknown_reward(self):
        response = self.client.post(self.url, data=json.dumps({
            "shopper_id": "redeem-test", "reward_id": "INVALID",
        }), content_type="application/json")
        assert response.status_code == 400
        assert "Unknown reward" in response.json()["error"]

    def test_redeem_nonexistent_shopper(self):
        response = self.client.post(self.url, data=json.dumps({
            "shopper_id": "no-such-shopper", "reward_id": "MUG",
        }), content_type="application/json")
        assert response.status_code == 404

    def test_redeem_missing_shopper_id(self):
        response = self.client.post(self.url, data=json.dumps({
            "reward_id": "MUG",
        }), content_type="application/json")
        assert response.status_code == 400

    def test_redeem_records_redemption(self):
        self.client.post(self.url, data=json.dumps({
            "shopper_id": "redeem-test", "reward_id": "TOTE_BAG",
        }), content_type="application/json")
        redemptions = StickerRedemption.objects.filter(shopper_id="redeem-test")
        assert redemptions.count() == 1
        assert redemptions[0].reward_id == "TOTE_BAG"
        assert redemptions[0].stickers_cost == 20

    def test_balance_deducted_on_duplicate_redeem_second_fails(self):
        self.client.post(self.url, data=json.dumps({
            "shopper_id": "redeem-test", "reward_id": "MUG",
        }), content_type="application/json")
        self.shopper.refresh_from_db()
        assert self.shopper.sticker_balance == 15
        response = self.client.post(self.url, data=json.dumps({
            "shopper_id": "redeem-test", "reward_id": "MUG",
        }), content_type="application/json")
        assert response.status_code == 200
        self.shopper.refresh_from_db()
        assert self.shopper.sticker_balance == 5
