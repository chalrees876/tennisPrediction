from django.urls import path
from . import views

app_name = "tennis"
urlpatterns = [
    path("", views.home, name="home"),
    path("<int:match_id>/", views.match_odds, name="match_odds")
]