"""Quick double-check: a seeded random pick of the items that passed the quality check."""
from __future__ import annotations

import math
import random


def size(k: int, fraction: float, minimum: int) -> int:
    if k <= 0:
        return 0
    return min(k, max(int(minimum), math.ceil(float(fraction) * k)))


def pick(auto_ids: list[str], seed: int, fraction: float, minimum: int) -> list[str]:
    """auto_ids in evidence order. Same seed, same picks."""
    n = size(len(auto_ids), fraction, minimum)
    if n == 0:
        return []
    return random.Random(seed).sample(list(auto_ids), n)
