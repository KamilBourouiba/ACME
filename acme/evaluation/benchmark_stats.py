"""Bootstrap confidence intervals and judge agreement stats for MemoryBench exports."""

from __future__ import annotations

import math
import random
from typing import Iterable


def bootstrap_ci(
    values: list[float],
    *,
    n_resamples: int = 5000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Return (mean, lower, upper) 95% CI via percentile bootstrap."""
    if not values:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = max(0, int((alpha / 2) * n_resamples) - 1)
    hi_idx = min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))
    mean = sum(values) / n
    return mean, means[lo_idx], means[hi_idx]


def pearson_r(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def scenario_metrics(scenarios: list[dict]) -> dict[str, list[float]]:
    return {
        "retention": [float(s.get("retention_score", 0)) for s in scenarios],
        "groundedness": [float(s.get("hallucination_score", 0)) for s in scenarios],
        "feedback": [float(s.get("feedback_score", 0)) for s in scenarios],
        "belief": [float(s.get("belief_quality_score", 0)) for s in scenarios],
        "keyword_retention": [float(s.get("keyword_retention_score", 0)) for s in scenarios],
    }


def mean_metric(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0
