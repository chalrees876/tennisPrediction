import base64

from django.shortcuts import render
from .models import Player, Tournament, Match
import src.trainingModel as model
from django.views.generic import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy


# Create your views here.
def home(request):
    players = Player.objects.all()
    tournaments = Tournament.objects.all()
    matches = Match.objects.all()
    pipeline = model.run_pipeline('~/WGU/tennisPrediction/data/matches.csv')

    context = {
        'players': players,
        'tournaments': tournaments,
        'matches': matches,
        'cnf_matrix': pipeline['confusion_matrix'],
        'heatmap': pipeline['heatmap_b64'],
        'cr': pipeline['classification_report'],
        'auc': pipeline['auc_b64'],
        'scatter': pipeline['scatter_b64'],
        'fs_sigmoid': pipeline['fs_sigmoid64'],
        'df_sigmoid': pipeline['df_sigmoid64'],
    }

    return render(request, 'tennis/ml_results.html', context=context)
