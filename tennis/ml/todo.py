import os, sys, django
import pandas as pd
from itertools import chain
from django.db.models import F, Case, When, Value, BooleanField

# If you're running this outside manage.py, make sure Django is bootstrapped:
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_dev")
django.setup()

def two_rows_per_match_df():
    from tennis.models import Match

    # Player 1 rows
    p1_qs = (
        Match.objects
        .select_related("player1", "winner")
        .annotate(
            match=F("match_id"),
            player=F("player1__name"),
            fsp=F("p1_first_serve_pctg"),
            ssp=F("p1_second_serve_pctg"),
            df =F("p1_double_faults"),
            is_winner=Case(
                When(winner=F("player1"), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        .values("match", "player", "fsp", "ssp", "df", "is_winner")
    )

    # Player 2 rows
    p2_qs = (
        Match.objects
        .select_related("player2", "winner")
        .annotate(
            match=F("match_id"),
            player=F("player2__name"),
            fsp=F("p2_first_serve_pctg"),
            ssp=F("p2_second_serve_pctg"),
            df =F("p2_double_faults"),
            is_winner=Case(
                When(winner=F("player2"), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        .values("match", "player", "fsp", "ssp", "df", "is_winner")
    )

    combined = list(chain(p1_qs, p2_qs))
    df = pd.DataFrame(combined, columns=["match","player","fsp","ssp","df","is_winner"])
    df = df.sort_values(["match", "is_winner"], ascending=[True, False]).reset_index(drop=True)
    print(df)
    return df

two_rows_per_match_df()