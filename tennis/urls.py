from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path('search/', views.player_search, name="player_search"),
    path('all_players/', views.all_players, name="all_players"),
    path('player/<int:pk>/', views.single_player, name="single_player"),
]