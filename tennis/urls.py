from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="ml"),
    path('search/', views.player_search, name="player_search")
]