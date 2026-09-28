"""Agreement metrics between a model's verdicts and the human gold labels."""
from collections import Counter


def cohen_kappa(a, b):
    n = len(a)
    if n == 0:
        return float("nan")
    observed = sum(x == y for x, y in zip(a, b)) / n
    expected = sum((a.count(c) / n) * (b.count(c) / n) for c in set(a) | set(b))
    return float("nan") if expected == 1 else (observed - expected) / (1 - expected)


def agreement(rows, pred="judge_verdict", gold="human_verdict"):
    """Counts, percentages, kappa and the confusion matrix, with 'fail' as the positive class."""
    rows = [r for r in rows if r.get(pred) in ("pass", "fail")]
    p, g = [r[pred] for r in rows], [r[gold] for r in rows]
    n = len(rows)
    confusion = Counter(zip(g, p))
    tp, fn = confusion[("fail", "fail")], confusion[("fail", "pass")]
    fp, tn = confusion[("pass", "fail")], confusion[("pass", "pass")]
    return {
        "n": n,
        "agree": tp + tn,
        "agree_pct": round(100 * (tp + tn) / n, 1) if n else None,
        "kappa": round(cohen_kappa(p, g), 3),
        "confusion": {"gold_fail_judged_fail": tp, "gold_fail_judged_pass": fn,
                      "gold_pass_judged_fail": fp, "gold_pass_judged_pass": tn},
        "fail_recall_pct": round(100 * tp / (tp + fn), 1) if tp + fn else None,
        "pass_recall_pct": round(100 * tn / (tn + fp), 1) if tn + fp else None,
    }


def breakdown(rows, key, pred="judge_verdict", gold="human_verdict"):
    """Agreement per group (e.g. per flaw type), as 'agree/total'."""
    groups = {}
    for r in rows:
        if r.get(pred) in ("pass", "fail"):
            groups.setdefault(r[key], []).append(r[pred] == r[gold])
    return {k: f"{sum(v)}/{len(v)}" for k, v in sorted(groups.items())}


def usage_summary(rows, prefix=""):
    """Mean tokens, latency and cost per item for the calls recorded under `prefix`."""
    calls = [r for r in rows if r.get(prefix + "cost_usd") is not None]
    if not calls:
        return {}
    n = len(calls)
    lat = sorted(r[prefix + "latency_s"] for r in calls if r.get(prefix + "latency_s") is not None)
    mean = lambda key: round(sum(r[prefix + "tokens"][key] for r in calls) / n, 1)
    return {
        "calls": n,
        "mean_input_tokens": mean("input"),
        "mean_output_tokens": mean("output"),
        "mean_thinking_tokens": mean("thinking"),
        "cost_per_item_usd": round(sum(r[prefix + "cost_usd"] for r in calls) / n, 6),
        "cost_per_1k_usd": round(1000 * sum(r[prefix + "cost_usd"] for r in calls) / n, 3),
        "latency_median_s": lat[len(lat) // 2] if lat else None,
        "latency_p90_s": lat[int(len(lat) * 0.9)] if lat else None,
    }
