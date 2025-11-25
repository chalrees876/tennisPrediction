# tennis/utils/scoring.py

from typing import Any, Dict, List


def normalize_api_score_line(scores: List[Dict[str, Any]]) -> str:
    """
    API 'scores' looks like:
      [{"score_first": "7", "score_second": "5", "score_set": "1"}, ...]
    We collapse to: "7-5 7-6 6-4" etc.

    For now we ignore decimal tie-break info like "7.7" -> "7".
    You can enhance later to add (2) etc.
    """
    if not scores:
        return ""

    parts = []
    for s in scores:
        g1_raw = s.get("score_first")
        g2_raw = s.get("score_second")
        if not g1_raw or not g2_raw:
            continue

        # skip dummy 0-0 sets
        if g1_raw == "0" and g2_raw == "0":
            continue

        try:
            g1 = int(float(str(g1_raw)))
            g2 = int(float(str(g2_raw)))
        except ValueError:
            continue

        parts.append(f"{g1}-{g2}")

    return " ".join(parts)
