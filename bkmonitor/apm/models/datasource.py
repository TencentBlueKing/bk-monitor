"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
import json
import math
import operator
import re
from functools import reduce
from typing import Any, ClassVar, Optional

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.functional import cached_property
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm import constants
from apm.constants import (
    DATABASE_CONNECTION_NAME,
    DEFAULT_APM_ES_WARM_RETENTION_RATIO,
    GLOBAL_CONFIG_BK_BIZ_ID,
)
from apm.core.handlers.bk_data.constants import FlowStatus
from apm.models.doris import BkDataDorisProvider
from apm.utils.es_search import EsSearch
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.user import get_global_user
from common.log import logger
from constants.apm import (
    FlowType,
    OtlpKey,
    SpanKind,
    TRACE_RESULT_TABLE_OPTION,
    TraceDataSourceConfig,
    DEFAULT_DATA_LABEL,
)
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from core.errors.api import BKAPIError
from metadata import models as metadata_models


class ApmDataSourceConfigBase(models.Model):
    LOG_DATASOURCE = "log"
    TRACE_DATASOURCE = "trace"
    METRIC_DATASOURCE = "metric"
    PROFILE_DATASOURCE = "profile"

    TABLE_SPACE_PREFIX = "space"

    DATASOURCE_CHOICE = (
        (TRACE_DATASOURCE, "Log"),
        (TRACE_DATASOURCE, "Trace"),
        (METRIC_DATASOURCE, "Metric"),
        (PROFILE_DATASOURCE, "Profile"),
    )

    DATA_NAME_PREFIX = "bkapm"

    DATASOURCE_TYPE_MAP = {
        METRIC_DATASOURCE: "metric",
        LOG_DATASOURCE: "log",
        TRACE_DATASOURCE: "trace",
        PROFILE_DATASOURCE: "profile",
    }

    # target字段配置
    DATA_ID_PARAM: ClassVar[dict[str, Any]]
    DATASOURCE_TYPE: ClassVar[str]

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("所属应用", max_length=255)
    bk_data_id = models.IntegerField("数据id", default=-1)
    result_table_id = models.CharField("结果表id", max_length=128, default="")

    class Meta:
        abstract = True
        index_together = [["bk_biz_id", "app_name"]]

    @property
    def data_name(self) -> str:
        bk_biz_id = int(self.bk_biz_id)

        if bk_biz_id > 0:
            return f"{bk_biz_id}_{self.DATA_NAME_PREFIX}_{self.DATASOURCE_TYPE}_{self.app_name}"
        else:
            return (
                f"{self.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{self.DATA_NAME_PREFIX}_{self.DATASOURCE_TYPE}_{self.app_name}"
            )

    @property
    def table_id(self) -> str:
        raise NotImplementedError

    @classmethod
    def get_table_id(cls, bk_biz_id: int, app_name: str, **kwargs) -> str:
        raise NotImplementedError

    @classmethod
    def start(cls, bk_biz_id, app_name):
        instance = cls.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        if instance:
            instance.switch_result_table(True)

    @classmethod
    def stop(cls, bk_biz_id, app_name):
        instance = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if instance:
            instance.switch_result_table(False)

    def switch_result_table(self, is_enable=True):
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        resource.metadata.modify_result_table(
            {
                "table_id": self.result_table_id,
                "is_enable": is_enable,
                "bk_tenant_id": bk_tenant_id,
                "operator": get_global_user(bk_tenant_id=bk_tenant_id),
            }
        )

    def create_data_id(self):
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        if self.bk_data_id != -1:
            return self.bk_data_id
        try:
            data_id_info = resource.metadata.query_data_source(bk_tenant_id=bk_tenant_id, data_name=self.data_name)
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
            data_id_info = resource.metadata.create_data_id(
                {
                    "bk_tenant_id": bk_tenant_id,
                    "bk_biz_id": self.bk_biz_id,
                    "data_name": self.data_name,
                    "operator": get_global_user(bk_tenant_id=bk_tenant_id),
                    "data_description": self.data_name,
                    **self.DATA_ID_PARAM,
                    **data_link_param,
                }
            )
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
    def apply_datasource(cls, bk_biz_id, app_name, **options):
        obj = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not obj:
            obj = cls.objects.create(bk_biz_id=bk_biz_id, app_name=app_name)
        # 创建data_id
        obj.create_data_id()
        # 创建结果表
        obj.create_or_update_result_table(**options)

        option = options["option"]
        if not option:
            # 关闭
            obj.stop(bk_biz_id, app_name)


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
        return self.get_table_id(bk_biz_id, self.app_name)

    @classmethod
    def get_table_id(cls, bk_biz_id: int, app_name: str, **kwargs) -> str:
        if bk_biz_id > 0:
            return f"{bk_biz_id}_{cls.DATA_NAME_PREFIX}_{cls.DATASOURCE_TYPE}_{app_name}.{cls.DEFAULT_MEASUREMENT}"
        else:
            return (
                f"{cls.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{cls.DATA_NAME_PREFIX}_"
                f"{cls.DATASOURCE_TYPE}_{app_name}.{cls.DEFAULT_MEASUREMENT}"
            )

    def create_or_update_result_table(self, **option):
        if self.result_table_id != "":
            return

        bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        global_user = get_global_user(bk_tenant_id=bk_tenant_id)
        params = {
            "operator": global_user,
            "bk_data_id": self.bk_data_id,
            # 平台级接入，ts_group 业务id对应为0
            "bk_biz_id": self.bk_biz_id,
            "bk_tenant_id": bk_tenant_id,
            "time_series_group_name": self.event_group_name,
            "label": "application_check",
            "table_id": self.table_id,
            "data_label": DEFAULT_DATA_LABEL,
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
                "bk_tenant_id": bk_tenant_id,
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
                "operator": global_user,
            }
        )
        self.time_series_group_id = group_info["time_series_group_id"]
        self.result_table_id = group_info["table_id"]
        self.data_label = group_info["data_label"]
        self.save()

    def update_fields(self, field_list):
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        return resource.metadata.modify_time_series_group(
            {
                "bk_tenant_id": bk_tenant_id,
                "time_series_group_id": self.time_series_group_id,
                "field_list": field_list,
                "operator": get_global_user(bk_tenant_id=bk_tenant_id),
            }
        )


class LogDataSource(ApmDataSourceConfigBase):
    DATASOURCE_TYPE = ApmDataSourceConfigBase.LOG_DATASOURCE

    DATA_NAME_PREFIX = "bklog"

    collector_config_id = models.IntegerField("索引集id", null=True)
    index_set_id = models.IntegerField("索引集id", null=True)

    def to_json(self):
        return {
            "bk_data_id": self.bk_data_id,
            "result_table_id": self.result_table_id,
            "collector_config_id": self.collector_config_id,
            "index_set_id": self.index_set_id,
        }

    @property
    def table_id(self) -> str:
        return self.get_table_id(int(self.bk_biz_id), self.app_name)

    @classmethod
    def get_table_id(cls, bk_biz_id: int, app_name: str, **kwargs) -> str:
        valid_app_name = cls.app_name_to_log_config_name(app_name)
        if bk_biz_id > 0:
            return f"{bk_biz_id}_{cls.DATA_NAME_PREFIX}.{valid_app_name}"
        else:
            return f"{cls.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{cls.DATA_NAME_PREFIX}.{valid_app_name}"

    @classmethod
    def app_name_to_log_config_name(cls, app_name: str):
        """
        LOG 和 APM 的英文名不同规则：APM 允许中划线(-)，LOG 不允许，所以这里替换为下划线(_)
        并且日志的名称必须大于等于 5 个字符
        """
        res = app_name.replace("-", "_")
        if len(res) < 5:
            res = f"otlp_{res}"
        return res

    @classmethod
    @atomic(using=DATABASE_CONNECTION_NAME)
    def apply_datasource(cls, bk_biz_id, app_name, **options):
        option = options["option"]
        obj = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()

        if not obj:
            if not option:
                # 如果没有 logDatasource 并且没有开启 直接返回
                return
            obj = cls.objects.create(bk_biz_id=bk_biz_id, app_name=app_name)

        storage_params = {
            "storage_cluster_id": options["es_storage_cluster"],
            "retention": options.get("es_retention", settings.APM_APP_DEFAULT_ES_RETENTION),
            "storage_replies": options.get("es_number_of_replicas", settings.APM_APP_DEFAULT_ES_REPLICAS),
            "es_shards": options.get("es_shards", settings.APM_APP_DEFAULT_ES_SHARDS),
        }

        if obj.bk_data_id == -1:
            # 指定了存储集群会有默认的清洗规则所以这里不需要配置规则
            try:
                valid_log_config_name = cls.app_name_to_log_config_name(app_name)
                response = api.log_search.create_custom_report(
                    **{
                        "bk_tenant_id": bk_biz_id_to_bk_tenant_id(bk_biz_id),
                        "bk_biz_id": bk_biz_id,
                        "collector_config_name_en": valid_log_config_name,
                        "collector_config_name": valid_log_config_name,
                        "custom_type": "otlp_log",
                        "category_id": "application_check",
                        # 兼容集群不支持冷热配置
                        "allocation_min_days": 0,
                        "description": f"APM({app_name})",
                        **storage_params,
                    }
                )
            except BKAPIError as e:
                raise BKAPIError(f"创建日志自定义上报失败：{e}")

            obj.result_table_id = cls.get_table_id(bk_biz_id, app_name)
            obj.collector_config_id = response["collector_config_id"]
            obj.bk_data_id = response["bk_data_id"]
            obj.index_set_id = response["index_set_id"]
            obj.save()
        else:
            # 更新
            try:
                api.log_search.update_custom_report(
                    bk_tenant_id=bk_biz_id_to_bk_tenant_id(bk_biz_id),
                    collector_config_id=obj.collector_config_id,
                    category_id="application_check",
                    collector_config_name=cls.app_name_to_log_config_name(app_name),
                    allocation_min_days=0,
                    **storage_params,
                )
            except BKAPIError as e:
                raise BKAPIError(f"更新日志自定义上报失败：{e}")

    @classmethod
    def start(cls, bk_biz_id, app_name):
        instance = cls.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        api.log_search.start_collectors(collector_config_id=instance.collector_config_id)

    @classmethod
    def stop(cls, bk_biz_id, app_name):
        instance = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if instance:
            api.log_search.stop_collectors(collector_config_id=instance.collector_config_id)


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

    FILTER_KIND = {
        "exists": lambda field_name, _, q: q & Q(**{f"{field_name}__exists": ""}),
        "does not exists": lambda field_name, _, q: q & Q(**{f"{field_name}__nexists": ""}),
        "=": lambda field_name, value, q: q & Q(**{f"{field_name}__eq": value}),
        "!=": lambda field_name, value, q: q & Q(**{f"{field_name}__neq": value}),
    }

    NESTED_FILED = ["events", "links"]

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

    GROUP_KEY_CONFIG = {
        "db_system": OtlpKey.get_attributes_key(SpanAttributes.DB_SYSTEM),
        "http_url": OtlpKey.get_attributes_key(SpanAttributes.HTTP_URL),
        "messaging_system": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM),
        "rpc_system": OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM),
        "trpc_callee_method": OtlpKey.get_attributes_key("trpc.callee_method"),
    }

    GROUP_KEY_FILTER_CONFIG = {
        "db_system": Q(**{f"{OtlpKey.get_attributes_key(SpanAttributes.DB_SYSTEM)}__exists": ""}),
        "http_url": Q(**{f"{OtlpKey.get_attributes_key(SpanAttributes.HTTP_URL)}__exists": ""}),
        "messaging_system": Q(**{f"{OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM)}__exists": ""}),
        "rpc_system": Q(**{f"{OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM)}__exists": ""}),
        "trpc_callee_method": Q(**{f"{OtlpKey.get_attributes_key('trpc.namespace')}__exists": ""}),
    }

    DEFAULT_LIMIT_MAX_SIZE = 10000

    index_set_id = models.IntegerField("索引集id", null=True)
    index_set_name = models.CharField("索引集名称", max_length=512, null=True)

    def to_json(self):
        return {**super().to_json(), "index_set_id": self.index_set_id}

    @property
    def table_id(self) -> str:
        return self.get_table_id(int(self.bk_biz_id), self.app_name)

    @classmethod
    def get_table_id(cls, bk_biz_id: int, app_name: str, **kwargs) -> str:
        if bk_biz_id > 0:
            return f"{bk_biz_id}_{cls.DATA_NAME_PREFIX}.{cls.DATASOURCE_TYPE}_{app_name}"
        else:
            return f"{cls.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{cls.DATA_NAME_PREFIX}.{cls.DATASOURCE_TYPE}_{app_name}"

    def create_or_update_result_table(self, **option):
        table_id = self.table_id
        if self.result_table_id:
            table_id = self.result_table_id

        bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        params = {
            "bk_data_id": self.bk_data_id,
            # 必须为 库名.表名
            "table_id": table_id,
            "bk_tenant_id": bk_tenant_id,
            "operator": get_global_user(bk_tenant_id=bk_tenant_id),
            "is_enable": True,
            "table_name_zh": self.app_name,
            "is_custom_table": True,
            "schema_type": "free",
            "default_storage": "elasticsearch",
            "default_storage_config": {
                "cluster_id": option["es_storage_cluster"],
                "storage_cluster_id": option["es_storage_cluster"],
                # 指定 UnifyQuery 查询索引。
                "index_set": self.table_id.replace(".", "_"),
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
            "field_list": TraceDataSourceConfig.TRACE_FIELD_LIST,
            "is_time_field_only": True,
            "bk_biz_id": self.bk_biz_id,
            "label": "application_check",
            "option": TRACE_RESULT_TABLE_OPTION,
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
                bk_tenant_id=bk_biz_id_to_bk_tenant_id(self.bk_biz_id),
                cluster_id=option["es_storage_cluster"],
                cluster_type="elasticsearch",
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
                    f"[TraceDatasource] update index set failed {e} \n index set id: {index_set_id} params: {params}"
                )
                return self.index_set_id, self.index_set_name

        return res.get("index_set_id"), res.get("index_set_name")

    @cached_property
    def index_name(self) -> str:
        try:
            # 获取索引名称列表
            es_index_name = self.result_table_id.replace(".", "_")
            routes_str = self.es_client.transport.perform_request(
                "GET",
                f"/_cat/indices/{es_index_name}_*_*?h=index",
            )
            # 过滤出有效的索引名称
            index_names = self._filter_and_sort_valid_index_names(
                self.app_name,
                index_names=[i for i in routes_str.split("\n") if i],
            )
            if not index_names:
                raise ValueError("[IndexName] valid indexName not found!")
            return ",".join(index_names)
        except Exception as e:  # noqa
            res = f"{self.result_table_id.replace('.', '_')}_*"
            logger.error(f"[IndexName] retrieve failed, error: {e}, use default: {res}")
            return res

    @classmethod
    def _filter_and_sort_valid_index_names(cls, app_name, index_names):
        date_index_pairs = []
        pattern = re.compile(rf".*_bkapm_trace_{re.escape(app_name)}_(\d{{8}})_(\d+)$")

        for name in index_names:
            match = pattern.search(name)
            if match:
                date_str = match.group(1)
                num = int(match.group(2))
                # 检查 app_name 之后的格式是否是日期类型
                try:
                    date = datetime.datetime.strptime(date_str, "%Y%m%d")
                    date_index_pairs.append((date, num, name))
                except ValueError:
                    logger.warning(f"[FilterValidIndexName] filter invalid indexName: {name} with wrong dateString")
                    continue

        # 按照时间排序 便于快捷获取最新的索引
        date_index_pairs.sort(reverse=True, key=lambda x: (x[0], x[1]))

        return [i[-1] for i in date_index_pairs]

    @cached_property
    def retention(self):
        return metadata_models.ESStorage.objects.filter(table_id=self.result_table_id).values_list(
            "retention", flat=True
        )[0]

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
    def build_filter_params(cls, filter_params: list[dict[str, Any]] | None, category: str | None) -> Q:
        """根据过滤参数 & 服务分类构建查询条件"""
        if not filter_params:
            filter_params = []
        if category:
            category_filter_params: list[dict[str, Any]] = cls.CATEGORY_PARAMS.get(category, cls.ENDPOINT_FILTER_PARAMS)
            filter_params.extend(category_filter_params)

        q: Q = Q()
        for filter_param in filter_params:
            q = cls.FILTER_KIND.get(filter_param["op"], cls.FILTER_KIND["="])(
                filter_param["key"], filter_param["value"], q
            )
        return q

    def get_q(
        self,
        filter_params: list[dict[str, Any]] | None = None,
        category: str | None = None,
        fields: list[str] | None = None,
    ):
        """根据过滤条件（filter_params）、节点类别（category）、字段列表（fields）构建 QueryConfig"""
        return (
            QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM))
            .table(self.result_table_id)
            .filter(self.build_filter_params(filter_params, category))
            .time_field("end_time")
            .values(*(fields or []))
        )

    def get_qs(self, start_time: int, end_time: int) -> UnifyQuerySet:
        """根据时间范围（start_time、end_time）获取 UnifyQuerySet"""
        return (
            UnifyQuerySet()
            .scope(self.bk_biz_id)
            .time_align(False)
            .start_time(start_time * 1000)
            .end_time(end_time * 1000)
        )

    @classmethod
    def get_category_kind(cls, attributes: dict[str, Any]) -> tuple[str, str]:
        """根据 Attributes 获取节点类别"""
        for key in cls.SERVICE_CATEGORY_KIND:
            if key in attributes:
                return key, attributes[key]
        return "", ""

    def query_endpoint(
        self,
        start_time: int,
        end_time: int,
        service_name: str | None = None,
        filter_params: list[dict[str, Any]] | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询端点 / 接口（Endpoint）列表"""
        if not filter_params:
            filter_params = []

        if service_name:
            # 获取指定服务的数据。
            filter_params.append({"key": ResourceAttributes.SERVICE_NAME, "value": service_name, "op": "="})

        spans: list[dict[str, Any]] = self.query_span(
            start_time,
            end_time,
            filter_params=filter_params,
            fields=[OtlpKey.SPAN_NAME, OtlpKey.KIND, OtlpKey.RESOURCE, OtlpKey.ATTRIBUTES],
            category=category,
        )

        duplicated_endpoints: set[tuple[Any, ...]] = set()
        for span in spans:
            duplicated_endpoints.add(
                (
                    span[OtlpKey.SPAN_NAME],
                    span[OtlpKey.KIND],
                    span.get(OtlpKey.RESOURCE, {}).get(ResourceAttributes.SERVICE_NAME),
                    self.get_category_kind(span.get(OtlpKey.ATTRIBUTES, {})),
                )
            )

        return [
            {
                "endpoint_name": span_name,
                "kind": kind,
                "service_name": service_name,
                "category_kind": {"key": category_kind[0], "value": category_kind[1]},
            }
            for span_name, kind, service_name, category_kind in duplicated_endpoints
        ]

    def query_span(
        self,
        start_time: int,
        end_time: int,
        filter_params: list[dict[str, Any]] | None = None,
        fields: list[str] | None = None,
        category: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """查询 Span 列表"""
        qs: UnifyQuerySet = (
            self.get_qs(start_time, end_time)
            .add_query(self.get_q(filter_params, category, fields))
            .limit(limit or 10_000)
        )
        try:
            return list(qs)
        except Exception as e:
            logger.error(
                f"[APM][query trace detail] bk_biz_id => [{self.bk_biz_id}] app_name [{self.app_name}] "
                f"es scan data failed => {e}"
            )
            return []

    @classmethod
    def _query_field_aggregated_records(
        cls, q: QueryConfigBuilder, qs: UnifyQuerySet, group_by: list[str], field: str, agg_method: str
    ) -> list[dict[str, Any]]:
        """按指定聚合方法（agg_method）计算指定字段（field）的聚合值"""
        aggregated_records: list[dict[str, Any]] = []
        q = q.metric(field=field, method=agg_method, alias="a").alias("a")
        for record in list(qs.add_query(q).time_agg(False).instant()):
            aggregated_records.append(
                {
                    # 某个聚合维度不存在也要展示成空字符串。
                    "dimensions": {field: record.get(field) or "" for field in group_by},
                    "agg_method": agg_method,
                    "value": record["_result_"],
                }
            )

        return aggregated_records

    def query_span_with_group_keys(
        self,
        start_time: int,
        end_time: int,
        group_keys: list[str],
        filter_params: list[dict[str, Any]] | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """按 group_keys 对一段时间内的 Span 数据进行聚合统计
        TODO(crayon) 目前默认拉取 1w 条聚合结果的方式存在性能瓶颈，需改造为前端分页 + TopN 拉取（需 UnifyQuery 支持多 Query 聚合）。
        """
        group_by: list[str] = [
            self.GROUP_KEY_CONFIG[group_key] for group_key in group_keys if group_key in self.GROUP_KEY_CONFIG
        ]
        or_query: Q = reduce(
            operator.or_,
            [
                self.GROUP_KEY_FILTER_CONFIG[group_key]
                for group_key in group_keys
                if group_key in self.GROUP_KEY_FILTER_CONFIG
            ],
        )
        q: QueryConfigBuilder = self.get_q(filter_params, category).group_by(*group_by).filter(or_query)
        qs: UnifyQuerySet = self.get_qs(start_time, end_time).limit(self.DEFAULT_LIMIT_MAX_SIZE)

        pool = ThreadPool(5)
        field_aggregated_records_list = pool.imap_unordered(
            lambda _agg_method: self._query_field_aggregated_records(
                q, qs, group_by, OtlpKey.ELAPSED_TIME, _agg_method
            ),
            ["avg", "max", "min", "sum", "count"],
        )
        pool.close()

        span_group_aggregated_result_map: dict[frozenset, dict[str, Any]] = {}
        field_group_key_map: dict[str, str] = {field: group_key for group_key, field in self.GROUP_KEY_CONFIG.items()}
        for field_aggregated_records in field_aggregated_records_list:
            for record in field_aggregated_records:
                # 将 GroupBy 字段转为 GroupKey，构建 SpanGroup 作为聚合唯一 Key。
                span_group: dict[str, str] = {
                    field_group_key_map.get(field, field): field_value
                    for field, field_value in record["dimensions"].items()
                }

                if record["agg_method"] == "count":
                    construct_value = {"doc_count": record["value"]}
                else:
                    construct_value = {f"{record['agg_method']}_duration": {"value": record["value"]}}

                # 按 SpanGroup 将不同聚合方法的聚合结果进行合并。
                span_group_aggregated_result_map.setdefault(frozenset(span_group.items()), {"key": span_group}).update(
                    construct_value
                )

        return list(span_group_aggregated_result_map.values())

    def query_exists_trace_ids(self, trace_ids: list[str], start_time: int, end_time: int) -> list[str]:
        """过滤出存在的 TraceID 列表"""
        if not trace_ids:
            return []

        spans: list[dict[str, str]] = self.query_span(
            start_time,
            end_time,
            filter_params=[{"key": OtlpKey.TRACE_ID, "op": "=", "value": trace_ids}],
            fields=[OtlpKey.TRACE_ID],
        )
        return list({span[OtlpKey.TRACE_ID] for span in spans})

    def query_event(
        self,
        start_time: int,
        end_time: int,
        name: list[str],
        filter_params: list[dict[str, Any]] | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """获取事件列表"""
        q: QueryConfigBuilder = self.get_q(
            filter_params, category, [OtlpKey.EVENTS, OtlpKey.RESOURCE, OtlpKey.SPAN_NAME, OtlpKey.TRACE_ID]
        ).filter(**{f"{OtlpKey.EVENTS}.name__exists": ""})
        if name:
            # 仅获取包含指定事件名的数据。
            q = q.filter(**{f"{OtlpKey.EVENTS}.name__eq": name})

        try:
            spans: list[dict[str, Any]] = (
                self.get_qs(start_time, end_time).add_query(q).limit(constants.DISCOVER_BATCH_SIZE)
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                f"[APM][query event] bk_biz_id => [{self.bk_biz_id}] app_name [{self.app_name}] "
                f"es scan data failed => {e}"
            )
            return []

        events: list[dict[str, Any]] = []
        for span in spans:
            # 从 Span 提取 / 格式化事件。
            for event in span.get(OtlpKey.EVENTS, []):
                event["service_name"] = span.get(OtlpKey.RESOURCE, {}).get(ResourceAttributes.SERVICE_NAME)
                event["endpoint_name"] = span.get(OtlpKey.SPAN_NAME)
                event["trace_id"] = span.get(OtlpKey.TRACE_ID, "")
                events.append(event)
        return events

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

    @classmethod
    def stop(cls, bk_biz_id, app_name):
        super().stop(bk_biz_id, app_name)
        # 删除关联的索引集
        ins = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if ins:
            try:
                api.log_search.delete_index_set(index_set_id=ins.index_set_id)
                logger.info(f"[StopTraceDatasource] delete index_set_id: {ins.index_set_id} of ({bk_biz_id}){app_name}")
            except BKAPIError as e:
                logger.error(f"[StopTraceDatasource] delete index_set_id: {ins.index_set_id} failed, error: {e}")


class ProfileDataSource(ApmDataSourceConfigBase):
    """Profile 数据源"""

    DATASOURCE_TYPE = ApmDataSourceConfigBase.PROFILE_DATASOURCE

    BUILTIN_APP_NAME = "builtin_profile_app"
    _CACHE_BUILTIN_DATASOURCE: Optional["ProfileDataSource"] = None

    profile_bk_biz_id = models.IntegerField(
        "Profile数据源创建在 bkbase 的业务 id(非业务下创建会与 bk_biz_id 不一致)",
        null=True,
    )
    retention = models.IntegerField("过期时间", null=True)
    created = models.DateTimeField("创建时间", auto_now_add=True)
    updated = models.DateTimeField("更新时间", auto_now=True)

    @property
    def table_id(self) -> str:
        return self.get_table_id(int(self.bk_biz_id), self.app_name)

    @classmethod
    def get_table_id(cls, bk_biz_id: int, app_name: str, **kwargs) -> str:
        return f"{bk_biz_id}_{cls.DATA_NAME_PREFIX}.{cls.DATASOURCE_TYPE}_{app_name}"

    @classmethod
    @atomic(using=DATABASE_CONNECTION_NAME)
    def apply_datasource(cls, bk_biz_id, app_name, **options):
        option = options["option"]
        profile_bk_biz_id = bk_biz_id
        if bk_biz_id < 0:
            # 非业务创建 profile 将创建在公共业务下
            profile_bk_biz_id = settings.BK_DATA_BK_BIZ_ID

        obj = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()

        if not obj:
            if not option:
                # 如果没有 profileDatasource 并且没有开启 直接返回
                return
            obj = cls.objects.create(bk_biz_id=bk_biz_id, app_name=app_name, profile_bk_biz_id=profile_bk_biz_id)
        elif obj.bk_data_id != -1:
            # 如果有 dataId 证明创建过了 profile 因为都是内置配置所以不支持更新 直接返回
            return

        # 创建接入
        apm_maintainers = ",".join(settings.APM_APP_BKDATA_MAINTAINER)
        global_user = get_global_user(bk_tenant_id=bk_biz_id_to_bk_tenant_id(bk_biz_id))
        essentials = BkDataDorisProvider.from_datasource_instance(
            obj,
            maintainer=global_user if not apm_maintainers else f"{global_user},{apm_maintainers}",
            operator=global_user,
            name_stuffix=bk_biz_id,
        ).provider()
        obj.bk_data_id = essentials["bk_data_id"]
        obj.result_table_id = essentials["result_table_id"]
        obj.retention = essentials["retention"]
        obj.save()

        return

    @classmethod
    @atomic(using=DATABASE_CONNECTION_NAME)
    def create_builtin_source(cls):
        # datasource is enough, no real app created.
        cls.apply_datasource(bk_biz_id=settings.DEFAULT_BK_BIZ_ID, app_name=cls.BUILTIN_APP_NAME, option=True)
        cls._CACHE_BUILTIN_DATASOURCE = cls.objects.get(
            bk_biz_id=settings.DEFAULT_BK_BIZ_ID, app_name=cls.BUILTIN_APP_NAME
        )

    @classmethod
    def get_builtin_source(cls) -> Optional["ProfileDataSource"]:
        if cls._CACHE_BUILTIN_DATASOURCE:
            return cls._CACHE_BUILTIN_DATASOURCE

        try:
            return cls.objects.get(bk_biz_id=settings.DEFAULT_BK_BIZ_ID, app_name=cls.BUILTIN_APP_NAME)
        except cls.DoesNotExist:
            return None

    @classmethod
    def start(cls, bk_biz_id, app_name):
        instance = cls.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        api.bkdata.start_databus_cleans(result_table_id=instance.result_table_id)

    @classmethod
    def stop(cls, bk_biz_id, app_name):
        instance = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if instance:
            api.bkdata.stop_databus_cleans(result_table_id=instance.result_table_id)


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
    elasticsearch_cluster_id = models.IntegerField(
        "默认ES集群ID(在快速创建应用、创建默认预计算集群时会用到)", null=True
    )
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

    def to_json(self):
        return {
            "elasticsearch_cluster_id": self.elasticsearch_cluster_id,
        }


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
