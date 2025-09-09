from django.shortcuts import render
from .models import Player, Tournament, Match
from django.views.generic import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy


# Create your views here.
def home(request):
    players = Player.objects.all()
    tournaments = Tournament.objects.all()
    matches = Match.objects.all()
    return render(request, 'tennis/home.html', {'players': players, 'tournaments': tournaments, 'matches': matches})

