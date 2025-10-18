from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.fields.related import ForeignKey
from django.urls import reverse
from django import forms
# Create your models here.

class Player(models.Model):
    name = models.CharField(max_length=100, unique=True)
    age = models.IntegerField()
    ranking = models.FloatField()



    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("tennis-detail", args=[str(self.id)])

class PlayerElo(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    elo = models.FloatField()
    elo_ranking = models.FloatField()
    h_elo = models.FloatField()
    h_elo_ranking = models.FloatField()
    c_elo = models.FloatField()
    c_elo_ranking = models.FloatField()
    g_elo = models.FloatField()
    g_elo_ranking = models.FloatField()
    peak_elo = models.FloatField()

class PlayerPressureStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    break_p_saved_pctg = models.FloatField() # % Break Points Saved
    deciding_s_w_pctg = models.FloatField() # % Deciding Sets Won
    tb_w_pctg = models.FloatField() # % Tie Breaks Won
    under_pressure_rating = models.FloatField() # Under Pressure Rating

class PlayerReturnStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    fsr_p_w_pctg = models.FloatField()  # % 1st Serve Return Points Won
    ssr_p_w_pctg = models.FloatField()  # % 2nd Serve Return Points Won
    break_p_w_pctg = models.FloatField()  # % Break Points Converted
    return_g_w_pctg = models.FloatField()  # % Return Games Won
    return_rating = models.FloatField()  # Return Rating

class PlayerServeStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    fsp = models.FloatField()  # % 1st serve
    fs_p_w_pctg = models.FloatField()  # % 1st Serve Points Won
    ss_p_w_pctg = models.FloatField()  # % 2nd Serve Points Won
    s_g_w_pctg = models.FloatField()  # % Service Games Won
    a_m = models.FloatField()  # Avg. Aces/ Match
    df_m = models.FloatField()  # Avg. Double Faults/Match
    sr = models.FloatField()  # Serve Rating


class Tournament(models.Model):
    name = models.CharField(max_length=100)
    year = models.IntegerField()

    class Meta:
        unique_together = ("name", "year")

    def __str__(self):
        return self.name


# TODO
class Match(models.Model):
    player = ForeignKey(Player, on_delete=models.CASCADE)
    tournament = ForeignKey(Tournament, on_delete=models.CASCADE)
    surface = models.FloatField()
    round = models.CharField(max_length=50)
    opponent = models.ForeignKey(Player, on_delete=models.CASCADE)
    score = models.CharField(max_length=50)

    def clean(self):
        if self.player1 == self.player2:
            raise ValidationError("Player 1 and Player 2 must be different")
        if self.winner not in [self.player1, self.player2]:
            raise ValidationError("Winner must be player1 or player2")
        if self.loser not in [self.player1, self.player2]:
            raise ValidationError("Loser must be player1 or player2")
        if self.winner == self.loser:
            raise ValidationError("winner cannot be loser")

    def __str__(self):
        return f"{self.player1} vs {self.player2}"

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


