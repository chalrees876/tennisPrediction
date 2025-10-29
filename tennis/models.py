from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.fields.related import ForeignKey
from django.urls import reverse
from django import forms
# Create your models here.

class Player(models.Model):
    name = models.CharField(max_length=100, unique=True)
    age = models.IntegerField(null=True, blank=True)
    ranking = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}"

class PlayerElo(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    elo = models.FloatField()
    elo_ranking = models.IntegerField()
    h_elo = models.FloatField()
    h_elo_ranking = models.IntegerField()
    c_elo = models.FloatField()
    c_elo_ranking = models.IntegerField()
    g_elo = models.FloatField()
    g_elo_ranking = models.IntegerField()
    peak_elo = models.FloatField()

class PlayerServeStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    matches = models.IntegerField()
    matches_w_pctg = models.FloatField()
    service_p_w_pctg = models.FloatField()
    service_p_in_w_pctg = models.FloatField()
    aces = models.IntegerField()
    aces_pctg = models.FloatField()
    dfs = models.IntegerField()
    df_pctg = models.FloatField()
    df_per_2nd = models.FloatField()
    fs_pctg = models.FloatField()
    fs_w_pctg = models.FloatField()
    ss_w_pctg = models.FloatField()
    ss_w_pctg_less_df = models.FloatField()
    hold_pctg = models.FloatField()
    pts_per_sg = models.FloatField()
    pts_l_per_sg = models.FloatField()

class PlayerReturnStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    matches = models.IntegerField()
    return_p_w_pctg = models.FloatField()
    return_p_in_w_pctg = models.FloatField()
    ace_pctg_against = models.FloatField()
    df_pctg_against = models.FloatField()
    fs_r_p_w_pctg = models.FloatField()
    ss_r_p_w_pctg = models.FloatField()
    break_pctg = models.FloatField()
    pts_per_rg = models.FloatField()
    pts_w_per_rg = models.FloatField()
    med_opp_ranking = models.FloatField()
    mean_opp_ranking = models.FloatField()

class PlayerBreakStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    matches = models.IntegerField()
    break_p_conv_pctg = models.FloatField()
    bp_conv = models.FloatField()
    bp_chances = models.FloatField()
    bp_per_g = models.FloatField()
    bp_per_s = models.FloatField()
    bp_per_m = models.FloatField()
    break_per_s = models.FloatField()
    break_per_m = models.FloatField()
    bp_saved_pctg = models.FloatField()
    bp_saved = models.IntegerField()
    bp_faced = models.IntegerField()
    bp_faced_per_g = models.FloatField()
    bp_faced_per_s = models.FloatField()
    bp_faced_per_m = models.FloatField()
    sg_l_per_s = models.FloatField()
    sg_l_per_m = models.FloatField()

class PlayerMoreStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    matches = models.IntegerField()
    dominance_ratio = models.FloatField()
    points = models.IntegerField()
    p_w_pctg = models.FloatField()
    tbs = models.IntegerField()
    tb_wl = models.CharField(max_length=100)
    tb_w_pctg = models.FloatField()
    tb_per_s = models.FloatField()
    sets = models.IntegerField()
    set_wl = models.CharField(max_length=100)
    set_w_pctg = models.FloatField()
    games = models.IntegerField()
    game_wl = models.CharField(max_length=100)
    game_w_pctg = models.FloatField()
    time_per_match = models.CharField(max_length=100)
    min_per_s = models.FloatField()
    sec_per_p = models.FloatField()

class Tournament(models.Model):
    name = models.CharField(max_length=100)
    year = models.IntegerField()

    class Meta:
        unique_together = ("name", "year")

    def __str__(self):
        return f"{self.name}"

class PlayerMatch(models.Model):
    date = models.DateField(default=None)
    player = ForeignKey(Player, on_delete=models.CASCADE, related_name="matches_as_player")
    tournament = ForeignKey(Tournament, on_delete=models.CASCADE)
    surface = models.CharField(max_length=20, default="Not Specified")
    round = models.CharField(max_length=50)
    rank = models.IntegerField()
    opponent_rank = models.IntegerField()
    opponent = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="matches_as_opponent")
    score = models.CharField(max_length=50)
    won = models.BooleanField(default=None)
    completed = models.BooleanField(blank=True, null=True)

    def __str__(self):
        return f"{self.player.name} v {self.opponent.name} - {self.tournament} {self.date}"


class PlayerMatchServeStats(models.Model):
    match = models.ForeignKey(PlayerMatch, on_delete=models.CASCADE)
    dominance_ratio = models.FloatField()
    ace_pctg = models.FloatField()
    df_pctg = models.FloatField()
    fs_pctg = models.FloatField()
    fs_w_pctg = models.FloatField()
    ss_w_pctg = models.FloatField()
    bp_saved = models.IntegerField()
    bp_faced = models.IntegerField()
    time = models.CharField(max_length=50)

class PlayerMatchReturnStats(models.Model):
    match = models.ForeignKey(PlayerMatch, on_delete=models.CASCADE)
    dominance_ratio = models.FloatField()
    total_p_w = models.FloatField()
    return_p_w = models.FloatField()
    v_ace_pctg = models.FloatField()
    v_fs_pctg = models.FloatField()
    v_ss_pctg = models.FloatField()
    bp_conv = models.IntegerField()
    bp_chances = models.IntegerField()
    time = models.CharField(max_length=50)

class PlayerMatchKeyGames(models.Model):
    match = models.ForeignKey(PlayerMatch, on_delete=models.CASCADE)
    bp_games = models.CharField(max_length=100)
    bp_conv = models.CharField(max_length=100)
    break_back = models.CharField(max_length=100)
    g_with_bp = models.CharField(max_length=100)
    hold_per_g_with_bp = models.CharField(max_length=100)
    consolidation_pctg = models.FloatField()
    serve_for_s = models.CharField(max_length=100)
    serve_stay_s = models.CharField(max_length=100)
    serve_for_m = models.CharField(max_length=100)
    serve_stay_m = models.CharField(max_length=100)

class PlayerPointByPointStats(models.Model):
    match = models.ForeignKey(PlayerMatch, on_delete=models.CASCADE)
    balanced_leverage_ration = models.FloatField()
    dominance_ratio_plus = models.FloatField()
    excitement_index = models.FloatField()
    comeback_factor = models.FloatField()
    deuce_ace_pctg = models.FloatField()
    deuce_s_w_pctg = models.FloatField()
    ad_ace_pctg = models.FloatField()
    ad_s_w_pctg = models.FloatField()
    deuce_r_w_pctg = models.FloatField()
    ad_r_w_pctg = models.FloatField()

class MatchForm(forms.Form):
    player = forms.ModelChoiceField(
        queryset=Player.objects.all(),
        widget=forms.Select(attrs={'id': 'player_select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If the form is bound (GET), include the submitted choice in the queryset
        if self.is_bound:
            raw = self.data.get(self.add_prefix("player")) or self.data.get("player")
            if raw:
                self.fields["player"].queryset = Player.objects.filter(pk=raw)


