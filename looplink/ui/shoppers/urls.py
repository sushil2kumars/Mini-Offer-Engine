from django.urls import path

from . import views

urlpatterns = [
    path("", views.ShopperSearchView.as_view(), name="shoppers_search"),
    path("<str:shopper_id>/", views.ShopperDetailView.as_view(), name="shoppers_portal_detail"),
]
