"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from metadata import models
from metadata.models.data_source import ResultTableField
from metadata.resources import NotifyEsDataLinkAdaptNano
from metadata.tests.common_utils import consul_client

table_id = "1001_test_log.__default__"


@pytest.fixture
def create_or_delete_records(mocker):
    models.ResultTable.objects.create(
        table_id=table_id,
        bk_biz_id=1001,
        is_custom_table=False,
    )
    models.ResultTableField.objects.create(
        table_id=table_id,
        field_name="dtEventTimeStamp",
        field_type="timestamp",
        description="数据时间",
        tag="dimension",
        is_config_by_user=True,
    )

    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name="dtEventTimeStamp",
        name="es_type",
        value="date_nanos",
        value_type="string",
    )

    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name="dtEventTimeStamp",
        name="es_format",
        value="strict_date_optional_time_nanos",
        value_type="string",
    )

    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name="dtEventTimeStamp",
        name="time_format",
        value="yyyy-MM-dd HH:mm:ss.SSSSSS",
        value_type="string",
    )

    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name="dtEventTimeStamp",
        name="time_zone",
        value="8",
        value_type="string",
    )

    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name="dtEventTimeStamp",
        name="real_path",
        value="bk_separator_object.log_time",
        value_type="string",
    )

    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name="dtEventTimeStamp",
        name="field_index",
        value="1",
        value_type="string",
    )

    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name="dtEventTimeStamp",
        name="timestamp_unit",
        value="µs",
        value_type="string",
    )

    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name="dtEventTimeStamp",
        name="default_function",
        value="fn:timestamp_from_utctime",
        value_type="string",
    )

    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name="time",
        name="es_format",
        value="strict_date_optional_time_nanos",
        value_type="string",
    )

    models.DataSource.objects.create(
        bk_data_id=100111,
        data_name="data_link_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.DataSourceResultTable.objects.create(table_id=table_id, bk_data_id=100111)
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.ResultTable.objects.filter(table_id=table_id).delete()
    models.ResultTableField.objects.filter(table_id=table_id).delete()
    models.ResultTableFieldOption.objects.filter(table_id=table_id).delete()
    models.DataSource.objects.filter(bk_data_id=100111).delete()
    models.DataSourceResultTable.objects.filter(bk_data_id=100111).delete()


def es_mapping_same(es_properties, current_mapping, alias_field_list):
    for field_name, database_config in list(es_properties.items()):
        if field_name in alias_field_list:
            continue
        try:
            current_config = current_mapping[field_name]
        except KeyError:
            return False
        # 判断具体的内容是否一致，只要判断具体的四个内容
        for field_config in ["type", "include_in_all", "doc_values", "format", "analyzer", "path"]:
            database_value = database_config.get(field_config, None)
            current_value = current_config.get(field_config, None)

            if field_config == "type" and current_value is None:
                current_field_properties = current_config.get("properties", None)
                # object 字段动态写入数据后 不再有type这个字段 只有 properties
                if current_field_properties and database_value != ResultTableField.FIELD_TYPE_OBJECT:
                    return False
                continue

            if database_value != current_value:
                return False
    return True


@pytest.mark.django_db(databases="__all__")
def test_notify_es_data_link_adapt_nano(create_or_delete_records):
    data = NotifyEsDataLinkAdaptNano().request(table_id=table_id)

    expected = [
        {
            "alias_name": "",
            "default_value": None,
            "description": "数据时间",
            "field_name": "dtEventTimeStamp",
            "is_config_by_user": True,
            "is_disabled": False,
            "option": {
                "default_function": "fn:timestamp_from_utctime",
                "es_format": "strict_date_optional_time_nanos||epoch_millis",
                "es_type": "date",
                "field_index": "1",
                "real_path": "bk_separator_object.log_time",
                "time_format": "yyyy-MM-dd HH:mm:ss.SSSSSS",
                "time_zone": "8",
                "timestamp_unit": "µs",
            },
            "tag": "dimension",
            "type": "timestamp",
            "unit": "",
        },
        {
            "alias_name": "",
            "default_value": None,
            "description": "数据时间",
            "field_name": "dtEventTimeStampNanos",
            "is_config_by_user": True,
            "is_disabled": False,
            "option": {
                "default_function": "fn:timestamp_from_utctime",
                "es_format": "strict_date_optional_time_nanos||epoch_millis",
                "es_type": "date_nanos",
                "field_index": "1",
                "real_path": "bk_separator_object.log_time",
                "time_format": "yyyy-MM-dd HH:mm:ss.SSSSSS",
                "time_zone": "8",
                "timestamp_unit": "µs",
            },
            "tag": "dimension",
            "type": "timestamp",
            "unit": "",
        },
    ]

    assert data == expected


@pytest.mark.django_db(databases="__all__")
def test_es_mapping_same(create_or_delete_records):
    es_properties = {
        "__ext": {"type": "object"},
        "bk_host_id": {"type": "integer"},
        "cloudId": {"type": "integer"},
        "dtEventTimeStamp": {"type": "date", "format": "epoch_millis"},
        "gseIndex": {"type": "long"},
        "iterationIndex": {"type": "integer"},
        "log": {"type": "text", "norms": False},
        "path": {"type": "keyword"},
        "serverIp": {"type": "keyword"},
        "time": {"type": "date", "format": "epoch_millis"},
        "cluster_id": {"type": "alias", "path": "__ext.bk_bcs_cluster_id"},
        "container_id": {"type": "alias", "path": "__ext.container_id"},
        "image_name": {"type": "alias", "path": "__ext.container_image"},
        "container_name": {"type": "alias", "path": "__ext.container_name"},
        "pod_name": {"type": "alias", "path": "__ext.io_kubernetes_pod"},
        "pod_ip": {"type": "alias", "path": "__ext.io_kubernetes_pod_ip"},
        "namespace": {"type": "alias", "path": "__ext.io_kubernetes_pod_namespace"},
        "pod_uid": {"type": "alias", "path": "__ext.io_kubernetes_pod_uid"},
        "workload_name": {"type": "alias", "path": "__ext.io_kubernetes_workload_name"},
        "workload_type": {"type": "alias", "path": "__ext.io_kubernetes_workload_type"},
        "__ext.bk_bcs_cluster_id": {"type": "keyword"},
        "__ext.container_id": {"type": "keyword"},
        "__ext.container_image": {"type": "keyword"},
        "__ext.container_name": {"type": "keyword"},
        "__ext.io_kubernetes_pod": {"type": "keyword"},
        "__ext.io_kubernetes_pod_ip": {"type": "keyword"},
        "__ext.io_kubernetes_pod_namespace": {"type": "keyword"},
        "__ext.io_kubernetes_pod_uid": {"type": "keyword"},
        "__ext.io_kubernetes_workload_name": {"type": "keyword"},
        "__ext.io_kubernetes_workload_type": {"type": "keyword"},
    }

    current_mapping = {
        "__ext": {
            "properties": {
                "bk_bcs_cluster_id": {"type": "keyword"},
                "container_id": {"type": "keyword"},
                "container_image": {"type": "keyword"},
                "container_name": {"type": "keyword"},
                "io_kubernetes_pod": {"type": "keyword"},
                "io_kubernetes_pod_ip": {"type": "keyword"},
                "io_kubernetes_pod_namespace": {"type": "keyword"},
                "io_kubernetes_pod_uid": {"type": "keyword"},
                "io_kubernetes_workload_name": {"type": "keyword"},
                "io_kubernetes_workload_type": {"type": "keyword"},
                "labels": {
                    "properties": {
                        "agones_dev_gameserver": {"type": "keyword"},
                        "agones_dev_role": {"type": "keyword"},
                        "agones_dev_safe_to_evict": {"type": "keyword"},
                        "component": {"type": "keyword"},
                        "part_of": {"type": "keyword"},
                    }
                },
            }
        },
        "bk_host_id": {"type": "integer"},
        "cloudId": {"type": "integer"},
        "cluster_id": {"type": "alias", "path": "__ext.bk_bcs_cluster_id"},
        "container_id": {"type": "alias", "path": "__ext.container_id"},
        "container_name": {"type": "alias", "path": "__ext.container_name"},
        "dtEventTimeStamp": {"type": "date", "format": "epoch_millis"},
        "gseIndex": {"type": "long"},
        "image_name": {"type": "alias", "path": "__ext.container_image"},
        "iterationIndex": {"type": "integer"},
        "log": {"type": "text", "norms": False},
        "namespace": {"type": "alias", "path": "__ext.io_kubernetes_pod_namespace"},
        "path": {"type": "keyword"},
        "pod_ip": {"type": "alias", "path": "__ext.io_kubernetes_pod_ip"},
        "pod_name": {"type": "alias", "path": "__ext.io_kubernetes_pod"},
        "pod_uid": {"type": "alias", "path": "__ext.io_kubernetes_pod_uid"},
        "serverIp": {"type": "keyword"},
        "time": {"type": "date", "format": "epoch_millis"},
        "workload_name": {"type": "alias", "path": "__ext.io_kubernetes_workload_name"},
        "workload_type": {"type": "alias", "path": "__ext.io_kubernetes_workload_type"},
    }

    alias_field_list = [
        "__ext.bk_bcs_cluster_id",
        "__ext.container_id",
        "__ext.container_name",
        "__ext.container_image",
        "__ext.io_kubernetes_pod_namespace",
        "__ext.io_kubernetes_pod_ip",
        "__ext.io_kubernetes_pod",
        "__ext.io_kubernetes_pod_uid",
        "__ext.io_kubernetes_workload_name",
        "__ext.io_kubernetes_workload_type",
    ]
    assert es_mapping_same(
        es_properties=es_properties, current_mapping=current_mapping, alias_field_list=alias_field_list
    )
