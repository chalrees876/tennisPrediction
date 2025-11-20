from typing import Optional
from django.db import models
from django_enum import EnumField


class Player(models.Model):
    name = models.CharField(max_length=100, unique=True)
    age = models.IntegerField(null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    # API player_key
    key = models.IntegerField(primary_key=True)

    def __str__(self):
        if self.age:
            return f"{self.name} ({self.age})"
        return self.name


class PlayerRanking(models.Model):
    class League(models.TextChoices):
        ATP = "ATP", "ATP"
        WTA = "WTA", "WTA"

    class Movement(models.TextChoices):
        UP = "up", "UP"
        DOWN = "down", "DOWN"
        SAME = "same", "SAME"

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    ranking = models.IntegerField(null=True, blank=True)
    league = EnumField(League, default=None, null=True, blank=True)
    movement = EnumField(Movement, default=None, null=True, blank=True)
    points = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.player.name} {self.league} #{self.ranking} ({self.points} pts)"


# tennis/models.py

class Tournament(models.Model):
    """
    One row per tournament_key (per event type).
    Example:
      tournament_key=2131, name='Acapulco', event_type_type='Atp Singles'
    """

    tournament_key = models.IntegerField(unique=True)  # from API "tournament_key"
    name = models.CharField(max_length=100)

    # Optional event-type metadata (from get_tournaments / fixtures)
    event_type_key = models.IntegerField(null=True, blank=True)
    event_type_type = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PlayerMatch(models.Model):
    """
    One row per event (match).
    Ties directly to api-tennis "event_*" fields.
    """
    # event_key from API
    key = models.IntegerField(primary_key=True)

    date = models.DateField(null=False)
    time = models.TimeField(null=False)

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)

    # "tournament_round" from the API, e.g. "US Open - 1/64-finals" or "Athens - Final"
    round = models.CharField(max_length=100)

    # Surface (you can later map actual surfaces if API provides it)
    surface = models.CharField(max_length=20, default="Not Specified", blank=True)

    # Best-of-X sets (3 or 5 usually). May be null if unknown.
    best_of = models.IntegerField(null=True, blank=True)

    # Player roles as given by API (First Player / Second Player)
    first_player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="matches_as_first",
    )
    second_player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="matches_as_second",
    )

    # Winner of the match
    winner = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matches_won",
    )

    # Simple textual outcome
    final_result = models.CharField(
        max_length=20, blank=True
    )  # "2 - 1", "3 - 1", etc. (event_final_result)
    score_line = models.CharField(
        max_length=100, blank=True
    )  # "6-1 6-7(5) 6-2 6-1" (parsed from scores[])

    # Metadata about the event
    event_type = models.CharField(
        max_length=50, blank=True
    )  # "Atp Singles" (event_type_type)
    status = models.CharField(
        max_length=20, blank=True
    )  # "Finished", "Not Started", etc. (event_status)
    event_serve = models.CharField(
        max_length=20, blank=True
    )  # event_serve if used (e.g., who served first)

    is_live = models.BooleanField(default=False)
    is_qualification = models.BooleanField(default=False)

    # Rich data kept as JSON for flexibility. Not every match will have these.
    point_by_point = models.JSONField(null=True, blank=True)  # pointbypoint[]
    statistics_raw = models.JSONField(null=True, blank=True)  # raw statistics[] from API
    raw_scores = models.JSONField(null=True, blank=True)      # scores[]
    odds_raw = models.JSONField(null=True, blank=True)


    class Meta:
        ordering = ["-date", "-time"]

    def __str__(self):
        if self.winner_id:
            loser = (
                self.second_player if self.winner_id == self.first_player_id
                else self.first_player
            )
            if self.score_line:
                return f"{self.winner.name} d. {loser.name} {self.score_line} @ {self.tournament}"
            return f"{self.winner.name} d. {loser.name} @ {self.tournament}"
        return f"{self.first_player.name} vs {self.second_player.name} @ {self.tournament}"

    # ---------- generic helpers for stats (Option 1) ----------

    def get_stat(self, player, period: str, category: str, name: str) -> Optional["MatchStatistic"]:
        """
        Example:
        match.get_stat(djokovic, "match", "Service", "1st Serve Points Won")
        """
        return self.stats.filter(
            player=player,
            period=period,
            category=category,
            name=name,
        ).first()

    def get_stat_value(
        self,
        player,
        period: str,
        category: str,
        name: str,
        prefer_percent: bool = True,
    ) -> Optional[float]:
        """
        Convenience wrapper that returns the numeric value for a stat.
        - If prefer_percent=True and value_percent is available, returns that.
        - Else tries value_number.
        - Returns None if not found.
        """
        stat = self.get_stat(player, period, category, name)
        if not stat:
            return None
        if prefer_percent and stat.value_percent is not None:
            return stat.value_percent
        if stat.value_number is not None:
            return stat.value_number
        return None


class MatchStatistic(models.Model):
    """
    Parsed per-match statistics (optional – only when the API provides them).
    Kept generic so you don't hard-code fields like 'fs_win_pctg' in the DB.
    """

    class Period(models.TextChoices):
        MATCH = "match", "Match"
        SET1 = "set1", "Set 1"
        SET2 = "set2", "Set 2"
        SET3 = "set3", "Set 3"
        SET4 = "set4", "Set 4"
        SET5 = "set5", "Set 5"

    class Category(models.TextChoices):
        SERVICE = "Service", "Service"
        RETURN = "Return", "Return"
        POINTS = "Points", "Points"
        GAMES = "Games", "Games"

    match = models.ForeignKey(
        PlayerMatch,
        on_delete=models.CASCADE,
        related_name="stats",
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="match_stats",
    )

    # stat_period, stat_type, stat_name from API
    period = models.CharField(
        max_length=10,
        choices=Period.choices,
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
    )
    name = models.CharField(max_length=50)  # e.g. "1st Serve Points Won"

    # Values from API
    value_raw = models.CharField(
        max_length=20, blank=True
    )  # original "63%", "6", "0", etc.

    # Parsed versions for easier querying
    value_percent = models.FloatField(null=True, blank=True)  # 63.0
    value_number = models.FloatField(null=True, blank=True)   # 6.0, 100.0, etc.

    stat_won = models.IntegerField(null=True, blank=True)
    stat_total = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("match", "player", "period", "category", "name")

    def __str__(self):
        return f"{self.match.key} - {self.player.name} - {self.period} - {self.name}: {self.value_raw}"