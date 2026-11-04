"""Small, dependency-free statistics: percentiles, Wilson and bootstrap intervals."""
from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence


def percentile(xs: Sequence[float], q: float) -> float | None:
    """Linear-interpolated percentile, q in [0, 100]."""
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * q / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def mean(xs: Sequence[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def wilson(k: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def bootstrap_ci(clusters: Sequence[Sequence[float]], stat: Callable[[list[float]], float] = None,
                 n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> tuple[float, float] | None:
    """Percentile CI of `stat` (default: mean) over resampled clusters, e.g. the two
    colour-swapped games of one opening, or one position's paired decisions."""
    clusters = [list(c) for c in clusters if len(c)]
    if not clusters:
        return None
    stat = stat or (lambda xs: sum(xs) / len(xs))
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        flat: list[float] = []
        for _ in range(len(clusters)):
            flat.extend(clusters[rng.randrange(len(clusters))])
        vals.append(stat(flat))
    return (percentile(vals, 100 * alpha / 2), percentile(vals, 100 * (1 - alpha / 2)))
