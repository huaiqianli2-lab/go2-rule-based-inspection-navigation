"""Local geometric checks on constructed inputs."""
import json
from tools.route_intersections import transverse_crossings, repeated_length
from tools.visit_order_metrics import audit_visit_orders


def main():
    crossing_route = [[0, 0], [2, 2], [0, 2], [2, 0]]
    retraced_route = [[0, 0], [2, 0], [0, 0]]
    directed_costs = [[0, 1, 4, 7], [2, 0, 3, 6], [5, 8, 0, 9], [10, 11, 12, 0]]
    report = {
        "input_kind": "constructed_example",
        "transverse_crossings": transverse_crossings(crossing_route),
        "repeated_length": repeated_length(retraced_route),
        "visit_order_audit": audit_visit_orders(directed_costs, loop=True, sampled_average=None),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
