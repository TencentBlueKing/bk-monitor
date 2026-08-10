"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.conf import settings

from metadata import models
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.data_link_configs import DataBusConfig
from metadata.models.data_link.tags import (
    DatabusLabelContext,
    DatabusLabelGenerator,
    build_databus_labels,
    get_databus_label_registry,
)
from metadata.tests.common_utils import consul_client


class _FixedLabelGenerator(DatabusLabelGenerator):
    """测试用固定标签生成器。"""

    def __init__(self, name: str, priority: int, labels: dict[str, Any]):
        self.name = name
        self.priority = priority
        self._labels = labels

    def generate(self, context: DatabusLabelContext) -> dict[str, Any]:
        return dict(self._labels)


class _DatasourceEchoGenerator(DatabusLabelGenerator):
    """根据 DataSource 回显标签，用于验证上下文解析。"""

    name = "datasource_echo"
    priority = 10

    def generate(self, context: DatabusLabelContext) -> dict[str, Any]:
        if context.data_source is None:
            return {}
        return {
            "source_label": context.data_source.source_label,
            "type_label": context.data_source.type_label,
        }


class _ResultTableEchoGenerator(DatabusLabelGenerator):
    """根据 ResultTable 回显标签，用于验证上下文解析。"""

    name = "resulttable_echo"
    priority = 20

    def generate(self, context: DatabusLabelContext) -> dict[str, Any]:
        if context.result_table is None:
            return {}
        return {
            "data_label": context.result_table.data_label or "",
            "rt_label": context.result_table.label,
        }


@pytest.fixture
def create_or_delete_records(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=51010,
        data_name="databus_tag_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        source_label="bk_monitor",
        type_label="time_series",
        bk_tenant_id="system",
    )
    result_table = models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_51010.__default__",
        bk_biz_id=1001,
        is_custom_table=False,
        data_label="system.cpu",
        label="os",
        bk_tenant_id="system",
    )
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    yield data_source, result_table
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source.delete()
    result_table.delete()


@pytest.fixture
def isolated_registry():
    """隔离全局注册表，避免污染其他用例。"""
    registry = get_databus_label_registry()
    original_generators = {name: generator for name, generator in registry._generators.items()}
    registry.clear()
    yield registry
    registry.clear()
    for generator in original_generators.values():
        registry.register(generator)


@pytest.mark.django_db(databases="__all__")
def test_build_databus_labels_default_generators_return_empty(create_or_delete_records):
    """默认生成器首版规则未定，应返回空扩展标签。"""
    data_source, result_table = create_or_delete_records

    cases = [
        {
            "name": "with_objects",
            "kwargs": {"data_source": data_source, "result_table": result_table},
            "expected": {},
        },
        {
            "name": "with_ids",
            "kwargs": {
                "bk_data_id": data_source.bk_data_id,
                "table_id": result_table.table_id,
                "bk_tenant_id": "system",
            },
            "expected": {},
        },
        {
            "name": "empty_context",
            "kwargs": {},
            "expected": {},
        },
    ]
    for case in cases:
        assert build_databus_labels(**case["kwargs"]) == case["expected"], case["name"]


@pytest.mark.django_db(databases="__all__")
def test_registry_merge_priority_and_extra_labels(isolated_registry):
    """验证注册表按 priority 合并，且 extra_labels 优先级更高。"""
    isolated_registry.register(_FixedLabelGenerator("low", priority=10, labels={"a": "1", "b": "1"}))
    isolated_registry.register(_FixedLabelGenerator("high", priority=20, labels={"b": "2", "c": "3"}))

    labels = build_databus_labels(extra_labels={"c": "extra", "d": "4", "bk_biz_id": "should_be_removed"})

    assert labels == {"a": "1", "b": "2", "c": "extra", "d": "4"}
    assert "bk_biz_id" not in labels


@pytest.mark.django_db(databases="__all__")
def test_build_databus_labels_resolve_datasource_and_resulttable(create_or_delete_records, isolated_registry):
    """验证可从 bk_data_id / table_id 解析对象并交给生成器。"""
    data_source, result_table = create_or_delete_records
    isolated_registry.register(_DatasourceEchoGenerator())
    isolated_registry.register(_ResultTableEchoGenerator())

    labels = build_databus_labels(
        bk_data_id=data_source.bk_data_id,
        table_id=result_table.table_id,
        bk_tenant_id="system",
    )

    assert labels == {
        "source_label": "bk_monitor",
        "type_label": "time_series",
        "data_label": "system.cpu",
        "rt_label": "os",
    }


@pytest.mark.django_db(databases="__all__")
def test_compose_databus_config_with_extended_labels(create_or_delete_records, isolated_registry):
    """创建 Databus 配置时应同步写入扩展标签，且保留 bk_biz_id。"""
    data_source, result_table = create_or_delete_records
    isolated_registry.register(_DatasourceEchoGenerator())
    isolated_registry.register(_ResultTableEchoGenerator())

    settings.ENABLE_MULTI_TENANT_MODE = False
    sinks = [
        {
            "kind": DataLinkKind.VMSTORAGEBINDING.value,
            "name": "bkm_databus_tag_test",
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        }
    ]
    data_bus_ins, _ = DataBusConfig.objects.get_or_create(
        name="bkm_databus_tag_test",
        data_id_name="bkm_databus_tag_test",
        data_link_name="bkm_databus_tag_test",
        namespace="bkmonitor",
        bk_biz_id=111,
        bk_tenant_id="system",
        defaults={"bk_data_id": data_source.bk_data_id},
    )

    content = data_bus_ins.compose_config(
        sinks,
        data_source=data_source,
        table_id=result_table.table_id,
        labels={"custom_tag": "demo"},
    )

    assert content["metadata"]["labels"] == {
        "source_label": "bk_monitor",
        "type_label": "time_series",
        "data_label": "system.cpu",
        "rt_label": "os",
        "custom_tag": "demo",
        "bk_biz_id": "111",
    }


@pytest.mark.django_db(databases="__all__")
def test_compose_databus_config_reserved_bk_biz_id_not_overridden(create_or_delete_records, isolated_registry):
    """扩展生成器即使产出 bk_biz_id，也不能覆盖系统保留值。"""
    data_source, result_table = create_or_delete_records
    isolated_registry.register(_FixedLabelGenerator("evil", priority=1, labels={"bk_biz_id": "999", "env": "prod"}))

    data_bus_ins, _ = DataBusConfig.objects.get_or_create(
        name="bkm_databus_tag_reserved",
        data_id_name="bkm_databus_tag_reserved",
        data_link_name="bkm_databus_tag_reserved",
        namespace="bkmonitor",
        bk_biz_id=111,
        bk_tenant_id="system",
        defaults={"bk_data_id": data_source.bk_data_id},
    )
    content = data_bus_ins.compose_config(
        sinks=[],
        data_source=data_source,
        table_id=result_table.table_id,
    )

    assert content["metadata"]["labels"]["bk_biz_id"] == "111"
    assert content["metadata"]["labels"]["env"] == "prod"
