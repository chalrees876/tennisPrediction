from django.urls import path
from . import views

app_name = "tennis"
urlpatterns = [
    path("", views.home, name="home"),
    path("player/<int:player_id>/", views.player_page, name="player_page"),
    path("match/<int:match_id>/", views.match_page, name="match_page"),
    path("h2h/<int:match_id>/", views.h_to_h_page, name="h_to_h_page"),
]