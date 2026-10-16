"""ANV-019: transparent binary retrieval metrics and query bootstrap intervals."""

import math
import random
import statistics

METRICS = ("ndcg@10", "mrr@10", "precision@10", "recall@10", "recall@50", "success@10")


def query_metrics(ranking: list[str], qrels: dict[str, int]) -> dict[str, float]:
    if len(ranking) != len(set(ranking)):
        raise ValueError("Duplicate document IDs in ranking")
    if any(type(grade) is not int or grade not in (0, 1) for grade in qrels.values()):
        raise ValueError("Binary integer relevance required")
    relevant = {did for did, grade in qrels.items() if grade == 1}
    hits = [int(did in relevant) for did in ranking]
    dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits[:10]))
    ideal = sum(1 / math.log2(rank + 2) for rank in range(min(10, len(relevant))))
    return {
        "ndcg@10": dcg / ideal if ideal else 0.0,
        "mrr@10": next((1 / (rank + 1) for rank, hit in enumerate(hits[:10]) if hit), 0.0),
        "precision@10": sum(hits[:10]) / 10,
        "recall@10": sum(hits[:10]) / len(relevant) if relevant else 0.0,
        "recall@50": sum(hits[:50]) / len(relevant) if relevant else 0.0,
        "success@10": float(any(hits[:10])),
    }


def percentile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def bootstrap_mean(values: list[float], samples=1000, seed=20261016):
    if not values or type(samples) is not int or not 100 <= samples <= 10000:
        raise ValueError("Bootstrap needs values and 100..10000 samples")
    rng = random.Random(seed)
    size = len(values)
    means = [sum(values[rng.randrange(size)] for _ in range(size)) / size for _ in range(samples)]
    return {
        "mean": round(statistics.fmean(values), 6),
        "ci95": [round(percentile(means, p), 6) for p in (0.025, 0.975)],
    }


def aggregate(records, samples=1000):
    """Bootstrap query units; paired deltas use the same query ordering."""
    return {metric: bootstrap_mean([row[metric] for row in records], samples) for metric in METRICS}
