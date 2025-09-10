import base64

from django.http.response import JsonResponse
from django.shortcuts import render
from .models import Player, Tournament, Match, MatchForm
import src.trainingModel as model



# Create your views here.
def home(request):
    players = Player.objects.all()
    tournaments = Tournament.objects.all()
    matches = Match.objects.all()
    pipeline = model.run_pipeline('~/WGU/tennisPrediction/data/matches.csv')
    form = MatchForm()

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
        'form': form,
    }

    return render(request, 'tennis/ml_results.html', context=context)

def player_search(request):
    query = request.GET.get('search', '').strip()
    if not query:
        return JsonResponse({'results': []})
    qs = Player.objects.filter(name__icontains=query).order_by('name')[:20]
    return JsonResponse({
        'results': [{'id': p.id, 'text': p.name} for p in qs]
    })
