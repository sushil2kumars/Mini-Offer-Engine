from django.urls import path

from . import views

urlpatterns = [
    path("redeem/", views.redeem_stickers, name="api_shopper_redeem"),
    path("<str:shopper_id>/", views.shopper_detail, name="api_shopper_detail"),
]
