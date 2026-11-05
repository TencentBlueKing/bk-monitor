"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import struct

import pytest
from django.db import IntegrityError, connections, transaction
from django.utils import timezone

from metadata.models import TimeSeriesMetricOverride, TimeSeriesReportScope, TimeSeriesReportValue, TimeSeriesScope

pytestmark = pytest.mark.django_db(databases="__all__")


def create_report_value(**kwargs) -> TimeSeriesReportValue:
    values: dict = {
        "group_id": 1,
        "field_name": "request_duration_sum",
        "fingerprint": "a" * 32,
        "original_name": "request_duration",
        "original_type": "histogram",
        "metric_type": "counter",
        "meta": {"unit": "s", "description": "请求耗时"},
    }
    values.update(kwargs)
    return TimeSeriesReportValue.objects.create(**values)


def test_report_value_deduplicates_within_group():
    create_report_value()
    with pytest.raises(IntegrityError), transaction.atomic():
        create_report_value()

    create_report_value(group_id=2)
    create_report_value(fingerprint="b" * 32, meta={"unit": "ms"})
    create_report_value(field_name="request_duration_count")
    assert TimeSeriesReportValue.objects.count() == 4


def test_report_value_metric_names_are_case_sensitive():
    create_report_value(field_name="Requests")
    create_report_value(field_name="requests")
    assert TimeSeriesReportValue.objects.count() == 2


def test_report_scope_deduplicates_within_group():
    values: dict = {
        "group_id": 1,
        "scope_hash": "a" * 32,
        "scope_type": "APM",
        "labels": {"service_name": "checkout", "scope_name": "http"},
        "raw_scope": "checkout||http",
        "report_value_ids": struct.pack("<II", 1, 2),
        "value_count": 2,
        "last_seen": timezone.now(),
    }
    report_scope = TimeSeriesReportScope.objects.create(**values)
    with pytest.raises(IntegrityError), transaction.atomic():
        TimeSeriesReportScope.objects.create(**values)

    values["group_id"] = 2
    TimeSeriesReportScope.objects.create(**values)
    report_scope.refresh_from_db()
    assert bytes(report_scope.report_value_ids) == struct.pack("<II", 1, 2)
    assert report_scope.version == 0


def test_report_scope_can_store_more_than_blob_limit():
    # 6w 个 ID 超过普通 BLOB 的 64 KiB，必须由 MEDIUMBLOB 完整保存。
    blob: bytes = struct.pack("<I", 1) * 60_000
    scope = TimeSeriesReportScope.objects.create(
        group_id=1,
        scope_hash="a" * 32,
        scope_type="DEFAULT",
        raw_scope="",
        report_value_ids=blob,
        value_count=60_000,
        last_seen=timezone.now(),
    )
    scope.refresh_from_db()
    assert bytes(scope.report_value_ids) == blob
    assert scope.labels is None


def test_override_separates_selectors_and_preserves_empty_values():
    for selector_hash, selector in (("", {}), ("a" * 32, {"service_name": "checkout"})):
        TimeSeriesMetricOverride.objects.create(
            group_id=1,
            selector_hash=selector_hash,
            selector=selector,
            field_name="requests",
            field_config={"alias": "", "disabled": False, "interval": 0, "function": []},
        )

    override = TimeSeriesMetricOverride.objects.get(group_id=1, selector_hash="", field_name="requests")
    assert override.scope_id is None
    assert override.field_config == {"alias": "", "disabled": False, "interval": 0, "function": []}
    with pytest.raises(IntegrityError), transaction.atomic():
        TimeSeriesMetricOverride.objects.create(group_id=1, selector_hash="", field_name="requests")


def test_optional_metadata_and_config_are_nullable():
    value = create_report_value(meta=None)
    override = TimeSeriesMetricOverride.objects.create(group_id=1, selector_hash="", field_name="requests")
    value.refresh_from_db()
    override.refresh_from_db()
    assert value.meta is None
    assert value.scope_count == 0
    assert override.selector is None
    assert override.field_config is None


def test_page_groups_allow_same_name_for_different_selectors():
    global_scope = TimeSeriesScope.objects.create(group_id=1, scope_name="支付")
    TimeSeriesScope.objects.create(
        group_id=1, scope_name="支付", selector={"service_name": "checkout"}, selector_hash="a" * 32
    )
    assert global_scope.selector is None
    assert global_scope.selector_hash == ""
    with pytest.raises(IntegrityError), transaction.atomic():
        TimeSeriesScope.objects.create(group_id=1, scope_name="支付", selector_hash="a" * 32)


@pytest.mark.parametrize("model", [TimeSeriesReportValue, TimeSeriesReportScope, TimeSeriesMetricOverride])
def test_report_table_indexes_match_model(model):
    connection = connections[model.objects.db]
    with connection.cursor() as cursor:
        constraints: dict = connection.introspection.get_constraints(cursor, model._meta.db_table)

    for constraint in model._meta.constraints:
        assert constraints[constraint.name]["unique"]
        assert constraints[constraint.name]["columns"] == list(constraint.fields)
    for index in model._meta.indexes:
        assert constraints[index.name]["index"]
        assert constraints[index.name]["columns"] == list(index.fields)
    assert not any(constraint["foreign_key"] for constraint in constraints.values())
