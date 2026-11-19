"""Audit small scenes without changing Unitree's 200-shuffle benchmark.

The bound applies only to the current observation stops and checked directed
leg costs. It is not a claim of global optimality over all possible photo poses
or a waiver of the contractual 15% requirement.
"""
import itertools
import math

MAX_EXACT_TARGETS = 8
SIMPLE_SCENE_NOTE = '备注：场景较简单，当前停靠点下访问顺序可优化空间有限。'


def audit_visit_orders(distances, *, loop, sampled_average):
    """Enumerate all small-tour orders, never select a worse random baseline."""
    count = len(distances) - 1
    if not 1 <= count <= MAX_EXACT_TARGETS:
        return None
    if any(len(row) != count + 1 for row in distances):
        raise ValueError('访问顺序距离矩阵不是方阵。')
    values = [[float(x) for x in row] for row in distances]
    if any(math.isnan(x) or x < 0 for row in values for x in row):
        raise ValueError('访问顺序距离包含负数或NaN。')
    total = 0
    feasible = 0
    length_sum = 0.
    best = math.inf
    for order in itertools.permutations(range(1, count + 1)):
        seq = (0,) + order + ((0,) if loop else ())
        cost = sum(values[a][b] for a, b in zip(seq, seq[1:]))
        total += 1
        if not math.isfinite(cost):
            continue
        feasible += 1
        length_sum += cost
        best = min(best, cost)
    if not feasible:
        return None
    avg = length_sum / feasible
    gain = lambda baseline: 100. * (baseline - best) / baseline if baseline > 0 else 0.
    sampled = float(sampled_average) if sampled_average is not None else math.nan
    return dict(schema=1, method='all_permutations_current_checked_legs_v1',
                target_count=count, loop=bool(loop), total_orders=total,
                feasible_orders=feasible, best_length_m=best,
                complete_random_average_m=avg, complete_gain_upper_pct=gain(avg),
                sampled_gain_upper_pct=gain(sampled) if math.isfinite(sampled) and sampled > 0 else None,
                scope='current_observation_stops_and_checked_legs')


def limited_order_note(metrics):
    """Explain a failure only with exhaustive evidence, never green-check it."""
    if not isinstance(metrics, dict):
        return ''
    audit = metrics.get('visit_order_audit')
    if not isinstance(audit, dict):
        return ''
    finite = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
    count = metrics.get('target_count')
    gain = metrics.get('improvement_vs_random_pct')
    length = metrics.get('path_length_m')
    best = audit.get('best_length_m')
    avg = audit.get('complete_random_average_m')
    sample = metrics.get('random_avg_length_m')
    if not finite(count) or int(count) != count or not 1 <= count <= MAX_EXACT_TARGETS:
        return ''
    if audit.get('schema') != 1 or audit.get('method') != 'all_permutations_current_checked_legs_v1':
        return ''
    if audit.get('scope') != 'current_observation_stops_and_checked_legs' or audit.get('target_count') != count:
        return ''
    total = math.factorial(int(count))
    # Incomplete/disconnected scenes are not classified as merely simple.
    if audit.get('total_orders') != total or audit.get('feasible_orders') != total:
        return ''
    if not all(finite(x) for x in (gain, length, best, avg, sample)) or not (gain < 15 and 0 <= best <= length + .011 and avg > 0 and sample > 0):
        return ''
    if not (100 * (avg - best) / avg < 15 and 100 * (sample - best) / sample < 15):
        return ''
    return SIMPLE_SCENE_NOTE
