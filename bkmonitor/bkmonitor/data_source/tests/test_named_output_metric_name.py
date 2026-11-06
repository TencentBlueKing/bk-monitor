"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy

import pytest

from bkmonitor.data_source.unify_query.query import UnifyQuery


@pytest.fixture
def named_outputs():
    outputs = []
    for reference_name, value in [("A", 10), ("B", 20), ("C", 90), ("RESULT", 30)]:
        labels = {"service": "api", "instance": "node-a"}
        if reference_name != "RESULT":
            labels["__name__"] = f"metric_{reference_name.lower()}"
        outputs.append(
            {
                "reference_name": reference_name,
                "state": "SUCCESS",
                "series": [
                    {
                        "columns": ["_time", "_value"],
                        "types": ["float", "float"],
                        "group_keys": list(labels),
                        "group_values": list(labels.values()),
                        "values": [[1700000000000, value]],
                    }
                ],
            }
        )
    return {"contract_version": "named_outputs/v1", "outputs": outputs}


def parse_named_outputs(data):
    return UnifyQuery.process_named_outputs_data({"legacy_output_ref": "RESULT"}, data)[0]


@pytest.mark.parametrize("result_metric_name", [None, "result_metric"])
def test_metric_names_do_not_prevent_named_output_alignment(named_outputs, result_metric_name):
    if result_metric_name is not None:
        result_series = named_outputs["outputs"][-1]["series"][0]
        result_series["group_keys"].append("__name__")
        result_series["group_values"].append(result_metric_name)
    original = deepcopy(named_outputs)

    records = parse_named_outputs(named_outputs)

    assert len(records) == 1
    assert records[0]["_time_"] == 1700000000000
    assert records[0]["_result_"] == 30
    assert records[0]["_ref_values_"] == {
        "A": {"value": 10, "state": "SUCCESS"},
        "B": {"value": 20, "state": "SUCCESS"},
        "C": {"value": 90, "state": "SUCCESS"},
        "RESULT": {"value": 30, "state": "SUCCESS"},
    }
    assert records[0].get("__name__") == result_metric_name
    assert named_outputs == original


@pytest.mark.parametrize("mismatch", ["label_value", "missing_label", "extra_label", "timestamp"])
def test_other_labels_and_timestamps_still_require_exact_matches(named_outputs, mismatch):
    series = named_outputs["outputs"][1]["series"][0]
    if mismatch == "label_value":
        series["group_values"][series["group_keys"].index("instance")] = "node-b"
    elif mismatch == "missing_label":
        index = series["group_keys"].index("instance")
        series["group_keys"].pop(index)
        series["group_values"].pop(index)
    elif mismatch == "extra_label":
        series["group_keys"].append("zone")
        series["group_values"].append("zone-a")
    else:
        series["values"][0][0] += 60000

    record = parse_named_outputs(named_outputs)[0]

    assert record["_ref_values_"]["A"] == {"value": 10, "state": "SUCCESS"}
    assert record["_ref_values_"]["B"] == {"state": "MISSING"}
    assert record["_ref_values_"]["RESULT"] == {"value": 30, "state": "SUCCESS"}


@pytest.mark.parametrize("reference_name", ["A", "RESULT"])
def test_metric_name_only_duplicates_are_rejected(named_outputs, reference_name):
    output = next(output for output in named_outputs["outputs"] if output["reference_name"] == reference_name)
    duplicate = deepcopy(output["series"][0])
    if "__name__" in duplicate["group_keys"]:
        duplicate["group_values"][duplicate["group_keys"].index("__name__")] = "another_metric"
    else:
        duplicate["group_keys"].append("__name__")
        duplicate["group_values"].append("another_metric")
    output["series"].append(duplicate)

    with pytest.raises(ValueError, match=f"duplicate named output point: {reference_name}"):
        parse_named_outputs(named_outputs)


def test_distinct_business_labels_keep_outputs_separate(named_outputs):
    for output in named_outputs["outputs"]:
        extra = deepcopy(output["series"][0])
        extra["group_values"][extra["group_keys"].index("instance")] = "node-b"
        extra["values"][0][1] *= 2
        output["series"].append(extra)

    records = {record["instance"]: record for record in parse_named_outputs(named_outputs)}

    assert set(records) == {"node-a", "node-b"}
    for reference_name, value in [("A", 10), ("B", 20), ("C", 90), ("RESULT", 30)]:
        assert records["node-a"]["_ref_values_"][reference_name] == {"value": value, "state": "SUCCESS"}
        assert records["node-b"]["_ref_values_"][reference_name] == {"value": value * 2, "state": "SUCCESS"}


def test_legacy_series_processing_keeps_metric_name_without_adding_snapshots(named_outputs):
    records = UnifyQuery.process_unify_query_data(
        {"query_list": [{"reference_name": "A"}]}, {"series": named_outputs["outputs"][0]["series"]}
    )

    assert records[0]["__name__"] == "metric_a"
    assert records[0]["_result_"] == 10
    assert "_ref_values_" not in records[0]
