from dataclasses import dataclass
from typing import Dict, List, Tuple

from apm_web.handlers.trace_handler.base import StatisticsHandler
from apm_web.trace.diagram.diff import DiffMark


@dataclass
class StatisticsDiagrammer:
    """Flamegraph diagrammer"""

    def draw(self, trace_detail: list, **options) -> list:
        # call trace_query/trace_statistics instead
        raise NotImplementedError

    def diff(self, base: list, comp: list, **options) -> list:
        return trace_diff_to_statistics(base, comp, options.get("group_fields", []), options.get("filters", {}))


DURATION_FIELDS = ["max_duration", "min_duration", "avg_duration", "sum_duration", "P95"]


def make_empty_element():
    """Make empty element"""

    return {
        **{x: 0 for x in DURATION_FIELDS},
        "count": 0,
    }


def get_unique_values(element: dict, group_keys: List[str]) -> tuple:
    """Get unique values"""
    values = []
    for x in group_keys:

        # "resource.sdk.name", "kind" will be dict, fetch value directly
        if isinstance(element[x], dict):
            values.append(element[x]["value"])
        else:
            values.append(element[x])
    return tuple(values)


def find_similarity_from_comparison(
    group_keys: List[str], baseline_element: dict, comparison_unique_together_mapping: Dict[tuple, dict]
) -> Tuple[bool, tuple, dict]:
    """Find similarity from comparison"""

    # unique values, example: (SET, FOO_SERVICE, opentelemetry, 1)
    baseline_unique_values = get_unique_values(baseline_element, group_keys)

    if baseline_unique_values not in comparison_unique_together_mapping:
        empty = baseline_element.copy()
        empty.update(make_empty_element())
        return False, (), empty

    return True, baseline_unique_values, comparison_unique_together_mapping[baseline_unique_values]


def trace_diff_to_statistics(curr: list, base: list, group_fields: list, filters: dict) -> list:
    """Convert trace diff to statistics"""

    baseline = StatisticsHandler.get_trace_statistics(curr, group_fields, filters)
    comparison = StatisticsHandler.get_trace_statistics(base, group_fields, filters)

    # unique values -> element mapping, example:  {(SET, FOO_SERVICE, opentelemetry, 1): {**element}}
    comparison_unique_together_mapping = {get_unique_values(z, group_fields): z for z in comparison}

    # find similarity from `comparison` and injecting diff into to elements in `baseline`
    found_keys = []
    for element in baseline:
        found, unique_values, comparison_element = find_similarity_from_comparison(
            group_fields, element, comparison_unique_together_mapping
        )
        element["comparison"] = comparison_element

        if not found:
            diff_mark = DiffMark.ADDED.value
        else:
            found_keys.append(unique_values)
            diff_mark = (
                DiffMark.UNCHANGED.value
                if all(element[x] == comparison_element[x] for x in DURATION_FIELDS)
                else DiffMark.CHANGED.value
            )

        element["mark"] = diff_mark

    # not found elements in `comparison` means `added`
    for comparison_element in comparison:
        if get_unique_values(comparison_element, group_fields) not in found_keys:
            element = comparison_element.copy()
            element.update(make_empty_element())
            element["mark"] = DiffMark.REMOVED.value
            element["comparison"] = comparison_element
            baseline.append(element)

    return baseline
