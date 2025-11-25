# tennis/utils/odds.py

def prob_to_american(p: float, round_to: int = 1) -> int:
    p = min(max(p, 1e-6), 1 - 1e-6)
    if p >= 0.5:
        return -int(round((p / (1 - p)) * 100.0 / round_to) * round_to)
    return int(round(((1 - p) / p) * 100.0 / round_to) * round_to)


def prob_to_decimal(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return round(1.0 / p, 4)


def american_to_implied_prob(ml: int) -> float:
    if ml < 0:
        return (-ml) / ((-ml) + 100.0)
    return 100.0 / (ml + 100.0)
