"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import logging
import re
import time
from collections import defaultdict
from collections.abc import Generator
from datetime import datetime
from functools import reduce
from typing import Any

import requests
from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from apm_web.models import Application
from bkm_space.api import SpaceApi
from bkm_space.define import Space, SpaceTypeEnum
from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import is_build_in_process_data_source
from bkmonitor.documents import AlertDocument
from bkmonitor.models import (
    AlertConfig,
    BaseAlarm,
    EventPluginV2,
    QueryConfigModel,
    SnapshotHostIndex,
    StrategyModel,
)
from bkmonitor.models.metric_list_cache import MetricListCache
from bkmonitor.utils import get_metric_category
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.k8s_metric import get_built_in_k8s_metrics
from common.context_processors import Platform
from constants.alert import IGNORED_TAGS, EventTargetType
from constants.apm import ApmMetricProcessor
from constants.data_source import (
    DataSourceLabel,
    DataTypeLabel,
    OthersResultTableLabel,
    ResultTableLabelObj,
)
from constants.apm import APM_TRACE_TABLE_REGEX
from constants.event import ALL_EVENT_PLUGIN_METRIC, EVENT_PLUGIN_METRIC_PREFIX
from constants.strategy import (
    HOST_SCENARIO,
    SERVICE_SCENARIO,
    SYSTEM_EVENT_RT_TABLE_ID,
    DimensionFieldType,
)
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata import models
from monitor_web.collecting.utils import chunks
from monitor_web.models import (
    CollectConfigMeta,
    CustomEventGroup,
    CustomEventItem,
    CustomTSTable,
    DataTarget,
    DataTargetMapping,
)
from monitor_web.models.plugin import CollectorPluginMeta, PluginVersionHistory
from monitor_web.plugin.constant import ParamMode, PluginType
from monitor_web.plugin.manager.process import (
    BuildInProcessDimension,
    BuildInProcessMetric,
)
from monitor_web.strategies.metric_cache.built_in_metrics import (
    PROCESS_METRIC_DIMENSIONS,
    PROCESS_METRICS,
    PROCESS_PORT_METRIC_DIMENSIONS,
    SYSTEM_HOST_METRICS,
    UPTIMECHECK_METRICS,
)
from monitor_web.tasks import run_metric_manager_async

FILTER_DIMENSION_LIST = ["time", "bk_supplier_id", "bk_cmdb_level", "timestamp"]
# 时序指标filed_type
TIME_SERIES_FIELD_TYPE = ["integer", "long", "float", "double", "int", "bigint"]
# 日志检索内置维度字段
LOG_SEARCH_DIMENSION_LIST = ["cloudId", "gseIndex", "iterationIndex", "container_id", "_iteration_idx"]

logger = logging.getLogger(__name__)


class DefaultDimensions:
    host = [{"id": "bk_target_ip", "name": _lazy("目标IP")}, {"id": "bk_target_cloud_id", "name": _lazy("云区域ID")}]
    service = [{"id": "bk_target_service_instance_id", "name": _lazy("服务实例")}]
    device = [{"id": "bk_target_device_ip", "name": _lazy("远程采集目标IP")}]
    uptime_check_response = [
        {"id": "task_id", "name": _lazy("任务ID")},
        {"id": "ip", "name": _lazy("节点地址")},
        {"id": "bk_cloud_id", "name": _lazy("节点云区域id")},
    ]
    uptime_check = [
        {"id": "task_id", "name": _lazy("任务ID")},
        {"id": "node_id", "name": _lazy("节点ID")},
        {"id": "ip", "name": _lazy("节点地址")},
        {"id": "bk_cloud_id", "name": _lazy("节点云区域id")},
    ]


class UptimeCheckMetricFuller:
    dimensions: list[dict[str, str]]

    def full_dimension(self, protocol):
        if protocol == "HTTP":
            self.dimensions.append({"id": "url", "name": _lazy("目标")})
        if protocol in ["TCP", "UDP"]:
            self.dimensions.append({"id": "target_host", "name": _lazy("目标IP")})
            self.dimensions.append({"id": "target_port", "name": _lazy("目标端口")})


class AvailableMetric(UptimeCheckMetricFuller):
    """
    单点可用率
    """

    def __init__(self, protocol):
        self.metric_field = "available"
        self.metric_field_name = _("单点可用率")
        self.dimensions = copy.deepcopy(DefaultDimensions.uptime_check)
        self.default_condition = []
        self.unit = "percentunit"
        self.full_dimension(protocol)


class TaskDurationMetric(UptimeCheckMetricFuller):
    """
    响应时间
    """

    def __init__(self, protocol):
        self.metric_field = "task_duration"
        self.metric_field_name = _("响应时间")
        self.unit = "ms"
        self.dimensions = copy.deepcopy(DefaultDimensions.uptime_check)
        self.default_condition = []
        self.full_dimension(protocol)


class ResponseCodeMetric(UptimeCheckMetricFuller):
    """
    响应码
    """

    def __init__(self, protocol):
        self.metric_field = "response_code"
        self.metric_field_name = _("期望响应码")
        self.dimensions = copy.deepcopy(DefaultDimensions.uptime_check_response)
        self.default_condition = []
        self.full_dimension(protocol)


class ResponseMetric(UptimeCheckMetricFuller):
    """
    响应内容
    """

    def __init__(self, protocol):
        self.metric_field = "message"
        self.metric_field_name = _("期望响应内容")
        self.dimensions = copy.deepcopy(DefaultDimensions.uptime_check_response)
        self.default_condition = []
        self.full_dimension(protocol)


DEFAULT_DIMENSIONS_MAP = {
    "host_target": DefaultDimensions.host,
    "service_target": DefaultDimensions.service,
    "none_target": [],
    "device_target": DefaultDimensions.device,
}

UPTIMECHECK_MAP = {
    "HTTP": [AvailableMetric, TaskDurationMetric, ResponseCodeMetric, ResponseMetric],
    "UDP": [AvailableMetric, TaskDurationMetric],
    "TCP": [AvailableMetric, TaskDurationMetric],
    "ICMP": [],
}

METRIC_POOL_KEYS = ["id", "metric_md5", "bk_biz_id", "result_table_id", "metric_field", "related_id", "readable_name"]


class BaseMetricCacheManager:
    """
    指标缓存管理器 基类
    """

    data_sources = (("", ""),)

    def __init__(self, bk_tenant_id: str, bk_biz_id: int | None = None):
        self.bk_biz_id = bk_biz_id
        self.bk_tenant_id = bk_tenant_id
        self.new_metric_ids = []
        self._label_names_map = None
        self.has_exception = False
        self.metric_use_frequency = {}

    def get_tables(self) -> Generator[dict, None, None]:
        """
        查询表数据
        """
        raise NotImplementedError

    def get_metrics_by_table(self, table) -> Generator[dict, None, None]:
        """
        根据表查询指标数据
        """
        raise NotImplementedError

    def get_metric_pool(self):
        """
        根据数据源的类型筛选出当前manager负责的指标缓存
        """
        return MetricListCache.objects.filter(
            reduce(
                lambda x, y: x | y,
                (
                    Q(data_source_label=data_source[0], data_type_label=data_source[1])
                    for data_source in self.data_sources
                ),
            ),
            bk_tenant_id=self.bk_tenant_id,
        )

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list[int]:
        """
        获取当前数据源类型可用的业务ID列表
        默认返回所有的业务ID， 子类根据自己的需求重写此方法， 返回符合要求的biz_id列表
        """
        # 默认返回所有业务ID
        businesses: list[Space] = SpaceApi.list_spaces(bk_tenant_id=bk_tenant_id)
        return [biz.bk_biz_id for biz in businesses]

    def refresh_metric_use_frequency(self):
        self.metric_use_frequency = {
            metric["metric_id"]: metric["use_frequency"]
            for metric in QueryConfigModel.objects.filter(
                reduce(
                    lambda x, y: x | y,
                    (
                        Q(data_source_label=data_source[0], data_type_label=data_source[1])
                        for data_source in self.data_sources
                    ),
                )
            )
            .values("metric_id")
            .annotate(use_frequency=Count("metric_id"))
        }

    def _run(self):
        """
        对比数据库已有数据， 实现指标缓存的增量更新
        """
        start_time = time.time()
        logger.info(f"[start] update metric {self.__class__.__name__}({self.bk_biz_id})")

        # 集中整理后进行差量更新
        to_be_create = []
        to_be_update = []
        to_be_delete = []
        self.refresh_metric_use_frequency()

        metric_pool = self.get_metric_pool()
        if self.bk_biz_id is not None:
            metric_pool = metric_pool.filter(bk_biz_id=self.bk_biz_id)
        metric_pool_values = metric_pool.only(*METRIC_POOL_KEYS)

        # metric_hash_dict(当前数据库[缓存]中的指标)
        metric_hash_dict = {}
        for m in list(metric_pool_values):
            metric_id = f"{m.bk_biz_id}.{m.result_table_id}.{m.metric_field}.{m.related_id}"
            if metric_id in metric_hash_dict:
                to_be_delete.append(m.pk)
            else:
                metric_hash_dict[metric_id] = m

        # 遍历非缓存数据[最新数据]
        for table in self.get_tables():
            for metric in self.get_metrics_by_table(table):
                # 处理result_table_id长度
                if len(metric.get("result_table_id", "")) > 256:
                    metric["result_table_id"] = metric["result_table_id"][:256]

                if metric.get("result_table_id", "") in ["bkunifylogbeat_task.base", "bkunifylogbeat_common.base"]:
                    continue

                # 补全维度字段
                dimensions = metric.get("dimensions", [])
                for dimension in dimensions:
                    if "is_dimension" not in dimension:
                        dimension["is_dimension"] = True
                    if "type" not in dimension:
                        dimension["type"] = DimensionFieldType.String

                # 更新metric使用频率
                metric.update(
                    dict(
                        use_frequency=self.metric_use_frequency.get(
                            f"{metric.get('data_source_label', '')}."
                            f"{metric.get('result_table_id', '')}.{metric['metric_field']}",
                            0,
                        )
                    )
                )
                # 生成指标的唯一标识符
                metric_id = "{}.{}.{}.{}".format(
                    metric["bk_biz_id"],
                    metric.get("result_table_id", ""),
                    metric["metric_field"],
                    metric.get("related_id", ""),
                )
                metric_instance = metric_hash_dict.pop(metric_id, None)
                # 处理新增指标
                if metric_instance is None:
                    _metric = MetricListCache(bk_tenant_id=self.bk_tenant_id, **metric)
                    metric["readable_name"] = _metric.get_human_readable_name()
                    _metric.readable_name = metric["readable_name"]
                    _metric.metric_md5 = count_md5(metric)

                    logger.info("Going to add %s to cache creating list", metric_id)
                    to_be_create.append(_metric)
                    continue

                # readable_name 可能会因用户修改data_label而变更，因此跟随周期任务自动更新
                metric["readable_name"] = metric_instance.get_human_readable_name()

                metric["metric_md5"] = count_md5(metric)
                # 处理更新逻辑
                if not metric_instance.metric_md5 or metric_instance.metric_md5 != metric["metric_md5"]:
                    metric["last_update"] = datetime.now()
                    logger.info(f"Going to adding {metric_id} to cache updating list")
                    metric["id"] = metric_instance.id
                    to_be_update.append(metric)
                    metric_instance.metric_md5 = metric["metric_md5"]

        # create
        if to_be_create:
            logger.info("Going to bulk create %s metric caches", len(to_be_create))
            MetricListCache.objects.bulk_create(to_be_create, batch_size=50)

        # update
        if to_be_update:
            logger.info("Going to bulk update %s metric caches", len(to_be_update))
            for metrics in chunks(to_be_update, 500):
                init_md5_metrics = []
                for metric in metrics:
                    _metric = MetricListCache(**metric)
                    init_md5_metrics.append(_metric)
                fields = [
                    field.name
                    for field in MetricListCache._meta.get_fields(include_parents=False)
                    if not field.auto_created
                ]
                MetricListCache.objects.bulk_update(init_md5_metrics, fields, batch_size=500)

        # clean (手动添加的自定义指标标记md5为0，不做删除处理）
        to_be_delete.extend([m.id for m in list(metric_hash_dict.values()) if m.metric_md5 != "0"])
        if to_be_delete:
            logger.info("Going to delete metric caches %s", list(metric_hash_dict.keys()))
            MetricListCache.objects.filter(id__in=to_be_delete).delete()

        logger.info(
            f"[end] update metric {self.__class__.__name__}({self.bk_biz_id}) "
            f"create {len(to_be_create)} metric,update {len(to_be_update)} metric, delete {len(to_be_delete)} metric."
            f"timestamp: {int(start_time)}, cost {time.time() - start_time}s"
        )

    def run(self, delay=False):
        if delay:
            run_metric_manager_async.delay(self)
        else:
            self._run()

    def get_label_name(self, label_id: str) -> str:
        """
        获取标签名称
        """
        if self._label_names_map is None:
            try:
                result = api.metadata.get_label(bk_tenant_id=self.bk_tenant_id, include_admin_only=True)
                self._label_names_map = {
                    label["label_id"]: label["label_name"] for label in result["result_table_label"]
                }
            except BaseException as e:
                logger.exception(e)
                self._label_names_map = {}

        return self._label_names_map.get(label_id, label_id)

    @staticmethod
    def _is_split_measurement(table) -> bool:
        # 如果表内有多个指标或表名以base结尾但指标不是base，则判断为老版的单表多指标，否则为单指标单表
        table_id = table["table_id"]
        return (
            True
            if not is_build_in_process_data_source(table_id)
            and not (
                table_id.endswith(".base")
                and (len(table["metric_info_list"]) != 1 or table["metric_info_list"][0]["field_name"] != "base")
            )
            else False
        )

    @staticmethod
    def get_time_series_metric_detail(metric: dict):
        return {
            "default_dimensions": [],
            "default_condition": [],
            "metric_field": metric["field_name"],
            "metric_field_name": metric["description"] or metric["field_name"],
            "dimensions": [
                {
                    "id": dimension["field_name"],
                    "name": BuildInProcessDimension(
                        dimension["description"] or dimension["field_name"]
                    ).field_name_description,
                }
                for dimension in metric["tag_list"]
            ],
            "unit": metric.get("unit", ""),
        }

    def get_ts_basic_dict(self, table):
        return {
            "result_table_name": table["time_series_group_name"],
            "result_table_label": table["label"],
            "result_table_label_name": self.get_label_name(table["label"]),
            "bk_biz_id": table["bk_biz_id"],
            "collect_config_ids": [],
            "related_name": table["time_series_group_name"],
            "related_id": str(table["time_series_group_id"]),
            "extend_fields": {"bk_data_id": table["bk_data_id"]},
            "data_label": table.get("data_label", ""),
        }


class CustomMetricCacheManager(BaseMetricCacheManager):
    """
    自定义指标缓存
    """

    data_sources = ((DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),)

    def get_metric_pool(self):
        # 自定义指标，补上进程采集相关(映射到了，bkmonitor + timeseries[业务id为0])
        # 这里不filter 业务id 是因为基类 _run 方法已有兜底过滤
        queryset = super().get_metric_pool()

        if settings.ENABLE_MULTI_TENANT_MODE:
            return queryset

        return queryset | MetricListCache.objects.filter(
            result_table_id__in=BuildInProcessMetric.result_table_list(),
            bk_tenant_id=self.bk_tenant_id,
        )

    def get_tables(self):
        custom_ts_result = api.metadata.query_time_series_group(
            bk_biz_id=self.bk_biz_id, bk_tenant_id=self.bk_tenant_id
        )
        # 过滤插件数据，且已知插件的bk_biz_id都为 0，所以可以仅对 0 的数据做过滤，减少不必要的查询
        if self.bk_biz_id == 0:
            plugin_data = (
                CollectorPluginMeta.objects.filter(bk_tenant_id=self.bk_tenant_id)
                .exclude(plugin_type__in=[PluginType.SNMP_TRAP, PluginType.LOG, PluginType.PROCESS])
                .values_list("plugin_type", "plugin_id")
            )
            db_name_list = [f"{plugin[0]}_{plugin[1]}".lower() for plugin in plugin_data]

            # 通过 time_series_group_name 的生成规则过滤掉插件类型的数据
            custom_ts_result = [i for i in custom_ts_result if i["time_series_group_name"] not in db_name_list]

        # 补充 APM 虚拟指标
        custom_ts_result = self.get_apm_extra_tables(custom_ts_result) + custom_ts_result

        # 不在监控创建的策略配置均展示，除了全局data id， 该过滤在get_metrics_by_table中生效
        for result in custom_ts_result:
            self.process_logbeat_table(result)
            self.process_apm_table(result)
            yield result

    @classmethod
    def process_apm_table(cls, table: dict):
        ApmMetricProcessor.process(table)

    def get_apm_extra_tables(self, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """获取 APM 相关的虚拟指标表
        - 找出 table_id & data_label 同时满足 APM 规则的表。
        - 对同个业务，多个应用的指标表进行合并，生成 custom:${data_label}:${field} 的同名指标。
        - 基于上述步骤生成的统一虚拟指标，可以同时在多个业务下使用，便于策略、仪表盘的迁移。
        """

        def _to_tags(_metric_info: dict[str, Any]) -> dict[str, Any]:
            return {tag["field_name"]: tag for tag in _metric_info.get("tag_list", [])}

        field_name_to_tags: dict[str, dict[str, Any]] = {}
        field_name_to_metric_info: dict[str, dict[str, Any]] = {}
        for table in tables:
            # data_label 和 table_id 必须同时满足。
            if not (ApmMetricProcessor.is_match_data_label(table) and ApmMetricProcessor.is_match_table_id(table)):
                continue

            # 虚拟指标由 data_label 和 field_name 组成，如果没有 data_label 则跳过。
            # Q：为什么删除（pop）原始表的 data_label？
            # A：存在 data_label 时，每个 table 都会额外展示一条 data_label.xxx 的记录，非常冗余。
            data_label: str = table.pop("data_label")

            for metric_info in table.get("metric_info_list") or []:
                field_name: str = metric_info["field_name"]
                if field_name in field_name_to_metric_info:
                    # 指标已存在，合并标签
                    field_name_to_tags[field_name].update(_to_tags(metric_info))
                    continue

                copy_metric_info: dict[str, Any] = copy.deepcopy(metric_info)
                copy_metric_info["data_label"] = data_label
                copy_metric_info["table_id"] = data_label
                field_name_to_metric_info[field_name] = copy_metric_info
                field_name_to_tags[field_name] = _to_tags(copy_metric_info)

        apm_extra_tables: list[dict[str, Any]] = []
        for field_name, metric_info in field_name_to_metric_info.items():
            metric_info["tag_list"] = list(field_name_to_tags.get(field_name, []).values())
            apm_extra_tables.append(
                {
                    "is_enable": True,
                    "bk_data_id": 0,
                    "time_series_group_id": 0,
                    "time_series_group_name": "",
                    "bk_biz_id": self.bk_biz_id,
                    "table_id": metric_info["table_id"],
                    "label": "apm",
                    "data_label": metric_info.pop("data_label", ""),
                    "metric_info_list": [metric_info],
                }
            )

        return apm_extra_tables

    @staticmethod
    def process_logbeat_table(table: dict):
        """
        设置日志采集器指标，配置到指定业务下"
        """
        table_id = table["table_id"]

        if settings.BKUNIFYLOGBEAT_METRIC_BIZ and table_id in [
            "bkunifylogbeat_task.base",
            "bkunifylogbeat_common.base",
        ]:
            table["bk_biz_id"] = settings.BKUNIFYLOGBEAT_METRIC_BIZ
            table["label"] = "host_process"

            if table_id == "bkunifylogbeat_task.base":
                metrics = [
                    {"field_name": "crawler_dropped", "description": _("需要过滤的事件数")},
                    {"field_name": "crawler_received", "description": _("接收到的采集事件数")},
                    {"field_name": "crawler_send_total", "description": _("正常发送事件数")},
                    {"field_name": "crawler_state", "description": _("接收到的采集进度事件数")},
                    {"field_name": "gse_publish_total", "description": _("按任务计算发送次数")},
                    {"field_name": "sender_received", "description": _("sender接收到的事件数")},
                    {"field_name": "sender_send_total", "description": _("sender发送的采集事件包数")},
                    {"field_name": "sender_state", "description": _("sender发送的采集进度包数")},
                    {"field_name": "gse_publish_failed", "description": _("按任务计算发送失败次数")},
                ]
            else:
                metrics = [
                    {
                        "field_name": "beat_cpu_total_norm_pct",
                        "description": _("beat-CPU资源占比"),
                        "unit": "percentunit",
                    },
                    {"field_name": "beat_cpu_total_pct", "description": _("beat-CPU资源单核占比")},
                    {"field_name": "beat_info_uptime_ms", "description": _("beat-采集器运行时间"), "unit": "ms"},
                    {"field_name": "beat_memstats_rss", "description": _("beat-内存使用情况"), "unit": "bytes"},
                    {"field_name": "bkbeat_crawler_dropped", "description": _("bkbeat-已过滤的事件数")},
                    {"field_name": "bkbeat_crawler_received", "description": _("bkbeat-已接收的采集事件数")},
                    {"field_name": "bkbeat_crawler_send_total", "description": _("bkbeat-已发送的事件数")},
                    {"field_name": "bkbeat_crawler_state", "description": _("bkbeat-已接收的采集进度数")},
                    {"field_name": "bkbeat_task_input_failed", "description": _("bkbeat-启动任务异常的次数")},
                    {
                        "field_name": "bkbeat_task_processors_failed",
                        "description": _("bkbeat-启动processors异常的次数"),
                    },
                    {"field_name": "bkbeat_task_sender_failed", "description": _("bkbeat-启动sender异常的次数")},
                    {"field_name": "bkbeat_registrar_marshal_error", "description": _("bkbeat-采集DB的解析异常的次数")},
                    {
                        "field_name": "bkbeat_gse_agent_receive_failed",
                        "description": _("gse_client-接收gse_agent异常的次数"),
                    },
                    {"field_name": "bkbeat_gse_agent_received", "description": _("gse_client-接收到gse_agent的次数")},
                    {"field_name": "bkbeat_gse_client_connect_retry", "description": _("gse_client-gse_agent重连次数")},
                    {
                        "field_name": "bkbeat_gse_client_connect_failed",
                        "description": _("gse_client-gse_agent连接失败的次数"),
                    },
                    {
                        "field_name": "bkbeat_gse_client_connected",
                        "description": _("gse_client-gse_agent连接成功的次数"),
                    },
                    {"field_name": "bkbeat_gse_client_received", "description": _("gse_client-已接收的事件数")},
                    {"field_name": "bkbeat_gse_client_send_retry", "description": _("gse_client-发送重试的次数")},
                    {"field_name": "bkbeat_gse_client_send_timeout", "description": _("gse_client-发送超时的次数")},
                    {"field_name": "bkbeat_gse_client_send_total", "description": _("gse_client-已发送的事件数")},
                    {"field_name": "bkbeat_gse_client_send_failed", "description": _("gse_client-发送失败的事件数")},
                    {"field_name": "bkbeat_gse_client_server_close", "description": _("gse_client-gse_agent断开次数")},
                    {"field_name": "bkbeat_gse_publish_received", "description": _("publish-已接收的采集事件数")},
                    {"field_name": "bkbeat_gse_publish_total", "description": _("publish-已发送的采集事件数")},
                    {"field_name": "bkbeat_gse_publish_dropped", "description": _("publish-已丢弃的采集事件数")},
                    {"field_name": "bkbeat_gse_publish_failed", "description": _("publish-发送失败的采集事件数")},
                    {"field_name": "bkbeat_gse_report_received", "description": _("publish-已接收的心跳事件数")},
                    {"field_name": "bkbeat_gse_report_send_total", "description": _("publish-已发送的心跳事件数")},
                    {"field_name": "bkbeat_gse_report_failed", "description": _("publish-发送失败的心跳事件数")},
                    {"field_name": "bkbeat_gse_send_total", "description": _("publish-发给gse_client的事件数")},
                    {"field_name": "bkbeat_manager_active", "description": _("bkbeat-当前有效的任务数")},
                    {"field_name": "bkbeat_manager_reload", "description": _("bkbeat-周期内Reload的任务数")},
                    {"field_name": "bkbeat_manager_start", "description": _("bkbeat-周期内启动的任务数")},
                    {"field_name": "bkbeat_manager_stop", "description": _("bkbeat-周期内停止的任务数")},
                    {"field_name": "bkbeat_manager_error", "description": _("bkbeat-周期内启动异常的任务数")},
                    {"field_name": "bkbeat_registrar_files", "description": _("bkbeat-采集DB注册的文件数")},
                    {"field_name": "bkbeat_registrar_flushed", "description": _("bkbeat-采集DB的刷新次数")},
                    {"field_name": "bkbeat_sender_received", "description": _("bkbeat-sender-已接收的采集事件数")},
                    {"field_name": "bkbeat_sender_send_total", "description": _("bkbeat-sender-已发送的事件数")},
                    {"field_name": "bkbeat_sender_state", "description": _("bkbeat-sender-已发送的采集进度数")},
                    {"field_name": "filebeat_harvester_closed", "description": _("beat-已释放的文件数")},
                    {"field_name": "filebeat_harvester_open_files", "description": _("beat-已打开的文件数")},
                    {"field_name": "filebeat_harvester_running", "description": _("beat-正在采集的文件数")},
                    {"field_name": "filebeat_harvester_skipped", "description": _("beat-已过滤的文件数")},
                    {"field_name": "filebeat_input_log_files_renamed", "description": _("beat-renamed的文件数")},
                    {"field_name": "filebeat_input_log_files_truncated", "description": _("beat-truncated的文件数")},
                    {"field_name": "libbeat_pipeline_events_active", "description": _("beat-正在发送的采集事件数")},
                    {"field_name": "libbeat_pipeline_events_published", "description": _("beat-已发送的采集事件数")},
                    {"field_name": "libbeat_pipeline_events_total", "description": _("beat-已接收的采集事件数")},
                    {"field_name": "libbeat_pipeline_queue_acked", "description": _("beat-已确认的采集事件数")},
                    {"field_name": "system_load_1", "description": _("beat-采集目标1分钟负载")},
                    {"field_name": "system_load_15", "description": _("beat-采集目标15分钟负载")},
                    {"field_name": "system_load_5", "description": _("beat-采集目标5分钟负载")},
                ]

            tags = [
                {"field_name": "bk_biz_id", "description": _("业务ID")},
                {"field_name": "target", "description": _("目标")},
                {"field_name": "task_data_id", "description": _("数据ID")},
                {"field_name": "type", "description": _("类型")},
                {"field_name": "version", "description": _("版本号")},
            ]

            for metric in metrics:
                metric["tag_list"] = tags
            table["metric_info_list"] = metrics

    def get_metrics_by_table(self, table):
        table_id = table["table_id"]
        # 如果表内有多个指标或表名以base结尾但指标不是base，则判断为老版的单表多指标，否则为单指标单表
        if self._is_split_measurement(table):
            table_id = f"{table_id.split('.')[0]}.__default__"

        data_target = DataTargetMapping().get_data_target(
            table["label"], DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES
        )
        base_dict = self.get_ts_basic_dict(table)
        base_dict.update(
            result_table_id=table_id,
            data_source_label=DataSourceLabel.CUSTOM,
            data_type_label=DataTypeLabel.TIME_SERIES,
        )

        for metric_msg in table["metric_info_list"]:
            if not metric_msg:
                continue
            metric_detail = self.get_time_series_metric_detail(metric_msg)
            metric_detail.update(base_dict)
            metric_detail.update(
                {
                    "data_target": self.get_data_target_by_result_lable(
                        data_target, table["label"], [dimension["field_name"] for dimension in metric_msg["tag_list"]]
                    )
                }
            )
            if is_build_in_process_data_source(table_id):
                metric_detail.update(BuildInProcessMetric(f"{table_id}.{metric_msg['field_name']}").to_dict())
                metric_detail["data_source_label"] = DataSourceLabel.BK_MONITOR_COLLECTOR

            yield metric_detail

    @staticmethod
    def get_data_target_by_result_lable(data_target, result_table_label, dimensions):
        if any(["bk_target_ip" in dimensions, "bk_target_service_instance_id" in dimensions]):
            return DataTargetMapping().get_data_target(
                result_table_label, DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES
            )
        return data_target

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list:
        """
        获取当前数据源类型可用的业务ID列表
        1. 有自定义时序指标的业务
        2. 有APM的业务
        3. 全局业务(0业务)
        """
        biz_ids = set()
        custom_ts_result = (
            CustomTSTable.objects.filter(bk_tenant_id=bk_tenant_id).values_list("bk_biz_id", flat=True).distinct()
        )
        apm_biz_ids = list(
            Application.objects.filter(bk_tenant_id=bk_tenant_id).values_list("bk_biz_id", flat=True).distinct()
        )
        biz_ids.update(custom_ts_result)
        biz_ids.update(apm_biz_ids)
        biz_ids.add(0)

        return list(biz_ids)


class BkdataMetricCacheManager(BaseMetricCacheManager):
    """
    数据平台时序型指标缓存
    """

    data_sources = ((DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),)
    # 需要补充单位的指标
    unit_metric_mapping = {"bk_apm_avg_duration": "ns", "bk_apm_max_duration": "ns", "bk_apm_sum_duration": "ns"}

    def get_tables(self):
        if str(self.bk_biz_id) == str(settings.BK_DATA_BK_BIZ_ID):
            return
        else:
            yield from api.bkdata.list_result_table(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=self.bk_biz_id,
                storages=["mysql", "tspider", "databus_tspider"],
            )

    def get_metrics_by_table(self, table):
        bk_biz_id = table["bk_biz_id"]
        result_table_id = table["result_table_id"]
        result_table_name = table["result_table_name"]

        dimensions = []
        for field in table["fields"]:
            if field["field_name"] in FILTER_DIMENSION_LIST:
                continue

            # 是否可以作为维度
            is_dimensions = field["field_type"] in ["string", "text"] or field["is_dimension"]

            if field["field_type"] in TIME_SERIES_FIELD_TYPE:
                field_type = DimensionFieldType.Number
            else:
                field_type = DimensionFieldType.String

            dimensions.append(
                {
                    "id": field["field_name"],
                    "name": f"{field['field_alias']}({field['field_name']})"
                    if field["field_alias"]
                    else field["field_name"],
                    "type": field_type,
                    "is_dimension": is_dimensions,
                }
            )

        result_table_label = table["result_table_type"] if table["result_table_type"] else "other_rt"

        base_dict = {
            "result_table_id": result_table_id,
            "result_table_name": result_table_name,
            "data_source_label": DataSourceLabel.BK_DATA,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "result_table_label": result_table_label,
            "result_table_label_name": self.get_label_name(result_table_label),
            "dimensions": dimensions,
            "data_target": DataTargetMapping().get_data_target(
                result_table_label=result_table_label,
                data_source_label=DataSourceLabel.BK_DATA,
                data_type_label=DataTypeLabel.TIME_SERIES,
            ),
            "bk_biz_id": bk_biz_id,
        }

        for field in table["fields"]:
            field_dict = {}
            field_dict.update(base_dict)

            if field["field_type"] in TIME_SERIES_FIELD_TYPE:
                field_dict["metric_field"] = field["field_name"]
                field_dict["metric_field_name"] = (
                    f"{field['field_alias']}({field['field_name']})"
                    if field["field_alias"] and field["field_alias"] != field["field_name"]
                    else field["field_name"]
                )
                field_dict["unit"] = field.get("unit", "") or self.unit_metric_mapping.get(field["field_name"], "")
                field_dict["unit_conversion"] = field.get("unit_conversion", 1.0)
                yield field_dict

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list:
        """
        获取对于数据平台可用的biz_id集合
        对特殊配置进行判断，返回当前租户的biz_id集合,
        """
        # 如果未开启数据平台指标缓存，则返回空列表
        if not settings.ENABLE_BKDATA_METRIC_CACHE:
            return []

        businesses: list[Space] = SpaceApi.list_spaces(bk_tenant_id=bk_tenant_id)

        # 数据平台仅支持bkcc业务
        return [business.bk_biz_id for business in businesses if business.bk_biz_id > 0]

    def run(self, delay=True):
        super().run(delay)


class BkLogSearchCacheManager(BaseMetricCacheManager):
    """
    日志平台指标缓存
    """

    data_sources = (
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
    )

    def __init__(self, bk_tenant_id: str, bk_biz_id: int | None = None):
        super().__init__(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

        self.cluster_id_to_name = {
            cluster["cluster_config"]["cluster_id"]: cluster["cluster_config"]["cluster_name"]
            for cluster in api.metadata.query_cluster_info(bk_tenant_id=self.bk_tenant_id, cluster_type="elasticsearch")
        }

    def get_tables(self):
        index_list = api.log_search.search_index_set(bk_tenant_id=self.bk_tenant_id, bk_biz_id=self.bk_biz_id)
        for index_set_msg in index_list:
            index_set_msg["bk_biz_id"] = self.bk_biz_id
            if not index_set_msg["category_id"]:
                index_set_msg["category_id"] = ResultTableLabelObj.OthersObj.other_rt

            # 如果时间字段为空，默认使用dtEventTimeStamp
            if not index_set_msg.get("time_field"):
                index_set_msg["time_field"] = "dtEventTimeStamp"
        yield from index_list

    def get_log_metric(self, table: dict, related_map: dict[str, list[str]]) -> dict:
        """
        日志关键字指标
        """
        return {
            "default_dimensions": [],
            "default_condition": [],
            "data_target": DataTargetMapping().get_data_target(
                table["category_id"], DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG
            ),
            "data_type_label": DataTypeLabel.LOG,
            "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
            "result_table_id": ",".join(related_map["related_id"]),
            "result_table_name": ",".join(related_map["related_name"]),
            "metric_field": "_index",
            "metric_field_name": table["index_set_name"],
            "dimensions": [],
            "bk_biz_id": table["bk_biz_id"],
            "related_id": str(table["index_set_id"]),
            "related_name": table["index_set_name"],
            "category_display": table["index_set_name"],
            "result_table_label": table["category_id"],
            "result_table_label_name": self.get_label_name(table["category_id"]),
            "extend_fields": {
                "index_set_id": table.get("index_set_id", ""),
                "time_field": table.get("time_field", ""),
                "scenario_name": table.get("scenario_name", ""),
                "scenario_id": table.get("scenario_id", ""),
                "storage_cluster_id": table.get("storage_cluster_id", ""),
                "storage_cluster_name": self.cluster_id_to_name.get(table.get("storage_cluster_id"), ""),
            },
        }

    def get_metrics_by_table(self, table):
        return_list = []

        try:
            fields_response = api.log_search.search_index_fields(
                bk_tenant_id=self.bk_tenant_id, bk_biz_id=table["bk_biz_id"], index_set_id=table["index_set_id"]
            )
        except BKAPIError:
            self.has_exception = True
            return

        related_map = {"related_id": [], "related_name": []}
        for indices_msg in table["indices"]:
            if indices_msg["result_table_name"]:
                related_name = indices_msg["result_table_name"]
            else:
                related_name = indices_msg["result_table_id"]

            related_map["related_id"].append(indices_msg["result_table_id"])
            related_map["related_name"].append(related_name)

        # apm索引集仅同步日志关键字指标
        name = table["index_set_name"]

        # 获取维度列表
        dimension_list = []
        for fields_msg in fields_response.get("fields", []):
            field_id = field_description = fields_msg["field_name"]
            if fields_msg["description"]:
                field_description = fields_msg["description"]

            # 限制维度数量不能太多
            if fields_msg.get("field_type") not in ["date", "text"] and len(dimension_list) < 1000:
                temp = {"id": field_id, "name": field_description, "is_dimension": bool(fields_msg["es_doc_values"])}
                dimension_list.append(temp)

            if (
                fields_msg["es_doc_values"]
                and fields_msg.get("field_type") in TIME_SERIES_FIELD_TYPE
                and fields_msg.get("field_name") not in LOG_SEARCH_DIMENSION_LIST
            ) and APM_TRACE_TABLE_REGEX.match(name) is None:
                create_data = {
                    "default_dimensions": [],
                    "default_condition": [],
                    "data_target": DataTargetMapping().get_data_target(
                        table["category_id"], DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES
                    ),
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
                    "result_table_id": ",".join(related_map["related_id"]),
                    "result_table_name": ",".join(related_map["related_name"]),
                    "metric_field": field_id,
                    "metric_field_name": field_description,
                    "dimensions": [],
                    "bk_biz_id": table["bk_biz_id"],
                    "related_id": str(table["index_set_id"]),
                    "related_name": table["index_set_name"],
                    "category_display": table["index_set_name"],
                    "result_table_label": table["category_id"],
                    "result_table_label_name": self.get_label_name(table["category_id"]),
                    "extend_fields": {
                        "index_set_id": table.get("index_set_id", ""),
                        "time_field": table.get("time_field", ""),
                        "scenario_name": table.get("scenario_name", ""),
                        "scenario_id": table.get("scenario_id", ""),
                        "storage_cluster_id": table.get("storage_cluster_id", ""),
                        "storage_cluster_name": self.cluster_id_to_name.get(table.get("storage_cluster_id"), ""),
                    },
                }
                return_list.append(create_data)

        # 日志关键字指标
        return_list.append(self.get_log_metric(table, related_map))

        for metric_msg in return_list:
            metric_msg["dimensions"] = [
                dimension for dimension in dimension_list if dimension["id"] != metric_msg["metric_field"]
            ]

        yield from return_list

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list:
        """日志平台指标缓存仅支持更新大于0业务"""
        businesses: list[Space] = SpaceApi.list_spaces(bk_tenant_id=bk_tenant_id)
        # 默认只刷新bkcc业务，其他业务引导用户自行触发刷新
        return [business.bk_biz_id for business in businesses if business.bk_biz_id > 0]

    def run(self, delay=True):
        super().run(delay)


class CustomEventCacheManager(BaseMetricCacheManager):
    """
    批量缓存自定义事件指标
    """

    data_sources = ((DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),)

    SYSTEM_EVENTS = [
        {
            "event_group_id": 0,
            "bk_data_id": 1100000,
            "bk_biz_id": 0,
            "table_id": "gse_custom_string",
            "event_group_name": "gse custom string",
            "label": "os",
            "event_info_list": [
                {
                    "event_name": "CustomString",
                    "dimension_list": ["bk_target_ip", "bk_target_cloud_id", "ip", "bk_cloud_id"],
                }
            ],
        },
        {
            "event_group_id": 0,
            "bk_data_id": 1000,
            "bk_biz_id": 0,
            "table_id": "gse_system_event",
            "event_group_name": "gse system event",
            "label": "os",
            "event_info_list": [
                {
                    "event_name": "AgentLost",
                    "dimension_list": ["bk_target_ip", "bk_target_cloud_id", "ip", "bk_cloud_id"],
                },
                {
                    "event_name": "CoreFile",
                    "dimension_list": [
                        "bk_target_ip",
                        "bk_target_cloud_id",
                        "ip",
                        "bk_cloud_id",
                        "executable",
                        "executable_path",
                        "signal",
                    ],
                    "condition_field_list": ["corefile"],
                },
                {
                    "event_name": "DiskFull",
                    "dimension_list": [
                        "bk_target_ip",
                        "bk_target_cloud_id",
                        "ip",
                        "bk_cloud_id",
                        "disk",
                        "file_system",
                        "fstype",
                    ],
                },
                {
                    "event_name": "DiskReadonly",
                    "dimension_list": [
                        "bk_target_ip",
                        "bk_target_cloud_id",
                        "ip",
                        "bk_cloud_id",
                        "position",
                        "fs",
                        "type",
                    ],
                },
                {
                    "event_name": "OOM",
                    "dimension_list": ["bk_target_ip", "bk_target_cloud_id", "ip", "bk_cloud_id", "process", "task"],
                    "condition_field_list": ["message", "oom_memcg", "task_memcg", "constraint"],
                },
                {
                    "event_name": "PingUnreachable",
                    "dimension_list": ["bk_target_ip", "bk_target_cloud_id", "ip", "bk_cloud_id"],
                },
            ],
        },
    ]

    def get_tables(self):
        # 1.系统事件(biz_id为0)
        yield from self.get_system_event_tables(self.bk_tenant_id, self.bk_biz_id)
        # # 2.自定义事件[查询CustomEventGroup表]
        custom_event_result = api.metadata.query_event_group.request.refresh(
            bk_tenant_id=self.bk_tenant_id, bk_biz_id=self.bk_biz_id
        )
        event_group_ids = [
            custom_event.bk_event_group_id
            for custom_event in CustomEventGroup.objects.filter(type="custom_event").only("bk_event_group_id")
        ]
        # 增加自定义事件筛选，不在监控创建的策略配置时不展示
        for result in custom_event_result:
            if result["event_group_id"] in event_group_ids:
                yield result
        if self.bk_biz_id < 0:
            space_uid = bk_biz_id_to_space_uid(self.bk_biz_id)
            if space_uid.startswith(SpaceTypeEnum.BKCI.value):
                space = SpaceApi.get_related_space(space_uid, SpaceTypeEnum.BKCC.value)
                custom_event_result += api.metadata.query_event_group.request.refresh(
                    bk_tenant_id=self.bk_tenant_id, bk_biz_id=space.bk_biz_id
                )
        # 3.k8s 事件
        # 1. 先拿业务下的集群列表
        # 区分 custom_event 和 k8s_event (来自metadata的设计)
        try:
            bcs_clusters = api.kubernetes.fetch_k8s_cluster_list(
                bk_biz_id=self.bk_biz_id, bk_tenant_id=self.bk_tenant_id
            )
        except (requests.exceptions.ConnectionError, BKAPIError) as err:
            logger.exception(f"[CustomEventCacheManager] fetch bcs_clusters error: {err}")
            # bcs 未就绪，不影响自定义事件
            bcs_clusters = []

        if not bcs_clusters:
            return
        # 启动监控的集群id 列表
        alert_ids = api.kubernetes.fetch_bcs_cluster_alert_enabled_id_list(
            bk_tenant_id=self.bk_tenant_id, bk_biz_id=self.bk_biz_id
        )
        cluster_map = {bcs_cluster["cluster_id"]: bcs_cluster for bcs_cluster in bcs_clusters}
        for cluster_id in cluster_map:
            for result in custom_event_result:
                if cluster_id in result["event_group_name"]:
                    if self.bk_biz_id < 0:
                        result["bk_biz_id"] = self.bk_biz_id
                    # bcs 集群事件 目标调整为kubernetes
                    result["label"] = "kubernetes"
                    # 补充是否告警
                    extend_cluster_info = {"monitoring": cluster_id in alert_ids}
                    # 补充k8s事件对应dataid的用途:
                    # bcs_${cluster_id}_custom_event: 自定义(custom)
                    # bcs_${cluster_id}_k8s_event：k8s系统(system)
                    usage = "custom" if result["event_group_name"].endswith("_custom_event") else "k8s"
                    extend_cluster_info["usage"] = usage
                    # 更新补充信息
                    cluster_map[cluster_id].update(extend_cluster_info)
                    result["k8s_cluster_info"] = cluster_map[cluster_id]
                    yield result

    def get_system_event_tables(self, bk_tenant_id: str, bk_biz_id: int) -> list[dict[str, Any]]:
        """
        获取系统事件表
        """
        from metadata.models import DataSource

        # 非多租户模式下，直接返回内置系统事件
        if not settings.ENABLE_MULTI_TENANT_MODE:
            if bk_biz_id == 0:
                return self.SYSTEM_EVENTS
            else:
                return []

        # 多租户模式下，跳过非cmdb业务
        if bk_biz_id <= 0:
            return []

        # 获取cmdb业务下的系统事件数据源
        data_source = DataSource.objects.filter(
            bk_tenant_id=bk_tenant_id, data_name=f"base_{bk_biz_id}_agent_event"
        ).first()
        if not data_source:
            return []

        system_event = copy.deepcopy(self.SYSTEM_EVENTS[1])
        system_event["bk_biz_id"] = bk_biz_id
        system_event["bk_data_id"] = data_source.bk_data_id
        system_event["table_id"] = f"base_{bk_tenant_id}_{bk_biz_id}_event"
        return [system_event]

    def get_metrics_by_table(self, table):
        # 默认均为自定义事件
        data_source_label = DataSourceLabel.CUSTOM
        table_display_name = table["event_group_name"]
        if "k8s_cluster_info" in table:
            pre_fix = "" if table["k8s_cluster_info"]["monitoring"] else "[{}]".format(_("不监控"))
            table_display_name = (
                f"{pre_fix}{table['k8s_cluster_info']['name']}({table['k8s_cluster_info']['cluster_id']})"
            )
            table_display_name = f"[{table['k8s_cluster_info']['usage']}]{table_display_name}"

        base_dict = {
            "result_table_id": table["table_id"],
            "result_table_name": table_display_name,
            "result_table_label": table["label"],
            "result_table_label_name": self.get_label_name(table["label"]),
            "data_source_label": data_source_label,
            "data_type_label": DataTypeLabel.EVENT,
            "bk_biz_id": table["bk_biz_id"],
            "data_target": DataTargetMapping().get_data_target(
                table["label"], DataSourceLabel.CUSTOM, DataTypeLabel.EVENT
            ),
            "collect_config_ids": [],
        }

        for metric_msg in table["event_info_list"]:
            metric_detail = {
                "default_dimensions": [],
                "default_condition": [],
                "metric_field": metric_msg["event_name"],
                "metric_field_name": f"{metric_msg['event_name']}-{table_display_name}",
                "dimensions": [
                    {"id": dimension_name, "name": dimension_name} for dimension_name in metric_msg["dimension_list"]
                ],
                "extend_fields": {
                    "custom_event_name": metric_msg["event_name"],
                    "bk_data_id": table["bk_data_id"],
                    "bk_event_group_id": table["event_group_id"],
                    # get_built_in_k8s_events 不一定有 event_id 字段
                    "bk_event_id": metric_msg.get("event_id", 0),
                },
            }

            # 支持非维度字段作为条件
            if "condition_field_list" in metric_msg:
                metric_detail["dimensions"].extend(
                    [
                        {"id": condition_name, "name": condition_name, "is_dimension": False}
                        for condition_name in metric_msg["condition_field_list"]
                    ]
                )

            metric_detail.update(base_dict)
            yield metric_detail

        # 新增整个事件源
        if table["event_group_id"] != 0:
            metric_detail = {
                "default_dimensions": [],
                "default_condition": [],
                # "__INDEX__" 表示整个事件源索引
                "metric_field": "__INDEX__",
                "metric_field_name": f"{table_display_name}({table['bk_data_id']})",
                "dimensions": [{"id": "event_name", "name": "event_name"}],
                "extend_fields": {
                    # 全局自定义事件指标， 不预定义事件名称
                    "custom_event_name": "",
                    "bk_data_id": table["bk_data_id"],
                    "bk_event_group_id": table["event_group_id"],
                },
            }
            metric_detail.update(base_dict)
            yield metric_detail

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list[int]:
        """
        获取匹配的业务ID列表
        1. 有自定义事件的业务
        2. 有k8s集群的业务
        3. 全局业务(biz_id=0)
        """
        biz_ids = set()

        # 1. 获取有自定义事件的业务ID
        custom_event_biz_ids = list(
            CustomEventGroup.objects.filter(type="custom_event", bk_tenant_id=bk_tenant_id)
            .values_list("bk_biz_id", flat=True)
            .distinct()
        )
        biz_ids.update(custom_event_biz_ids)

        # 2.添加业务ID为0（处理系统事件）
        biz_ids.add(0)

        # 3. 获取有K8s集群的业务ID
        try:
            # 一次性获取租户下所有集群
            all_clusters = api.kubernetes.fetch_k8s_cluster_list(bk_tenant_id=bk_tenant_id)
        except BKAPIError as e:
            logger.exception(f"Failed to get k8s clusters: {e}")
            return list(biz_ids)

        # 从集群信息中提取业务ID并添加到结果集
        for cluster in all_clusters:
            if cluster["bk_biz_id"]:
                biz_ids.add(int(cluster["bk_biz_id"]))

        return list(biz_ids)


class BkMonitorLogCacheManager(BaseMetricCacheManager):
    """
    缓存日志关键字指标
    """

    data_sources = ((DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),)

    def get_tables(self):
        custom_event_result = api.metadata.query_event_group.request.refresh(bk_tenant_id=self.bk_tenant_id)
        logger.info(f"[QUERY_EVENT_GROUP] event_group_list length is {len(custom_event_result)}")

        self.event_group_id_to_event_info = {}
        for e in custom_event_result:
            event_group_id = int(e["event_group_id"])
            self.event_group_id_to_event_info[event_group_id] = e

        yield from CollectConfigMeta.objects.filter(
            Q(collect_type=CollectConfigMeta.CollectType.SNMP_TRAP) | Q(collect_type=CollectConfigMeta.CollectType.LOG),
            bk_tenant_id=self.bk_tenant_id,
        )

    def get_metrics_by_table(self, table):
        version = table.deployment_config.plugin_version
        event_group_name = f"{version.plugin.plugin_type}_{version.plugin_id}"
        group_info = CustomEventGroup.objects.get(name=event_group_name, bk_tenant_id=self.bk_tenant_id)
        event_info_list = CustomEventItem.objects.filter(bk_event_group=group_info)

        metric = {
            "result_table_id": group_info.table_id,
            "result_table_name": group_info.name,
            "result_table_label": version.plugin.label,
            "result_table_label_name": self.get_label_name(version.plugin.label),
            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
            "data_type_label": DataTypeLabel.LOG,
            "bk_biz_id": table.bk_biz_id,
            "data_target": DataTargetMapping().get_data_target(
                version.plugin.label, DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG
            ),
            "collect_config_ids": [],
            "default_dimensions": [],
            "default_condition": [],
            "metric_field": "event.count",
            "metric_field_name": table.name,
            "related_name": table.name,
            "related_id": str(table.id),
        }

        dimensions = set()
        event_group_item = self.event_group_id_to_event_info.get(int(group_info.bk_event_group_id))
        if event_group_item:
            for event_info in event_group_item["event_info_list"]:
                for dimension in event_info["dimension_list"]:
                    dimensions.add(dimension)
        else:
            for event_info in event_info_list:
                for dimension in event_info.dimension_list:
                    dimensions.add(dimension["dimension_name"])

        metric["dimensions"] = [{"id": dimension_name, "name": dimension_name} for dimension_name in dimensions]
        yield metric

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list[int]:
        """
        获取监控日志的可用biz_id列表
        只返回实际配置了日志采集或SNMP Trap的业务ID
        """
        # 直接查询并获取去重的业务ID列表
        available_biz_ids = list(
            CollectConfigMeta.objects.filter(
                collect_type__in=[CollectConfigMeta.CollectType.SNMP_TRAP, CollectConfigMeta.CollectType.LOG],
                bk_tenant_id=bk_tenant_id,
                bk_biz_id__gt=0,  # 直接过滤掉非正常业务ID
            )
            .values_list("bk_biz_id", flat=True)
            .distinct()
        )
        return available_biz_ids


class BaseAlarmMetricCacheManager(BaseMetricCacheManager):
    """
    系统事件指标缓存
    """

    data_sources = ((DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.EVENT),)

    def add_gse_process_event_metrics(self, result_table_label):
        """
        增加gse进程托管相关指标
        """
        gse_process_dimensions = [
            {"id": "event_name", "name": _("事件名称")},
            {"id": "process_name", "name": _("进程名称")},
            {"id": "process_group_id", "name": _("进程组ID")},
            {"id": "process_index", "name": _("进程索引")},
        ]
        gse_base_dict = {
            "bk_biz_id": 0,
            "result_table_id": SYSTEM_EVENT_RT_TABLE_ID,
            "result_table_label": "host_process",
            "result_table_label_name": self.get_label_name("host_process"),
            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
            "data_type_label": DataTypeLabel.EVENT,
            "data_target": DataTargetMapping().get_data_target(
                result_table_label, DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.EVENT
            ),
            "dimensions": gse_process_dimensions,
            "default_dimensions": ["process_name", "process_group_id", "process_index", "event_name"],
            "default_condition": [],
            "collect_config_ids": [],
        }
        gse_custom_report = [{"metric_field": "gse_process_event", "metric_field_name": _("Gse进程托管事件")}]
        for metric in gse_custom_report:
            metric.update(gse_base_dict)
            yield metric

    def get_tables(self):
        # 多租户模式下暂时不内置系统事件
        if settings.ENABLE_MULTI_TENANT_MODE:
            return

        yield {}

    def get_metrics_by_table(self, table):
        result_table_label = "os"
        metric_list = BaseAlarm.objects.filter(is_enable=True)
        if Platform.te:
            # te平台不展示ping不可达告警， 同时也不内置
            metric_list = metric_list.exclude(title="ping-gse")
        base_dict = {
            "bk_biz_id": 0,
            "result_table_id": SYSTEM_EVENT_RT_TABLE_ID,
            "result_table_label": result_table_label,
            "result_table_label_name": self.get_label_name(result_table_label),
            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
            "data_type_label": DataTypeLabel.EVENT,
            "data_target": DataTargetMapping().get_data_target(
                result_table_label, DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.EVENT
            ),
            "default_dimensions": [],
            "default_condition": [],
            "collect_config_ids": [],
        }

        for metric in metric_list:
            metric_dict = copy.deepcopy(base_dict)
            metric_dict["metric_field"] = metric.title
            metric_dict["metric_field_name"] = metric.description

            dimensions = metric.dimensions
            # 调整oom维度，后续系统事件直接使用json文件记录
            if metric.title == "oom-gse":
                dimensions = ["oom_memcg", "task_memcg", "task", "constraint", "process", "message"]

            metric_dict["dimensions"] = [{"id": dimension, "name": dimension} for dimension in dimensions]
            yield metric_dict

        # 增加额外的系统事件指标
        extend_metrics = [
            # deprecated
            # {
            #     "metric_field": "gse_custom_event",
            #     "metric_field_name": _("自定义字符型告警"),
            #     "dimensions": DefaultDimensions.host,
            # },
            {
                "metric_field": "proc_port",
                "metric_field_name": _("进程端口"),
                "dimensions": [
                    {"id": "display_name", "name": "display_name"},
                    {"id": "protocol", "name": "protocol"},
                    {"id": "bind_ip", "name": "bind_ip"},
                ]
                + DefaultDimensions.host,
                "result_table_label": "host_process",
            },
            {"metric_field": "os_restart", "metric_field_name": _("主机重启"), "dimensions": DefaultDimensions.host},
        ]

        for metric in extend_metrics:
            metric_dict = copy.deepcopy(base_dict)
            metric_dict.update(metric)
            yield metric_dict

        # gse进程托管事件指标
        for metric in self.add_gse_process_event_metrics(result_table_label):
            yield metric

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list[int]:
        """获取系统事件相关的业务ID列表"""
        # 多租户模式下暂时不内置系统事件
        if settings.ENABLE_MULTI_TENANT_MODE:
            return []
        # 系统事件只在业务ID为0的情况下处理
        return [0]


class BkmonitorMetricCacheManager(BaseMetricCacheManager):
    """
    监控采集指标缓存
    """

    data_sources = ((DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),)

    def __init__(self, bk_tenant_id: str, bk_biz_id: int | None = None):
        super().__init__(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

        # 添加默认维度映射
        default_dimension_list = (
            SnapshotHostIndex.objects.exclude(dimension_field="")
            .values_list("result_table_id", "dimension_field")
            .distinct()
        )
        self.ts_db_name = []
        self.dimension_map = dict()
        # 将数据库中的表ID格式转化为结果表ID格式
        for result_table_id, dimension_field in default_dimension_list:
            map_key = result_table_id.replace("_", ".", 1)
            self.dimension_map[map_key] = dimension_field.split(",")

    def get_metric_pool(self):
        # 去掉进程采集相关,因为实际是自定义指标上报上来的。
        metric_queryset = MetricListCache.objects.filter(
            data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            data_type_label=DataTypeLabel.TIME_SERIES,
            bk_tenant_id=self.bk_tenant_id,
        ).exclude(result_table_id="")

        if not settings.ENABLE_MULTI_TENANT_MODE:
            metric_queryset = metric_queryset.exclude(result_table_id__in=BuildInProcessMetric.result_table_list())
        return metric_queryset

    def get_tables(self):
        """
        获取所有需要处理的表数据
        """
        # 多租户模式下，直接走新的处理逻辑
        if settings.ENABLE_MULTI_TENANT_MODE:
            yield {}
            return
        if self.bk_biz_id is None:
            yield from api.metadata.list_monitor_result_table(bk_tenant_id=self.bk_tenant_id, with_option=False)
        else:
            yield from api.metadata.list_monitor_result_table(
                bk_biz_id=self.bk_biz_id, bk_tenant_id=self.bk_tenant_id, with_option=False
            )

        plugin_data = (
            CollectorPluginMeta.objects.filter(bk_tenant_id=self.bk_tenant_id)
            .exclude(plugin_type__in=[PluginType.SNMP_TRAP, PluginType.LOG, PluginType.PROCESS])
            .filter(bk_biz_id=self.bk_biz_id)
            .values_list("plugin_type", "plugin_id")
        )
        if plugin_data.exists():
            # 获取全部的插件下的 ts 数据
            db_name_list = [f"{plugin[0]}_{plugin[1]}".lower() for plugin in plugin_data]
            for name in db_name_list:
                # 插件默认都是全局数据
                group_list = api.metadata.query_time_series_group.request.refresh(
                    bk_tenant_id=self.bk_tenant_id, bk_biz_id=0, time_series_group_name=name
                )
                if not group_list:
                    continue
                self.ts_db_name.append(name)

                for group in group_list:
                    group["bk_biz_id"] = self.bk_biz_id
                    yield group

        # 插件类指标
        yield from self.get_plugin_tables()

    def get_plugin_tables(self):
        """
        按metadata格式生成插件类表数据
        """
        # 只需要生成监控采集时序型上报的插件指标
        plugins = CollectorPluginMeta.objects.filter(bk_tenant_id=self.bk_tenant_id).exclude(
            plugin_type__in=[PluginType.SNMP_TRAP, PluginType.LOG, PluginType.PROCESS]
        )
        if self.bk_biz_id is not None:
            plugins = plugins.filter(bk_biz_id=self.bk_biz_id)
        plugin_mapping = {plugin.plugin_id: plugin for plugin in plugins}
        plugin_ids = list(plugin_mapping.keys())

        # 批量查询插件的最新release版本
        last_version_ids = [
            version["last_id"]
            for version in PluginVersionHistory.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                plugin_id__in=plugin_ids,
                stage=PluginVersionHistory.Stage.RELEASE,
            )
            .values("plugin_id")
            .order_by("plugin_id")
            .annotate(last_id=Max("id"))
        ]
        plugin_versions = PluginVersionHistory.objects.filter(bk_tenant_id=self.bk_tenant_id, id__in=last_version_ids)

        # 批量插件关联的采集配置，并按插件进行分组
        collect_configs = CollectConfigMeta.objects.filter(
            bk_tenant_id=self.bk_tenant_id, plugin_id__in=plugin_ids
        ).select_related("deployment_config")
        plugin_collect_configs = defaultdict(list)
        for collect_config in collect_configs:
            plugin_collect_configs[collect_config.plugin_id].append(collect_config)

        for plugin_version in plugin_versions:
            plugin = plugin_version.plugin
            # 如果该插件已经是 timeseriesgroup 的模式了，则过滤掉
            if f"{plugin.plugin_type}_{plugin.plugin_id}".lower() in self.ts_db_name:
                continue
            tables = plugin_version.info.metric_json
            config_json = plugin_version.config.config_json
            related_collects = plugin_collect_configs[plugin.plugin_id]

            # 没有采集配置下发指标不需显示
            if not related_collects:
                continue

            # 计算最小采集周期用作指标采集周期
            min_period = min([config.deployment_config.params["collector"]["period"] for config in related_collects])

            for table in tables:
                yield {
                    "bk_biz_id": plugin.bk_biz_id,
                    "table_type": "plugin",
                    "table_id": plugin_version.get_result_table_id(plugin, table["table_name"]).lower(),
                    "data_label": (f"{plugin.plugin_type}_{plugin.plugin_id}").lower(),
                    "table_name_zh": table["table_desc"],
                    "default_storage": "",
                    "label": plugin.label,
                    "source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                    "type_label": DataTypeLabel.TIME_SERIES,
                    "field_list": [
                        {
                            "field_name": field["name"],
                            "tag": field["monitor_type"],
                            "description": "",
                            "alias_name": field["description"],
                            "unit": field.get("unit", ""),
                            "unit_conversion": 1.0,
                        }
                        for field in table["fields"]
                    ],
                    "config_json": config_json,
                    "metric_info": {
                        "bk_biz_id": plugin.bk_biz_id,
                        "collect_interval": min_period,
                        "related_id": plugin.plugin_id,
                        "related_name": plugin_version.info.plugin_display_name,
                        "category_display": plugin_version.info.plugin_display_name,
                        "plugin_type": plugin.plugin_type,
                        "collect_config": ";".join([config.name for config in related_collects]),
                        "collect_config_ids": list({config.id for config in related_collects}),
                    },
                }

    def get_metrics_multi_tenant(self) -> Generator[dict, None, None]:
        """
        多租户模式下，使用全新的缓存逻辑，后续单租户模式同样兼容
        """
        if self.bk_biz_id == 0:
            # 主机数据
            result_table_label_name_map = {"os": "操作系统", "host_process": "进程"}
            for result_table_info in copy.deepcopy(SYSTEM_HOST_METRICS):
                # 判断是否需要补充节点类型和节点名称维度
                dimensions = result_table_info["dimensions"]
                if settings.IS_ACCESS_BK_DATA and settings.IS_ENABLE_VIEW_CMDB_LEVEL:
                    dimensions.append({"id": "bk_obj_id", "name": _("节点类型")})
                    dimensions.append({"id": "bk_inst_id", "name": _("节点名称")})

                for metric_info in result_table_info["metrics"]:
                    yield {
                        "bk_biz_id": 0,
                        "result_table_id": result_table_info["result_table_id"],
                        "result_table_name": result_table_info["result_table_name"],
                        "metric_field": metric_info["metric_field"],
                        "metric_field_name": metric_info["metric_field_name"],
                        "unit": metric_info["unit"],
                        "dimensions": result_table_info["dimensions"],
                        "default_dimensions": result_table_info["default_dimensions"],
                        "default_condition": [],
                        "result_table_label": result_table_info["result_table_label"],
                        "result_table_label_name": result_table_label_name_map[result_table_info["result_table_label"]],
                        "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                        "data_type_label": DataTypeLabel.TIME_SERIES,
                        "data_target": DataTarget.HOST_TARGET,
                        "data_label": result_table_info["data_label"],
                        "related_id": "system",
                        "related_name": "system",
                    }
            # 拨测数据
            for result_table_info in copy.deepcopy(UPTIMECHECK_METRICS):
                for metric_info in result_table_info["metrics"]:
                    yield {
                        "bk_biz_id": 0,
                        "result_table_id": result_table_info["result_table_id"],
                        "result_table_name": result_table_info["result_table_name"],
                        "metric_field": metric_info["metric_field"],
                        "metric_field_name": metric_info["metric_field_name"],
                        "unit": metric_info["unit"],
                        "dimensions": metric_info["dimensions"],
                        "default_dimensions": ["task_id"],
                        "default_condition": [],
                        "result_table_label": "uptimecheck",
                        "result_table_label_name": "服务拨测",
                        "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                        "data_type_label": DataTypeLabel.TIME_SERIES,
                        "data_target": DataTarget.NONE_TARGET,
                        "data_label": result_table_info["data_label"],
                    }

            # 内置进程采集插件
            # 进程性能
            for metric_info in PROCESS_METRICS:
                yield {
                    "bk_biz_id": 0,
                    "result_table_id": "process.perf",
                    "result_table_name": "进程性能",
                    "metric_field": metric_info["metric_field"],
                    "metric_field_name": metric_info["metric_field_name"],
                    "unit": metric_info["unit"],
                    "dimensions": PROCESS_METRIC_DIMENSIONS,
                    "default_dimensions": [],
                    "default_condition": [],
                    "result_table_label": "host_process",
                    "result_table_label_name": "进程",
                    "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "data_target": DataTarget.HOST_TARGET,
                    "data_label": "",
                    "related_id": "process",
                    "related_name": "进程采集",
                }
            # 进程端口
            yield {
                "bk_biz_id": 0,
                "result_table_id": "process.port",
                "result_table_name": "进程端口",
                "metric_field": "alive",
                "metric_field_name": "端口存活",
                "unit": "none",
                "dimensions": PROCESS_PORT_METRIC_DIMENSIONS,
                "default_dimensions": [],
                "default_condition": [],
                "result_table_label": "host_process",
                "result_table_label_name": "进程",
                "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "data_target": DataTarget.HOST_TARGET,
                "data_label": "",
                "related_id": "process",
                "related_name": "进程采集",
            }

        # 插件采集
        plugins = CollectorPluginMeta.objects.filter(bk_tenant_id=self.bk_tenant_id, bk_biz_id=self.bk_biz_id).exclude(
            plugin_type__in=CollectorPluginMeta.VIRTUAL_PLUGIN_TYPE
        )
        for plugin in plugins:
            # 刷新插件的metric_json
            plugin.refresh_metric_json()
            for table in plugin.current_version.info.metric_json:
                metric_infos: list[dict[str, Any]] = []
                dimension_infos: list[dict[str, Any]] = []
                for field in table["fields"]:
                    # 字段分类
                    if field["monitor_type"] == "metric":
                        # 跳过非活跃字段
                        if field["is_active"]:
                            metric_infos.append(field)
                    else:
                        dimension_infos.append(field)

                # 维度列表
                dimensions = [
                    {"id": dimension_info["name"], "name": dimension_info["description"] or dimension_info["name"]}
                    for dimension_info in dimension_infos
                ]

                # 判断目标类型
                data_target = DataTargetMapping.get_data_target(
                    result_table_label=plugin.label,
                    data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
                    data_type_label=DataTypeLabel.TIME_SERIES,
                )

                for metric_info in metric_infos:
                    yield {
                        "bk_biz_id": self.bk_biz_id,
                        "result_table_id": PluginVersionHistory.get_result_table_id(
                            plugin, table["table_name"]
                        ).lower(),
                        "result_table_name": table["table_desc"],
                        "metric_field": metric_info["name"],
                        "metric_field_name": metric_info["description"] or metric_info["name"],
                        "unit": metric_info["unit"],
                        "dimensions": dimensions,
                        "default_dimensions": [],
                        "default_condition": [],
                        "result_table_label": plugin.label,
                        "result_table_label_name": self.get_label_name(plugin.label),
                        "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                        "data_type_label": DataTypeLabel.TIME_SERIES,
                        "data_target": data_target,
                        "data_label": plugin.plugin_id,
                    }

    def get_metrics_by_table(self, table):
        """
        处理不同类型的表数据， 根据influx_db_name的不同， 进行不同的处理
        """
        # 多租户模式下，直接使用全新的缓存逻辑
        if settings.ENABLE_MULTI_TENANT_MODE:
            yield from self.get_metrics_multi_tenant()
            return

        try:
            result_table_id = table["table_id"]
            influx_db_name = table["table_id"].split(".")[0]

            if "elasticsearch" == table.get("default_storage") or re.match(r"_cmdb_level_split$", result_table_id):
                # 日志和拆分表的结果表不录入
                return
            if influx_db_name in self.ts_db_name:
                yield from self.get_plugin_ts_metric(table)
            elif influx_db_name == "uptimecheck":
                yield from self.get_uptime_check_metric(table)
            elif influx_db_name == "pingserver":
                yield from self.get_pingserver_metric(table)
            elif influx_db_name in ["dbm_system", "system", "devx_system", "perforce_system"]:
                if result_table_id in ["system.proc_port"]:
                    return

                yield from self.get_system_metric(table)
            elif influx_db_name.lower() == "agentmetric":
                yield from self.get_bkci_metric(table)
            elif table.get("table_type") == "plugin":
                yield from self.get_plugin_metric(table)
            elif influx_db_name.startswith("bkprecal_"):
                # 预聚合表
                yield from self.get_pre_calculate_metric(table)
        except BaseException:  # noqa
            logger.exception("get metrics error, table({})".format(table.get("table_id", "")))

    def get_pre_calculate_metric(self, table):
        base_metric = self.get_base_dict(table)
        base_metric.update(
            {"related_name": "bk_pre_cal", "related_id": "bk_pre_cal", "category_display": _("预计算指标")}
        )
        return self.get_field_metric_msg(table, base_metric)

    def get_base_dict(self, table):
        result_table_id = table["table_id"]
        result_table_name = table["table_name_zh"]

        dimensions = []
        for field in table["field_list"]:
            if field["tag"] == "dimension" and field["field_name"] not in FILTER_DIMENSION_LIST:
                dimensions.append(
                    {
                        "id": field["field_name"],
                        "name": field["description"] if field["description"] else field["field_name"],
                    }
                )

        data_target = DataTargetMapping().get_data_target(table["label"], table["source_label"], table["type_label"])

        default_dimensions = list([x["id"] for x in DEFAULT_DIMENSIONS_MAP[data_target]])

        return {
            "bk_biz_id": 0,
            "result_table_id": result_table_id,
            "result_table_name": result_table_name,
            "dimensions": dimensions,
            "default_dimensions": default_dimensions,
            "default_condition": [],
            "result_table_label": table["label"],
            "result_table_label_name": self.get_label_name(table["label"]),
            "data_source_label": table["source_label"],
            "data_type_label": table["type_label"],
            "data_target": data_target,
            "data_label": table.get("data_label", ""),
        }

    def get_field_metric_msg(self, table, base_metric):
        field_list = []
        result_table_id = table["table_id"]
        for field in table["field_list"]:
            field_dict = {}
            field_dict.update(copy.deepcopy(base_metric))
            if field["tag"] == "metric":
                field_dict["metric_field"] = field["field_name"]
                field_dict["metric_field_name"] = field["alias_name"] if field["alias_name"] else field["field_name"]
                field_dict["unit"] = field.get("unit", "")
                field_dict["unit_conversion"] = field.get("unit_conversion", 1.0)
                field_dict["description"] = field.get("description", "")
                if result_table_id in self.dimension_map:
                    field_dict["default_dimensions"].extend(self.dimension_map.get(result_table_id))

                field_list.append(field_dict)
        return field_list

    def get_uptime_check_metric(self, table):
        protocol = table["table_id"].split(".")[1].upper()
        base_metric = self.get_base_dict(table)
        base_metric["data_label"] = f"uptimecheck_{protocol.lower()}"

        if protocol == "ICMP":
            field_metric_list = self.get_field_metric_msg(table, base_metric)
        else:
            field_metric_list = UPTIMECHECK_MAP.get(protocol, [])

        for metric_model in field_metric_list:
            if protocol == "ICMP":
                metric_dict = metric_model
            else:
                metric_dict = base_metric.copy()
                metric_dict.update(metric_model(protocol).__dict__)

            metric_dict["metric_field_name"] = f"{protocol} {_(metric_dict['metric_field_name'])}"

            metric_dict.update(
                {
                    "category_display": _("服务拨测"),
                    "collect_interval": 5,
                    "related_name": "",
                    "related_id": "",
                    "bk_biz_id": 0,
                    "default_dimensions": ["task_id"],
                    # 当前http/tcp/udp类型维度为给定内容
                    # icmp维度与metadata保持一致
                    # 针对拨测服务采集，过滤业务/IP/云区域ID/错误码
                    "dimensions": [
                        dimension
                        for dimension in metric_dict["dimensions"]
                        if dimension["id"] not in ["bk_biz_id", "ip", "bk_cloud_id", "error_code"]
                    ],
                }
            )
            yield metric_dict

    def get_pingserver_metric(self, table):
        base_metric = self.get_base_dict(table)
        base_metric.update(
            {"related_name": "pingserver", "related_id": "pingserver", "category_display": _("PING服务")}
        )
        return self.get_field_metric_msg(table, base_metric)

    def get_bkci_metric(self, table):
        # 蓝盾构建机指标处理
        base_metric = self.get_base_dict(table)
        base_metric.update({"related_name": "bkci", "related_id": "bkci", "category_display": _("构建机")})
        return self.get_field_metric_msg(table, base_metric)

    def get_system_metric(self, table):
        base_metric = self.get_base_dict(table)
        if settings.IS_ACCESS_BK_DATA and settings.IS_ENABLE_VIEW_CMDB_LEVEL:
            base_metric["dimensions"].append({"id": "bk_obj_id", "name": _("节点类型")})
            base_metric["dimensions"].append({"id": "bk_inst_id", "name": _("节点名称")})
        base_metric.update({"related_name": "system", "related_id": "system", "category_display": _("物理机")})
        return self.get_field_metric_msg(table, base_metric)

    def get_plugin_metric(self, table):
        base_metric = self.get_base_dict(table)

        # 根据监控目标类型补充维度
        base_metric["dimensions"].extend(DEFAULT_DIMENSIONS_MAP[base_metric["data_target"]])
        base_metric["dimensions"].extend(
            [
                {"id": "ip", "name": _("采集器IP")},
                {"id": "bk_cloud_id", "name": _("采集器云区域ID")},
                {"id": "bk_collect_config_id", "name": _("采集配置")},
            ]
        )
        # 如果需要支持ipv6则补充bk_host_id维度
        if not self.bk_biz_id or is_ipv6_biz(self.bk_biz_id):
            base_metric["dimensions"].append({"id": "bk_host_id", "name": _("主机ID")})

        for param in table["config_json"]:
            if param["mode"] == ParamMode.DMS_INSERT:
                for dms_key in param["default"].keys():
                    base_metric["dimensions"].append({"id": dms_key, "name": dms_key})
        # 如果开启了节点聚合，则可以补充节点聚合维度
        if settings.IS_ACCESS_BK_DATA and settings.IS_ENABLE_VIEW_CMDB_LEVEL:
            base_metric["dimensions"].extend(
                [{"id": "bk_obj_id", "name": _("节点类型")}, {"id": "bk_inst_id", "name": _("节点名称")}]
            )

        base_metric.update(table["metric_info"])

        return self.get_field_metric_msg(table, base_metric)

    def get_plugin_ts_metric(self, table):
        table_id = f"{table['table_id'].split('.')[0]}.__default__"
        data_target = DataTargetMapping().get_data_target(
            table["label"], DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES
        )
        base_dict = self.get_ts_basic_dict(table)
        base_dict.update(
            result_table_id=table_id,
            data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            data_type_label=DataTypeLabel.TIME_SERIES,
            data_target=data_target,
        )
        for metric_msg in table["metric_info_list"]:
            if not metric_msg:
                continue
            metric_detail = self.get_time_series_metric_detail(metric_msg)
            metric_detail.update(base_dict)
            yield metric_detail

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list[int]:
        """
        获取监控采集的可用biz_id列表

        Note: 默认只刷新bkcc业务，其他业务引导用户自行触发刷新
        """
        spaces: list[Space] = SpaceApi.list_spaces(bk_tenant_id=bk_tenant_id)
        # 默认只刷新bkcc业务，其他业务引导用户自行触发刷新
        return [space.bk_biz_id for space in spaces if space.bk_biz_id > 0] + [0]


class BkmonitorK8sMetricCacheManager(BkmonitorMetricCacheManager):
    """
    监控采集k8s指标缓存
    """

    # 内置k8s指标映射维度，用于重名指标维度合并
    _build_in_metrics = None
    IGNORE_DIMENSIONS = ["bk_instance", "bk_job"]

    @property
    def build_in_metrics(self):
        if self._build_in_metrics is None:
            self._build_in_metrics = {}
            for metric in get_built_in_k8s_metrics():
                self._build_in_metrics[metric["field_name"]] = [
                    tag for tag in metric["tag_list"] if tag["field_name"] not in self.IGNORE_DIMENSIONS
                ]
        return self._build_in_metrics

    def get_metric_pool(self):
        # 指标池限定为table_id为空的k8s指标
        return MetricListCache.objects.filter(
            bk_tenant_id=self.bk_tenant_id,
            data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            data_type_label=DataTypeLabel.TIME_SERIES,
            result_table_id="",
        )

    def get_tables(self):
        # k8s 相关指标，table_id 设置为空dict
        yield {}

    def get_metrics_by_table(self, table):
        # 按业务获取指标
        # 业务id为Node时，抛出异常（k8s指标仅支持按业务缓存）
        # 业务id为0时，获取全局内置k8s指标
        # 业务id非0时，按业务缓存对应custom_data_id下的指标
        if self.bk_biz_id is None:
            logger.exception("get k8s metrics error, bk_biz_id is None.")
        else:
            yield from self.get_k8s_metric(
                api.metadata.query_bcs_metrics(bk_biz_ids=[self.bk_biz_id], bk_tenant_id=self.bk_tenant_id),
                bk_biz_id=self.bk_biz_id,
            )

    def get_k8s_metric(self, metrics, bk_biz_id):
        def get_base_table_by_metric(k8s_metric):
            # todo 暂时写死table_id 为空
            table_dict = {
                "source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                "type_label": DataTypeLabel.TIME_SERIES,
                "label": "kubernetes",
                "table_id": "",
                "table_name_zh": "kubernetes",
                "field_list": [
                    {
                        "field_name": k8s_metric["field_name"],
                        "description": k8s_metric.get("description", k8s_metric["field_name"]),
                        "tag": "metric",
                        "alias_name": "",
                        "unit": k8s_metric.get("unit", ""),
                        "type": k8s_metric.get("type", "float"),
                    }
                ],
            }
            for dimension in k8s_metric["dimensions"]:
                table_dict["field_list"].append(
                    {
                        "field_name": dimension["field_name"],
                        "description": dimension.get("description", ""),
                        "tag": "dimension",
                        "alias_name": "",
                        "type": k8s_metric.get("type", "string"),
                    }
                )
            return table_dict

        # 获取预定义指标信息
        metrics_define = api.kubernetes.fetch_metrics_define()

        for metric in metrics:
            # 获取该k8s指标基础表 及 基础指标结构
            table = get_base_table_by_metric(metric)
            base_metric = self.get_base_dict(table)
            # 解析指标前缀获取db名
            db, result_table_name = get_metric_category(metric["field_name"])
            base_metric.update(
                {
                    "related_name": db,
                    "related_id": db,
                    "category_display": db,
                    "result_table_name": f"{db}_{result_table_name}",
                }
            )
            # 获取field_list中tag为metric的指标列表
            field_metric_list = self.get_field_metric_msg(table, base_metric)
            for field in field_metric_list:
                field["bk_biz_id"] = bk_biz_id
                metric_define = metrics_define.get(field.get("metric_field"))
                if metric_define:
                    for k, v in metric_define.items():
                        field[k] = v

                if bk_biz_id != 0 and field["metric_field"] in self.build_in_metrics:
                    # 合并0业务下重名k8s指标的维度
                    dimensions = field.get("dimensions", [])
                    dimension_names = [dimension["id"] for dimension in dimensions]
                    for built_in_dimension in self.build_in_metrics[field["metric_field"]]:
                        if built_in_dimension["field_name"] in dimension_names:
                            continue
                        dimensions.append(
                            {
                                "id": built_in_dimension["field_name"],
                                "name": built_in_dimension["description"]
                                if built_in_dimension["description"]
                                else built_in_dimension["field_name"],
                            }
                        )
                    # 将该业务下的该重名指标打上标记
                    field["is_duplicate"] = 1
                yield field

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list[int]:
        """
        获取有K8s指标的业务ID列表

        K8s指标的业务来源有两种：
        1. 有K8s集群的bkcc及关联的bkci业务
        2. 业务0 - 处理内置的K8s指标
        """
        biz_ids: set[int] = set([0])

        # 查询bcs业务关联的bkcc业务
        bkcc_to_bkcis: dict[int, list[int]] = {}
        businesses: list[Space] = SpaceApi.list_spaces(bk_tenant_id=bk_tenant_id)
        for business in businesses:
            if business.space_type_id != SpaceTypeEnum.BKCI.value or not business.space_code:
                continue
            related_space: Space | None = SpaceApi.get_related_space(business.space_uid, SpaceTypeEnum.BKCC.value)
            if related_space:
                bkcc_to_bkcis.setdefault(related_space.bk_biz_id, []).append(business.bk_biz_id)

        # 获取有集群记录的bkcc业务ID
        biz_ids_with_clusters = (
            models.BCSClusterInfo.objects.filter(bk_biz_id__in=bkcc_to_bkcis.keys())
            .values_list("bk_biz_id", flat=True)
            .distinct()
        )
        biz_ids.update(biz_ids_with_clusters)

        # 将bkcc业务关联的bkci业务ID添加到结果集
        for bkcc_biz_id, bkci_biz_ids in bkcc_to_bkcis.items():
            if bkcc_biz_id not in biz_ids_with_clusters:
                continue
            biz_ids.update(bkci_biz_ids)

        return list(biz_ids)


class BkMonitorAlertCacheManager(BaseMetricCacheManager):
    """
    批量缓存监控告警事件指标
    """

    data_sources = ((DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.ALERT),)

    @staticmethod
    def is_composite(configs):
        """
        判断是否为关联策略
        :param configs:
        :return:
        """
        for query_config in configs:
            if query_config.data_type_label == DataTypeLabel.ALERT:
                return True
        return False

    @staticmethod
    def get_target_type(strategy, query_configs):
        """
        获取策略的目标类型
        """
        if not query_configs:
            return DataTarget.NONE_TARGET

        query_config = query_configs[0]

        if (
            strategy.scenario in HOST_SCENARIO
            and query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        ):
            return DataTarget.HOST_TARGET
        elif (
            strategy.scenario in SERVICE_SCENARIO
            and query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        ):
            return DataTarget.SERVICE_TARGET

        return DataTarget.NONE_TARGET

    def get_tables(self):
        if not self.bk_biz_id:
            return []

        strategies = StrategyModel.objects.filter(bk_biz_id=self.bk_biz_id).only("id", "bk_biz_id", "scenario", "name")
        strategy_ids = [item.id for item in strategies]
        query_configs = QueryConfigModel.objects.filter(strategy_id__in=strategy_ids).only(
            "data_type_label", "data_source_label", "config", "strategy_id"
        )
        strategy_configs = defaultdict(list)
        for query_config in query_configs:
            strategy_configs[query_config.strategy_id].append(query_config)

        for strategy in strategies:
            strategy_config = strategy_configs.get(strategy.id) or []
            strategy.alert_target_type = self.get_target_type(strategy, strategy_config)
            public_dimensions = reduce(
                lambda x, y: x & y, [set(item.config.get("agg_dimension", [])) for item in strategy_config]
            )
            strategy.public_dimensions = list(public_dimensions)
            if not self.is_composite(strategy_config):
                yield strategy

    def get_metrics_by_table(self, strategy):
        # 将策略表转换成缓存表信息

        public_dimensions = strategy.public_dimensions
        target_type = strategy.alert_target_type

        dimensions = []
        if target_type == DataTarget.HOST_TARGET:
            dimensions += [
                {"id": "ip", "name": _("目标IP")},
                {"id": "bk_cloud_id", "name": _("云区域ID")},
            ]
        if target_type == DataTarget.SERVICE_TARGET:
            dimensions += [
                {"id": "bk_service_instance_id", "name": _("目标服务实例ID")},
            ]

        public_dimensions = [dimension for dimension in public_dimensions if dimension not in IGNORED_TAGS]

        for dimension in public_dimensions:
            dimensions.append({"id": f"tags.{dimension}", "name": dimension})

        metric_detail = {
            "result_table_id": "strategy",
            "result_table_name": "",
            "result_table_label": strategy.scenario,
            "result_table_label_name": self.get_label_name(strategy.scenario),
            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
            "data_type_label": DataTypeLabel.ALERT,
            "bk_biz_id": strategy.bk_biz_id,
            "data_target": DataTarget.NONE_TARGET,
            "collect_config_ids": [],
            "default_dimensions": [dimension["id"] for dimension in dimensions],
            "default_condition": [],
            "metric_field": str(strategy.id),
            "metric_field_name": strategy.name,
            "dimensions": dimensions,
            "extend_fields": {},
        }

        yield metric_detail

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list[int]:
        """获取有监控策略的业务ID列表"""
        businesses: list[Space] = SpaceApi.list_spaces(bk_tenant_id=bk_tenant_id)
        # 只处理有策略的业务
        biz_ids = list(StrategyModel.objects.values_list("bk_biz_id", flat=True).distinct())
        # 默认只刷新bkcc业务，其他业务引导用户自行触发刷新
        return [
            business.bk_biz_id for business in businesses if business.bk_biz_id in biz_ids and business.bk_biz_id > 0
        ]


class BkFtaAlertCacheManager(BaseMetricCacheManager):
    """
    批量缓存告警源事件
    """

    data_sources = (
        (DataSourceLabel.BK_FTA, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_FTA, DataTypeLabel.ALERT),
    )

    def search_alerts(self):
        search = AlertDocument.search(all_indices=True).exclude("exists", field="strategy_id")

        if self.bk_biz_id:
            search = search.filter("term", **{"event.bk_biz_id": self.bk_biz_id})

        search.aggs.bucket("alert_name", "terms", field="alert_name.raw", size=1000).bucket(
            "plugins", "terms", field="event.plugin_id"
        ).bucket("target_type", "terms", field="event.target_type").bucket("tags", "nested", path="event.tags").bucket(
            "key", "terms", field="event.tags.key", size=1000
        )

        search_result = search[:0].execute()

        alert_tags = defaultdict(set)
        alert_target_types = defaultdict(set)
        alert_plugins = defaultdict(set)
        if search_result.aggs:
            for alert_bucket in search_result.aggs.alert_name.buckets:
                for plugin_bucket in alert_bucket.plugins:
                    alert_plugins[alert_bucket.key].add(plugin_bucket.key)
                    for target_bucket in plugin_bucket.target_type:
                        alert_target_types[alert_bucket.key].add(target_bucket.key)
                        for tag_bucket in target_bucket.tags.key.buckets:
                            if tag_bucket.key not in IGNORED_TAGS:
                                alert_tags[alert_bucket.key].add(tag_bucket.key)
        return {"alert_tags": alert_tags, "alert_target_types": alert_target_types, "alert_plugins": alert_plugins}

    def get_config_tables(self, bk_biz_id):
        """获取系统内置的告警配置表信息"""
        tables = defaultdict()
        plugins = EventPluginV2.objects.filter(bk_biz_id=bk_biz_id)
        plugin_names = {plugin.plugin_id: plugin.plugin_display_name for plugin in plugins}

        alert_names = set()

        for alert_config in AlertConfig.objects.filter(plugin_id__in=list(plugins.values_list("plugin_id", flat=True))):
            alert_names.add(alert_config.name)

            if alert_config.name in tables:
                tables[alert_config.name]["plugin_ids"].add(alert_config.plugin_id)
            else:
                table = {
                    "dimensions": [],
                    "plugin_ids": {alert_config.plugin_id},
                    "target_type": DataTarget.HOST_TARGET,
                    "result_table_label": OthersResultTableLabel.other_rt,
                    "bk_biz_id": bk_biz_id,
                    "alert_name_alias": f"[{plugin_names[alert_config.plugin_id]}] {alert_config.name}",
                }
                tables[alert_config.name] = table
        return tables

    def get_tables(self):
        tables = default_tables = self.get_config_tables(bk_biz_id=0)
        if self.bk_biz_id:
            tables = self.get_config_tables(bk_biz_id=self.bk_biz_id)
        else:
            tables[ALL_EVENT_PLUGIN_METRIC] = {
                "dimensions": [],
                "plugin_ids": set(),
                "target_type": DataTarget.HOST_TARGET,
                "result_table_label": OthersResultTableLabel.other_rt,
                "bk_biz_id": 0,
                "alert_name_alias": "ALL EVENT PLUGIN",
            }
            plugins = EventPluginV2.objects.filter(bk_biz_id=0)
            for plugin in plugins:
                tables[f"{EVENT_PLUGIN_METRIC_PREFIX}{plugin.plugin_id}"] = {
                    "dimensions": [],
                    "plugin_ids": {plugin.plugin_id},
                    "target_type": DataTarget.HOST_TARGET,
                    "result_table_label": OthersResultTableLabel.other_rt,
                    "bk_biz_id": 0,
                    "alert_name_alias": f"[{plugin.plugin_display_name}] ALL EVENT",
                }

        alerts_info = self.search_alerts()
        alert_tags = alerts_info["alert_tags"]
        alert_target_types = alerts_info["alert_target_types"]
        alert_plugins = alerts_info["alert_plugins"]

        for alert_name, tags in alert_tags.items():
            target_type = (
                list(alert_target_types[alert_name])[0] if alert_target_types[alert_name] else EventTargetType.HOST
            )
            target_type = f"{target_type.lower()}_target"

            dimensions = [
                {"id": "ip", "name": _("目标IP")},
                {"id": "bk_cloud_id", "name": _("云区域ID")},
            ]

            if target_type == DataTarget.SERVICE_TARGET:
                dimensions = [
                    {"id": "bk_service_instance_id", "name": _("目标服务实例ID")},
                ]

            if alert_name in default_tables and self.bk_biz_id:
                # 当告警名称为默认配置的，不做新增
                continue

            if alert_name in tables:
                # 告警名称原本属于当前业务，直接更新
                table = tables[alert_name]
                table["target_type"] = target_type
                table["plugin_ids"].update(alert_plugins[alert_name])
            elif self.bk_biz_id:
                # 不存在的时候，且具体业务自动发现的情况下，则新增
                table = {
                    "dimensions": [],
                    "plugin_ids": alert_plugins[alert_name],
                    "target_type": target_type,
                    "result_table_label": OthersResultTableLabel.other_rt,
                    "bk_biz_id": self.bk_biz_id,
                }
                tables[alert_name] = table
            else:
                continue
            table["dimensions"].extend([{"id": f"tags.{tag}", "name": tag} for tag in tags])
            table["dimensions"] += dimensions

        alerts = []
        for alert_name, table in tables.items():
            new_dimensions = []
            all_dimensions = [
                {"id": "ip", "name": _("目标IP"), "is_dimension": True},
                {"id": "bk_cloud_id", "name": _("云区域ID"), "is_dimension": True},
                {"id": "description", "name": _("事件描述"), "is_dimension": False},
            ] + table["dimensions"]
            exist_keys = set()
            for d in all_dimensions:
                if d["id"] not in exist_keys:
                    new_dimensions.append(d)
                    # 对相同维度去重
                    exist_keys.add(d["id"])

            alerts.append(
                {
                    "alert_name": alert_name,
                    "dimensions": new_dimensions,
                    "plugin_ids": list(table["plugin_ids"]),
                    "target_type": table["target_type"],
                    "result_table_label": table["result_table_label"],
                    "bk_biz_id": self.bk_biz_id,
                    "alert_name_alias": table.get("alert_name_alias", alert_name),
                }
            )

        yield from alerts

    def get_metrics_by_table(self, table):
        # 将自愈告警处理成缓存表信息
        for data_type_label in [DataTypeLabel.ALERT, DataTypeLabel.EVENT]:
            metric_detail = {
                "result_table_id": data_type_label,
                "result_table_name": "",
                "result_table_label": table["result_table_label"],
                "result_table_label_name": self.get_label_name(table["result_table_label"]),
                "data_source_label": DataSourceLabel.BK_FTA,
                "data_type_label": data_type_label,
                "bk_biz_id": table["bk_biz_id"],
                "data_target": table["target_type"],
                "collect_config_ids": [],
                "default_dimensions": [],
                "default_condition": [],
                "metric_field": table["alert_name"],
                "metric_field_name": table.get("alert_name_alias", table["alert_name"]),
                "dimensions": table["dimensions"],
                "extend_fields": {
                    "plugin_ids": table["plugin_ids"],
                },
            }

            yield metric_detail

    @classmethod
    def get_available_biz_ids(cls, bk_tenant_id: str) -> list[int]:
        """
        获取有第三方告警事件的业务ID列表

        返回:
        1. 从告警文档(ES)中提取的有第三方告警的业务ID(大于0)
        2. 业务ID 0(用于系统级告警事件)
        """
        biz_ids = []
        # 排除有策略ID的告警，只统计第三方告警
        search = AlertDocument.search(all_indices=True).exclude("exists", field="strategy_id")
        # 计算每个业务ID出现的文档数量
        search.aggs.bucket("biz_ids", "terms", field="event.bk_biz_id", size=1000)
        search_result = search[:0].execute()
        # 从聚合结果中抽取biz_id
        if search_result.aggs:
            biz_ids = [int(bucket.key) for bucket in search_result.aggs.biz_ids.buckets]

        # 默认只刷新bkcc业务，其他业务引导用户自行触发刷新
        result = [biz_id for biz_id in biz_ids if biz_id > 0]

        # 总是添加业务ID为0，用于系统级告警事件
        if 0 not in result:
            result.append(0)

        return result


# 当前支持的数据来源（监控、计算平台、系统事件）
SOURCE_TYPE: dict[str, type[BaseMetricCacheManager]] = {
    # 按业务，并补0业务
    "BKMONITOR": BkmonitorMetricCacheManager,
    "BKMONITORK8S": BkmonitorK8sMetricCacheManager,
    "CUSTOMEVENT": CustomEventCacheManager,
    "CUSTOMTIMESERIES": CustomMetricCacheManager,
    "BKFTAALERT": BkFtaAlertCacheManager,
    # 按业务
    "BKDATA": BkdataMetricCacheManager,
    "LOGTIMESERIES": BkLogSearchCacheManager,
    "BKMONITORALERT": BkMonitorAlertCacheManager,
    # 全业务
    "BASEALARM": BaseAlarmMetricCacheManager,
    "BKMONITORLOG": BkMonitorLogCacheManager,
}
