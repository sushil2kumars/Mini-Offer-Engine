"""Template view for the system-wide statistics portal."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum
from django.views.generic import TemplateView

from looplink.shoppers.models import ShopperProfile, StickerRedemption
from looplink.transactions.models import AppliedOffer, Transaction

ZERO = Decimal("0.00")
CENTS = Decimal("0.01")


class StatsView(TemplateView):
    """Aggregate platform statistics for the operations dashboard."""

    template_name = "stats/stats.html"

    def get_context_data(self, **kwargs) -> dict:
        """Build the full statistics context for the template."""
        context = super().get_context_data(**kwargs)

        tx_count = Transaction.objects.count()
        shopper_count = ShopperProfile.objects.count()
        total_stickers = Transaction.objects.aggregate(total=Sum("stickers_earned"))["total"] or 0

        total_revenue_agg = (
            Transaction.objects.aggregate(total=Sum("final_total"))["total"] or ZERO
        ).quantize(CENTS)

        total_discount_agg = (
            AppliedOffer.objects.aggregate(total=Sum("discount_amount"))["total"] or ZERO
        ).quantize(CENTS)

        stickers_per_store = list(
            Transaction.objects.values("store_id")
            .annotate(total=Sum("stickers_earned"))
            .order_by("-total")
        )

        discount_per_offer = list(
            AppliedOffer.objects.values("offer_id", "offer_name")
            .annotate(total_discount=Sum("discount_amount"), times_applied=Count("id"))
            .order_by("-total_discount")
        )

        redemption_count = StickerRedemption.objects.count()
        stickers_redeemed = StickerRedemption.objects.aggregate(total=Sum("stickers_cost"))["total"] or 0

        avg_discount = (total_discount_agg / tx_count).quantize(CENTS) if tx_count else ZERO
        avg_stickers = round(total_stickers / tx_count, 2) if tx_count else 0

        for offer in discount_per_offer:
            offer["total_discount"] = offer["total_discount"].quantize(CENTS)

        context["tx_count"] = tx_count
        context["shopper_count"] = shopper_count
        context["total_stickers"] = total_stickers
        context["total_revenue"] = total_revenue_agg
        context["total_discount"] = total_discount_agg
        context["avg_discount"] = avg_discount
        context["avg_stickers"] = avg_stickers
        context["stickers_per_store"] = stickers_per_store
        context["discount_per_offer"] = discount_per_offer
        context["redemption_count"] = redemption_count
        context["stickers_redeemed"] = stickers_redeemed
        return context
