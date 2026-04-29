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
from django.utils.translation import gettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm import constants
from apm.constants import (
    DATABASE_CONNECTION_NAME,
    DEFAULT_APM_ES_WARM_RETENTION_RATIO,
    GLOBAL_CONFIG_BK_BIZ_ID,
)
from apm.core.handlers.bk_data.constants import FlowStatus
from apm.models.doris import BkDataDorisProvider, BkDataDorisV4Provider, compose_profile_data_id_name
from apm.models.shared_datasource import BaseSharedDataSource, SHARED_DS_REGISTRY
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
    TelemetryDataType,
    TRACE_RESULT_TABLE_OPTION,
    TraceDataSourceConfig,
    DEFAULT_DATA_LABEL,
)
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from core.errors.api import BKAPIError
from metadata import models as metadata_models


class ApmDataSourceConfigBase(models.Model):
    LOG_DATASOURCE = TelemetryDataType.LOG.value
    TRACE_DATASOURCE = TelemetryDataType.TRACE.value
    METRIC_DATASOURCE = TelemetryDataType.METRIC.value
    # 注：TelemetryDataType.PROFILING.value 为 "profiling"，无法直接使用
    PROFILE_DATASOURCE = "profile"

    TABLE_SPACE_PREFIX = "space"

    DATA_NAME_PREFIX = "bkapm"

    # target字段配置
    DATA_ID_PARAM: ClassVar[dict[str, Any]]
    DATASOURCE_TYPE: ClassVar[str]

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("所属应用", max_length=255)
    bk_data_id = models.IntegerField("数据id", default=-1)
    result_table_id = models.CharField("结果表id", max_length=128, default="")
    shared_datasource_id = models.IntegerField("共享数据源 ID", null=True, default=None)

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
        instance = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not instance:
            return

        # 共享模式：结果表由共享池统一管理，单应用启停仅变更共享池计数
        if instance.is_shared and (shared_ds := instance._get_shared_datasource()):
            if not shared_ds.acquire():
                raise ValueError(_("当前所分配的共享池已达容量上限，请增加容量后再执行此操作"))
            return

        instance.switch_result_table(True)

    @classmethod
    def stop(cls, bk_biz_id, app_name):
        instance = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not instance:
            return

        # 共享模式：结果表由共享池统一管理，单应用启停仅变更共享池计数
        if instance.is_shared and (shared_ds := instance._get_shared_datasource()):
            shared_ds.release()
            return

        instance.switch_result_table(False)

    def _get_shared_datasource(self) -> Optional["BaseSharedDataSource"]:
        shared_cls = SHARED_DS_REGISTRY.get(self.DATASOURCE_TYPE)
        if not shared_cls or not self.shared_datasource_id:
            return None
        return shared_cls.objects.filter(pk=self.shared_datasource_id).first()

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

    def create_data_id(self, global_mode: bool = False, data_name: str | None = None) -> int:
        """创建 DataID。

        :param global_mode: 全局模式，使用特权业务 ID 和 DEFAULT_TENANT_ID，在全局公共空间注册共享数据源。
        :param data_name: 可指定 data_name，若不指定则使用 self.data_name。
        """
        if global_mode:
            bk_biz_id = settings.BKAPP_ADMIN_BIZ_ID
            bk_tenant_id = DEFAULT_TENANT_ID
        else:
            bk_biz_id = self.bk_biz_id
            bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        actual_data_name = data_name or self.data_name

        if self.bk_data_id != -1:
            return self.bk_data_id
        try:
            data_id_info = resource.metadata.query_data_source(bk_tenant_id=bk_tenant_id, data_name=actual_data_name)
        except metadata_models.DataSource.DoesNotExist:
            # 临时支持数据链路
            data_link = DataLink.get_data_link(bk_biz_id)
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
                    "bk_biz_id": bk_biz_id,
                    "data_name": actual_data_name,
                    "operator": get_global_user(bk_tenant_id=bk_tenant_id),
                    "data_description": actual_data_name,
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

    @property
    def is_shared(self) -> bool:
        """判断是否为共享数据源"""
        return self.shared_datasource_id is not None

    def to_link_info(self) -> dict[str, Any]:
        """导出链路元数据字典。

        子类可覆写以追加特有字段
        """
        return {
            "bk_data_id": self.bk_data_id,
            "result_table_id": self.result_table_id,
        }

    def set_from_shared(self, shared_info: dict[str, Any]) -> None:
        """从共享链路信息字典提取字段并赋值。

        子类可覆写以处理扩展字段
        """
        self.bk_data_id = shared_info["bk_data_id"]
        self.result_table_id = shared_info["result_table_id"]
        self.shared_datasource_id = shared_info["shared_datasource_id"]

    def reset_link_info(self) -> None:
        """重置当前数据源链路信息为未创建状态。

        子类可覆写以重置扩展字段
        """
        self.bk_data_id = -1
        self.result_table_id = ""
        self.shared_datasource_id = None

    def to_json(self):
        return {"bk_data_id": self.bk_data_id, "result_table_id": self.result_table_id}

    @classmethod
    @atomic(using=DATABASE_CONNECTION_NAME)
    def apply_datasource(cls, bk_biz_id: int, app_name: str, **options) -> None:
        """创建/更新应用的数据源（支持独占和共享两种模式）"""
        obj = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not obj:
            obj = cls.objects.create(bk_biz_id=bk_biz_id, app_name=app_name)

        is_shared: bool = options.get("is_shared", False)

        # 更新应用时判断模式变化：迁入（独占 → 共享，停用独占资源）或迁出（共享 → 独占，释放共享池占用），随后 reset_link_info，再复用既有创建流程
        if obj.result_table_id != "" and obj.is_shared != is_shared:
            cls.stop(bk_biz_id, app_name)
            obj.reset_link_info()

        if is_shared:
            obj._apply_shared_datasource(**options)
        else:
            obj._apply_exclusive_datasource(**options)

        option = options["option"]
        if not option:
            # 关闭
            obj.stop(bk_biz_id, app_name)

    def _apply_exclusive_datasource(self, **options) -> None:
        """独占模式"""
        # 创建data_id
        self.create_data_id()
        # 创建结果表
        self.create_or_update_result_table(**options)

    def _apply_shared_datasource(self, **options) -> None:
        """共享模式。

        流程：allocate(分配) → [reserve → create → activate] → set_from_shared
        """
        # 幂等保护：已完成共享分配的数据源，重复调用直接返回，防止 allocate 被重复触发导致 usage_count 重复计数
        if self.is_shared:
            return

        shared_cls = SHARED_DS_REGISTRY.get(self.DATASOURCE_TYPE)
        if not shared_cls:
            # 该数据类型不支持共享，降级为独占
            self._apply_exclusive_datasource(**options)
            return

        # 尝试从池中分配
        shared_info = shared_cls.allocate()
        if not shared_info:
            # 无可用共享源，创建新的
            shared_info = self._create_shared_datasource(shared_cls, **options)

        # 将共享链路信息写回到当前数据源
        self.set_from_shared(shared_info)
        self.save()

    def _create_shared_datasource(self, shared_cls: type[BaseSharedDataSource], **options) -> dict[str, Any]:
        """创建新的共享数据源。

        流程：reserve(草稿) → create_data_id → create_or_update_result_table → activate(激活)
        """
        reserved = shared_cls.reserve()

        try:
            self.create_data_id(global_mode=True, data_name=reserved.data_name)
            self.create_or_update_result_table(global_mode=True, table_id=reserved.table_id, **options)
        except Exception:
            reserved.delete()
            raise

        link_info = self.to_link_info()
        reserved.activate(link_info)

        return {**reserved.to_shared_info(), "shared_datasource_id": reserved.pk}


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
    GROUP_AGGREGATE_METHODS: ClassVar[tuple[str, ...]] = ("avg", "max", "min", "sum", "count")
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

    def to_link_info(self) -> dict[str, Any]:
        """导出链路元数据字典（含 Trace 特有字段）。"""
        info = super().to_link_info()
        info["index_set_id"] = self.index_set_id
        info["index_set_name"] = self.index_set_name
        return info

    def set_from_shared(self, shared_info: dict[str, Any]) -> None:
        """从共享链路信息字典提取字段并赋值（含 Trace 特有字段）。"""
        super().set_from_shared(shared_info)
        self.index_set_id = shared_info.get("index_set_id")
        self.index_set_name = shared_info.get("index_set_name")

    def reset_link_info(self) -> None:
        """重置当前数据源链路信息为未创建状态（含 Trace 特有字段）。"""
        super().reset_link_info()
        self.index_set_id = None
        self.index_set_name = None

    @property
    def table_id(self) -> str:
        return self.get_table_id(int(self.bk_biz_id), self.app_name)

    @classmethod
    def get_table_id(cls, bk_biz_id: int, app_name: str, **kwargs) -> str:
        if bk_biz_id > 0:
            return f"{bk_biz_id}_{cls.DATA_NAME_PREFIX}.{cls.DATASOURCE_TYPE}_{app_name}"
        else:
            return f"{cls.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{cls.DATA_NAME_PREFIX}.{cls.DATASOURCE_TYPE}_{app_name}"

    def create_or_update_result_table(self, global_mode: bool = False, table_id: str | None = None, **option) -> None:
        """创建或更新结果表。

        :param global_mode: 全局模式，使用 GLOBAL_CONFIG_BK_BIZ_ID 和 DEFAULT_TENANT_ID。
        :param table_id: 指定 table_id，用于共享模式传入 SharedTraceDataSource.table_id。
        """
        table_id = table_id or self.result_table_id or self.table_id

        if global_mode:
            bk_biz_id = GLOBAL_CONFIG_BK_BIZ_ID
            bk_tenant_id = DEFAULT_TENANT_ID
        else:
            bk_biz_id = self.bk_biz_id
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
                "index_set": table_id.replace(".", "_"),
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
            "bk_biz_id": bk_biz_id,
            "label": "application_check",
            "option": TRACE_RESULT_TABLE_OPTION,
            "time_option": {
                "es_type": "date",
                "es_format": "epoch_millis",
                "time_format": "yyyy-MM-dd HH:mm:ss",
                "time_zone": 0,
            },
        }

        # 全局模式下添加 bk_biz_id_alias 以支持 UnifyQuery 实现业务级别的数据隔离查询
        if global_mode:
            params["bk_biz_id_alias"] = "bk_biz_id"

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

        index_set_id, index_set_name = self.update_or_create_index_set(
            option["es_storage_cluster"],
            bk_biz_id=bk_biz_id,
            table_id=table_id,
            index_set_id=self.index_set_id,
        )

        if self.result_table_id != "":
            # 更新存储
            params["external_storage"] = {
                "elasticsearch": params["default_storage_config"],
            }
            resource.metadata.modify_result_table(params)

            return

        params["is_sync_db"] = False
        resource.metadata.create_result_table(params)

        self.result_table_id = table_id
        self.index_set_name = index_set_name
        self.index_set_id = index_set_id
        self.save()

    def update_or_create_index_set(self, storage_id, bk_biz_id: int, table_id: str, index_set_id=None):
        params = {
            "index_set_name": f"{table_id.replace('.', '_')}_index_set",
            "bk_biz_id": bk_biz_id,
            "category_id": "application_check",
            "scenario_id": "es",
            "view_roles": [],
            "indexes": [
                {
                    "bk_biz_id": bk_biz_id,
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

    @classmethod
    def _get_group_metric_key(cls, agg_method: str) -> str:
        return "doc_count" if agg_method == "count" else f"{agg_method}_duration"

    @classmethod
    def _get_missing_group_metric_keys(cls, group_bucket: dict[str, Any]) -> list[str]:
        missing_keys: list[str] = []
        for agg_method in cls.GROUP_AGGREGATE_METHODS:
            metric_key = cls._get_group_metric_key(agg_method)
            value = group_bucket.get(metric_key)
            if agg_method == "count":
                if value is None:
                    missing_keys.append(metric_key)
                continue

            if not isinstance(value, dict) or value.get("value") is None:
                missing_keys.append(metric_key)

        return missing_keys

    def _filter_complete_group_buckets(self, group_buckets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        complete_buckets: list[dict[str, Any]] = []
        filtered_buckets: list[dict[str, Any]] = []
        for group_bucket in group_buckets:
            if self._get_missing_group_metric_keys(group_bucket):
                # 热窗口（查询结束时间为「当前」）并发多次查询的场景下，存在部分稀疏 group_key 仅能统计到部分指标。
                # 例如请求发起顺序为 sum -- 1ms --> count，请求间隔期间写入一条新数据，此时 sum 无数据，count=1。
                # 为避免这种情况，过滤掉统计指标不全的数据。
                filtered_buckets.append(group_bucket)
                continue
            complete_buckets.append(group_bucket)

        if filtered_buckets:
            sample_bucket = filtered_buckets[0]
            logger.warning(
                "[APM][query_span_with_group_keys][filtered_incomplete_group_bucket] "
                f"bk_biz_id={self.bk_biz_id} app_name={self.app_name} "
                f"filtered_count={len(filtered_buckets)} sample_key={sample_bucket.get('key', {})} "
                f"missing_metric_keys={self._get_missing_group_metric_keys(sample_bucket)}",
            )

        return complete_buckets

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

        pool = ThreadPool(len(self.GROUP_AGGREGATE_METHODS))
        field_aggregated_records_list = pool.imap_unordered(
            lambda _agg_method: self._query_field_aggregated_records(
                q, qs, group_by, OtlpKey.ELAPSED_TIME, _agg_method
            ),
            self.GROUP_AGGREGATE_METHODS,
        )
        pool.close()

        span_group_aggregated_result_map: dict[frozenset, dict[str, Any]] = {}
        field_group_key_map: dict[str, str] = {field: group_key for group_key, field in self.GROUP_KEY_CONFIG.items()}
        for field_aggregated_records in field_aggregated_records_list:
            for record in field_aggregated_records:
                # 将 GroupBy 字段转为 GroupKey，构建 SpanGroup 作为聚合唯一 Key。
                span_group: dict[str, str] = {
                    field_group_key_map.get(field) or field: field_value
                    for field, field_value in record["dimensions"].items()
                }

                metric_key = self._get_group_metric_key(record["agg_method"])
                construct_value = {
                    metric_key: record["value"] if record["agg_method"] == "count" else {"value": record["value"]}
                }

                # 按 SpanGroup 将不同聚合方法的聚合结果进行合并。
                span_group_aggregated_result_map.setdefault(frozenset(span_group.items()), {"key": span_group}).update(
                    construct_value
                )

        return self._filter_complete_group_buckets(list(span_group_aggregated_result_map.values()))

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
        """停用 Trace 数据源。

        共享模式由父类统一处理释放；独占模式额外删除关联的索引集。
        """
        instance = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not instance:
            return

        # 共享模式：由父类执行释放逻辑，子类无需做额外操作
        super().stop(bk_biz_id, app_name)

        # 独占模式：额外删除关联的索引集
        if not instance.is_shared:
            try:
                api.log_search.delete_index_set(index_set_id=instance.index_set_id)
                logger.info(
                    f"[StopTraceDatasource] delete index_set_id: {instance.index_set_id} of ({bk_biz_id}){app_name}"
                )
            except BKAPIError as e:
                logger.error(f"[StopTraceDatasource] delete index_set_id: {instance.index_set_id} failed, error: {e}")


class ProfileDataSource(ApmDataSourceConfigBase):
    """Profile 数据源"""

    DATASOURCE_TYPE = ApmDataSourceConfigBase.PROFILE_DATASOURCE

    BUILTIN_APP_NAME = "builtin_profile_app"
    _CACHE_BUILTIN_DATASOURCE: Optional["ProfileDataSource"] = None

    bkdata_datalink_config = models.JSONField("BkData链路配置", default=dict)
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

    def is_bkbase_v4_link(self) -> bool:
        return (self.bkdata_datalink_config.get("version") or 3) == 4

    @classmethod
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
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        global_user = get_global_user(bk_tenant_id=bk_tenant_id)
        maintainer = global_user if not apm_maintainers else f"{global_user},{apm_maintainers}"

        # 判断是否使用 V4 链路（以 profile_bk_biz_id 作为判断依据，负数业务映射到公共业务 ID）
        use_v4 = profile_bk_biz_id in settings.APM_PROFILE_V4_BIZ_WHITE_LIST

        if use_v4:
            # V4 声明式链路：轮询可能长达 5 分钟，不可放入事务内
            # 先生成 DataId 名称并持久化，防止 provider() 中途失败后重试时生成不同随机后缀导致孤儿资源
            provider = BkDataDorisV4Provider.from_datasource_instance(
                obj,
                bk_tenant_id=bk_tenant_id,
                maintainer=maintainer,
                operator=global_user,
            )
            data_id_name = compose_profile_data_id_name(provider.data_biz_id, obj.app_name)
            obj.bkdata_datalink_config = {
                "version": 4,
                "v4_resource_names": {
                    "data_id_name": data_id_name,
                    "result_table_name": None,
                    "doris_binding_name": None,
                    "databus_name": None,
                },
            }
            obj.save()

            essentials = provider.provider()
            # provider() 成功后，补全 resource_name
            resource_names = provider.get_resource_names(bk_data_id=essentials["bk_data_id"])
            bkdata_datalink_config = {
                "version": 4,
                "v4_resource_names": {
                    "data_id_name": resource_names["data_id_name"],
                    "result_table_name": resource_names["result_table_name"],
                    "doris_binding_name": resource_names["doris_binding_name"],
                    "databus_name": resource_names["databus_name"],
                },
            }
        else:
            # V3 命令式链路（原有逻辑）
            essentials = BkDataDorisProvider.from_datasource_instance(
                obj,
                maintainer=maintainer,
                operator=global_user,
                name_stuffix=bk_biz_id,
            ).provider()
            bkdata_datalink_config = {}

        obj.bk_data_id = essentials["bk_data_id"]
        obj.result_table_id = essentials["result_table_id"]
        obj.retention = essentials["retention"]
        obj.bkdata_datalink_config = bkdata_datalink_config
        obj.save()

        return

    @classmethod
    def create_builtin_source(cls):
        # datasource is enough, no real app created.
        # 注意：不使用 @atomic，因为 apply_datasource 内部已自行管理事务
        # （V4 链路含轮询，不可放在长事务内）
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
        if instance.is_bkbase_v4_link():
            # V4 声明式链路：没有启停接口，通过 apply 重新声明资源（等价于启动）
            from apm.models.doris import BkDataDorisV4Provider

            bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
            apm_maintainers = ",".join(settings.APM_APP_BKDATA_MAINTAINER)
            global_user = get_global_user(bk_tenant_id=bk_tenant_id)
            maintainer = global_user if not apm_maintainers else f"{global_user},{apm_maintainers}"
            provider = BkDataDorisV4Provider.from_datasource_instance(
                instance, bk_tenant_id=bk_tenant_id, maintainer=maintainer, operator=global_user
            )
            provider.apply()
        else:
            api.bkdata.start_databus_cleans(result_table_id=instance.result_table_id)

    @classmethod
    def stop(cls, bk_biz_id, app_name):
        instance = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not instance:
            return
        if instance.is_bkbase_v4_link():
            # V4 声明式链路：没有启停接口，通过 delete 删除资源（等价于停止）
            from apm.models.doris import BkDataDorisV4Provider

            bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
            provider = BkDataDorisV4Provider.from_datasource_instance(
                instance,
                bk_tenant_id=bk_tenant_id,
                maintainer="",
                operator="",
            )
            provider.delete()
        else:
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
