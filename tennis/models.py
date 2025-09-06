from django.db import models

# Create your models here.

class Player(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    def __str__(self):
        return self.first_name

"""class Tournament(models.Model):
    players = models.ForeignKey(Player, on_delete=models.CASCADE)
    tournament_name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    level = models.CharField(max_length=100)

    def __str__(self):
        return self.tournament_name

class Match(models.Model):
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE)
    player2 = models.ForeignKey(Player, on_delete=models.CASCADE)
    winner = models.ForeignKey(Player, on_delete=models.CASCADE)
    loser = models.ForeignKey(Player, on_delete=models.CASCADE)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.player1} vs {self.player2}"""

