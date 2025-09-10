from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django import forms
# Create your models here.

class Player(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("tennis-detail", args=[str(self.id)])

class Tournament(models.Model):
    name = models.CharField(max_length=100)
    year = models.IntegerField()

    class Meta:
        unique_together = ("name", "year")

    def __str__(self):
        return self.name

class Match(models.Model):
    match_id = models.TextField(max_length=100)
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="player1")
    player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="player2")
    winner = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="winner")
    loser = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="loser")
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="matches")
    round = models.TextField(max_length=50)
    p1_first_serve_pctg = models.FloatField()
    p2_first_serve_pctg = models.FloatField()
    p1_second_serve_pctg = models.FloatField()
    p2_second_serve_pctg = models.FloatField()
    p1_double_faults = models.IntegerField()
    p2_double_faults = models.IntegerField()

    class Meta:
        unique_together = ("player1", "player2", "tournament")

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
        queryset=Player.objects.none(),
        widget=forms.Select(attrs={'id': 'player_select'})
    )


