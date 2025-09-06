from django.shortcuts import render

from .models import Player


# Create your views here.
def home(request):
    players = Player.objects.all()
    return render(request, 'tennis/home.html', {'players': players})