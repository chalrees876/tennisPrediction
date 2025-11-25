from typing import Optional

from django.db import transaction

from tennis.services.api_client import TennisAPIClient
from tennis.services.matches import upsert_match_from_fixture


@transaction.atomic
def sync_live_scores_and_stats() -> None:
    """
    Pull current live matches from the API and update PlayerMatch rows
    (status, scores, point-by-point, stats).
    """
    client = TennisAPIClient()
    events = client.get_livescores()
    for event in events:
        upsert_match_from_fixture(event)