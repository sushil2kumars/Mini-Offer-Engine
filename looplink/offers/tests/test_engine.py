from decimal import Decimal

import pytest

from datetime import datetime

from looplink.offers.engine import (
    EngineOutput,
    apply_bogo,
    apply_cart_fixed,
    apply_product_percent,
    apply_sticker_burn,
    apply_sticker_campaign,
    apply_sticker_earn,
    evaluate,
)

OFFERS = [
    {
        "offer_id": "OFFER10PCT-MILK",
        "type": "PRODUCT_PERCENT_DISCOUNT",
        "name": "10% off Milk",
        "details": {"sku": "SKU-MILK", "percent": 10},
    },
    {
        "offer_id": "OFFER-BOGO-CHEESE",
        "type": "BOGO",
        "name": "Buy 1 Get 1 Free Cheese",
        "details": {"sku": "SKU-CHEESE"},
    },
    {
        "offer_id": "OFFER5-OFF-50",
        "type": "CART_FIXED_DISCOUNT",
        "name": "$5 off orders over $50",
        "details": {"threshold": 50.00, "discount": 5.00},
    },
    {
        "offer_id": "OFFER-STICKER-EARN",
        "type": "STICKER_EARN",
        "name": "Sticker Reward",
        "details": {
            "rate_per_10": 1,
            "promo_skus": ["SKU-ORGANIC"],
            "promo_bonus": 1,
            "max_per_transaction": 5,
        },
    },
]


class TestProductPercent:
    def test_single_sku_match(self):
        items = [{"sku": "SKU-MILK", "unit_price": "3.50", "quantity": 2}]
        result = apply_product_percent(items, OFFERS[0])
        assert result.discount_amount == Decimal("0.70")
        assert result.detail["affected_skus"] == ["SKU-MILK"]
        assert result.detail["units"] == 2

    def test_multiple_skus_one_match(self):
        items = [
            {"sku": "SKU-MILK", "unit_price": "3.50", "quantity": 2},
            {"sku": "SKU-BREAD", "unit_price": "4.00", "quantity": 1},
        ]
        result = apply_product_percent(items, OFFERS[0])
        assert result.discount_amount == Decimal("0.70")
        assert result.detail["units"] == 2

    def test_sku_not_in_offer(self):
        items = [{"sku": "SKU-UNKNOWN", "unit_price": "10.00", "quantity": 1}]
        result = apply_product_percent(items, OFFERS[0])
        assert result.discount_amount == Decimal("0.00")
        assert result.detail["units"] == 0


class TestBOGO:
    def test_qty_one_no_discount(self):
        items = [{"sku": "SKU-CHEESE", "unit_price": "5.00", "quantity": 1}]
        result = apply_bogo(items, OFFERS[1])
        assert result.discount_amount == Decimal("0.00")
        assert result.detail["free_units"] == 0

    def test_qty_two_half_off(self):
        items = [{"sku": "SKU-CHEESE", "unit_price": "5.00", "quantity": 2}]
        result = apply_bogo(items, OFFERS[1])
        assert result.discount_amount == Decimal("5.00")
        assert result.detail["free_units"] == 1

    def test_qty_three_one_free(self):
        items = [{"sku": "SKU-CHEESE", "unit_price": "5.00", "quantity": 3}]
        result = apply_bogo(items, OFFERS[1])
        assert result.discount_amount == Decimal("5.00")
        assert result.detail["free_units"] == 1

    def test_qty_four_two_free(self):
        items = [{"sku": "SKU-CHEESE", "unit_price": "5.00", "quantity": 4}]
        result = apply_bogo(items, OFFERS[1])
        assert result.discount_amount == Decimal("10.00")
        assert result.detail["free_units"] == 2


class TestCartFixed:
    def test_below_threshold_not_applied(self):
        result = apply_cart_fixed(Decimal("30.00"), OFFERS[2])
        assert result.discount_amount == Decimal("0.00")

    def test_at_threshold_applied(self):
        result = apply_cart_fixed(Decimal("50.00"), OFFERS[2])
        assert result.discount_amount == Decimal("5.00")

    def test_above_threshold_applied(self):
        result = apply_cart_fixed(Decimal("75.00"), OFFERS[2])
        assert result.discount_amount == Decimal("5.00")


class TestStickerEarn:
    def test_below_10_earns_zero(self):
        items = [{"sku": "SKU-MILK", "unit_price": "3.00", "quantity": 3}]
        result = apply_sticker_earn(items, Decimal("9.00"), OFFERS[3])
        assert result.stickers_earned == 0

    def test_10_earns_1(self):
        items = [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 1}]
        result = apply_sticker_earn(items, Decimal("10.00"), OFFERS[3])
        assert result.stickers_earned == 1

    def test_19_earns_1(self):
        items = [{"sku": "SKU-MILK", "unit_price": "9.50", "quantity": 2}]
        result = apply_sticker_earn(items, Decimal("19.00"), OFFERS[3])
        assert result.stickers_earned == 1

    def test_20_earns_2(self):
        items = [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 2}]
        result = apply_sticker_earn(items, Decimal("20.00"), OFFERS[3])
        assert result.stickers_earned == 2

    def test_promo_item_bonus(self):
        items = [{"sku": "SKU-ORGANIC", "unit_price": "5.00", "quantity": 2}]
        result = apply_sticker_earn(items, Decimal("10.00"), OFFERS[3])
        assert result.stickers_earned == 3

    def test_cap_at_5(self):
        items = [{"sku": "SKU-ORGANIC", "unit_price": "100.00", "quantity": 10}]
        result = apply_sticker_earn(items, Decimal("1000.00"), OFFERS[3])
        assert result.stickers_earned == 5

    def test_zero_items(self):
        items = []
        result = apply_sticker_earn(items, Decimal("0.00"), OFFERS[3])
        assert result.stickers_earned == 0


class TestProductPercentEdgeCases:
    def test_multiple_items_same_sku(self):
        items = [
            {"sku": "SKU-MILK", "unit_price": "3.50", "quantity": 1},
            {"sku": "SKU-MILK", "unit_price": "3.50", "quantity": 1},
        ]
        result = apply_product_percent(items, OFFERS[0])
        assert result.discount_amount == Decimal("0.70")
        assert result.detail["units"] == 2

    def test_large_quantity(self):
        items = [{"sku": "SKU-MILK", "unit_price": "1.00", "quantity": 100}]
        result = apply_product_percent(items, OFFERS[0])
        assert result.discount_amount == Decimal("10.00")
        assert result.detail["units"] == 100

    def test_zero_unit_price(self):
        items = [{"sku": "SKU-MILK", "unit_price": "0.00", "quantity": 5}]
        result = apply_product_percent(items, OFFERS[0])
        assert result.discount_amount == Decimal("0.00")
        assert result.detail["units"] == 5

    def test_precision_rounding(self):
        items = [{"sku": "SKU-MILK", "unit_price": "1.99", "quantity": 3}]
        result = apply_product_percent(items, OFFERS[0])
        assert result.discount_amount == Decimal("0.60")


class TestBOGOEdgeCases:
    def test_qty_five_two_free(self):
        items = [{"sku": "SKU-CHEESE", "unit_price": "5.00", "quantity": 5}]
        result = apply_bogo(items, OFFERS[1])
        assert result.discount_amount == Decimal("10.00")
        assert result.detail["free_units"] == 2

    def test_qty_ten_five_free(self):
        items = [{"sku": "SKU-CHEESE", "unit_price": "4.00", "quantity": 10}]
        result = apply_bogo(items, OFFERS[1])
        assert result.discount_amount == Decimal("20.00")
        assert result.detail["free_units"] == 5

    def test_multiple_skus_only_one_matches(self):
        items = [
            {"sku": "SKU-CHEESE", "unit_price": "5.00", "quantity": 2},
            {"sku": "SKU-MILK", "unit_price": "3.00", "quantity": 3},
        ]
        result = apply_bogo(items, OFFERS[1])
        assert result.discount_amount == Decimal("5.00")
        assert result.detail["free_units"] == 1

    def test_zero_unit_price_bogo(self):
        items = [{"sku": "SKU-CHEESE", "unit_price": "0.00", "quantity": 4}]
        result = apply_bogo(items, OFFERS[1])
        assert result.discount_amount == Decimal("0.00")
        assert result.detail["free_units"] == 2


class TestCartFixedEdgeCases:
    def test_zero_basket(self):
        result = apply_cart_fixed(Decimal("0.00"), OFFERS[2])
        assert result.discount_amount == Decimal("0.00")

    def test_just_below_threshold(self):
        result = apply_cart_fixed(Decimal("49.99"), OFFERS[2])
        assert result.discount_amount == Decimal("0.00")

    def test_just_above_threshold(self):
        result = apply_cart_fixed(Decimal("50.01"), OFFERS[2])
        assert result.discount_amount == Decimal("5.00")

    def test_massive_basket_fixed_discount(self):
        result = apply_cart_fixed(Decimal("10000.00"), OFFERS[2])
        assert result.discount_amount == Decimal("5.00")


class TestStickerEarnEdgeCases:
    def test_basket_total_zero(self):
        items = [{"sku": "SKU-MILK", "unit_price": "0.00", "quantity": 5}]
        result = apply_sticker_earn(items, Decimal("0.00"), OFFERS[3])
        assert result.stickers_earned == 0

    def test_high_value_no_promo(self):
        items = [{"sku": "SKU-MILK", "unit_price": "50.00", "quantity": 2}]
        result = apply_sticker_earn(items, Decimal("100.00"), OFFERS[3])
        assert result.stickers_earned == 5

    def test_exactly_30_earns_3(self):
        items = [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 3}]
        result = apply_sticker_earn(items, Decimal("30.00"), OFFERS[3])
        assert result.stickers_earned == 3

    def test_9_99_earns_0(self):
        items = [{"sku": "SKU-MILK", "unit_price": "9.99", "quantity": 1}]
        result = apply_sticker_earn(items, Decimal("9.99"), OFFERS[3])
        assert result.stickers_earned == 0

    def test_promo_only_no_base(self):
        items = [{"sku": "SKU-ORGANIC", "unit_price": "3.00", "quantity": 2}]
        result = apply_sticker_earn(items, Decimal("6.00"), OFFERS[3])
        assert result.stickers_earned == 2

    def test_promo_bonus_does_not_exceed_cap_with_cap(self):
        items = [{"sku": "SKU-ORGANIC", "unit_price": "10.00", "quantity": 10}]
        result = apply_sticker_earn(items, Decimal("100.00"), OFFERS[3])
        assert result.stickers_earned == 5


BURN_OFFER = {
    "offer_id": "OFFER-BURN-10",
    "type": "STICKER_BURN",
    "name": "10 Stickers = $1 Off",
    "details": {"stickers_per_dollar": 10, "max_stickers": 0},
}

BURN_OFFER_CAPPED = {
    "offer_id": "OFFER-BURN-CAPPED",
    "type": "STICKER_BURN",
    "name": "Max 5 stickers per tx",
    "details": {"stickers_per_dollar": 10, "max_stickers": 5},
}


class TestStickerBurn:
    def test_burn_with_sufficient_balance(self):
        result = apply_sticker_burn(Decimal("20.00"), 50, BURN_OFFER)
        assert result.discount_amount == Decimal("5.00")
        assert result.detail["stickers_burned"] == 50
        assert result.detail["shopper_balance_before"] == 50

    def test_no_balance_returns_zero_discount(self):
        result = apply_sticker_burn(Decimal("20.00"), 0, BURN_OFFER)
        assert result.discount_amount == Decimal("0.00")
        assert "No sticker balance available" in result.detail["reason"]

    def test_burn_capped_by_max_stickers(self):
        result = apply_sticker_burn(Decimal("20.00"), 100, BURN_OFFER_CAPPED)
        assert result.discount_amount == Decimal("0.50")
        assert result.detail["stickers_burned"] == 5

    def test_burn_capped_by_current_total(self):
        result = apply_sticker_burn(Decimal("0.50"), 50, BURN_OFFER)
        assert result.discount_amount == Decimal("0.50")
        assert result.detail["stickers_burned"] == 5

    def test_burn_negative_balance_treated_as_zero(self):
        result = apply_sticker_burn(Decimal("20.00"), -10, BURN_OFFER)
        assert result.discount_amount == Decimal("0.00")

    def test_burn_with_evaluate_and_stacking(self):
        tx = {
            "items": [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 2}],
            "store_id": "STORE1",
        }
        offers = [BURN_OFFER]
        result = evaluate(tx, offers, shopper_sticker_balance=30)
        assert result.total_discount == Decimal("3.00")
        assert result.final_total == Decimal("17.00")
        assert result.stickers_burned == 30

    def test_evaluate_returns_burned_stickers_in_output(self):
        tx = {
            "items": [{"sku": "SKU-MILK", "unit_price": "5.00", "quantity": 1}],
        }
        result = evaluate(tx, [BURN_OFFER], shopper_sticker_balance=10)
        assert result.stickers_burned == 10
        assert result.total_discount == Decimal("1.00")


CAMPAIGN_OFFER = {
    "offer_id": "OFFER-CAMPAIGN-TEST",
    "type": "STICKER_CAMPAIGN",
    "name": "Wednesday Double Stickers",
    "details": {
        "weekday_bonus": {"wednesday": 2},
        "min_basket": 5.00,
        "store_ids": ["STORE1"],
        "bonus_stickers": 1,
    },
}

WEDNESDAY = datetime(2026, 6, 3, 10, 0, 0)  # Jun 3 2026 is a Wednesday
MONDAY = datetime(2026, 6, 1, 10, 0, 0)     # Jun 1 2026 is a Monday


class TestStickerCampaign:
    def test_qualifies_on_wednesday(self):
        items = [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 2}]
        result = apply_sticker_campaign(items, Decimal("20.00"), "STORE1", WEDNESDAY, CAMPAIGN_OFFER)
        assert result.stickers_earned == 5
        assert result.detail["weekday"] == "wednesday"
        assert result.detail["multiplier"] == 2
        assert result.detail["bonus_stickers"] == 1

    def test_flat_bonus_applies_on_non_campaign_weekday(self):
        items = [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 2}]
        result = apply_sticker_campaign(items, Decimal("20.00"), "STORE1", MONDAY, CAMPAIGN_OFFER)
        assert result.stickers_earned == 3
        assert result.detail["weekday"] == "monday"
        assert result.detail["multiplier"] == 1
        assert result.detail["bonus_stickers"] == 1

    def test_no_campaign_without_weekday_and_without_bonus(self):
        no_bonus_offer = {
            "offer_id": "OFFER-CAMPAIGN-ONLY-WEEKDAY",
            "type": "STICKER_CAMPAIGN",
            "name": "Weekday Only",
            "details": {"weekday_bonus": {"wednesday": 3}, "min_basket": 0, "store_ids": [], "bonus_stickers": 0},
        }
        items = [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 1}]
        result = apply_sticker_campaign(items, Decimal("10.00"), "", MONDAY, no_bonus_offer)
        assert result.stickers_earned == 0

    def test_campaign_without_weekday_and_without_bonus_on_right_day(self):
        no_bonus_offer = {
            "offer_id": "OFFER-CAMPAIGN-ONLY-WEEKDAY",
            "type": "STICKER_CAMPAIGN",
            "name": "Weekday Only",
            "details": {"weekday_bonus": {"wednesday": 3}, "min_basket": 0, "store_ids": [], "bonus_stickers": 0},
        }
        items = [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 1}]
        result = apply_sticker_campaign(items, Decimal("10.00"), "", WEDNESDAY, no_bonus_offer)
        assert result.stickers_earned == 3

    def test_below_min_basket(self):
        items = [{"sku": "SKU-MILK", "unit_price": "2.00", "quantity": 1}]
        result = apply_sticker_campaign(items, Decimal("2.00"), "STORE1", WEDNESDAY, CAMPAIGN_OFFER)
        assert result.stickers_earned == 0
        assert "below minimum" in result.detail["reason"]

    def test_wrong_store(self):
        items = [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 2}]
        result = apply_sticker_campaign(items, Decimal("20.00"), "STORE99", WEDNESDAY, CAMPAIGN_OFFER)
        assert result.stickers_earned == 0
        assert "not in campaign stores" in result.detail["reason"]

    def test_edge_min_basket_exact(self):
        items = [{"sku": "SKU-MILK", "unit_price": "5.00", "quantity": 1}]
        result = apply_sticker_campaign(items, Decimal("5.00"), "STORE1", WEDNESDAY, CAMPAIGN_OFFER)
        assert result.stickers_earned == 1
        assert result.detail["base_earn"] == 0

    def test_integration_with_evaluate(self):
        tx = {
            "items": [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 2}],
            "store_id": "STORE1",
            "timestamp": WEDNESDAY,
        }
        result = evaluate(tx, [CAMPAIGN_OFFER])
        assert result.stickers_earned == 5
        assert len(result.applied_offers) == 1
        assert result.applied_offers[0].offer_id == "OFFER-CAMPAIGN-TEST"

    def test_campaign_not_applied_without_offer(self):
        tx = {
            "items": [{"sku": "SKU-MILK", "unit_price": "10.00", "quantity": 2}],
            "store_id": "STORE1",
            "timestamp": WEDNESDAY,
        }
        result = evaluate(tx, [])
        assert result.stickers_earned == 0
        assert len(result.applied_offers) == 0


class TestEvaluate:
    def test_no_matching_offers(self):
        tx = {
            "items": [{"sku": "SKU-UNKNOWN", "unit_price": "5.00", "quantity": 1}],
        }
        offers = [OFFERS[0], OFFERS[1], OFFERS[2], OFFERS[3]]
        result = evaluate(tx, offers)
        assert result.basket_total == Decimal("5.00")
        assert result.total_discount == Decimal("0.00")
        assert result.final_total == Decimal("5.00")
        assert result.stickers_earned == 0
        assert len(result.applied_offers) == 0

    def test_all_offer_types_combined(self):
        tx = {
            "items": [
                {"sku": "SKU-MILK", "unit_price": "3.50", "quantity": 2},
                {"sku": "SKU-CHEESE", "unit_price": "5.00", "quantity": 3},
                {"sku": "SKU-ORGANIC", "unit_price": "8.00", "quantity": 1},
            ],
        }
        offers = [OFFERS[0], OFFERS[1], OFFERS[2], OFFERS[3]]
        result = evaluate(tx, offers)
        assert result.basket_total == Decimal("30.00")
        assert result.total_discount == Decimal("5.70")
        assert result.final_total == Decimal("24.30")
        assert result.stickers_earned == 4
        assert len(result.applied_offers) == 3

    def test_cart_fixed_applied_when_over_50(self):
        tx = {
            "items": [
                {"sku": "SKU-MILK", "unit_price": "30.00", "quantity": 2},
            ],
        }
        offers = [OFFERS[2]]
        result = evaluate(tx, offers)
        assert result.basket_total == Decimal("60.00")
        assert result.total_discount == Decimal("5.00")
        assert result.final_total == Decimal("55.00")

    def test_evaluate_return_type(self):
        tx = {
            "items": [{"sku": "SKU-MILK", "unit_price": "3.50", "quantity": 1}],
        }
        offers = [OFFERS[0], OFFERS[3]]
        result = evaluate(tx, offers)
        assert isinstance(result, EngineOutput)
        assert isinstance(result.basket_total, Decimal)
        assert isinstance(result.total_discount, Decimal)
        assert isinstance(result.final_total, Decimal)
        assert isinstance(result.stickers_earned, int)

    def test_empty_offers_list(self):
        tx = {
            "items": [{"sku": "SKU-MILK", "unit_price": "3.50", "quantity": 2}],
        }
        result = evaluate(tx, {})
        assert result.basket_total == Decimal("7.00")
        assert result.total_discount == Decimal("0.00")
        assert result.final_total == Decimal("7.00")
        assert result.stickers_earned == 0
        assert len(result.applied_offers) == 0

    def test_empty_items(self):
        tx = {"items": []}
        offers = [OFFERS[0], OFFERS[1], OFFERS[2], OFFERS[3]]
        result = evaluate(tx, offers)
        assert result.basket_total == Decimal("0.00")
        assert result.total_discount == Decimal("0.00")
        assert result.final_total == Decimal("0.00")
        assert result.stickers_earned == 0
        assert len(result.applied_offers) == 0

    def test_offers_with_zero_result_not_in_applied(self):
        tx = {
            "items": [{"sku": "SKU-CHEESE", "unit_price": "5.00", "quantity": 1}],
        }
        offers = [OFFERS[1], OFFERS[3]]
        result = evaluate(tx, offers)
        assert result.total_discount == Decimal("0.00")
        assert result.stickers_earned == 0
        assert len(result.applied_offers) == 0
