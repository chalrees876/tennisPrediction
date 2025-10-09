import base64
from pathlib import Path

from django.core.cache import cache
from django.http.response import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls.base import reverse
from django.http import HttpResponseServerError
from .models import Player, Tournament, Match, MatchForm
from .ml.training import run_pipeline
import logging
logger = logging.getLogger("tennis")

def home(request):
    form = MatchForm(request.GET or None)
    selected_player = None
    if form.is_valid():
        selected_player = form.cleaned_data['player']
        return redirect('single_player', pk=selected_player.pk)
    return render(request, 'tennis/home.html', context={'form': form})


# Create your views here.
def all_players(request):
    try:
        form = MatchForm(request.GET or None)

        # Redirect to single player if chosen
        if form.is_valid():
            selected_player = form.cleaned_data['player']
            return redirect('single_player', pk=selected_player.pk)

        # Don’t load thousands of rows unnecessarily.
        # The Select2 on the page will search via AJAX anyway.
        players = Player.objects.none()            # <- empty list for initial render
        tournaments = Tournament.objects.order_by('-year')[:25]  # show a small recent slice
        matches = Match.objects.order_by('-id')[:25]             # small slice for the page

        # Try to reuse a cached ML result; recompute at most every 6 hours.
        pipeline = cache.get('ml_dashboard_v1')
        if pipeline is None:
            try:
                pipeline = run_pipeline()
                cache.set('ml_dashboard_v1', pipeline, 6 * 60 * 60)  # 6 hours
            except Exception:
                logger.exception("run_pipeline failed")
                pipeline = None

        context = {
            'players': players,
            'tournaments': tournaments,
            'matches': matches,
            'form': form,
        }

        # Only add ML charts if we have them
        if pipeline:
            context.update({
                'cnf_matrix': pipeline.get('confusion_matrix'),
                'heatmap': pipeline.get('heatmap_b64'),
                'cr': pipeline.get('classification_report'),
                'auc': pipeline.get('auc_b64'),
                'scatter': pipeline.get('scatter_b64'),
                'fs_sigmoid': pipeline.get('fs_sigmoid64'),
                'df_sigmoid': pipeline.get('df_sigmoid64'),
                'db': pipeline.get('db64'),
            })

        return render(request, 'tennis/ml_results.html', context=context)

    except Exception:
        logger.exception('all_players failed')
        return HttpResponseServerError('Something went wrong')

# Create your views here.
def single_player(request, pk):
    form = MatchForm(request.GET or None)
    selected_player = None
    if form.is_valid():
        selected_player = form.cleaned_data['player']
        return redirect('single_player', pk=selected_player.pk)
    players = Player.objects.all()
    tournaments = Tournament.objects.all()
    matches = Match.objects.all()
    name = None
    name = get_object_or_404(Player, pk=pk).name
    if name:
        pipeline = run_pipeline(name)
    else:
        pipeline = run_pipeline()
    if pipeline:
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
            'form': form,
        }

        if name:
            return render(request, 'tennis/player_result.html', context=context)
        else:
            return render(request, 'tennis/ml_results.html', context=context)
    else:
        return render(request, 'tennis/error.html', context={'name': name})

def player_search(request):
    query = request.GET.get('search', '').strip()
    if not query:
        return JsonResponse({'results': []})
    qs = Player.objects.filter(name__icontains=query).order_by('name')[:20]
    return JsonResponse({
        'results': [{'id': p.id, 'text': p.name, 'url': reverse('single_player', kwargs={'pk': p.id})} for p in qs]
    })
