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
import json
import math
from typing import Optional

from django.conf import settings
from django.db import models
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from elasticsearch_dsl import Q
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm import constants
from apm.constants import (
    DATABASE_CONNECTION_NAME,
    DEFAULT_APM_ES_WARM_RETENTION_RATIO,
    GLOBAL_CONFIG_BK_BIZ_ID,
)
from apm.core.handlers.bk_data.constants import FlowStatus
from apm.utils.es_search import EsSearch
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.user import get_global_user
from common.log import logger
from constants.apm import FlowType, OtlpKey, SpanKind
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.result_table import ResultTableField
from core.drf_resource import api, resource
from metadata import models as metadata_models

from .doris import BkDataDorisProvider


class ApmDataSourceConfigBase(models.Model):
    TRACE_DATASOURCE = "trace"
    METRIC_DATASOURCE = "metric"
    PROFILE_DATASOURCE = "profile"

    TABLE_SPACE_PREFIX = "space"

    DATASOURCE_CHOICE = ((TRACE_DATASOURCE, "Trace"), (METRIC_DATASOURCE, _("指标")))

    DATA_NAME_PREFIX = "bkapm"

    DATASOURCE_TYPE_MAP = {METRIC_DATASOURCE: "metric", TRACE_DATASOURCE: "trace"}

    # target字段配置
    DATA_ID_PARAM = None
    DATASOURCE_TYPE = None

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("所属应用", max_length=255)
    bk_data_id = models.IntegerField("数据id", default=-1)
    result_table_id = models.CharField("结果表id", max_length=128, default="")

    class Meta:
        abstract = True

    @property
    def data_name(self) -> str:
        bk_biz_id = int(self.bk_biz_id)

        if bk_biz_id > 0:
            return f"{bk_biz_id}_{self.DATA_NAME_PREFIX}_{self.DATASOURCE_TYPE}_{self.app_name}"
        else:
            return (
                f"{self.TABLE_SPACE_PREFIX}_{-bk_biz_id}"
                f"_{self.DATA_NAME_PREFIX}_{self.DATASOURCE_TYPE}_{self.app_name}"
            )

    @property
    def table_id(self) -> str:
        raise NotImplementedError

    @classmethod
    def start(cls, bk_biz_id, app_name):
        cls.objects.get(bk_biz_id=bk_biz_id, app_name=app_name).switch_result_table(True)

    @classmethod
    def stop(cls, bk_biz_id, app_name):
        cls.objects.get(bk_biz_id=bk_biz_id, app_name=app_name).switch_result_table(False)

    def switch_result_table(self, is_enable=True):
        resource.metadata.modify_result_table(
            {"table_id": self.result_table_id, "is_enable": is_enable, "operator": get_global_user()}
        )

    def create_data_id(self):
        try:
            data_id_info = resource.metadata.query_data_source({"data_name": self.data_name})
        except metadata_models.DataSource.DoesNotExist:
            # 临时支持数据链路
            data_link = DataLink.get_data_link(self.bk_biz_id)
            data_link_param = {}
            if data_link and data_link.kafka_cluster_id:
                data_link_param["mq_cluster"] = data_link.kafka_cluster_id
                if self.DATASOURCE_TYPE == self.METRIC_DATASOURCE:
                    if data_link.metric_transfer_cluster_id:
                        data_link_param["transfer_cluster"] = data_link.metric_transfer_cluster_id
                if self.DATASOURCE_TYPE == self.TRACE_DATASOURCE:
                    if data_link.trace_transfer_cluster_id:
                        data_link_param["transfer_cluster"] = data_link.trace_transfer_cluster_id
            param = {
                "data_name": self.data_name,
                "operator": get_global_user(),
                "data_description": self.data_name,
                **self.DATA_ID_PARAM,
                **data_link_param,
            }
            data_id_info = resource.metadata.create_data_id(param)
        bk_data_id = data_id_info["bk_data_id"]
        self.bk_data_id = bk_data_id
        self.save()
        return bk_data_id

    def create_or_update_result_table(self, **option):
        pass

    def to_json(self):
        return {"bk_data_id": self.bk_data_id, "result_table_id": self.result_table_id}

    @classmethod
    @atomic(using=DATABASE_CONNECTION_NAME)
    def apply_datasource(cls, bk_biz_id, app_name, **option):
        obj = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not obj:
            obj = cls.objects.create(bk_biz_id=bk_biz_id, app_name=app_name)
        # 创建data_id
        obj.create_data_id()
        # 创建结果表
        obj.create_or_update_result_table(**option)


class MetricDataSource(ApmDataSourceConfigBase):
    DATASOURCE_TYPE = ApmDataSourceConfigBase.METRIC_DATASOURCE

    DEFAULT_MEASUREMENT = "__default__"

    DATA_ID_PARAM = {
        "etl_config": "bk_standard_v2_time_series",
        "type_label": DataTypeLabel.TIME_SERIES,
        "source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
        "option": {"inject_local_time": True},
    }

    METRIC_NAME = "bk_apm_duration"

    time_series_group_id = models.IntegerField("时序分组ID", default=0)
    data_label = models.CharField("数据标签", max_length=128, default="")
    bk_data_virtual_metric_config = JsonField("数据平台虚拟指标配置", null=True)

    def to_json(self):
        return {
            "bk_data_id": self.bk_data_id,
            "result_table_id": self.result_table_id,
            "time_series_group_id": self.time_series_group_id,
        }

    @property
    def event_group_name(self) -> str:
        return f"bkapm_{self.app_name}_{self.DATASOURCE_TYPE}"

    @property
    def table_id(self) -> str:
        bk_biz_id = int(self.bk_biz_id)

        if bk_biz_id > 0:
            return (
                f"{bk_biz_id}_{self.DATA_NAME_PREFIX}_"
                f"{self.DATASOURCE_TYPE}_{self.app_name}.{self.DEFAULT_MEASUREMENT}"
            )
        else:
            return (
                f"{self.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{self.DATA_NAME_PREFIX}_"
                f"{self.DATASOURCE_TYPE}_{self.app_name}.{self.DEFAULT_MEASUREMENT}"
            )

    def create_or_update_result_table(self, **option):
        if self.result_table_id != "":
            return
        params = {
            "operator": get_global_user(),
            "bk_data_id": self.bk_data_id,
            # 平台级接入，ts_group 业务id对应为0
            "bk_biz_id": self.bk_biz_id,
            "time_series_group_name": self.event_group_name,
            "label": "application_check",
            "table_id": self.table_id,
            "is_split_measurement": True,
        }
        datalink = DataLink.get_data_link(self.bk_biz_id)
        if datalink and datalink.influxdb_cluster_name:
            params["default_storage_config"] = {"proxy_cluster_name": datalink.influxdb_cluster_name}
            logger.info(
                f"[MetricDataSource] bk_data_id: {self.bk_data_id} app_name: {self.app_name} "
                f"use proxy_cluster_name: {datalink.influxdb_cluster_name}"
            )

        group_info = resource.metadata.create_time_series_group(params)
        resource.metadata.modify_time_series_group(
            {
                "time_series_group_id": group_info["time_series_group_id"],
                "field_list": [
                    {
                        "field_name": self.METRIC_NAME,
                        "field_type": "float",
                        "tag": "metric",
                        "description": f"{self.app_name}",
                        "unit": "ns",
                    }
                ],
                "operator": get_global_user(),
            }
        )
        self.time_series_group_id = group_info["time_series_group_id"]
        self.result_table_id = group_info["table_id"]
        self.data_label = group_info["label"]
        self.save()

    def update_fields(self, field_list):
        return resource.metadata.modify_time_series_group(
            {
                "time_series_group_id": self.time_series_group_id,
                "field_list": field_list,
                "operator": get_global_user(),
            }
        )


class TraceDataSource(ApmDataSourceConfigBase):
    DATASOURCE_TYPE = ApmDataSourceConfigBase.TRACE_DATASOURCE
    CONCURRENT_NUMBER = 5
    DATA_ID_PARAM = {
        "etl_config": "bk_flat_batch",
        "type_label": DataTypeLabel.LOG,
        "source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
        "option": {
            "encoding": "UTF-8",
            "is_log_data": True,
            "allow_metrics_missing": True,
        },
    }

    EVENT_EXCEPTION_NAME = "exception"

    STORAGE_TYPE = "elasticsearch"

    ES_KEYWORD_OPTION = {"es_type": "keyword"}

    # object 字段配置
    ES_OBJECT_OPTION = {"es_type": "object", "es_dynamic": True}

    # NESTED 配置
    ES_NESTED_OPTION = {"es_type": "nested"}

    # OTLP status 配置
    TRACE_STATUS_OPTION = {
        **ES_OBJECT_OPTION,
        "es_properties": {"message": {"type": "text"}, "code": {"type": "integer"}},
    }

    # OTLP events 配置
    TRACE_EVENT_OPTION = {
        **ES_NESTED_OPTION,
        "es_properties": {
            "attributes": {
                "properties": {
                    "exception": {"properties": {"message": {"type": "text"}, "stacktrace": {"type": "text"}}},
                    "message": {"type": "object"},
                }
            },
            "timestamp": {"type": "long"},
        },
    }

    # 默认的动态维度发现配置
    ES_DYNAMIC_CONFIG = {
        "dynamic_templates": [
            {
                "strings_as_keywords": {
                    "match_mapping_type": "string",
                    "mapping": {"norms": "false", "type": "keyword"},
                }
            }
        ]
    }

    # 默认ES配置信息
    STORAGE_ES_CONFIG = {
        "retention": 15,
        # 默认1天区分一个index
        "slice_gap": 60 * 24,
        "date_format": "%Y%m%d",
        "mapping_settings": ES_DYNAMIC_CONFIG,
        "index_settings": {
            "number_of_shards": 3,
            "number_of_replicas": 1,
        },
    }

    # TRACE 存储字段信息
    TRACE_FIELD_LIST = [
        {
            "field_name": "attributes",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_OBJECT_OPTION,
            "is_config_by_user": True,
            "description": "Span Attributes",
        },
        {
            "field_name": "resource",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_OBJECT_OPTION,
            "is_config_by_user": True,
            "description": "Span Resources",
        },
        {
            "field_name": "events",
            "field_type": ResultTableField.FIELD_TYPE_NESTED,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": TRACE_EVENT_OPTION,
            "is_config_by_user": True,
            "description": "Span Events",
        },
        {
            "field_name": "elapsed_time",
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span Elapsed Time",
        },
        {
            "field_name": "end_time",
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span End Time",
        },
        {
            "field_name": "start_time",
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span Start Time",
        },
        {
            "field_name": "kind",
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Span Kind",
        },
        {
            "field_name": "links",
            "field_type": ResultTableField.FIELD_TYPE_NESTED,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_NESTED_OPTION,
            "is_config_by_user": True,
            "description": "Span Links",
        },
        {
            "field_name": "parent_span_id",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Parent Span ID",
        },
        {
            "field_name": "span_id",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Span ID",
        },
        {
            "field_name": "span_name",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Span Name",
        },
        {
            "field_name": "status",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": TRACE_STATUS_OPTION,
            "is_config_by_user": True,
            "description": "Span Status",
        },
        {
            "field_name": "trace_id",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Trace ID",
        },
        {
            "field_name": "trace_state",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Trace State",
        },
    ]

    FILTER_KIND = {
        "does not exists": lambda field_name, _, q: q.query("bool", must_not=[Q("exists", field=field_name)]),
        "exists": lambda field_name, _, q: q.query("bool", must=[Q("exists", field=field_name)]),
        "=": lambda field_name, value, q: q.query("bool", must=[Q("terms", **{field_name: value})]),
        "!=": lambda field_name, value, q: q.query("bool", must_not=[Q("terms", **{field_name: value})]),
    }

    NESTED_FILED = ["events", "links"]

    NESTED_FILTER_KIND = {
        "does not exists": lambda field_name, _, q: q.query("bool", must_not=[Q("exists", field=field_name)]),
        "exists": lambda field_name, _, q: q.query("bool", must=[Q("exists", field=field_name)]),
        "=": lambda field_name, value, q: q.query("bool", must=[Q("terms", **{field_name: value})]),
        "!=": lambda field_name, value, q: q.query("bool", must_not=[Q("terms", **{field_name: value})]),
    }

    ENDPOINT_FILTER_PARAMS = [
        {
            "key": OtlpKey.KIND,
            "op": "=",
            "value": [
                SpanKind.SPAN_KIND_SERVER,
                SpanKind.SPAN_KIND_CLIENT,
                SpanKind.SPAN_KIND_CONSUMER,
                SpanKind.SPAN_KIND_PRODUCER,
            ],
        }
    ]

    CATEGORY_PARAMS = {
        "http": [
            {
                "key": OtlpKey.get_attributes_key(SpanAttributes.HTTP_METHOD),
                "op": "exists",
                "value": [],
            }
        ],
        "rpc": [
            {
                "key": OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM),
                "op": "exists",
                "value": [],
            }
        ],
        "db": [
            {
                "key": OtlpKey.get_attributes_key(SpanAttributes.DB_SYSTEM),
                "op": "exists",
                "value": [],
            }
        ],
        "messaging": [
            {
                "key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM),
                "op": "exists",
                "value": [],
            },
            {
                "key": OtlpKey.KIND,
                "op": "=",
                "value": [SpanKind.SPAN_KIND_PRODUCER],
            },
        ],
        "async_backend": [
            {
                "key": OtlpKey.KIND,
                "op": "=",
                "value": [SpanKind.SPAN_KIND_CONSUMER],
            }
        ],
        "other": [
            {
                "key": OtlpKey.KIND,
                "op": "=",
                "value": [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_SERVER],
            },
            {
                "key": OtlpKey.get_attributes_key(SpanAttributes.DB_SYSTEM),
                "op": "does not exists",
                "value": [],
            },
            {
                "key": OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM),
                "op": "does not exists",
                "value": [],
            },
            {
                "key": OtlpKey.get_attributes_key(SpanAttributes.HTTP_METHOD),
                "op": "does not exists",
                "value": [],
            },
        ],
    }

    SERVICE_CATEGORY_KIND = [
        SpanAttributes.DB_SYSTEM,
        SpanAttributes.MESSAGING_SYSTEM,
        SpanAttributes.RPC_SYSTEM,
        SpanAttributes.HTTP_METHOD,
        SpanAttributes.MESSAGING_DESTINATION,
    ]

    index_set_id = models.IntegerField("索引集id", null=True)
    index_set_name = models.CharField("索引集名称", max_length=512, null=True)

    @property
    def table_id(self) -> str:
        bk_biz_id = int(self.bk_biz_id)

        if bk_biz_id > 0:
            return f"{bk_biz_id}_{self.DATA_NAME_PREFIX}.{self.DATASOURCE_TYPE}_{self.app_name}"
        else:
            return (
                f"{self.TABLE_SPACE_PREFIX}_"
                f"{-bk_biz_id}_{self.DATA_NAME_PREFIX}.{self.DATASOURCE_TYPE}_{self.app_name}"
            )

    def create_or_update_result_table(self, **option):
        table_id = self.table_id
        if self.result_table_id:
            table_id = self.result_table_id

        params = {
            "bk_data_id": self.bk_data_id,
            # 必须为 库名.表名
            "table_id": table_id,
            "operator": get_global_user(),
            "is_enable": True,
            "table_name_zh": self.app_name,
            "is_custom_table": True,
            "schema_type": "free",
            "default_storage": "elasticsearch",
            "default_storage_config": {
                "cluster_id": option["es_storage_cluster"],
                "storage_cluster_id": option["es_storage_cluster"],
                "slice_size": option.get("es_slice_size", settings.APM_APP_DEFAULT_ES_SLICE_LIMIT),
                "retention": option.get("es_retention", settings.APM_APP_DEFAULT_ES_RETENTION),
                # 默认1天区分一个index
                "slice_gap": 60 * 24,
                "date_format": "%Y%m%d",
                "mapping_settings": self.ES_DYNAMIC_CONFIG,
                "index_settings": {
                    "number_of_shards": option.get("es_shards", settings.APM_APP_DEFAULT_ES_SHARDS),
                    "number_of_replicas": option.get("es_number_of_replicas", settings.APM_APP_DEFAULT_ES_REPLICAS),
                },
            },
            "field_list": self.TRACE_FIELD_LIST,
            "is_time_field_only": True,
            "bk_biz_id": self.bk_biz_id,
            "label": "application_check",
            "option": {
                "es_unique_field_list": ["trace_id", "span_id", "parent_span_id", "start_time", "end_time", "span_name"]
            },
            "time_option": {
                "es_type": "date",
                "es_format": "epoch_millis",
                "time_format": "yyyy-MM-dd HH:mm:ss",
                "time_zone": 0,
            },
        }

        # 获取集群信息
        try:
            cluster_info_list = api.metadata.query_cluster_info(
                {"cluster_id": option["es_storage_cluster"], "cluster_type": "elasticsearch"}
            )
            cluster_info = cluster_info_list[0]
            custom_option = json.loads(cluster_info["cluster_config"].get("custom_option"))
            hot_warm_config = custom_option.get("hot_warm_config", {})
        except Exception as e:
            hot_warm_config = {}
            logger.error("集群ID:{}, error: {}".format(option["es_storage_cluster"], e))

        # 是否启用冷热集群
        if hot_warm_config and hot_warm_config.get("is_enabled"):
            es_retention = option.get("es_retention", settings.APM_APP_DEFAULT_ES_RETENTION)
            allocation_min_days = math.ceil(es_retention * DEFAULT_APM_ES_WARM_RETENTION_RATIO)

            # 对于新数据，路由到热节点
            params["default_storage_config"]["index_settings"].update(
                {
                    f"index.routing.allocation.include.{hot_warm_config['hot_attr_name']}": hot_warm_config[
                        "hot_attr_value"
                    ],
                }
            )
            # n天后的数据，路由到冷节点
            params["default_storage_config"].update(
                {
                    "warm_phase_days": allocation_min_days,
                    "warm_phase_settings": {
                        "allocation_attr_name": hot_warm_config["warm_attr_name"],
                        "allocation_attr_value": hot_warm_config["warm_attr_value"],
                        "allocation_type": "include",
                    },
                }
            )

        index_set_id, index_set_name = self.update_or_create_index_set(option["es_storage_cluster"], self.index_set_id)

        if self.result_table_id != "":
            # 更新存储
            params["external_storage"] = {
                "elasticsearch": params["default_storage_config"],
            }
            resource.metadata.modify_result_table(params)

            return

        params["is_sync_db"] = False
        resource.metadata.create_result_table(params)

        self.result_table_id = self.table_id
        self.index_set_name = index_set_name
        self.index_set_id = index_set_id
        self.save()

    def update_or_create_index_set(self, storage_id, index_set_id=None):
        table_id = self.table_id
        if self.result_table_id:
            table_id = self.result_table_id

        params = {
            "index_set_name": self.index_set,
            "bk_biz_id": self.bk_biz_id,
            "category_id": "application_check",
            "scenario_id": "es",
            "view_roles": [],
            "indexes": [
                {
                    "bk_biz_id": self.bk_biz_id,
                    "result_table_id": f"{table_id.replace('.', '_')}_*",
                }
            ],
            "storage_cluster_id": storage_id,
            "time_field": "time",
            "time_field_unit": "microsecond",
            "time_field_type": "date",
            "is_editable": False,
        }

        if not index_set_id:
            try:
                res = api.log_search.create_index_set(**params)
            except Exception as e:  # noqa
                logger.error(f"[TraceDatasource] create index set failed {e} \nparams: {params}")
                return None, None
        else:
            try:
                res = api.log_search.update_index_set(index_set_id=index_set_id, **params)
            except Exception as e:  # noqa
                logger.error(
                    f"[TraceDatasource] update index set failed {e} "
                    f"\n index set id: {index_set_id} params: {params}"
                )
                return self.index_set_id, self.index_set_name

        return res.get("index_set_id"), res.get("index_set_name")

    @property
    def index_name(self) -> str:
        return f"{self.result_table_id.replace('.', '_')}_*"

    @cached_property
    def retention(self):
        return metadata_models.ESStorage.objects.filter(table_id=self.result_table_id).first().retention

    @cached_property
    def es_client(self):
        return metadata_models.ESStorage.objects.filter(table_id=self.result_table_id).first().get_client()

    @cached_property
    def storage(self):
        return metadata_models.ESStorage.objects.filter(table_id=self.result_table_id).first()

    @property
    def index_set(self) -> str:
        return f"{self.table_id.replace('.', '_')}_index_set"

    @property
    def ping(self):
        return self.es_client.ping()

    @property
    def fetch(self):
        return EsSearch(using=self.es_client, index=self.index_name)

    @classmethod
    def build_filter_params(cls, query, filter_params=None, category=None):
        if not filter_params:
            filter_params = []
        if category:
            category_filter_params = cls.CATEGORY_PARAMS.get(category, cls.ENDPOINT_FILTER_PARAMS)
            filter_params.extend(category_filter_params)
        for filter_param in filter_params:
            first_key, *_ = filter_param["key"].split(".")
            if first_key in cls.NESTED_FILED:
                query = cls.NESTED_FILTER_KIND.get(
                    filter_param["op"],
                    lambda field_name, value, q: q.query("bool", must=[Q("terms", **{field_name: value})]),
                )(filter_param["key"], filter_param["value"], query)
                continue
            query = cls.FILTER_KIND.get(
                filter_param["op"],
                lambda field_name, value, q: q.query("bool", must=[Q("terms", **{field_name: value})]),
            )(filter_param["key"], filter_param["value"], query)
        return query

    @classmethod
    def get_category_kind(cls, attributes):
        for key in cls.SERVICE_CATEGORY_KIND:
            if key in attributes:
                return key, attributes[key]
        return "", ""

    def query_endpoint(self, start_time, end_time, service_name=None, category=None, filter_params=None):
        all_span = self.query_span(start_time, end_time, category=category, filter_params=filter_params)
        result_set = set()
        for span in all_span:
            result_set.add(
                (
                    span[OtlpKey.SPAN_NAME],
                    span[OtlpKey.KIND],
                    span.get(OtlpKey.RESOURCE, {}).get(ResourceAttributes.SERVICE_NAME),
                    self.get_category_kind(span.get(OtlpKey.ATTRIBUTES, {})),
                )
            )
        endpoints = [
            {
                "endpoint_name": span_name,
                "kind": kind,
                "service_name": service_name,
                "category_kind": {"key": category_kind[0], "value": category_kind[1]},
            }
            for span_name, kind, service_name, category_kind in result_set
        ]
        return [endpoint for endpoint in endpoints if not service_name or endpoint.get("service_name") == service_name]

    def query_span(self, start_time, end_time, filter_params=None, fields=None, category=None):
        query = self.fetch.query(
            "bool",
            must=[
                Q("range", end_time={"gt": start_time * 1000 * 1000, "lte": end_time * 1000 * 1000}),
            ],
        ).extra(size=10000)
        if fields:
            query.source(fields)

        query = self.build_filter_params(query, filter_params, category)
        result = []
        try:
            for span in query.execute():
                result.append(span.to_dict())
        except Exception as e:
            logger.error(
                f"[APM][query trace detail] bk_biz_id => [{self.bk_biz_id}] app_name [{self.app_name}] "
                f"es scan data failed => {e}"
            )
        return result

    @classmethod
    def exists_by_trace_ids(cls, app, trace_ids, start_time, end_time):
        """查询在此app下是否有trace_id信息 有的话范围trace_id与app关联"""
        datasource = app.trace_datasource.fetch
        response = (
            datasource.query(
                "bool",
                filter=[Q("terms", **{OtlpKey.TRACE_ID: trace_ids})],
                must=[Q("range", end_time={"gt": start_time * 1000 * 1000, "lte": end_time * 1000 * 1000})],
            )
            .extra(size=10000)
            .execute()
        )
        if not response.hits:
            return {}
        app_info = {"bk_biz_id": app.bk_biz_id, "app_name": app.app_name}
        return {i[OtlpKey.TRACE_ID]: app_info for i in response.hits}

    def query_event(self, start_time: int, end_time: int, name: list, filter_params: dict = None, category: str = None):
        have_events_data_query = (
            self.fetch.query(
                "bool",
                must=[
                    Q("nested", path="events", query=Q("exists", field="events.name")),
                    Q("range", end_time={"gt": start_time * 1000 * 1000, "lte": end_time * 1000 * 1000}),
                ]
                + [
                    Q("nested", path="events", query=Q("terms", events__name=name)),
                ]
                if name
                else [],
            )
            .extra(size=constants.DISCOVER_BATCH_SIZE)
            .source(["events", "resource", "span_name"])
        )
        have_events_data_query = self.build_filter_params(have_events_data_query, filter_params, category)
        result = []
        try:
            for span in have_events_data_query.execute():
                span_dict = span.to_dict()
                events = span_dict.get("events", [])
                for event in events:
                    event["service_name"] = span_dict.get(OtlpKey.RESOURCE, {}).get(ResourceAttributes.SERVICE_NAME)
                    event["endpoint_name"] = span_dict.get("span_name")
                result.extend(events)
        except Exception as e:
            logger.error(
                f"[APM][query event] bk_biz_id => [{self.bk_biz_id}] app_name [{self.app_name}] "
                f"es scan data failed => {e}"
            )
        return result

    def fields(self):
        mapping = self.es_client.indices.get_mapping(index=self.index_name)
        properties = self._get_properties(mapping)
        fields = {}
        for propertie in properties:
            fields = self._get_fields(propertie, fields)
        return fields

    @classmethod
    def _get_fields(cls, propertie: dict, fields: dict):
        for field_name, field_attr in propertie.items():
            if not isinstance(field_attr, dict):
                continue
            if "properties" in field_attr:
                field_attr["name"] = field_name
                cls._get_field(field_attr, fields)
                continue
            if "type" not in field_attr:
                continue
            fields[field_name] = field_attr["type"]
        return fields

    @classmethod
    def _get_field(cls, obj: dict, fields: dict):
        for field_name, field_attr in obj["properties"].items():
            if not isinstance(field_attr, dict):
                continue
            if "properties" in field_attr:
                field_attr["name"] = f"{obj['name']}.{field_name}"
                cls._get_field(field_attr, fields)
                continue
            fields[f"{obj['name']}.{field_name}"] = field_attr["type"]
        return fields

    @classmethod
    def _get_properties(cls, mapping: dict):
        properties = []
        for value in mapping.values():
            cur = value.get("mappings", {})
            cls._mappings_properties(cur, properties)
        return properties

    @classmethod
    def _mappings_properties(cls, mappings: dict, properties: list):
        if not isinstance(mappings, dict):
            return
        if "properties" in mappings:
            properties.append(mappings["properties"])
            return
        for v in mappings.values():
            cls._mappings_properties(v, properties)


class ProfileDataSource(ApmDataSourceConfigBase):
    """Profile 数据源"""

    DATASOURCE_TYPE = ApmDataSourceConfigBase.PROFILE_DATASOURCE

    BUILTIN_APP_NAME = "builtin_profile_app"
    _CACHE_BUILTIN_DATASOURCE: Optional['ProfileDataSource'] = None

    retention = models.IntegerField("过期时间", null=True)
    created = models.DateTimeField("创建时间", auto_now_add=True)
    updated = models.DateTimeField("更新时间", auto_now=True)

    @property
    def table_id(self) -> str:
        bk_biz_id = int(self.bk_biz_id)
        return f"{bk_biz_id}_{self.DATA_NAME_PREFIX}.{self.DATASOURCE_TYPE}_{self.app_name}"

    @classmethod
    @atomic(using=DATABASE_CONNECTION_NAME)
    def apply_datasource(cls, bk_biz_id, app_name, **option):
        obj = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not obj:
            obj = cls.objects.create(bk_biz_id=bk_biz_id, app_name=app_name)
        # 创建接入
        essentials = BkDataDorisProvider.from_datasource_instance(obj, operator=get_global_user()).provider(**option)

        obj.bk_data_id = essentials["bk_data_id"]
        obj.result_table_id = essentials["result_table_id"]
        obj.retention = essentials["retention"]
        obj.save(update_fields=["bk_data_id", "result_table_id", "updated"])
        return

    @classmethod
    @atomic(using=DATABASE_CONNECTION_NAME)
    def create_builtin_source(cls):
        builtin_biz = api.cmdb.get_blueking_biz()
        # datasource is enough, no real app created.
        cls.apply_datasource(bk_biz_id=builtin_biz, app_name=cls.BUILTIN_APP_NAME)
        cls._CACHE_BUILTIN_DATASOURCE = cls.objects.get(bk_biz_id=builtin_biz, app_name=cls.BUILTIN_APP_NAME)

    @classmethod
    def get_builtin_source(cls) -> Optional['ProfileDataSource']:
        if cls._CACHE_BUILTIN_DATASOURCE:
            return cls._CACHE_BUILTIN_DATASOURCE

        builtin_biz = api.cmdb.get_blueking_biz()
        try:
            return cls.objects.get(bk_biz_id=builtin_biz, app_name=cls.BUILTIN_APP_NAME)
        except cls.DoesNotExist:
            return None


class DataLink(models.Model):
    """
    数据链路配置
    预计算数据存储配置数据格式: (可以将预计算数据存储不同集群中)
    {
        "cluster": [
            {
                "cluster_id": 1,
                "table_name": "xx"
            },
            {
                "cluster_id": 2,
                "table_name": "xx"
            }
        ]
    }
    """

    bk_biz_id = models.IntegerField("业务id")
    trace_transfer_cluster_id = models.CharField("Trace Es Transfer集群id", max_length=128, null=True)
    metric_transfer_cluster_id = models.CharField("Metric Transfer集群id", max_length=128, null=True)
    kafka_cluster_id = models.IntegerField("kafka集群id", null=True)
    influxdb_cluster_name = models.CharField("时序数据存储的influxdb集群名称", max_length=128, null=True)
    elasticsearch_cluster_id = models.IntegerField("默认ES集群ID(在快速创建应用、创建默认预计算集群时会用到)", null=True)
    pre_calculate_config = JsonField("预计算数据存储配置", null=True)

    @classmethod
    def get_data_link(cls, bk_biz_id):
        data_link = cls.objects.filter(bk_biz_id=bk_biz_id).first()
        if data_link:
            return data_link
        # 取全局默认配置
        data_link = cls.objects.filter(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID).first()
        return data_link

    @classmethod
    def create_global(cls, **kwargs):
        return cls.objects.create(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID, **kwargs)


class BkdataFlowConfig(models.Model):
    """
    计算平台APM Flow管理
    以下Flow的配置由此表管理:
    1. APM尾部采样
    """

    bk_biz_id = models.IntegerField("监控业务id")
    app_name = models.CharField("应用名称", max_length=50)
    is_finished = models.BooleanField("是否已配置完成", default=False)
    finished_time = models.DateTimeField("配置完成时间", null=True)
    project_id = models.CharField("project id", null=True, max_length=128)
    deploy_bk_biz_id = models.IntegerField("计算平台数据源所在的业务ID")
    deploy_data_id = models.CharField("数据源dataid", null=True, max_length=128)
    deploy_config = models.JSONField("数据源配置", null=True)
    databus_clean_id = models.CharField("清洗配置ID", null=True, max_length=128)
    databus_clean_config = models.JSONField("清洗配置", null=True)
    databus_clean_result_table_id = models.CharField("清洗输出结果表ID", null=True, max_length=128)
    flow_id = models.CharField("dataflow id", null=True, max_length=128)
    status = models.CharField("配置状态", null=True, choices=FlowStatus.choices, max_length=64)
    process_info = models.JSONField("执行日志", null=True)
    last_process_time = models.DateTimeField("上次执行时间", null=True)
    flow_type = models.CharField("Flow类型", choices=FlowType.choices, max_length=32)

    create_at = models.DateTimeField("创建时间", auto_now_add=True)
    update_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "APM Flow管理表"
