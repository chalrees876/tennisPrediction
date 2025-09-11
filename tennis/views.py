import base64

from django.http.response import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls.base import reverse

from .models import Player, Tournament, Match, MatchForm
import src.trainingModel as model


def home(request):
    form = MatchForm(request.GET or None)
    selected_player = None
    if form.is_valid():
        selected_player = form.cleaned_data['player']
        return redirect('single_player', pk=selected_player.pk)
    return render(request, 'tennis/home.html', context={'form': form})


# Create your views here.
def all_players(request):
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
        'db': pipeline['db64'],
    }

    return render(request, 'tennis/ml_results.html', context=context)

# Create your views here.
def single_player(request, pk):
    players = Player.objects.all()
    tournaments = Tournament.objects.all()
    matches = Match.objects.all()
    name = None
    name = get_object_or_404(Player, pk=pk).name
    if name:
        pipeline = model.run_pipeline('~/WGU/tennisPrediction/data/matches.csv', name)
    else:
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
        'db': pipeline['db64'],
        'player': name,
    }

    if name:
        return render(request, 'tennis/player_result.html', context=context)
    else:
        return render(request, 'tennis/ml_results.html', context=context)

def player_search(request):
    query = request.GET.get('search', '').strip()
    if not query:
        return JsonResponse({'results': []})
    qs = Player.objects.filter(name__icontains=query).order_by('name')[:20]
    return JsonResponse({
        'results': [{'id': p.id, 'text': p.name, 'url': reverse('single_player', kwargs={'pk': p.id})} for p in qs]
    })
