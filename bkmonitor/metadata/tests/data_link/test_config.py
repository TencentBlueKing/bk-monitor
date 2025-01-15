# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from django.conf import settings

from metadata.models.data_link.constants import (
    DEFAULT_METRIC_TRANSFORMER,
    DEFAULT_METRIC_TRANSFORMER_FORMAT,
    DEFAULT_METRIC_TRANSFORMER_KIND,
    DataLinkKind,
)
from metadata.models.data_link.resource import DataLinkResourceConfig

from .conftest import (
    DEFAULT_NAME,
    DEFAULT_SPACE_ID,
    DEFAULT_SPACE_TYPE,
    DEFAULT_VM_NAME,
)

pytestmark = pytest.mark.django_db


def test_compose_data_id_config():
    content = DataLinkResourceConfig.compose_data_id_config(DEFAULT_NAME)

    assert content["kind"] == DataLinkKind.DATAID.value
    assert content["metadata"]["name"] == DEFAULT_NAME
    assert content["metadata"]["namespace"] == settings.DEFAULT_VM_DATA_LINK_NAMESPACE

    # 确认key存在
    assert set(content["spec"].keys()) == {"alias", "bizId", "description", "maintainers"}


def test_compose_vm_table_id_config():
    content = DataLinkResourceConfig.compose_vm_table_id_config(DEFAULT_NAME)

    assert content["kind"] == DataLinkKind.RESULTTABLE.value
    assert content["metadata"]["name"] == DEFAULT_NAME
    assert content["metadata"]["namespace"] == settings.DEFAULT_VM_DATA_LINK_NAMESPACE

    # 确认key存在
    assert set(content["spec"].keys()) == {"alias", "bizId", "dataType", "description", "maintainers"}
    assert type(content["spec"]["maintainers"]) == list


def test_compose_vm_storage_binding(create_and_delete_data_link):
    content = DataLinkResourceConfig.compose_vm_storage_binding(
        DEFAULT_NAME, DEFAULT_NAME, DEFAULT_VM_NAME, DEFAULT_SPACE_TYPE, DEFAULT_SPACE_ID
    )

    assert content["kind"] == DataLinkKind.VMSTORAGEBINDING.value
    assert content["metadata"]["name"] == DEFAULT_NAME
    assert content["metadata"]["namespace"] == settings.DEFAULT_VM_DATA_LINK_NAMESPACE

    # 确认数据key存在，及对应的值
    assert set(content["spec"]["data"].keys()) == {"kind", "name", "namespace"}
    assert content["spec"]["data"]["kind"] == DataLinkKind.RESULTTABLE.value
    assert content["spec"]["data"]["name"] == DEFAULT_NAME
    assert content["spec"]["data"]["namespace"] == settings.DEFAULT_VM_DATA_LINK_NAMESPACE

    # 确认存储key存在，及对应的值
    assert set(content["spec"]["storage"].keys()) == {"kind", "name", "namespace"}
    assert content["spec"]["storage"]["kind"] == "VmStorage"
    assert content["spec"]["storage"]["name"] == DEFAULT_VM_NAME
    assert content["spec"]["storage"]["namespace"] == settings.DEFAULT_VM_DATA_LINK_NAMESPACE

    assert type(content["spec"]["maintainers"]) == list


def test_compose_vm_databus_config():
    content = DataLinkResourceConfig.compose_vm_data_bus_config(DEFAULT_NAME, DEFAULT_NAME, DEFAULT_NAME)

    assert content["kind"] == DataLinkKind.DATABUS.value
    assert content["metadata"]["name"] == DEFAULT_NAME
    assert content["metadata"]["namespace"] == settings.DEFAULT_VM_DATA_LINK_NAMESPACE

    # 确认key存在及上下游链路类型及名称
    assert set(content["spec"].keys()) == {"maintainers", "sinks", "sources", "transforms"}
    assert type(content["spec"]["maintainers"]) == list
    spec = content["spec"]
    assert spec["sinks"][0]["kind"] == DataLinkKind.VMSTORAGEBINDING.value
    assert spec["sinks"][0]["name"] == DEFAULT_NAME

    assert spec["sources"][0]["kind"] == DataLinkKind.DATAID.value
    assert spec["sources"][0]["name"] == DEFAULT_NAME

    assert spec["transforms"][0]["kind"] == DEFAULT_METRIC_TRANSFORMER_KIND
    assert spec["transforms"][0]["name"] == DEFAULT_METRIC_TRANSFORMER
    assert spec["transforms"][0]["format"] == DEFAULT_METRIC_TRANSFORMER_FORMAT
