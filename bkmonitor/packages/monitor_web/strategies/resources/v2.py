import datetime
import logging
import operator
import re
import time
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import reduce
from itertools import chain, product, zip_longest
from typing import Any

import arrow
import pytz
from django.conf import settings
from django.db import close_old_connections
from django.db.models import Count, ExpressionWrapper, F, Q, QuerySet, fields
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.cmdb.define import Host, Module, Set, TopoTree
from bkm_ipchooser.handlers import template_handler
from bkmonitor.action.utils import get_strategy_user_group_dict
from bkmonitor.aiops.utils import AiSetting
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import Functions, UnifyQuery, load_data_source
from bkmonitor.dataflow.constant import (
    AI_SETTING_ALGORITHMS,
    AccessStatus,
)
from bkmonitor.dataflow.flow import DataFlow
from bkmonitor.documents import AlertDocument
from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.permission import Permission
from bkmonitor.models import (
    ActionConfig,
    ActionSignal,
    AlgorithmModel,
    DetectModel,
    ItemModel,
    MetricListCache,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyHistoryModel,
    StrategyLabel,
    StrategyModel,
    UserGroup,
)
from bkmonitor.models.strategy import AlgorithmChoiceConfig
from bkmonitor.strategy.new_strategy import (
    ActionRelation,
    Algorithm,
    NoticeRelation,
    QueryConfig,
    Strategy,
    get_metric_id,
    parse_metric_id,
)
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.request import get_request_tenant_id, get_request_username, get_source_app
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.time_format import duration_string, parse_duration
from bkmonitor.utils.user import get_global_user
from constants.aiops import SDKDetectStatus
from constants.alert import EventStatus
from constants.cmdb import TargetNodeType, TargetObjectType
from constants.common import SourceApp
from constants.data_source import DATA_CATEGORY, DataSourceLabel, DataTypeLabel
from constants.strategy import SPLIT_DIMENSIONS, DataTarget, TargetFieldType
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.drf_resource.contrib.cache import CacheResource
from core.errors.bkmonitor.data_source import CmdbLevelValidateError
from core.errors.strategy import StrategyNameExist
from monitor.models import ApplicationConfig
from monitor_web.models import (
    CollectorPluginMeta,
    CustomEventGroup,
    CustomTSTable,
    DataTargetMapping,
)
from monitor_web.shield.utils import ShieldDetectManager
from monitor_web.strategies.constant import (
    DEFAULT_TRIGGER_CONFIG_MAP,
    GLOBAL_TRIGGER_CONFIG,
)
from monitor_web.strategies.serializers import handle_target
from monitor_web.tasks import update_metric_list_by_biz

logger = logging.getLogger(__name__)


def db_safe_wrapper(func):
    """数据库连接安全装饰器"""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            close_old_connections()

    return wrapper


class GetStrategyListV2Resource(Resource):
    """
    获取策略列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        scenario = serializers.CharField(required=False, label="监控场景")
        conditions = serializers.ListField(required=False, child=serializers.DictField(), default=[], label="条件")
        page = serializers.IntegerField(required=False, default=1, label="页数")
        page_size = serializers.IntegerField(required=False, default=10, label="每页数量")
        with_user_group = serializers.BooleanField(default=False, label="是否补充告警组信息")
        with_user_group_detail = serializers.BooleanField(required=False, default=False, label="补充告警组详细信息")
        convert_dashboard = serializers.BooleanField(required=False, default=True, label="是否转换仪表盘格式")

    @classmethod
    def filter_by_ip(cls, ips: list[dict], strategies: QuerySet, bk_biz_id: int = None) -> QuerySet:
        """
        查询监控范围包含ip的策略
        """
        # 全业务过滤暂不处理
        if bk_biz_id is None:
            return strategies

        # 根据场景和数据源过滤出有监控目标的策略
        strategy_ids = [
            s.id
            for s in strategies.filter(
                scenario__in=["os", "host_process", "service_module", "component", "service_process"]
            )
        ]

        strategy_ids = (
            QueryConfigModel.objects.filter(
                strategy_id__in=strategy_ids,
                data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            )
            .values_list("strategy_id", flat=True)
            .distinct()
        )

        # 查询Item信息
        items = ItemModel.objects.filter(strategy_id__in=strategy_ids)

        # 查询主机和拓扑树信息，构造拓扑链
        hosts: list[Host] = api.cmdb.get_host_by_ip(bk_biz_id=bk_biz_id, ips=ips)
        topo_tree: TopoTree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)
        topo_link = topo_tree.convert_to_topo_link()

        ips = set()
        topo_nodes: set[tuple[str, int]] = set()
        bk_module_ids = set()
        bk_set_ids = set()

        # 构造ip集合和节点集合
        for host in hosts:
            bk_module_ids.update(host.bk_module_ids)
            bk_set_ids.update(host.bk_set_ids)
            ips.add((host.ip, host.bk_cloud_id))

            for bk_module_id in host.bk_module_ids:
                for topo_node in topo_link.get(f"module|{bk_module_id}", []):
                    topo_nodes.add((topo_node.bk_obj_id, topo_node.bk_inst_id))

        # 根据主机集群ID查询集群模板
        if bk_set_ids:
            sets: list[Set] = api.cmdb.get_set(bk_biz_id=bk_biz_id, bk_set_ids=bk_set_ids)
            for _set in sets:
                topo_nodes.add(("SET_TEMPLATE", _set.set_template_id))

        # 根据主机模块ID查询服务模板
        if bk_module_ids:
            modules: list[Module] = api.cmdb.get_module(bk_biz_id=bk_biz_id, bk_module_ids=bk_module_ids)
            for module in modules:
                topo_nodes.add(("SERVICE_TEMPLATE", module.service_template_id))

        ip_strategy_ids = set()
        for item in items:
            # 如果没有监控目标，则监控全部主机
            if not item.target or not item.target[0]:
                ip_strategy_ids.add(item.strategy_id)
                continue

            target = item.target[0][0]
            # 通过节点或主机集合是否有交集判断该策略是否监控这些IP
            if target["field"] in ["ip", "bk_target_ip"]:
                target_ips = {
                    (
                        host.get("bk_target_ip") or host["ip"],
                        int(host.get("bk_target_cloud_id") or host.get("bk_cloud_id", 0)),
                    )
                    for host in target["value"]
                }
                if target_ips & ips:
                    ip_strategy_ids.add(item.strategy_id)

            elif target["field"].endswith("topo_node"):
                nodes = {(node["bk_obj_id"], node["bk_inst_id"]) for node in target["value"]}
                if nodes & topo_nodes:
                    ip_strategy_ids.add(item.strategy_id)

        return strategies.filter(id__in=ip_strategy_ids)

    @classmethod
    def filter_strategy_ids_by_id(cls, filter_dict: dict, filter_strategy_ids_set: set):
        """过滤策略ID"""
        if filter_dict["id"]:
            ids = set()
            for _id in filter_dict["id"]:
                try:
                    ids.add(int(_id))
                except (ValueError, TypeError):
                    # 无效的过滤条件，查不出数据
                    continue
            filter_strategy_ids_set.intersection_update(ids)

    @classmethod
    def filter_strategy_ids_by_label(
        cls, filter_dict: dict, filter_strategy_ids_set: set, bk_biz_id: str | None = None
    ):
        """过滤策略标签"""
        if filter_dict["label"]:
            labels = [f"/{label.strip('/')}/" for label in filter_dict["label"]]
            strategy_label_qs = StrategyLabel.objects.filter(label_name__in=labels)
            if bk_biz_id is not None:
                strategy_label_qs = strategy_label_qs.filter(bk_biz_id=bk_biz_id)
            label_strategy_ids = strategy_label_qs.values_list("strategy_id", flat=True).distinct()
            filter_strategy_ids_set.intersection_update(set(label_strategy_ids))

    @classmethod
    def filter_strategy_ids_by_data_source(cls, filter_dict: dict, filter_strategy_ids_set: set):
        """过滤数据源"""
        if filter_dict["data_source"]:
            data_sources: list[tuple] = []
            for data_source in filter_dict["data_source"]:
                for category in DATA_CATEGORY:
                    if data_source != category["type"]:
                        continue
                    data_sources.append((category["data_source_label"], category["data_type_label"]))
                    break
            if not data_sources:
                filter_strategy_ids_set.intersection_update(set())
            else:
                data_source_strategy_ids = (
                    QueryConfigModel.objects.filter(
                        reduce(
                            lambda x, y: x | y, [Q(data_source_label=ds, data_type_label=dt) for ds, dt in data_sources]
                        ),
                        strategy_id__in=filter_strategy_ids_set,
                    )
                    .values_list("strategy_id", flat=True)
                    .distinct()
                )
                filter_strategy_ids_set.intersection_update(set(data_source_strategy_ids))

    @classmethod
    def filter_strategy_ids_by_result_table(cls, filter_dict: dict, filter_strategy_ids_set: set):
        """过滤结果表"""
        if filter_dict["result_table_id"]:
            result_table_id_strategy_ids = []
            for result_table_id in filter_dict["result_table_id"]:
                result_table_id_strategy_ids.extend(
                    list(
                        QueryConfigModel.objects.filter(config__result_table_id=result_table_id)
                        .values_list("strategy_id", flat=True)
                        .distinct()
                    )
                )
            filter_strategy_ids_set.intersection_update(set(result_table_id_strategy_ids))

    @classmethod
    def filter_strategy_ids_by_status(
        cls, filter_dict: dict, filter_strategy_ids_set: set, bk_biz_id: str | None = None
    ):
        """策略状态过滤"""
        if filter_dict["strategy_status"]:
            strategy_status_ids = []
            for status in filter_dict["strategy_status"]:
                filter_status_params = {"status": status}
                if bk_biz_id is not None:
                    filter_status_params["bk_biz_id"] = bk_biz_id

                strategy_status_ids.extend(cls.filter_by_status(**filter_status_params))
            filter_strategy_ids_set.intersection_update(set(strategy_status_ids))

    @classmethod
    def filter_strategy_ids_by_algo_type(cls, filter_dict: dict, filter_strategy_ids_set: set):
        """算法类型过滤"""
        if filter_dict["algorithm_type"]:
            algorithm_strategy_ids = (
                AlgorithmModel.objects.filter(
                    type__in=filter_dict["algorithm_type"], strategy_id__in=filter_strategy_ids_set
                )
                .values_list("strategy_id", flat=True)
                .distinct()
            )
            filter_strategy_ids_set.intersection_update(set(algorithm_strategy_ids))

    @classmethod
    def filter_strategy_ids_by_invalid_type(cls, filter_dict: dict, filter_strategy_ids_set: set):
        """失效类型过滤"""
        if filter_dict["invalid_type"]:
            algorithm_strategy_ids = (
                StrategyModel.objects.filter(
                    invalid_type__in=filter_dict["invalid_type"], id__in=filter_strategy_ids_set
                )
                .values_list("id", flat=True)
                .distinct()
            )
            filter_strategy_ids_set.intersection_update(set(algorithm_strategy_ids))

    @classmethod
    def filter_strategy_ids_by_event_group(
        cls, filter_dict: dict, filter_strategy_ids_set: set, bk_biz_id: str | None = None
    ):
        """过滤自定义事件组ID"""
        if filter_dict["custom_event_group_id"] or filter_dict["bk_event_group_id"]:
            event_group_id = filter_dict["custom_event_group_id"] or filter_dict["bk_event_group_id"]
            custom_event_qs = CustomEventGroup.objects.filter(bk_event_group_id__in=event_group_id)
            if bk_biz_id is not None:
                custom_event_qs = custom_event_qs.filter(bk_biz_id=bk_biz_id)
            custom_event_table_ids = custom_event_qs.values_list("table_id", flat=True)
            custom_event_strategy_ids = []
            if custom_event_table_ids:
                custom_event_strategy_ids = set(
                    QueryConfigModel.objects.filter(
                        reduce(
                            lambda x, y: x | y,
                            (Q(config__result_table_id=table_id) for table_id in custom_event_table_ids),
                        )
                        if len(custom_event_table_ids) > 1
                        else Q(config__result_table_id=custom_event_table_ids[0]),
                        data_source_label=DataSourceLabel.CUSTOM,
                        data_type_label=DataTypeLabel.EVENT,
                    )
                    .values_list("strategy_id", flat=True)
                    .distinct()
                )
            filter_strategy_ids_set.intersection_update(set(custom_event_strategy_ids))

    @classmethod
    def filter_strategy_ids_by_series_group(
        cls, filter_dict: dict, filter_strategy_ids_set: set, bk_biz_id: str | None = None
    ):
        """过滤自定义指标ID"""
        if filter_dict["time_series_group_id"]:
            time_series_group_id = filter_dict["time_series_group_id"]
            custom_ts_qs = CustomTSTable.objects.filter(time_series_group_id__in=time_series_group_id)
            if bk_biz_id is not None:
                custom_ts_qs = custom_ts_qs.filter(bk_biz_id=bk_biz_id)
            custom_metric_table_ids = custom_ts_qs.values_list("table_id", flat=True)

            custom_metric_strategy_ids = []
            if custom_metric_table_ids:
                custom_metric_strategy_ids = set(
                    QueryConfigModel.objects.filter(
                        reduce(
                            lambda x, y: x | y,
                            (Q(config__result_table_id=table_id) for table_id in custom_metric_table_ids),
                        )
                        if len(custom_metric_table_ids) > 1
                        else Q(config__result_table_id=custom_metric_table_ids[0]),
                        data_source_label=DataSourceLabel.CUSTOM,
                        data_type_label=DataTypeLabel.TIME_SERIES,
                    )
                    .values_list("strategy_id", flat=True)
                    .distinct()
                )
            filter_strategy_ids_set.intersection_update(set(custom_metric_strategy_ids))

    @classmethod
    def filter_strategy_ids_by_plugin_id(
        cls, filter_dict: dict, filter_strategy_ids_set: set, bk_biz_id: str | None = None
    ):
        # 无业务id，不支持搜索(RequestSerializer 明确bk_biz_id 必填)
        if not bk_biz_id:
            return

        # 过滤插件ID
        if filter_dict["plugin_id"]:
            plugin_id = filter_dict["plugin_id"]
            plugins = CollectorPluginMeta.objects.filter(
                bk_tenant_id=get_request_tenant_id(), plugin_id__in=plugin_id, bk_biz_id__in=[0, bk_biz_id]
            ).values("plugin_id")

            plugin_strategy_ids = []
            query_configs = QueryConfigModel.objects.filter(strategy_id__in=filter_strategy_ids_set).only(
                "config", "strategy_id"
            )
            for qc in query_configs:
                for plugin in plugins:
                    if f"{plugin['plugin_id']}." in qc.config.get("result_table_id", ""):
                        plugin_strategy_ids.append(qc.strategy_id)
                        break

            filter_strategy_ids_set.intersection_update(set(plugin_strategy_ids))

    @classmethod
    def filter_strategy_ids_by_metric_id(cls, filter_dict: dict, filter_strategy_ids_set: set):
        """过滤指标ID"""
        if filter_dict["metric_id"]:
            metric_strategy_ids = set(
                QueryConfigModel.objects.filter(
                    metric_id__in=filter_dict["metric_id"], strategy_id__in=filter_strategy_ids_set
                )
                .values_list("strategy_id", flat=True)
                .distinct()
            )
            filter_strategy_ids_set.intersection_update(metric_strategy_ids)

    @classmethod
    def filter_strategy_ids_by_uct_id(cls, filter_dict: dict, filter_strategy_ids_set: set):
        """过滤拨测任务ID"""
        if filter_dict["uptime_check_task_id"]:
            filter_dict["uptime_check_task_id"] = [str(task_id) for task_id in filter_dict["uptime_check_task_id"]]
            uptime_check_query_configs = QueryConfigModel.objects.filter(
                metric_id__startswith="bk_monitor.uptimecheck.", strategy_id__in=filter_strategy_ids_set
            )

            uptime_check_strategy_ids = set()
            for query_config in uptime_check_query_configs:
                agg_conditions = query_config.config.get("agg_condition", [])
                for agg_condition in agg_conditions:
                    if agg_condition["key"] == "task_id" and agg_condition["method"] == "eq":
                        value = agg_condition["value"]
                        if not isinstance(value, list):
                            value = [value]
                        value = {str(v) for v in value}

                        if value & set(filter_dict["uptime_check_task_id"]):
                            uptime_check_strategy_ids.add(query_config.strategy_id)

            filter_strategy_ids_set.intersection_update(uptime_check_strategy_ids)

    @classmethod
    def filter_strategy_ids_by_level(cls, filter_dict: dict, filter_strategy_ids_set: set):
        """过滤告警级别"""
        if filter_dict["level"]:
            level_strategy_ids = DetectModel.objects.filter(
                strategy_id__in=filter_strategy_ids_set, level__in=filter_dict["level"]
            ).values_list("strategy_id", flat=True)
            filter_strategy_ids_set.intersection_update(set(level_strategy_ids))

    @classmethod
    def filter_strategy_ids_by_source(cls, filter_dict: dict[str, list], filter_strategy_ids_set: set) -> None:
        """过滤来源"""
        source_field: str | None = None
        for key in filter_dict.keys():
            fields = key.split("__")
            if "source" == fields[0]:
                source_field = key
                break

        if not source_field:
            return

        source_strategy_ids = StrategyModel.objects.filter(id__in=filter_strategy_ids_set)
        if len(fields) == 1 or fields[1] == "in":
            source_strategy_ids = source_strategy_ids.filter(source__in=filter_dict[source_field])

        elif fields[1] == "neq":
            source_strategy_ids = source_strategy_ids.exclude(source__in=filter_dict[source_field])
        else:
            # 暂不支持其他的操作
            filter_strategy_ids_set.intersection_update(set())
            return

        filter_strategy_ids_set.intersection_update(set(source_strategy_ids.values_list("id", flat=True).distinct()))

    @classmethod
    def filter_by_conditions(cls, conditions: list[dict], strategies: QuerySet, bk_biz_id: int = None) -> QuerySet:
        """
        按条件进行过滤
        - id: 策略ID
        - name: 策略名称
        - user_group_id: 通知组ID
        - user_group_name: 通知组名
        - create_user: 创建者
        - update_user: 更新这
        - strategy_status: 状态
        - algorithm_type: 算法类型
        - invalid_type: 失效类型
        - uptime_check_task_id: 拨测任务ID
        - metric_field: 指标
        - metric_field_name: 指标名称
        - custom_event_group_id: 自定义事件ID
        - data_source: 数据源
        - scenario：监控场景
        - label: 监控标签
        - query: 关键字查询
        - ip: IP地址
        - bk_cloud_id: 云区域
        - result_table_id:结果表
        """

        field_mapping = {
            "strategy_id": "id",
            "strategy_name": "name",
            "task_id": "uptime_check_task_id",
            "metric_alias": "metric_field_name",
            "metric_name": "metric_field",
            "creators": "create_user",
            "updaters": "update_user",
            "data_source_list": "data_source",
            "label_name": "label",
        }

        filter_dict = defaultdict(list)
        for condition in conditions:
            key = condition["key"].lower()
            key = field_mapping.get(key, key)
            value = condition["value"]
            if not isinstance(value, list):
                value = [value]
            if len(value) == 1:
                # 默认按list传递，多个值用 | 分割
                value = [i.strip() for i in str(value[0]).split(" | ") if i.strip()]
            filter_dict[key].extend(value)

        filter_strategy_ids_set = set(strategies.values_list("id", flat=True).distinct())

        filter_methods: list[tuple] = [
            (cls.filter_strategy_ids_by_id, (filter_dict, filter_strategy_ids_set)),
            (cls.filter_strategy_ids_by_label, (filter_dict, filter_strategy_ids_set, bk_biz_id)),
            (cls.filter_strategy_ids_by_data_source, (filter_dict, filter_strategy_ids_set)),
            (cls.filter_strategy_ids_by_result_table, (filter_dict, filter_strategy_ids_set)),
            (cls.filter_strategy_ids_by_status, (filter_dict, filter_strategy_ids_set, bk_biz_id)),
            (cls.filter_strategy_ids_by_algo_type, (filter_dict, filter_strategy_ids_set)),
            (cls.filter_strategy_ids_by_invalid_type, (filter_dict, filter_strategy_ids_set)),
            (cls.filter_by_user_groups, (filter_dict, filter_strategy_ids_set, bk_biz_id)),
            (cls.filter_by_action, (filter_dict, filter_strategy_ids_set, bk_biz_id)),
            (cls.filter_by_metric_field, (filter_dict, filter_strategy_ids_set, bk_biz_id)),
            (cls.filter_strategy_ids_by_event_group, (filter_dict, filter_strategy_ids_set, bk_biz_id)),
            (cls.filter_strategy_ids_by_series_group, (filter_dict, filter_strategy_ids_set, bk_biz_id)),
            (cls.filter_strategy_ids_by_plugin_id, (filter_dict, filter_strategy_ids_set, bk_biz_id)),
            (cls.filter_strategy_ids_by_metric_id, (filter_dict, filter_strategy_ids_set)),
            (cls.filter_strategy_ids_by_uct_id, (filter_dict, filter_strategy_ids_set)),
            (cls.filter_strategy_ids_by_level, (filter_dict, filter_strategy_ids_set)),
            (cls.filter_strategy_ids_by_source, (filter_dict, filter_strategy_ids_set)),
        ]
        for filter_method, args in filter_methods:
            filter_method(*args)
            if not filter_strategy_ids_set:
                return strategies.none()
        strategies = strategies.filter(id__in=filter_strategy_ids_set)

        # 过滤创建人
        if filter_dict["create_user"]:
            strategies = strategies.filter(create_user__in=filter_dict["create_user"])

        # 过滤修改人
        if filter_dict["update_user"]:
            strategies = strategies.filter(update_user__in=filter_dict["update_user"])

        # 关键字搜索
        if filter_dict["query"]:
            q = []
            result_table_id_strategy_ids = []
            for query in filter_dict["query"]:
                q.append(Q(name__icontains=query))
                try:
                    q.append(Q(id__icontains=int(query)))
                except (ValueError, TypeError):
                    pass
                try:
                    result_table_id_strategy_ids.extend(
                        list(
                            QueryConfigModel.objects.filter(
                                config__result_table_id=query, strategy_id__in=filter_strategy_ids_set
                            )
                            .values_list("strategy_id", flat=True)
                            .distinct()
                        )
                    )
                except (ValueError, TypeError):
                    pass
            if result_table_id_strategy_ids:
                q.append(Q(id__in=set(result_table_id_strategy_ids)))

            strategies = strategies.filter(reduce(lambda x, y: x | y, q))

        # 策略名称搜索
        if filter_dict["name"]:
            q = []
            for name in filter_dict["name"]:
                q.append(Q(name__icontains=name))
            strategies = strategies.filter(reduce(lambda x, y: x | y, q))

        # 按监控目标过滤主机
        if filter_dict["ip"]:
            ips = []
            if filter_dict["bk_cloud_id"]:
                for ip, bk_cloud_id in product(filter_dict["ip"], filter_dict["bk_cloud_id"]):
                    ips.append({"ip": ip, "bk_cloud_id": bk_cloud_id})
            else:
                ips = [{"ip": ip for ip in filter_dict["ip"]}]
            filter_ip_params = {"ips": ips, "strategies": strategies}
            if bk_biz_id is not None:
                filter_ip_params["bk_biz_id"] = bk_biz_id
            strategies = cls.filter_by_ip(**filter_ip_params)

        return strategies

    @staticmethod
    def filter_by_metric_field(filter_dict, filter_strategy_ids_set: set, bk_biz_id: int = None):
        """
        指标相关的过滤
        """
        # 过滤指标别名
        if filter_dict["metric_field_name"]:
            metric_qs = MetricListCache.objects.filter(
                bk_tenant_id=get_request_tenant_id(), metric_field_name__in=filter_dict["metric_field_name"]
            )
            if bk_biz_id is not None:
                metric_qs = metric_qs.filter(bk_biz_id__in=[0, bk_biz_id])
            metric_fields = metric_qs.values_list("metric_field", flat=True).distinct()
            filter_dict["metric_field"] = (
                list(set(filter_dict["metric_field"]) & set(metric_fields))
                if filter_dict["metric_fields"]
                else metric_fields
            )

        if not filter_dict["metric_field"]:
            return

        metric_strategy_ids = set(
            QueryConfigModel.objects.filter(
                reduce(
                    lambda x, y: x | y,
                    (Q(config__metric_field=metric_field) for metric_field in filter_dict["metric_field"]),
                )
            )
            .values_list("strategy_id", flat=True)
            .distinct()
        )

        filter_strategy_ids_set.intersection_update(metric_strategy_ids)

    @staticmethod
    def filter_by_user_groups(filter_dict, filter_strategy_ids_set: set, bk_biz_id: int = None):
        """
        根据告警组信息查询策略
        """
        if not filter_dict.get("user_group_id") and not filter_dict.get("user_group_name"):
            return

        filter_user_group_ids = filter_dict.get("user_group_id", [])
        if filter_dict["user_group_name"]:
            user_group_qs = UserGroup.objects.filter(
                reduce(operator.or_, (Q(**{"name__contains": name}) for name in filter_dict["user_group_name"])),
            )
            if bk_biz_id is not None:
                user_group_qs = user_group_qs.filter(bk_biz_id=bk_biz_id)
            filter_user_group_ids.extend(user_group_qs.values_list("id", flat=True))

        if not filter_user_group_ids:
            filter_strategy_ids_set.intersection_update(set())
            return

        or_condition = reduce(
            operator.or_, (Q(**{"user_groups__contains": group_id}) for group_id in set(filter_user_group_ids))
        )

        user_group_strategy_ids = set(
            StrategyActionConfigRelation.objects.filter(or_condition).values_list("strategy_id", flat=True).distinct()
        )
        filter_strategy_ids_set.intersection_update(user_group_strategy_ids)

    @staticmethod
    def filter_by_action(filter_dict, filter_strategy_ids_set: set, bk_biz_id: int = None):
        if "action_name" not in filter_dict and "action_id" not in filter_dict:
            return

        filter_strategy_ids = set()

        if 0 in filter_dict.get("action_id", []) or "" in filter_dict.get("action_name", []):
            # 如果 action_name 是个空列表，那么就检索出没有配置处理套餐的策略
            # 先找出这个业务所有的策略
            strategy_qs = StrategyModel.objects.all()
            if bk_biz_id is not None:
                strategy_qs = strategy_qs.filter(bk_biz_id=bk_biz_id)
                strategy_ids = strategy_qs.values_list("id", flat=True)
                # 再找出关联了处理动作的策略
                strategy_ids_with_action = StrategyActionConfigRelation.objects.filter(
                    strategy_id__in=strategy_ids,
                    relate_type=StrategyActionConfigRelation.RelateType.ACTION,
                ).values_list("strategy_id", flat=True)
            else:
                strategy_ids = strategy_qs.values_list("id", flat=True)
                strategy_ids_with_action = StrategyActionConfigRelation.objects.filter(
                    relate_type=StrategyActionConfigRelation.RelateType.ACTION,
                ).values_list("strategy_id", flat=True)
            # 通过差集计算出没有关联处理动作的策略
            filter_strategy_ids = set(strategy_ids) - set(strategy_ids_with_action)

        action_qs = ActionConfig.objects.exclude(plugin_id=ActionConfig.NOTICE_PLUGIN_ID)
        if bk_biz_id is not None:
            action_qs = action_qs.filter(bk_biz_id__in=[0, bk_biz_id])
        action_ids = action_qs.values_list("id", flat=True)

        conditions = []
        if filter_dict.get("action_name"):
            conditions.extend(
                [Q(name__contains=action_name) for action_name in filter_dict["action_name"] if action_name]
            )
        if filter_dict.get("action_id"):
            conditions.extend([Q(id=action_id) for action_id in filter_dict["action_id"] if action_id])

        if not conditions:
            # 如果没有其他条件，则不需要处理
            if filter_strategy_ids:
                filter_strategy_ids_set.intersection_update(filter_strategy_ids)
            return

        action_ids = action_ids.filter(reduce(operator.or_, conditions))

        filter_strategy_ids_set.intersection_update(
            filter_strategy_ids
            | set(
                StrategyActionConfigRelation.objects.filter(config_id__in=list(action_ids))
                .values_list("strategy_id", flat=True)
                .distinct()
            )
        )

    @classmethod
    def filter_by_status(cls, status: str, filter_strategy_ids: list = None, bk_biz_id: int = None):
        strategy_ids = set()
        if status == "ALERT":
            # 告警中的策略
            strategy_ids.update(cls.get_strategies_by_shield_status(bk_biz_id))

        elif status == "INVALID":
            invalid_qs = StrategyModel.objects.filter(is_invalid=True)
            if bk_biz_id is not None:
                invalid_qs = invalid_qs.filter(bk_biz_id=bk_biz_id)
            strategy_ids.update(list(invalid_qs.values_list("id", flat=True).distinct()))

        elif status == "SHIELDED":
            shield_manager = ShieldDetectManager(bk_biz_id, "strategy")
            for shield_obj in shield_manager.shield_list:
                match_info = {"strategy_id": shield_obj.dimension_config["strategy_id"], "level": [1, 2, 3]}
                if shield_manager.is_shielded(shield_obj, match_info):
                    strategy_ids.update(shield_obj.dimension_config["strategy_id"])
            # 屏蔽中的策略
            strategy_ids.update(cls.get_strategies_by_shield_status(bk_biz_id, is_shielded=True))
        else:
            enabled_qs = StrategyModel.objects.filter(is_enabled=status == "ON")
            if bk_biz_id is not None:
                enabled_qs = enabled_qs.filter(bk_biz_id=bk_biz_id)
            strategy_ids.update(list(enabled_qs.values_list("id", flat=True).distinct()))

        if filter_strategy_ids is not None:
            return list(set(filter_strategy_ids) & strategy_ids)
        return list(strategy_ids)

    @staticmethod
    def get_strategies_by_shield_status(bk_biz_id, is_shielded=False):
        # 告警中的策略
        alert_qs = AlertDocument.search(all_indices=True).filter("term", status=EventStatus.ABNORMAL)
        if is_shielded:
            alert_qs = alert_qs.filter("term", is_shielded=True)
        else:
            # 屏蔽状态告警生成时未写入值，可能为null，用排除法比较好
            alert_qs = alert_qs.exclude("term", is_shielded=True)

        if bk_biz_id is not None:
            alert_qs = alert_qs.filter("term", **{"event.bk_biz_id": bk_biz_id})

        search_object = alert_qs[:0]
        search_object.aggs.bucket("strategy_id", "terms", field="strategy_id", size=10000)
        search_result = search_object.execute()
        strategy_ids = []
        if search_result.aggs:
            for bucket in search_result.aggs.strategy_id.buckets:
                strategy_ids.append(int(bucket.key))
        return strategy_ids

    @staticmethod
    def get_shield_info(filter_strategy_ids: list = None, bk_biz_id: int = None):
        shield_manager = ShieldDetectManager(bk_biz_id, "strategy")
        strategy_shield_info = defaultdict(dict)
        for strategy_id in filter_strategy_ids:
            match_info = {"strategy_id": strategy_id, "level": [1, 2, 3]}
            try:
                strategy_shield_info[strategy_id] = shield_manager.check_shield_status(match_info)
            except BaseException as error:
                logger.exception("get shield info for strategy_id(%s) failed, reason: %s ", strategy_id, str(error))
                strategy_shield_info[strategy_id] = {"is_shielded": False}
        return strategy_shield_info

    @staticmethod
    def get_user_group_list(strategy_ids: list[int], bk_biz_id: int):
        """
        按告警处理组统计策略数量
        """
        strategy_count_of_user_group = get_strategy_user_group_dict(strategy_ids)
        user_group_list = []
        for ug in UserGroup.objects.filter(bk_biz_id=bk_biz_id).only("id", "name"):
            user_group_list.append(
                {
                    "user_group_id": ug.id,
                    "user_group_name": ug.name,
                    "count": len(set(strategy_count_of_user_group.get(ug.id, []))),
                }
            )
        return user_group_list

    @staticmethod
    def get_alert_search_result(bk_biz_id, strategy_ids):
        search_object = (
            AlertDocument.search(all_indices=True)
            .filter("term", **{"event.bk_biz_id": bk_biz_id})
            .filter("term", status=EventStatus.ABNORMAL)
            .filter("terms", strategy_id=strategy_ids)[:0]
        )
        # 构建ES聚合查询
        # 按strategy_id分桶,size=10000表示最多返回10000个桶
        # 每个strategy_id桶下再按is_shielded字段分桶,统计屏蔽和未屏蔽的告警数量
        search_object.aggs.bucket("strategy_id", "terms", field="strategy_id", size=10000).bucket(
            "shield_status", "terms", field="is_shielded", size=10000
        )
        search_result = search_object.execute()
        return search_result

    @staticmethod
    def get_action_config_list(strategy_ids: list[int], bk_biz_id: int):
        """
        按告警处理组统计策略数量
        """
        action_relations = StrategyActionConfigRelation.objects.filter(
            strategy_id__in=strategy_ids,
            relate_type=StrategyActionConfigRelation.RelateType.ACTION,
        ).values("strategy_id", "config_id")

        no_config_strategy = set(strategy_ids)
        config_count = defaultdict(set)
        for relation in action_relations:
            config_count[relation["config_id"]].add(relation["strategy_id"])
            no_config_strategy.discard(relation["strategy_id"])

        action_config_list = [
            {
                "id": 0,
                "name": _("- 未配置 -"),
                "count": len(no_config_strategy),
            }
        ]
        for action_config in (
            ActionConfig.objects.filter(bk_biz_id__in=[0, bk_biz_id])
            .exclude(plugin_id=ActionConfig.NOTICE_PLUGIN_ID)
            .values("id", "name")
        ):
            action_config_list.append(
                {
                    "id": action_config["id"],
                    "name": action_config["name"],
                    "count": len(config_count[action_config["id"]]),
                }
            )

        return action_config_list

    def get_data_source_list(self, strategy_ids: list[int]):
        """
        按数据源统计策略数量
        """
        data_source_list = []
        count_records = (
            QueryConfigModel.objects.filter(strategy_id__in=strategy_ids)
            .values("data_source_label", "data_type_label")
            .annotate(total=Count("strategy_id", distinct=True))
            .order_by("data_source_label", "data_type_label")
        )

        data_source_counts = {
            (record["data_source_label"], record["data_type_label"]): record["total"] for record in count_records
        }

        for ds in DATA_CATEGORY:
            data_source_list.append(
                {
                    "type": ds["type"],
                    "name": str(ds["name"]),
                    "data_type_label": ds["data_type_label"],
                    "data_source_label": ds["data_source_label"],
                    "count": data_source_counts.get((ds["data_source_label"], ds["data_type_label"]), 0),
                }
            )

        return data_source_list

    def get_strategy_label_list(self, strategy_ids: list[int], bk_biz_id):
        """
        按策略标签统计策略数量
        """

        # 按策略标签进行聚合统计
        count_records = (
            StrategyLabel.objects.filter(strategy_id__in=strategy_ids)
            .values("label_name")
            .annotate(total=Count("strategy_id", distinct=True))
            .order_by("label_name")
        )

        label_counts = {record["label_name"]: record["total"] for record in count_records}

        # 查询业务下所有的策略标签
        labels = (
            StrategyLabel.objects.filter(bk_biz_id__in=[0, bk_biz_id]).values_list("label_name", flat=True).distinct()
        )

        return [{"label_name": label.strip("/"), "id": label, "count": label_counts.get(label, 0)} for label in labels]

    def get_scenario_list(self, strategies: QuerySet):
        """
        按监控对象统计策略数量
        """
        # 按监控对象统计数量
        scenarios = strategies.values("scenario").annotate(count=Count("scenario"))

        scenario_list = []
        try:
            labels = resource.commons.get_label()
        except Exception as e:
            logger.exception(e)
            # 如果拉取标签信息报错，则直接使用监控对象ID展示
            for scenario in scenarios:
                scenario_list.append(
                    {"id": scenario["scenario"], "name": scenario["scenario"], "count": scenario["count"]}
                )
        else:
            scenario_counts = {scenario["scenario"]: scenario["count"] for scenario in scenarios}
            for label in chain(*(_label["children"] for _label in labels)):
                scenario_list.append(
                    {"id": label["id"], "display_name": label["name"], "count": scenario_counts.get(label["id"], 0)}
                )
        return scenario_list

    def get_strategy_status_list(self, strategy_ids: list[int], bk_biz_id: int):
        """
        按策略状态统计策略数量
        """
        status_list = [
            {
                "id": "ALERT",
                "name": _("告警中"),
                "count": 0,
            },
            {
                "id": "INVALID",
                "name": _("策略已失效"),
                "count": 0,
            },
            {"id": "OFF", "name": _("已停用"), "count": 0},
            {"id": "ON", "name": _("已启用"), "count": 0},
            {"id": "SHIELDED", "name": _("屏蔽中"), "count": 0},
        ]
        for status in status_list:
            data = self.filter_by_status(status["id"], strategy_ids, bk_biz_id)
            status["count"] = len(data)
        return status_list

    def get_alert_level_list(self, strategy_ids: list[int]):
        """
        按告警级别统计策略数量
        """
        alert_level_list = []
        count_records = (
            DetectModel.objects.filter(strategy_id__in=strategy_ids)
            .values("level")
            .annotate(total=Count("strategy_id", distinct=True))
            .order_by("level")
        )

        level_counts = {record["level"]: record["total"] for record in count_records}

        all_level = {1: _("致命"), 2: _("预警"), 3: _("提醒")}
        for level_id, level_name in all_level.items():
            alert_level_list.append({"id": level_id, "name": level_name, "count": level_counts.get(level_id, 0)})
        return alert_level_list

    def get_invalid_type_list(self, strategy_ids: list[int]):
        """
        按策略失效类型统计策略数量
        """
        invalid_type_list = []
        count_records = (
            StrategyModel.objects.filter(is_invalid=True, id__in=strategy_ids)
            .values("invalid_type")
            .annotate(total=Count("id", distinct=True))
        )

        invalid_type_counts = {record["invalid_type"]: record["total"] for record in count_records}

        for invalid_type_id, invalid_type_name in StrategyModel.InvalidType.Choices:
            if not invalid_type_id:
                continue
            invalid_type_list.append(
                {"id": invalid_type_id, "name": invalid_type_name, "count": invalid_type_counts.get(invalid_type_id, 0)}
            )
        return invalid_type_list

    def get_algorithm_type_list(self, strategy_ids: list[int]):
        """
        按算法类型统计策略数量
        """
        algorithm_type_list = []
        count_records = (
            AlgorithmModel.objects.filter(strategy_id__in=strategy_ids)
            .values("type")
            .annotate(total=Count("strategy_id", distinct=True))
        )

        algorithm_type_counts = {record["type"]: record["total"] for record in count_records if record["type"]}

        for algorithm_type_id, algorithm_type_name in AlgorithmModel.ALGORITHM_CHOICES:
            algorithm_type_list.append(
                {
                    "id": algorithm_type_id,
                    "name": algorithm_type_name,
                    "count": algorithm_type_counts.get(algorithm_type_id, 0),
                }
            )
        return algorithm_type_list

    @staticmethod
    def get_metric_info(bk_biz_id: int, strategies: list[dict]):
        """
        获取策略相关指标信息
        """
        query_tuples = set()

        # 按数据源提取查询参数并使用集合去重
        for strategy in strategies:
            item = strategy["items"][0]
            for query_config in item["query_configs"]:
                if query_config["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH:
                    query_tuples.add(
                        (
                            query_config["data_source_label"],
                            query_config["data_type_label"],
                            query_config["index_set_id"],
                            query_config.get("metric_field", "_index"),
                        )
                    )
                elif (query_config["data_source_label"], query_config["data_type_label"]) == (
                    DataSourceLabel.CUSTOM,
                    DataTypeLabel.EVENT,
                ):
                    if query_config["custom_event_name"]:
                        query_tuples.add(
                            (
                                query_config["data_source_label"],
                                query_config["data_type_label"],
                                query_config["result_table_id"],
                                query_config["custom_event_name"],
                            )
                        )
                    else:
                        query_tuples.add(
                            (
                                query_config["data_source_label"],
                                query_config["data_type_label"],
                                query_config["result_table_id"],
                                "__INDEX__",
                            )
                        )
                elif query_config["data_source_label"] == DataSourceLabel.BK_FTA:
                    query_tuples.add(
                        (
                            query_config["data_source_label"],
                            query_config["data_type_label"],
                            query_config["data_type_label"],
                            query_config["alert_name"],
                        )
                    )
                elif (query_config["data_source_label"], query_config["data_type_label"]) == (
                    DataSourceLabel.BK_MONITOR_COLLECTOR,
                    DataTypeLabel.ALERT,
                ):
                    query_tuples.add(
                        (
                            query_config["data_source_label"],
                            query_config["data_type_label"],
                            "strategy",
                            query_config["bkmonitor_strategy_id"],
                        )
                    )
                elif query_config["data_source_label"] in [DataSourceLabel.PROMETHEUS, DataSourceLabel.DASHBOARD]:
                    continue
                else:
                    query_tuples.add(
                        (
                            query_config["data_source_label"],
                            query_config["data_type_label"],
                            query_config["result_table_id"],
                            query_config.get("metric_field", "_index"),
                        )
                    )

        # 查询策略相关指标信息
        queries = []
        for query_tuple in query_tuples:
            table_field = "result_table_id" if query_tuple[0] != DataSourceLabel.BK_LOG_SEARCH else "related_id"
            queries.append(
                Q(
                    **{
                        "data_source_label": query_tuple[0],
                        "data_type_label": query_tuple[1],
                        table_field: query_tuple[2],
                        "metric_field": query_tuple[3],
                    }
                )
            )

        if not queries:
            return {}

        bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        metrics = MetricListCache.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id__in=[bk_biz_id, 0]).filter(
            reduce(lambda x, y: x | y, queries)
        )

        metric_dicts = {get_metric_id(**metric.__dict__): metric for metric in metrics}

        return metric_dicts

    @staticmethod
    def fill_metric_info(strategy: dict, metric_info: dict):
        """
        补充策略相关指标信息
        """
        item = strategy["items"][0]
        for query_config in item["query_configs"]:
            metric_id = get_metric_id(**query_config)
            if metric_id in metric_info:
                query_config["name"] = metric_info[metric_id].metric_field_name
            else:
                query_config["name"] = (
                    query_config.get("metric_field")
                    or query_config.get("custom_event_name")
                    or query_config.get("bkmonitor_strategy_id")
                    or query_config.get("alert_name")
                    or query_config.get("result_table_id", "")
                )

    @staticmethod
    def fill_allow_target(strategy: dict, target_strategy_mapping):
        """
        补充是否允许增删目标
        """
        target = target_strategy_mapping.get(strategy["id"])
        algorithms = strategy["items"][0]["algorithms"]
        algorithm = algorithms[0] if algorithms else {}
        strategy["add_allowed"] = (target != DataTarget.NONE_TARGET) or (
            algorithm.get("type") == AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection
        )

    @staticmethod
    def fill_data_source_type(strategy_config, data_source_names):
        """
        补充数据源类型
        """
        data_source_label = strategy_config["items"][0]["query_configs"][0]["data_source_label"]
        data_type_label = strategy_config["items"][0]["query_configs"][0]["data_type_label"]
        strategy_config["data_source_type"] = data_source_names.get((data_source_label, data_type_label), "")

    @staticmethod
    def get_target_strategy_mapping(strategies: list[dict]):
        """
        根据策略列表获取目标策略映射
        """
        target_strategy_mapping = {}

        for strategy in strategies:
            query_config = strategy["items"][0]["query_configs"][0]

            target = DataTargetMapping().get_data_target(
                result_table_label=strategy["scenario"],
                data_source_label=query_config["data_source_label"],
                data_type_label=query_config["data_type_label"],
            )

            target_strategy_mapping[strategy["id"]] = target

        return target_strategy_mapping

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        strategies = StrategyModel.objects.filter(bk_biz_id=bk_biz_id)

        # 按条件过滤策略
        if params["conditions"]:
            strategies = self.filter_by_conditions(params["conditions"], strategies, bk_biz_id)

        # 在过滤监控对象前统计数量
        scenario_list = self.get_scenario_list(strategies)

        # 按当前选择的监控对象过滤
        scenarios = set(params.get("scenario", []))
        for condition in params["conditions"]:
            if condition["key"] != "scenario":
                continue
            if not isinstance(condition["value"], list):
                values = [condition["value"]]
            else:
                values = condition["value"]
            scenarios.update(values)

        if scenarios:
            strategies = strategies.filter(scenario__in=scenarios)

        # 统计其他分类数量
        strategy_ids = list(strategies.values_list("id", flat=True).distinct())

        executor = ThreadPoolExecutor()
        user_group_list_future = executor.submit(db_safe_wrapper(self.get_user_group_list), strategy_ids, bk_biz_id)
        action_config_list_future = executor.submit(
            db_safe_wrapper(self.get_action_config_list), strategy_ids, bk_biz_id
        )
        data_source_list_future = executor.submit(db_safe_wrapper(self.get_data_source_list), strategy_ids)
        strategy_label_list_future = executor.submit(
            db_safe_wrapper(self.get_strategy_label_list), strategy_ids, bk_biz_id
        )
        strategy_status_list_future = executor.submit(
            db_safe_wrapper(self.get_strategy_status_list), strategy_ids, bk_biz_id
        )
        alert_level_list_future = executor.submit(db_safe_wrapper(self.get_alert_level_list), strategy_ids)
        invalid_type_list_future = executor.submit(db_safe_wrapper(self.get_invalid_type_list), strategy_ids)
        algorithm_type_list_future = executor.submit(db_safe_wrapper(self.get_algorithm_type_list), strategy_ids)

        # 统计总数
        total = strategies.count()

        # 排序
        strategies = strategies.order_by("-update_time")

        # 分页
        if params.get("page") and params.get("page_size"):
            strategies = strategies[(params["page"] - 1) * params["page_size"] : params["page"] * params["page_size"]]

        # 生成策略配置
        strategy_objs = Strategy.from_models(strategies)
        for strategy_obj in strategy_objs:
            strategy_obj.restore()
        strategy_configs = [s.to_dict(convert_dashboard=params["convert_dashboard"]) for s in strategy_objs]

        # 补充告警组信息
        if params["with_user_group"]:
            Strategy.fill_user_groups(strategy_configs, params["with_user_group_detail"])

        # 补充AsCode字段
        for strategy_config in strategy_configs:
            if strategy_config.get("app"):
                strategy_config["config_source"] = "YAML"
            else:
                strategy_config["config_source"] = "UI"

        strategy_ids = [strategy_config["id"] for strategy_config in strategy_configs]

        # 查询ES，统计策略告警数量
        search_result_future = executor.submit(db_safe_wrapper(self.get_alert_search_result), bk_biz_id, strategy_ids)
        metric_info_future = executor.submit(db_safe_wrapper(self.get_metric_info), bk_biz_id, strategy_configs)
        target_strategy_mapping_future = executor.submit(
            db_safe_wrapper(self.get_target_strategy_mapping), strategy_configs
        )
        strategy_shield_info_future = executor.submit(db_safe_wrapper(self.get_shield_info), strategy_ids, bk_biz_id)

        # 获取到ES查询结果
        search_result = search_result_future.result()
        strategy_alert_counts = defaultdict(dict)
        if search_result.aggs:
            for strategy_bucket in search_result.aggs.strategy_id.buckets:
                strategy_alert_counts[strategy_bucket.key]["alert_count"] = strategy_bucket.doc_count
                for shield_bucket in strategy_bucket.shield_status:
                    strategy_alert_counts[strategy_bucket.key][shield_bucket.key_as_string] = shield_bucket.doc_count
        data_source_names = {
            (category["data_source_label"], category["data_type_label"]): category["name"] for category in DATA_CATEGORY
        }

        metric_info = metric_info_future.result()
        target_strategy_mapping = target_strategy_mapping_future.result()
        strategy_shield_info = strategy_shield_info_future.result()

        for strategy_config in strategy_configs:
            # 补充告警数量
            strategy_config["alert_count"] = strategy_alert_counts.get(str(strategy_config["id"]), {}).get("false", 0)
            # 补充屏蔽告警数量
            strategy_config["shield_alert_count"] = strategy_alert_counts.get(str(strategy_config["id"]), {}).get(
                "true", 0
            )
            # 补充策略屏蔽状态
            strategy_config["shield_info"] = strategy_shield_info.get(strategy_config["id"])
            self.fill_metric_info(strategy_config, metric_info)
            self.fill_allow_target(strategy_config, target_strategy_mapping)
            self.fill_data_source_type(strategy_config, data_source_names)

        user_group_list = user_group_list_future.result()
        action_config_list = action_config_list_future.result()
        data_source_list = data_source_list_future.result()
        strategy_label_list = strategy_label_list_future.result()
        strategy_status_list = strategy_status_list_future.result()
        alert_level_list = alert_level_list_future.result()
        invalid_type_list = invalid_type_list_future.result()
        algorithm_type_list = algorithm_type_list_future.result()
        # 等待线程执行完成，并关闭线程池
        executor.shutdown(wait=True)

        return {
            "scenario_list": scenario_list,
            "strategy_config_list": strategy_configs,
            "data_source_list": data_source_list,
            "strategy_label_list": strategy_label_list,
            "strategy_status_list": strategy_status_list,
            "user_group_list": user_group_list,
            "action_config_list": action_config_list,
            "alert_level_list": alert_level_list,
            "invalid_type_list": invalid_type_list,
            "algorithm_type_list": algorithm_type_list,
            "total": total,
        }


class GetStrategyV2Resource(Resource):
    """
    获取策略详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="策略ID")

    def perform_request(self, params):
        try:
            strategy = StrategyModel.objects.get(bk_biz_id=params["bk_biz_id"], id=params["id"])
        except StrategyModel.DoesNotExist:
            raise ValidationError(_("策略({})不存在").format(params["id"]))

        strategy_obj = Strategy.from_models([strategy])[0]
        strategy_obj.restore()
        config = strategy_obj.to_dict()

        # 补充告警组配置
        Strategy.fill_user_groups([config])
        return config


class PlainStrategyListV2Resource(Resource):
    """获取轻量的策略列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    @staticmethod
    def get_label_msg(scenario: str, labels: list) -> dict:
        for first_label in labels:
            for second_label in first_label["children"]:
                if second_label["id"] != scenario:
                    continue
                return {
                    "first_label": first_label["id"],
                    "first_label_name": first_label["name"],
                    "second_label": second_label["id"],
                    "second_label_name": second_label["name"],
                }

        return {
            "first_label": scenario,
            "first_label_name": scenario,
            "second_label": scenario,
            "second_label_name": scenario,
        }

    def perform_request(self, validated_request_data):
        # 获取指定业务下启用的策略
        bk_biz_id = validated_request_data.get("bk_biz_id")
        strategies = (
            StrategyModel.objects.filter(bk_biz_id=bk_biz_id)
            .values("id", "name", "scenario", "is_enabled")
            .order_by("-is_enabled", "-update_time")
        )
        # 获取分类标签
        labels = resource.commons.get_label()

        strategy_list = []
        for strategy in strategies:
            label_msg = self.get_label_msg(strategy["scenario"], labels)
            strategy.update(label_msg)
            strategy_list.append(strategy)
        return strategy_list


class DeleteStrategyV2Resource(Resource):
    """
    删除策略
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        ids = serializers.ListField(child=serializers.IntegerField(), required=True)

    def perform_request(self, params):
        strategy_ids = list(
            StrategyModel.objects.filter(bk_biz_id=params["bk_biz_id"], id__in=params["ids"]).values_list(
                "id", flat=True
            )
        )
        Strategy.delete_by_strategy_ids(strategy_ids)
        return strategy_ids


class GetMetricListV2Resource(Resource):
    GrafanaDataSource = (
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
    )

    PromqlDataSourcePrefix = {
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES): "bkmonitor",
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES): "custom",
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES): "bkdata",
    }

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        data_source_label = serializers.ListField(default=[], label="指标数据源", child=serializers.CharField())
        data_type_label = serializers.CharField(default="", label="指标数据类型", allow_blank=True)
        data_source = serializers.ListSerializer(
            label="数据源",
            child=serializers.ListField(min_length=2, max_length=2, child=serializers.CharField()),
            allow_empty=True,
            default=[],
        )
        result_table_label = serializers.ListField(allow_empty=True, child=serializers.CharField(), default=[])
        tag = serializers.CharField(default="", label="标签", allow_blank=True)
        conditions = serializers.ListField(required=False, child=serializers.DictField(), default=[], label="条件")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页数目")

    @classmethod
    def filter_by_double_paragaphs_metric_id(cls, metrics, filter_dict: dict) -> QuerySet:
        """
        处理二段式指标ID查询
        """
        filters: list[Q] = []
        for metric_id in filter_dict["metric_id"]:
            split_field_list = metric_id.split(".")
            if len(split_field_list) == 2:
                filters.append(Q(**{"data_label": split_field_list[0], "metric_field": split_field_list[1]}))

        if filters:
            return metrics.filter(reduce(lambda x, y: x | y, filters))
        return metrics.none()

    @classmethod
    def filter_by_conditions(cls, metrics: QuerySet, params: dict) -> QuerySet:
        """
        按查询条件过滤指标
        """
        filter_dict = defaultdict(list)
        for condition in params.get("conditions", []):
            if "key" not in condition or "value" not in condition:
                continue
            key = condition["key"]
            value = condition["value"]
            if not isinstance(value, list):
                value = [value]
            filter_dict[key].extend(value)

        search_fields = [
            "result_table_id",
            "result_table_name",
            "data_label",
            "metric_field",
            "metric_field_name",
            "related_id",
            "related_name",
        ]

        # 过滤为空的data_label条件
        if "data_label" in filter_dict:
            filter_dict["data_label"] = [label for label in filter_dict["data_label"] if label]

        # 直接过滤字段
        metrics = metrics.filter(
            **{f"{field}__in": filter_dict[field] for field in search_fields if filter_dict[field]}
        )

        # 过滤告警名称
        if filter_dict["alert_name"]:
            metrics = metrics.filter(
                reduce(lambda x, y: x | y, [Q(metric_field__icontains=name) for name in filter_dict["alert_name"]])
            )

        # 过滤索引集ID
        if filter_dict["index_set_id"]:
            metrics = metrics.filter(related_id__in=filter_dict["index_set_id"])

        if filter_dict["strategy_id"]:
            metrics = metrics.filter(metric_field__in=filter_dict["strategy_id"])

        if filter_dict["strategy_name"]:
            metrics = metrics.filter(
                reduce(
                    lambda x, y: x | y, [Q(metric_field_name__icontains=name) for name in filter_dict["strategy_name"]]
                )
            )

        # 支持metric_id查询
        if filter_dict["metric_id"]:
            queries: list[Q] = []
            for metric_id in filter_dict["metric_id"]:
                metric: dict = parse_metric_id(metric_id)

                if "index_set_id" in metric:
                    metric["related_id"] = metric["index_set_id"]
                    del metric["index_set_id"]
                if metric:
                    queries.append(Q(**metric))

            found_metric = False
            if queries:
                metric_filter = metrics.filter(reduce(lambda x, y: x | y, queries))
                found_metric = metric_filter.exists()

            metrics = metric_filter if found_metric else cls.filter_by_double_paragaphs_metric_id(metrics, filter_dict)
        # 模糊搜索
        if filter_dict["query"]:
            # 尝试解析指标ID格式的query字符串
            exact_query = []
            for query in filter_dict["query"]:
                query = query.strip()

                # promql格式的查询
                if ":" in query:
                    fields = query.split(":")
                    if fields[0] in ["custom", "bkmonitor"]:
                        fields = fields[1:]
                    fields = [field.strip() for field in fields if field.strip()]

                    if len(fields) == 3:
                        exact_query.append(
                            Q(result_table_id=f"{fields[0]}.{fields[1]}", metric_field__icontains=fields[2])
                        )
                    elif len(fields) == 2:
                        exact_query.append(Q(data_label=fields[0], metric_field__icontains=fields[1]))

                    continue

                # metric_id格式的查询
                fields = query.split(".")
                if len(fields) == 2:
                    exact_query.extend(
                        [
                            Q(data_label=fields[0], metric_field__icontains=fields[1]),
                            Q(result_table_id=fields[0], metric_field__icontains=fields[1]),
                        ]
                    )
                elif len(fields) >= 3:
                    exact_query.append(
                        Q(result_table_id=".".join(fields[:2]), metric_field__icontains=".".join(fields[2:]))
                    )

            queries = []
            for query, field in product(
                filter_dict["query"], ["data_label", "result_table_id", "metric_field", "metric_field_name"]
            ):
                queries.append(Q(**{f"{field}__icontains": query}))

            queries.extend(exact_query)
            metrics = metrics.filter(reduce(lambda x, y: x | y, queries))

        return metrics

    @classmethod
    def page_filter(cls, metrics: QuerySet, params) -> tuple[QuerySet, int]:
        """
        分页过滤
        """
        count = metrics.count()
        if params.get("page") and params.get("page_size"):
            # fmt: off
            metrics = metrics[(params["page"] - 1) * params["page_size"]: params["page"] * params["page_size"]]
            # fmt: on
        return metrics, count

    @classmethod
    def data_type_filter(cls, metrics: QuerySet, params) -> QuerySet:
        """
        指标数据类型过滤
        """
        if not params["data_type_label"]:
            return metrics

        if params["data_type_label"] != "grafana":
            metrics = metrics.filter(data_type_label=params["data_type_label"])
        else:
            metrics = metrics.filter(
                reduce(
                    lambda x, y: x | y,
                    [
                        Q(data_source_label=data_source_label, data_type_label=data_type_label)
                        for data_source_label, data_type_label in cls.GrafanaDataSource
                    ],
                )
            )

        return metrics

    @classmethod
    def data_source_filter(cls, metrics: QuerySet, params):
        """
        数据分类过滤
        """
        if params.get("data_source_label"):
            metrics = metrics.filter(data_source_label__in=params["data_source_label"])
        if params["data_source"]:
            metrics = metrics.filter(
                reduce(
                    lambda x, y: x | y,
                    [
                        Q(data_source_label=data_source_label, data_type_label=data_type_label)
                        for data_source_label, data_type_label in params["data_source"]
                    ],
                )
            )
        return metrics.order_by("-use_frequency")

    @classmethod
    def scenario_filter(cls, metrics: QuerySet, params):
        """
        场景过滤
        """
        # 对象过滤
        if params["result_table_label"]:
            metrics = metrics.filter(result_table_label__in=params["result_table_label"])
        return metrics

    @classmethod
    def tag_filter(cls, metrics: QuerySet, params):
        """
        标签过滤
        """
        tag = params["tag"]

        if tag == "__COMMON_USED__":
            metrics = metrics.exclude(use_frequency=0)
        elif tag.startswith("system."):
            metrics = metrics.filter(result_table_id=tag)
        elif tag:
            metrics = metrics.filter(related_id=tag)

        return metrics

    @classmethod
    def get_data_source_list(cls, metrics: QuerySet, params):
        """
        数据来源及类型分组统计
        """
        if params["data_type_label"]:
            if params["data_type_label"] != "grafana":
                metrics = metrics.filter(data_type_label=params["data_type_label"])
            else:
                metrics = metrics.filter(
                    reduce(
                        lambda x, y: x | y,
                        [
                            Q(data_source_label=data_source_label, data_type_label=data_type_label)
                            for data_source_label, data_type_label in cls.GrafanaDataSource
                        ],
                    )
                )
        elif params["data_source"]:
            metrics = metrics.filter(
                reduce(
                    lambda x, y: x | y,
                    (
                        Q(data_source_label=data_source[0], data_type_label=data_source[1])
                        for data_source in params["data_source"]
                    ),
                )
            )

        # 按数据源分组聚合指标数量
        source_counts = {
            (source_count["data_source_label"], source_count["data_type_label"]): source_count["count"]
            for source_count in metrics.values("data_source_label", "data_type_label").annotate(count=Count("id"))
        }

        return [
            {
                "count": source_counts.get((category["data_source_label"], category["data_type_label"]), 0),
                "data_source_label": category["data_source_label"],
                "data_type_label": category["data_type_label"],
                "id": category["type"],
                "name": category["name"],
            }
            for category in DATA_CATEGORY
        ]

    @classmethod
    def get_tag_list(cls, metrics: QuerySet, params):
        """
        可选分类
        """
        result_tables = (
            metrics.exclude(
                Q(
                    data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
                    data_type_label__in=[DataTypeLabel.EVENT, DataTypeLabel.LOG],
                )
                | Q(data_source_label__in=[DataSourceLabel.BK_DATA, DataSourceLabel.BK_LOG_SEARCH])
            )
            .values(
                "result_table_id",
                "result_table_name",
                "data_source_label",
                "data_type_label",
                "related_id",
                "related_name",
            )
            .annotate(count=Count("metric_field"))
            .order_by("related_id", "result_table_id")[:50]
        )

        category_tags = defaultdict(dict)
        for result_table in result_tables:
            data_source = (result_table["data_source_label"], result_table["data_type_label"])
            if result_table["data_source_label"] == DataSourceLabel.CUSTOM:
                # 如果是自定义事件或自定义时序，则使用related_id和related_name作为分类
                category_tags[data_source][result_table["related_id"]] = result_table["related_name"]
            elif data_source == (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES):
                # 系统分类特殊处理
                if result_table["result_table_id"].startswith("system."):
                    category_tags["system"][result_table["result_table_id"]] = result_table["result_table_name"]
                else:
                    category_tags[data_source][result_table["related_id"]] = result_table["related_name"]

        # 每种类型取几个
        tags = [{"id": "__COMMON_USED__", "name": _("常用")}]
        for tag_list in zip_longest(
            *([{"id": key, "name": value} for key, value in tags.items()] for tags in category_tags.values())
        ):
            tags.extend(tag for tag in tag_list if tag and tag["id"])

        return tags

    @classmethod
    def get_scenario_list(cls, metrics: QuerySet):
        """
        按监控场景统计指标数量
        """
        # 按监控对象统计数量
        scenarios = metrics.values("result_table_label").annotate(count=Count("result_table_label"))

        scenario_list = []
        try:
            labels = resource.commons.get_label()
        except Exception as e:
            logger.exception(e)
            # 如果拉取标签信息报错，则直接使用监控对象ID展示
            for scenario in scenarios:
                scenario_list.append(
                    {
                        "id": scenario["result_table_label"],
                        "name": scenario["result_table_label"],
                        "count": scenario["count"],
                    }
                )
        else:
            scenario_counts = {scenario["result_table_label"]: scenario["count"] for scenario in scenarios}
            for label in chain(*(_label["children"] for _label in labels)):
                scenario_list.append(
                    {"id": label["id"], "name": label["name"], "count": scenario_counts.get(label["id"], 0)}
                )
        return scenario_list

    @staticmethod
    def get_metric_remarks(data_source_label: str, data_type_label: str, metric_field) -> list:
        """
        指标备注
        """
        metric = {
            "data_source_label": data_source_label,
            "data_type_label": data_type_label,
            "metric_field": metric_field,
        }
        # 复用 v1 中的指标备注
        return resource.strategies.get_metric_list.get_metric_remarks(metric)

    @staticmethod
    def translate_metric(metric: dict) -> dict:
        """
        指标字段翻译
        """
        fields = [
            "result_table_name",
            "metric_field_name",
            "category_display",
            "description",
            "result_table_label_name",
        ]

        for field in fields:
            if field in metric:
                metric[field] = _(metric[field])

        for dimension in metric["dimensions"]:
            dimension["name"] = _(dimension["name"])

        return metric

    @classmethod
    def get_promql_format_metric(cls, metric: dict) -> str:
        """
        获取promql风格的指标名
        """
        data_source = (metric["data_source_label"], metric["data_type_label"])
        if data_source not in cls.PromqlDataSourcePrefix:
            return ""

        prefix = cls.PromqlDataSourcePrefix[data_source]
        if metric["readable_name"]:
            return f"{prefix}:{metric['readable_name'].replace('.', ':')}"

        return f"{prefix}:{metric['result_table_id'].replace('.', ':')}:{metric['metric_field']}"

    @classmethod
    def get_metric_list(cls, bk_biz_id: int, metrics: QuerySet):
        """
        指标数据
        """
        metric_list: list[dict] = []
        for metric in metrics:
            metric: MetricListCache

            default_trigger_config = (
                DEFAULT_TRIGGER_CONFIG_MAP.get(metric.data_source_label, {})
                .get(metric.data_type_label, {})
                .get(f"{metric.result_table_id}.{metric.metric_field}", GLOBAL_TRIGGER_CONFIG)
            )

            # ipv6业务的默认维度需要改为bk_host_id
            default_dimensions = metric.default_dimensions
            if is_ipv6_biz(bk_biz_id):
                is_host_metric = bool({"bk_target_ip", "bk_target_cloud_id"} and set(default_dimensions))
                if is_host_metric:
                    default_dimensions.append("bk_host_id")
                    default_dimensions = [
                        d for d in default_dimensions if d not in ["bk_target_ip", "bk_target_cloud_id"]
                    ]

            data = {
                "id": metric.id,
                "name": metric.metric_field_name,
                "bk_biz_id": metric.bk_biz_id,
                "data_source_label": metric.data_source_label,
                "data_type_label": metric.data_type_label,
                "dimensions": sorted(metric.dimensions, key=lambda x: x["name"]),
                "collect_interval": metric.collect_interval,
                "unit": metric.unit,
                "metric_field": metric.metric_field,
                "result_table_id": metric.result_table_id,
                "time_field": metric.extend_fields.get("time_field", "time"),
                "result_table_label": metric.result_table_label,
                "result_table_label_name": metric.result_table_label_name,
                "metric_field_name": metric.metric_field_name,
                "result_table_name": metric.result_table_name,
                "readable_name": metric.readable_name or metric.get_human_readable_name(),
                "data_label": metric.data_label,
                "description": metric.description,
                "remarks": cls.get_metric_remarks(
                    metric.data_source_label, metric.data_type_label, metric.metric_field
                ),
                "default_condition": metric.default_condition,
                "default_dimensions": default_dimensions,
                "default_trigger_config": default_trigger_config,
                "related_id": metric.related_id,
                "related_name": metric.related_name,
                "extend_fields": metric.extend_fields,
                "use_frequency": metric.use_frequency,
                "disabled": False,
                "data_target": metric.data_target,
            }

            # promql指标名
            data["promql_metric"] = cls.get_promql_format_metric(data)

            # 拨测指标特殊处理
            if metric.result_table_id.startswith("uptimecheck."):
                # 针对拨测服务采集，过滤业务/IP/云区域ID/错误码
                data["dimensions"] = [
                    dimension
                    for dimension in data["dimensions"]
                    if dimension["id"] not in ["bk_biz_id", "ip", "bk_cloud_id", "error_code"]
                ]

            # 特殊数据类型字段调整
            if metric.data_source_label == DataSourceLabel.BK_LOG_SEARCH:
                data.update(
                    {
                        "index_set_id": metric.related_id,
                        "index_set_name": metric.related_name,
                        "time_field": metric.extend_fields.get("time_field", "dtEventTimeStamp"),
                    }
                )
            elif (metric.data_source_label, metric.data_type_label) == (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT):
                data["custom_event_name"] = data["extend_fields"]["custom_event_name"]
                data["extend_fields"]["bk_data_id"] = metric.result_table_id
            elif metric.data_source_label == DataSourceLabel.BK_DATA:
                data["time_field"] = "dtEventTimeStamp"

            data["metric_id"] = get_metric_id(**data)
            data = cls.translate_metric(data)
            metric_list.append(data)

        return metric_list

    @classmethod
    def translate_monitor_dimensions(cls, metric_list, params):
        """
        补充监控策略的维度翻译
        """
        strategy_ids = []
        for metric in metric_list:
            if (metric["data_source_label"], metric["data_type_label"]) == (
                DataSourceLabel.BK_MONITOR_COLLECTOR,
                DataTypeLabel.ALERT,
            ):
                strategy_ids.append(metric["metric_field"])

        if not strategy_ids:
            return metric_list

        strategy_objs = StrategyModel.objects.filter(id__in=strategy_ids)
        strategies = Strategy.from_models(strategy_objs)
        metric_id_by_strategy = {}
        for strategy in strategies:
            for query_config in strategy.items[0].query_configs:
                if (query_config.data_source_label, query_config.data_type_label) != (
                    DataSourceLabel.BK_MONITOR_COLLECTOR,
                    DataTypeLabel.ALERT,
                ):
                    metric_id_by_strategy[strategy.id] = query_config.metric_id

        monitor_metrics = GetMetricListV2Resource()(
            bk_biz_id=params["bk_biz_id"],
            conditions=[{"key": "metric_id", "value": list(metric_id_by_strategy.values())}],
        )
        dimension_translation = {}
        for metric in monitor_metrics["metric_list"]:
            dimension_translation[metric["metric_id"]] = {d["id"]: d["name"] for d in metric["dimensions"]}

        for metric in metric_list:
            metric_id = metric_id_by_strategy.get(metric["id"])
            if not metric_id:
                continue

            trans_dict = dimension_translation.get(metric_id)
            if not trans_dict:
                continue

            for d in metric["dimensions"]:
                if d["id"].startswith("tags."):
                    d["name"] = trans_dict.get(d["id"][len("tags.") :], d["name"])
        return metric_list

    def perform_request(self, params):
        # 从指标选择器缓存表根据业务查询指标
        metrics = MetricListCache.objects.filter(
            bk_tenant_id=get_request_tenant_id(), bk_biz_id__in=[0, params["bk_biz_id"]]
        )

        if get_source_app() == SourceApp.FTA:
            metrics = metrics.filter(
                Q(data_type_label=DataTypeLabel.ALERT) | Q(data_source_label=DataSourceLabel.BK_FTA)
            )

        # 按查询条件过滤指标
        metrics = self.filter_by_conditions(metrics, params)

        # 区分指标/事件/日志关键字选择器或Grafana选择器
        metrics = self.data_type_filter(metrics, params)

        # 按标签过滤
        tag_metrics = self.tag_filter(metrics, params)
        # 按场景和数据源统计
        scenario_list = self.get_scenario_list(tag_metrics)
        data_source_list = self.get_data_source_list(tag_metrics, params)

        metrics = self.scenario_filter(metrics, params)
        metrics = self.data_source_filter(metrics, params)

        # 按标签统计并过滤标签
        tag_list = self.get_tag_list(metrics, params)
        metrics = self.tag_filter(metrics, params)

        # 分页过滤
        metrics, count = self.page_filter(metrics, params)

        metric_list = self.get_metric_list(params["bk_biz_id"], metrics)
        metric_list = self.translate_monitor_dimensions(metric_list, params)

        return {
            "metric_list": metric_list,
            "tag_list": tag_list,
            "data_source_list": data_source_list,
            "scenario_list": scenario_list,
            "count": count,
        }


class VerifyStrategyNameResource(Resource):
    """
    策略名校验
    """

    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)
        id = serializers.IntegerField(required=False, default=0)

        def validate(self, params):
            qs = StrategyModel.objects.filter(name=params["name"], bk_biz_id=params["bk_biz_id"])
            if params["id"]:
                qs.exclude(id=params["id"])
            if qs.exists():
                raise StrategyNameExist(name=params["name"])
            return super().validate(params)

    def perform_request(self, params):
        return "ok"


class BulkSwitchStrategyResource(Resource):
    """
    批量启停策略
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        labels = serializers.ListField(required=True, child=serializers.CharField())
        action = serializers.ChoiceField(required=True, label="操作类型", choices=("on", "off"))
        force = serializers.BooleanField(label="是否强制操作", default=False)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        # get_strategy_list_v2
        query_set = StrategyModel.objects.filter(bk_biz_id=bk_biz_id)
        # 是否强制覆盖已更新过的策略
        if not params["force"]:
            query_set = query_set.annotate(
                time_difference=ExpressionWrapper(
                    F("update_time") - F("create_time"), output_field=fields.DurationField()
                )
            ).filter(time_difference__lte=datetime.timedelta(seconds=1))
        target_ids = set(query_set.values_list("id", flat=True).distinct())
        filter_dict = {"label": params["labels"]}
        # filter by label
        resource.strategies.get_strategy_list_v2.filter_strategy_ids_by_label(filter_dict, target_ids, bk_biz_id)
        if not target_ids:
            return []
        # update_partial_strategy
        update_params = {
            "ids": target_ids,
            "edit_data": {"is_enabled": params["action"] == "on"},
            "bk_biz_id": bk_biz_id,
        }
        return resource.strategies.update_partial_strategy_v2(**update_params)


class SaveStrategyV2Resource(Resource):
    """
    保存策略
    """

    RequestSerializer = Strategy.Serializer

    @classmethod
    def validate_cmdb_level(cls, strategy: Strategy):
        """
        校验cmdb节点聚合配置是否合法
        """
        metric_count = len(strategy.items[0].query_configs)

        # 单指标一定合法
        if metric_count == 1:
            return

        for item in strategy.items:
            for query_config in item.query_configs:
                if (query_config.data_source_label, query_config.data_type_label) != (
                    DataSourceLabel.BK_MONITOR_COLLECTOR,
                    DataTypeLabel.TIME_SERIES,
                ):
                    continue

                used_dimensions = set(getattr(query_config, "agg_dimension", []))
                agg_condition = getattr(query_config, "agg_condition", [])

                for c in agg_condition:
                    used_dimensions.add(c["key"])

                if used_dimensions & set(SPLIT_DIMENSIONS):
                    raise CmdbLevelValidateError()

    @classmethod
    def validate_realtime_kafka(cls, strategy: Strategy):
        """
        校验实时策略对应插件的kafka存储是否存在
        """
        is_realtime_table_id = []
        for item in strategy.items:
            for query_config in item.query_configs:
                agg_method = getattr(query_config, "agg_method", "")
                result_table_id = getattr(query_config, "result_table_id", "")
                if agg_method == "REAL_TIME":
                    is_realtime_table_id.append(result_table_id)

        if is_realtime_table_id:
            api.metadata.check_or_create_kafka_storage(table_ids=is_realtime_table_id)

    @classmethod
    def validate_upgrade_user_groups(cls, strategy: Strategy):
        notice_info = strategy.notice
        upgrade_config = notice_info.options.get("upgrade_config", {})
        if not upgrade_config.get("is_enabled"):
            return
        if set(upgrade_config["user_groups"]) & set(notice_info.user_groups):
            raise ValidationError(detail=_("通知升级的用户组不能包含第一次接收告警的用户组"))

    def perform_request(self, params):
        strategy = Strategy(**params)
        strategy.convert()
        self.validate_realtime_kafka(strategy)
        self.validate_cmdb_level(strategy)
        self.validate_upgrade_user_groups(strategy)
        strategy.save()

        # 编辑后需要重置AsCode相关配置
        StrategyModel.objects.filter(id=strategy.id).update(hash="", snippet="")
        return strategy.to_dict()


class UpdatePartialStrategyV2Resource(Resource):
    """
    批量更新策略局部配置
    """

    class RequestSerializer(serializers.Serializer):
        class ConfigSerializer(serializers.Serializer):
            is_enabled = serializers.BooleanField(required=False)
            notice_group_list = serializers.ListField(required=False, child=serializers.IntegerField())
            labels = serializers.DictField(required=False)
            trigger_config = serializers.DictField(required=False)
            recovery_config = serializers.DictField(required=False)
            alarm_interval = serializers.IntegerField(required=False)
            send_recovery_alarm = serializers.BooleanField(required=False)
            message_template = serializers.CharField(required=False, allow_blank=True)
            no_data_config = serializers.DictField(required=False)
            notice = serializers.DictField(required=False)
            target = serializers.ListField(
                required=False, child=serializers.ListField(child=serializers.DictField(), allow_empty=True)
            )
            actions = serializers.ListField(required=False, child=serializers.DictField(), allow_empty=True)
            algorithms = Algorithm.Serializer(many=True, required=False)

            def validate_target(self, target):
                if target and target[0]:
                    handle_target(target)
                return target

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        ids = serializers.ListField(required=True, label="批量修改的策略ID列表")
        edit_data = ConfigSerializer(required=True)

    @staticmethod
    def update_dict_recursive(src, dst):
        """
        递归合并字典
        :param src: {"a": {"c": 2, "d": 1}, "b": 2}
        :param dst: {"a": {"c": 1, "f": {"zzz": 2}}, "c": 3, }
        :return: {'a': {'c': 1, 'd': 1, 'f': {'zzz': 2}}, 'b': 2, 'c': 3}
        """
        for key, value in dst.items():
            if key not in src:
                src[key] = value
            else:
                if isinstance(value, dict):
                    UpdatePartialStrategyV2Resource.update_dict_recursive(src[key], value)
                else:
                    src[key] = value
        return src

    @staticmethod
    def update_labels(strategy: Strategy, labels: dict):
        """
        更新策略标签，追加或者替换标签
        :param strategy: 需要更新标签的策略对象
        :param labels: 包含更新标签所需信息的字典
                        -如果字典中包含 "append_keys" 键，并且其值是一个包含 "labels" 的列表，则新的标签会被追加到现有标签中
                            例如：
                            labels = {
                                "labels": ["label2", "label3"],
                                "append_keys": ["labels"]
                            }
                            此时，新标签 "label2", "label3" 会被追加到现有标签中
                        -如果未传递 "append_keys" 或 "append_keys" 中不包含 "labels"，则现有标签将被新的标签完全替换
                            例如：
                                labels = {
                                    "labels": ["label2", "label3"]
                                }
                                或者
                                labels = {
                                    "labels": ["label2", "label3"],
                                    "append_keys": ["other_key"]
                                }
                                此时，现有标签将被新标签 "label2", "label3" 完全替换
        """
        old_labels: list = strategy.labels
        # 1、如果有传append_keys，则表示要将新的标签追加到原有策略的标签中
        if labels.get("append_keys"):
            if "labels" in labels["append_keys"]:
                # 将新的标签追加到旧标签中
                updated_labels = list(set(old_labels) | set(labels.get("labels", [])))
            else:
                # labels["append_keys"] 追加逻辑的字段列表里没有 labels 字段则替换
                updated_labels = labels.get("labels", [])
        else:
            # 2、如果没有传append_keys，则表示将原有策略的旧标签全部替换为新的标签
            updated_labels = labels.get("labels", [])

        # 3、保存策略标签
        strategy.labels = updated_labels
        strategy.save_labels()

        return None, [], []

    @staticmethod
    def update_is_enabled(strategy: Strategy, is_enabled: bool):
        """
        更新策略启停状态
        """
        strategy.is_enabled = is_enabled

        return StrategyModel, ["is_enabled"], [strategy.instance]

    @staticmethod
    def update_notice_group_list(strategy: Strategy, notice_group_list: list[int]):
        """
        更新告警组配置
        """
        for action in strategy.actions:
            action.user_groups = notice_group_list

        strategy.notice.user_groups = notice_group_list

        return StrategyActionConfigRelation, ["user_groups"], [action.instance, strategy.notice.instance]

    @staticmethod
    def update_trigger_config(strategy: Strategy, trigger_config: dict):
        """
        更新触发条件
        """
        for detect in strategy.detects:
            detect.trigger_config.update(trigger_config)

        return DetectModel, ["trigger_config"], [detect.instance for detect in strategy.detects]

    @staticmethod
    def update_alarm_interval(strategy: Strategy, alarm_interval: int):
        """
        更新通知间隔
        """
        strategy.notice.config["notify_interval"] = alarm_interval * 60

        return StrategyActionConfigRelation, ["config"], [strategy.notice.instance]

    @staticmethod
    def update_send_recovery_alarm(strategy: Strategy, send_recovery_alarm: bool):
        """
        更新恢复通知
        """
        if send_recovery_alarm and ActionSignal.RECOVERED not in strategy.notice.signal:
            strategy.notice.signal.append(ActionSignal.RECOVERED)

        if not send_recovery_alarm and ActionSignal.RECOVERED in strategy.notice.signal:
            strategy.notice.signal.remove(ActionSignal.RECOVERED)

        return StrategyActionConfigRelation, ["signal"], [strategy.notice.instance]

    @staticmethod
    def update_recovery_config(strategy: Strategy, recovery_config: dict):
        """
        更新告警恢复通知
        """
        for detect in strategy.detects:
            detect.recovery_config = recovery_config

        return DetectModel, ["recovery_config"], [detect.instance for detect in strategy.detects]

    @staticmethod
    def update_target(strategy: Strategy, target: list[list[dict]]):
        """
        更新监控目标
        """
        if not target or not target or not target[0][0]["value"]:
            target = []

        for item in strategy.items:
            item.target = target

        return ItemModel, ["target"], [item.instance for item in strategy.items]

    @staticmethod
    def update_algorithms(strategy: Strategy, algorithms: list[dict]):
        """更新检测算法。"""
        for item in strategy.items:
            item.algorithms = [Algorithm(strategy.id, item.id, **data) for data in algorithms]
            item.save_algorithms()

        return None, [], []

    @staticmethod
    def update_message_template(strategy: Strategy, message_template: str):
        """
        更新通知模板
        """
        for template in strategy.notice.config["template"]:
            template["message_tmpl"] = message_template

        return StrategyActionConfigRelation, ["config"], [strategy.notice.instance]

    @staticmethod
    def update_no_data_config(strategy: Strategy, no_data_config: dict):
        for item in strategy.items:
            UpdatePartialStrategyV2Resource.update_dict_recursive(item.no_data_config, no_data_config)

        return ItemModel, ["no_data_config"], [item.instance for item in strategy.items]

    @staticmethod
    def update_notice(
        strategy: Strategy,
        notice: dict,
        relations: dict[int, list[StrategyActionConfigRelation]],
        action_configs: dict[int, ActionConfig],
    ):
        """
        更新告警通知

        ```pyhon
        notice["append_keys"]: List[str]  # 追加逻辑的字段
        ```

        当 append_keys 有 key 时会将 old_notice[key] 的值添加到 notice[key] 中
        ```python
        notice = {
            append_keys: ["user_groups"],
            user_groups: [1, 2, 3],
            ...
        }
        old_notice: {
            append_keys: ["user_groups"],
            user_groups: [1, 4],
            ...
        }

        # 追加后并删除 append_keys
        notice = {
            user_groups: [1, 2, 3, 4]
        }
        ```
        """
        old_notice = strategy.notice.to_dict()
        new_notice = deepcopy(notice)
        # 判断是否进行追加操作
        if new_notice.get("append_keys"):
            for key in new_notice.get("append_keys", []):
                if new_notice.get(key):
                    if type(new_notice[key]) is list:
                        [new_notice[key].append(i) for i in old_notice.get(key) if i not in new_notice[key]]

            new_notice.pop("append_keys")

        UpdatePartialStrategyV2Resource.update_dict_recursive(old_notice, new_notice)
        strategy.notice = NoticeRelation(strategy.id, **old_notice)
        # 同步当前的通知时间和通知组
        for action in strategy.actions:
            action.user_groups = strategy.notice.user_groups
            action.options.update(
                {
                    "start_time": strategy.notice.options.get("start_time", "00:00:00"),
                    "end_time": strategy.notice.options.get("end_time", "23:59:59"),
                }
            )

        extra_create_or_update_datas = strategy.bulk_save_notice(relations, action_configs)
        return (
            StrategyActionConfigRelation,
            ["user_groups", "options"],
            [action.instance for action in strategy.actions],
            extra_create_or_update_datas,
        )

    @staticmethod
    def update_actions(strategy: Strategy, actions: list[dict]):
        new_actions = []
        for action in actions:
            slz = ActionRelation.Serializer(data=action)
            slz.is_valid(raise_exception=True)
            action_data = slz.validated_data
            action_relation = ActionRelation(strategy.id, **action_data)
            action_relation.user_groups = strategy.notice.user_groups
            action_relation.options.update(
                {
                    "start_time": strategy.notice.options.get("start_time", "00:00:00"),
                    "end_time": strategy.notice.options.get("end_time", "23:59:59"),
                }
            )
            new_actions.append(action_relation)

        strategy.actions = new_actions

        strategy.save_actions()
        return None, [], []

    @staticmethod
    def get_relations(strategy_ids: list[int]):
        action_config_ids = set()
        relations: dict[int, list[StrategyActionConfigRelation]] = defaultdict(list)
        related_query = StrategyActionConfigRelation.objects.filter(
            strategy_id__in=strategy_ids, relate_type=StrategyActionConfigRelation.RelateType.NOTICE
        )
        for relation in related_query:
            relations[relation.strategy_id].append(relation)
            action_config_ids.add(relation.config_id)
        return list(action_config_ids), relations

    @staticmethod
    def get_action_configs(action_config_ids: list[int]):
        action_query = ActionConfig.objects.filter(id__in=action_config_ids)
        action_configs: dict[int, ActionConfig] = {}
        for action_config in action_query:
            action_configs[action_config.id] = action_config
        return action_configs

    @staticmethod
    def process_extra_data(
        extra_create_or_update_datas: dict[str, list[dict[str, any]]],
        key: str,
        updates_data: defaultdict[str, dict[str, any]],
        create_datas: defaultdict[str, dict[str, any]],
    ):
        extra_update_datas = extra_create_or_update_datas.get("update_data", [])
        extra_create_datas = extra_create_or_update_datas.get("create_data", [])
        for update_data in extra_update_datas:
            if update_data["cls"] is ActionConfig:
                updates_data[f"extra_{key}_config"]["cls"] = update_data["cls"]
                updates_data[f"extra_{key}_config"]["keys"] = update_data["keys"]
                updates_data[f"extra_{key}_config"]["objs"].extend(update_data["objs"])
            elif update_data["cls"] is StrategyActionConfigRelation:
                updates_data[f"extra_{key}_relation"]["cls"] = update_data["cls"]
                updates_data[f"extra_{key}_relation"]["keys"] = update_data["keys"]
                updates_data[f"extra_{key}_relation"]["objs"].extend(update_data["objs"])

        for data in extra_create_datas:
            if data["cls"] is ActionConfig:
                create_datas[f"extra_{key}_config"]["cls"] = data["cls"]
                create_datas[f"extra_{key}_config"]["objs"].extend(data["objs"])
            elif data["cls"] is StrategyActionConfigRelation:
                create_datas[f"extra_{key}_relation"]["cls"] = data["cls"]
                create_datas[f"extra_{key}_relation"]["objs"].extend(data["objs"])

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        config: dict = params["edit_data"]
        username = get_global_user()
        strategy_ids = params["ids"]
        strategies = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=strategy_ids)

        action_config_ids, relations = self.get_relations(strategy_ids)
        action_configs = self.get_action_configs(action_config_ids)

        create_datas = defaultdict(lambda: {"cls": None, "objs": []})
        updates_data = defaultdict(lambda: {"cls": None, "keys": [], "objs": []})
        updates_data["update_time"]["cls"] = StrategyModel
        updates_data["update_time"]["keys"] = ["update_time", "update_user"]
        update_time = datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
        history = []
        for strategy in Strategy.from_models(strategies):
            affect_history_data = False
            for key, value in config.items():
                update_method: Callable[[Strategy, Any], None] = getattr(self, f"update_{key}", None)
                if not update_method:
                    continue
                if key == "notice":
                    (update_cls, update_keys, update_objs, extra_create_or_update_datas) = self.update_notice(
                        strategy, value, relations, action_configs
                    )
                    self.process_extra_data(extra_create_or_update_datas, key, updates_data, create_datas)
                else:
                    update_cls, update_keys, update_objs = update_method(strategy, value)
                if update_cls:
                    updates_data[key]["cls"] = update_cls
                    updates_data[key]["keys"] = update_keys
                    updates_data[key]["objs"].extend(update_objs)

                if key in ("is_enabled",):
                    affect_history_data = True

            if affect_history_data:
                # 对于影响历史依赖的配置，如果使用的是智能监控SDK，还需要重置状态触发重新拉取历史依赖的逻辑
                for item in strategy.items:
                    if getattr(item.query_configs[0], "intelligent_detect", None) and item.query_configs[
                        0
                    ].intelligent_detect.get("use_sdk", False):
                        item.query_configs[0].intelligent_detect["status"] = SDKDetectStatus.PREPARING
                        item.query_configs[0].save()

            strategy.instance.update_time = update_time
            strategy.instance.update_user = username
            updates_data["update_time"]["objs"].append(strategy.instance)
            history.append(
                StrategyHistoryModel(
                    create_user=username,
                    strategy_id=strategy.id,
                    operate="update",
                    content=strategy.to_dict(),
                )
            )

        for update_data in updates_data.values():
            update_data["cls"].objects.bulk_update(update_data["objs"], update_data["keys"])

        for create_data in create_datas.values():
            create_data["cls"].objects.bulk_create(create_data["objs"])

        StrategyHistoryModel.objects.bulk_create(history)

        # 编辑后需要重置AsCode相关配置
        strategies.update(hash="", snippet="")

        return params["ids"]


class CloneStrategyV2Resource(Resource):
    """
    克隆策略
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        ids = serializers.ListField(required=True, child=serializers.IntegerField(), label="待克隆策略ID")

    def perform_request(self, params):
        strategies = Strategy.from_models(
            StrategyModel.objects.filter(bk_biz_id=params["bk_biz_id"], id__in=params["ids"])
        )

        for strategy in strategies:
            strategy.id = 0
            strategy.name += "_copy"
            strategy.app = ""
            strategy.source = settings.APP_CODE

            while StrategyModel.objects.filter(bk_biz_id=params["bk_biz_id"], name=strategy.name).exists():
                strategy.name += "_copy"
            strategy.save()

        return [strategy.id for strategy in strategies]


class GetPlainStrategyListV2Resource(Resource):
    """
    获取精简策略列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        page = serializers.IntegerField(default=1)
        page_size = serializers.IntegerField(default=10)
        search = serializers.CharField(required=False, default="")

    def perform_request(self, params):
        strategies = StrategyModel.objects.filter(bk_biz_id=params["bk_biz_id"])

        # 检索条件
        if params["search"]:
            query = None

            # 尝试当成策略ID查询
            try:
                strategy_id = int(params["search"])
                query = Q(id=strategy_id)
            except (ValueError, TypeError):
                pass

            # 查询策略名称
            if query is None:
                query = Q(name__icontains=params["search"])
            else:
                query |= Q(name__icontains=params["search"])

            strategies = strategies.filter(query)

        # 统计总数
        count = strategies.count()

        # 分页查询
        strategies = strategies[(params["page"] - 1) * params["page_size"] : params["page"] * params["page_size"]]

        return {
            "count": count,
            "strategy_configs": [
                {"id": strategy.id, "name": strategy.name, "scenario": strategy.scenario} for strategy in strategies
            ],
        }


class GetTargetDetailWithCache(CacheResource):
    """获取监控目标详情，具有缓存功能"""

    backend_cache_type = CacheType.CC_CACHE_ALWAYS
    cache_user_related = False

    class RequestSerializer(serializers.Serializer):
        strategy_id = serializers.IntegerField(required=True, label="策略ID")

    def perform_request(self, validate_data):
        """
        为了获取最佳的性能，在执行request()方法之前，请先执行set_mapping()方法，传入策略和监控目标的映射关系字典，以避免频繁查询数据库。
        并且请显示使用instance.request()的方式执行perform_request，而非使用instance()方式，
        使用instance()方式执行时会重新实例化，导致先前执行的set_mapping失效。

        example:
            >>instance = GetTargetDetailWithCache()
            >>instance.set_mapping({xxx})
            >>instance.request(xxx)
        """

        strategy_id = validate_data["strategy_id"]
        if not hasattr(self, "strategy_target_mapping"):
            bk_biz_id = StrategyModel.objects.get(id=strategy_id).bk_biz_id
            target = ItemModel.objects.get(strategy_id=strategy_id).target
            logger.warning("Please call set_mapping() before calling perform_request().")
        else:
            bk_biz_id, target = self.strategy_target_mapping[strategy_id]

        return self.get_target_detail(bk_biz_id, target)

    def set_mapping(self, mapping: dict) -> None:
        """
        设置策略和监控目标的映射关系
        格式:{ strategy_id:(bk_biz_id,target) }
        """

        if not isinstance(mapping, dict):
            logging.error("Invalid type for 'mapping'. Expected dict.")
            raise TypeError("mapping must be a dict.")

        self.strategy_target_mapping = mapping

    def cache_write_trigger(self, target_info: Any) -> bool:
        """获取到监控目标信息不为None，则进行缓存"""
        if target_info:
            return True
        return False

    @classmethod
    def get_target_detail(cls, bk_biz_id: int, target: list[list[dict]]):
        """
        target : [
                    [
                    {"field":"ip", "method":"eq", "value": [{"ip":"127.0.0.1","bk_supplier_id":0,"bk_cloud_id":0},]},
                    {"field":"host_topo_node", "method":"eq", "value": [{"bk_obj_id":"test","bk_inst_id":2}]}
                    ],
                    [
                    {"field":"ip", "method":"eq", "value": [{"ip":"127.0.0.1","bk_supplier_id":0,"bk_cloud_id":0},]},
                    {"field":"host_topo_node", "method":"eq", "value": [{"bk_obj_id":"test","bk_inst_id":2}]}
                    ]
                ]
        target理论上支持多个列表以或关系存在，列表内部亦存在多个对象以且关系存在，
        由于目前产品形态只支持单对象的展示，因此若存在多对象，只取第一个对象返回给前端
        """
        target_type_map = {
            TargetFieldType.host_target_ip: TargetNodeType.INSTANCE,
            TargetFieldType.host_ip: TargetNodeType.INSTANCE,
            TargetFieldType.host_topo: TargetNodeType.TOPO,
            TargetFieldType.service_topo: TargetNodeType.TOPO,
            TargetFieldType.service_service_template: TargetNodeType.SERVICE_TEMPLATE,
            TargetFieldType.service_set_template: TargetNodeType.SET_TEMPLATE,
            TargetFieldType.host_service_template: TargetNodeType.SERVICE_TEMPLATE,
            TargetFieldType.host_set_template: TargetNodeType.SET_TEMPLATE,
            TargetFieldType.dynamic_group: TargetNodeType.DYNAMIC_GROUP,
        }
        obj_type_map = {
            TargetFieldType.host_target_ip: TargetObjectType.HOST,
            TargetFieldType.host_ip: TargetObjectType.HOST,
            TargetFieldType.host_topo: TargetObjectType.HOST,
            TargetFieldType.service_topo: TargetObjectType.SERVICE,
            TargetFieldType.service_service_template: TargetObjectType.SERVICE,
            TargetFieldType.service_set_template: TargetObjectType.SERVICE,
            TargetFieldType.host_service_template: TargetObjectType.HOST,
            TargetFieldType.host_set_template: TargetObjectType.HOST,
            TargetFieldType.dynamic_group: TargetObjectType.HOST,
        }
        info_func_map = {
            TargetFieldType.host_target_ip: resource.commons.get_host_instance_by_ip,
            TargetFieldType.host_ip: resource.commons.get_host_instance_by_ip,
            TargetFieldType.service_topo: resource.commons.get_service_instance_by_node,
            TargetFieldType.host_topo: resource.commons.get_host_instance_by_node,
            TargetFieldType.service_service_template: resource.commons.get_nodes_by_template,
            TargetFieldType.service_set_template: resource.commons.get_nodes_by_template,
            TargetFieldType.host_service_template: resource.commons.get_nodes_by_template,
            TargetFieldType.host_set_template: resource.commons.get_nodes_by_template,
            TargetFieldType.dynamic_group: resource.commons.get_dynamic_group_instance,
        }

        # 判断target格式是否符合预期
        if not target or not target[0]:
            return None
        else:
            target = target[0][0]

        field = target.get("field")
        if not field or not target.get("value"):
            return None

        params = {"bk_biz_id": bk_biz_id}
        if field in [TargetFieldType.host_ip, TargetFieldType.host_target_ip]:
            params["ip_list"] = []
            for x in target["value"]:
                if x.get("bk_host_id"):
                    ip = {"bk_host_id": x["bk_host_id"]}
                elif x.get("bk_target_ip"):
                    ip = {"ip": x["bk_target_ip"], "bk_cloud_id": x["bk_target_cloud_id"]}
                else:
                    ip = {"ip": x["ip"], "bk_cloud_id": x["bk_cloud_id"]}
                params["ip_list"].append(ip)

            params["bk_biz_ids"] = [bk_biz_id]
        elif field in [
            TargetFieldType.host_set_template,
            TargetFieldType.host_service_template,
            TargetFieldType.service_set_template,
            TargetFieldType.service_service_template,
        ]:
            params["bk_obj_id"] = target_type_map[field]
            params["bk_inst_type"] = obj_type_map[field]
            params["bk_inst_ids"] = [inst["bk_inst_id"] for inst in target["value"]]
        elif field == TargetFieldType.dynamic_group:
            params["dynamic_group_ids"] = [x["dynamic_group_id"] for x in target["value"]]
        else:
            node_list = target.get("value")
            for target_item in node_list:
                if "bk_biz_id" not in target_item:
                    target_item.update(bk_biz_id=bk_biz_id)
            params["node_list"] = node_list

        target_detail = info_func_map[field](params)

        # 统计实例数量
        if field in [TargetFieldType.host_ip, TargetFieldType.host_target_ip]:
            instance_count = len(target_detail)
        else:
            instances = set()
            for node in target_detail:
                instances.update(node.get("all_host", []))
            instance_count = len(instances)

        # 补充未查询到模块的模版信息
        if (
            "bk_inst_ids" in params
            and len(target_detail) != len(params["bk_inst_ids"])
            and field
            in [
                TargetFieldType.host_set_template,
                TargetFieldType.host_service_template,
                TargetFieldType.service_set_template,
                TargetFieldType.service_service_template,
            ]
        ):
            # 已经查询到的模板ID
            queried_template_ids = {d[target_type_map[field]] for d in target_detail}

            templates_params = {
                "scope_list": [{"scope_type": "biz", "scope_id": bk_biz_id, "bk_biz_id": bk_biz_id}],
                "template_type": target_type_map[field],
            }
            # 获取到所有的模板信息
            templates = {t["id"]: t for t in template_handler.TemplateHandler(**templates_params).list_templates()}

            for _id in params["bk_inst_ids"]:
                if _id in queried_template_ids or _id not in templates:
                    continue

                target_detail.append(
                    {
                        "bk_obj_id": "",
                        "bk_inst_id": None,
                        "bk_biz_id": bk_biz_id,
                        "bk_inst_name": "",
                        "SERVICE_TEMPLATE": _id,
                        "node_path": templates[_id]["name"],
                        "all_host": [],
                        "count": 0,
                        "agent_error_count": 0,
                        "labels": [{"first": "None", "second": "None"}],
                    }
                )

        return {
            "node_type": target_type_map[field],
            "node_count": len(target["value"]),
            "instance_type": obj_type_map[field],
            "instance_count": instance_count,
            "target_detail": target_detail,
        }


class GetTargetDetail(Resource):
    """
    获取监控目标详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        strategy_ids = serializers.ListField(required=True, label="策略ID列表", child=serializers.IntegerField())
        refresh = serializers.BooleanField(required=False, default=False, label="是否刷新缓存")

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        strategies = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=params["strategy_ids"]).only(
            "id", "scenario"
        )
        strategy_ids = [strategy.id for strategy in strategies]
        items = ItemModel.objects.filter(strategy_id__in=strategy_ids)

        get_target_detail_with_cache = GetTargetDetailWithCache()
        # 提前设置策略与监控目标映射，避免频繁查询数据库
        get_target_detail_with_cache.set_mapping({item.strategy_id: (bk_biz_id, item.target) for item in items})

        empty_strategy_ids = []
        result = {}
        for item in items:
            # 使用instance.request()方式调用，而非instance()方式。
            # instance()方式执行时会重新实例化，导致先前执行的set_mapping失效
            if params["refresh"]:
                info = get_target_detail_with_cache.request.refresh({"strategy_id": item.strategy_id})
            else:
                info = get_target_detail_with_cache.request({"strategy_id": item.strategy_id})

            if info:
                result[item.strategy_id] = info
            else:
                empty_strategy_ids.append(item.strategy_id)

        if not empty_strategy_ids:
            return result

        query_configs = QueryConfigModel.objects.filter(strategy_id__in=empty_strategy_ids).only(
            "strategy_id", "data_type_label", "data_source_label"
        )
        strategy_data_source = {
            query_config.strategy_id: (query_config.data_source_label, query_config.data_type_label)
            for query_config in query_configs
        }
        strategy_scenario = {strategy.id: strategy.scenario for strategy in strategies}

        data_target_to_instance_type = {
            DataTarget.NONE_TARGET: None,
            DataTarget.HOST_TARGET: TargetObjectType.HOST,
            DataTarget.DEVICE_TARGET: TargetObjectType.HOST,
            DataTarget.SERVICE_TARGET: TargetObjectType.SERVICE,
        }
        for strategy_id in empty_strategy_ids:
            scenario = strategy_scenario[strategy_id]
            if strategy_id in strategy_data_source:
                data_target = DataTargetMapping.get_data_target(
                    result_table_label=scenario,
                    data_source_label=strategy_data_source[strategy_id][0],
                    data_type_label=strategy_data_source[strategy_id][1],
                )
                instance_type = data_target_to_instance_type[data_target]
            else:
                instance_type = None
            result[strategy_id] = {
                "bk_target_type": None,
                "bk_obj_type": None,
                "bk_target_detail": None,
                "instance_type": instance_type,
            }

        return result


class SearchMetricIDResource(Resource):
    """
    查询指标ID
    """

    def perform_request(self, params):
        return []


class QueryConfigToPromql(Resource):
    """
    查询配置转换为PromQL
    """

    re_metric_id = re.compile(r"([A-Za-z0-9_]+(:[A-Za-z0-9_]+)+)")

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        expression = serializers.CharField()
        query_configs = serializers.ListField(child=serializers.DictField())
        query_config_format = serializers.ChoiceField(choices=("strategy", "graph"), default="strategy")

        def validate(self, attrs):
            """
            按数据源类型校验查询配置
            """
            for index, query_config in enumerate(attrs["query_configs"]):
                if "data_source_label" not in query_config or "data_type_label" not in query_config:
                    raise ValidationError("fields(data_source_label, data_type_label) are required")

                # 限制能够使用PromQL的数据源类型
                data_source = (query_config["data_source_label"], query_config["data_type_label"])
                if data_source not in [
                    (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
                    (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
                    (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
                ]:
                    raise ValidationError(f"not support data_source({data_source})")

                # 兼容图表接口
                if attrs["query_config_format"] != "strategy":
                    query_config["result_table_id"] = query_config.pop("table", "")
                    query_config["data_label"] = query_config.pop("data_label", "")
                    query_config["metric_field"] = query_config.pop("metric")
                    query_config["agg_method"] = query_config.pop("method")
                    query_config["agg_dimension"] = query_config.pop("group_by", [])
                    query_config["agg_condition"] = query_config.pop("where", [])
                    query_config["agg_interval"] = query_config.pop("interval")

                # 兼容自动周期，默认转换为一分钟
                if query_config["agg_interval"] == "auto":
                    query_config["agg_interval"] = 60

                serializer_class = QueryConfig.QueryConfigSerializerMapping.get(data_source)
                serializer = serializer_class(data=query_config)
                serializer.is_valid(raise_exception=True)
                attrs["query_configs"][index] = serializer.validated_data

                attrs["query_configs"][index]["data_source_label"] = query_config["data_source_label"]
                attrs["query_configs"][index]["data_type_label"] = query_config["data_type_label"]
                attrs["query_configs"][index]["alias"] = query_config["alias"]
            return attrs

    @classmethod
    def check(cls, unify_query_config: dict, data_source_label: str = "bkmonitor") -> None:
        """
        配置预处理，判断配置是否能够转换PromQL，调整部分配置以适应配置转换
        检测规则:
        1. 监控条件不能存在or语句
        2. 监控条件匹配多个值时，需要使用正则进行合成
        """

        for query_config in unify_query_config["query_list"]:
            condition_list = query_config["conditions"]["condition_list"]
            field_list = query_config["conditions"]["field_list"]
            query_config["data_source"] = data_source_label

            # 监控条件不能存在or语句
            if "or" in condition_list:
                raise ValidationError(_("监控条件包含or语句时无法转换为PromQL语句"))

            for condition in field_list:
                # contains及ncontains需要转换为eq,ne或req,nreq
                if condition["op"] in ["contains", "ncontains"]:
                    if len(condition["value"]) == 1:
                        condition["op"] = {"contains": "eq", "ncontains": "ne"}[condition["op"]]
                    else:
                        condition["op"] = {"contains": "req", "ncontains": "nreq"}[condition["op"]]
                        condition["value"] = [re.escape(str(v)) for v in condition["value"]]
                        condition["value"] = ["^(" + "|".join(condition["value"]) + ")$"]
                elif condition["op"] in ["req", "nreq"]:
                    condition["value"] = ["|".join(condition["value"])]

    def perform_request(self, params):
        data_sources = []
        data_source_label = "bkmonitor"
        data_source_label_mapping = {
            "bk_monitor": "bkmonitor",
            "custom": "custom",
            "bk_data": "bkdata",
            "bk_log_search": "bklog",
        }
        for query_config in params["query_configs"]:
            data_source_label = data_source_label_mapping.get(query_config["data_source_label"], data_source_label)
            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            init_params = dict(query_config=query_config)
            init_params.update({"bk_biz_id": params["bk_biz_id"]})
            data_sources.append(data_source_class.init_by_query_config(**init_params))

        # 构造统一查询配置
        query = UnifyQuery(bk_biz_id=params["bk_biz_id"], data_sources=data_sources, expression=params["expression"])
        unify_query_config = query.get_unify_query_params()
        self.check(unify_query_config, data_source_label)
        promql = api.unify_query.struct_to_promql(unify_query_config)["promql"]
        return {"promql": promql}


class PromqlToQueryConfig(Resource):
    """
    PromQL转为查询配置
    """

    # 时间字符串提取及转换
    re_time_parse = re.compile(r"^(\d+)([^\d]*)")
    time_trans_mapping = {"w": 7 * 24 * 3600, "d": 24 * 3600, "h": 3600, "m": 60, "s": 1}
    # PromQL match相关算符正则
    re_ignoring_on_op = re.compile(r"(?![A-Za-z0-9_]) ?(ignoring|on) ?\(.*\) ?")
    re_group_op = re.compile(r"(?![A-Za-z0-9_]) ?(group_left|group_right) ?(\([0-9a-zA-Z_ ]*\))?")
    # 按表名判断数据源
    re_custom_time_series = re.compile(r"\d+bkmonitor_time_series_\d+")
    # 支持聚合方法
    aggr_ops = {"sum", "avg", "mean", "max", "min", "count"}
    # 条件算符转换
    condition_op_mapping: dict[str, str] = {"req": "reg", "nreq": "nreg", "eq": "eq", "ne": "neq"}
    # 指标ID正则
    re_metric_id = re.compile(r"([A-Za-z0-9_]+(:[A-Za-z0-9_]+)+)")
    # 内置k8s维度替换
    k8s_dimension_map = {"cluster_id": "bcs_cluster_id"}
    # 时间聚合函数映射
    time_functon_map = {"count": "sum"}

    class RequestSerializer(serializers.Serializer):
        promql = serializers.CharField(label="查询语句")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        query_config_format = serializers.ChoiceField(choices=("strategy", "graph"), default="strategy")

    @classmethod
    def parse_time(cls, s: str) -> int:
        """
        解析时间字段(1h2m3s)
        """
        parts = cls.re_time_parse.findall(s.lower().replace(" ", ""))
        seconds = 0
        for part in parts:
            seconds += int(part[0]) * cls.time_trans_mapping[part[1]]
        return seconds

    @classmethod
    def check(cls, unify_query_config: dict):
        """
        配置预处理，判断配置是否符合预期
        检测规则:
        1. 时间聚合函数及维度聚合函数保证有且仅有一个
        2. 函数仅支持Function中注册的函数
        3. 如果勾选映射规则，判断映射范围内指标/表数据是否存在，若为容器指标跳过（无需result_table_id）
        4. 维度匹配检查，忽略ignore/on/group_left/group_right等算符
        问题:
        1. ignoring/on/group_left/group_right只能去除，交由默认逻辑处理，不好做详细的检查。
        2. 聚合函数的without语法未被考虑，无法分别是sum by还是sum without，语义可能出错。
        3. 是否需要强制检查指标维度？
        """
        for query in unify_query_config["query_list"]:
            # 函数使用统计
            function_counts = defaultdict(int)
            query["function"] = query.get("function") or []
            for function in query["function"]:
                if function["method"] not in Functions and function["method"] not in cls.aggr_ops:
                    raise ValidationError(_("不支持的函数({})").format(function["method"]))
                function_counts[function["method"]] += 1

            # 维度聚合方法检查
            dimension_function_names = list(set(function_counts.keys()) & cls.aggr_ops)
            dimension_function_names = [name if name != "mean" else "avg" for name in dimension_function_names]
            if not dimension_function_names:
                dimension_function_names = ["avg"]
                query["function"].append({"method": "mean", "dimensions": []})
            elif function_counts[dimension_function_names[0]] > 1:
                raise ValidationError(_("只能进行一次维度聚合，如sum、avg等"))

            # 判断时间聚合方法是否符合预期
            time_function = query["time_aggregation"].get("function")
            if time_function:
                if time_function[:-10] not in cls.aggr_ops and (
                    time_function not in Functions or not Functions[time_function].time_aggregation
                ):
                    raise ValidationError(_("不支持的方法({})").format(time_function))
                # 维度聚合和时间聚合函数是否对应,count场景特殊处理
                dimension_function_name = cls.time_functon_map.get(time_function[:-10], time_function[:-10])
                if time_function[:-10] in cls.aggr_ops and dimension_function_names[0] != dimension_function_name:
                    raise ValidationError(
                        _("如果时间聚合函数使用{}，那么维度聚合函数必须使用{}").format(
                            time_function, dimension_function_name
                        )
                    )
            else:
                query["time_aggregation"] = {}

        return unify_query_config

    @classmethod
    def convert_to_query_config(cls, unify_query_config: dict, query_config_format="strategy"):
        """
        转换为监控查询参数
        """
        # 表达式剔除ignoring/on/group_left/group_right
        expression = unify_query_config["metric_merge"]
        expression = cls.re_group_op.sub(" ", expression)
        expression = cls.re_ignoring_on_op.sub(" ", expression)

        # 去除单指标单表达式
        if expression == "a":
            expression = ""
        config = {"expression": expression, "query_configs": []}
        for query in unify_query_config["query_list"]:
            functions = []
            dimensions = []
            method = ""
            # 函数参数解析
            for function in query.get("function") or []:
                if function["method"] in cls.aggr_ops:
                    method = function["method"]
                    if method == "mean":
                        method = "avg"
                    method = method.upper()
                    dimensions = function.get("dimensions") or []
                else:
                    functions.append(
                        {
                            "id": function["method"],
                            "params": [
                                {"id": param.id, "value": str(value)}
                                for param, value in zip(
                                    Functions[function["method"]].params, function.get("vargs_list") or []
                                )
                            ],
                        }
                    )

            # 时间聚合方法解析
            time_function = query["time_aggregation"]
            if time_function:
                interval = cls.parse_time(time_function["window"])
                if time_function["function"].endswith("_over_time") and time_function["function"][:-10] in cls.aggr_ops:
                    method = time_function["function"][:-10].upper()
                else:
                    function = {
                        "id": time_function["function"],
                        "params": [
                            {"id": param.id, "value": str(value)}
                            for param, value in zip(
                                Functions[time_function["function"]].params, time_function.get("vargs_list") or []
                            )
                        ],
                    }
                    window = f"{interval // 60}m"
                    if interval % 60 != 0:
                        window += f"{interval % 60}s"
                    interval = interval // 2

                    function["params"].append({"id": "window", "value": window})
                    functions.append(function)
            else:
                interval = 60
                method = f"{method or 'avg'}_without_time".lower()

            # offset方法解析
            if query.get("offset"):
                time_shift_value = duration_string(parse_duration(query["offset"]))
                functions.append(
                    {
                        "id": "time_shift",
                        "params": [
                            {
                                "id": "n",
                                "value": "-" + time_shift_value if query.get("offset_forward") else time_shift_value,
                            }
                        ],
                    }
                )

            # 条件解析
            conditions = []
            for index, field in enumerate(query.get("conditions", {}).get("field_list", [])):
                condition = {
                    "key": field["field_name"],
                    "method": cls.condition_op_mapping[field["op"]],
                    "value": field["value"],
                }
                if index > 0:
                    condition["condition"] = "and"
                conditions.append(condition)

            # 根据table_id格式判定是否为data_label二段式, 如果是则需要根据data_label去指标选择器缓存表中查询结果表ID
            # 计算平台指标没有data_label，table_id 就直接是结果表ID result_table_id
            table_id = query.get("table_id", "")
            result_table_id = ""
            data_label = ""
            if len(table_id.split(".")) == 1 and query["data_source"] != "bkdata":
                data_label = table_id
            else:
                result_table_id = table_id
            if (result_table_id and cls.re_custom_time_series.match(result_table_id)) or query[
                "data_source"
            ] == DataSourceLabel.CUSTOM:
                data_source_label = DataSourceLabel.CUSTOM
            elif query["data_source"] == "bkdata":
                data_source_label = DataSourceLabel.BK_DATA
            else:
                data_source_label = DataSourceLabel.BK_MONITOR_COLLECTOR
            data_type_label = DataTypeLabel.TIME_SERIES
            # 根据data_label查找对应指标缓存结果表
            if not result_table_id:
                metric = MetricListCache.objects.filter(
                    bk_tenant_id=get_request_tenant_id(),
                    data_label=data_label,
                    data_source_label=data_source_label,
                    data_type_label=data_type_label,
                    metric_field=query["field_name"],
                ).first()
                if metric:
                    result_table_id = metric.result_table_id

            query_config = {
                "data_source_label": data_source_label,
                "data_type_label": data_type_label,
                "refId": query["reference_name"],
                "metric_id": get_metric_id(
                    data_source_label=data_source_label,
                    data_type_label=data_type_label,
                    metric_field=query["field_name"],
                    result_table_id=result_table_id,
                ),
                "functions": functions,
                "interval_unit": "s",
                "display": True,
                "filter_dict": {},
                "time_field": "",
            }

            if query_config_format == "strategy":
                query_config.update(
                    {
                        "result_table_id": result_table_id,
                        "data_label": data_label,
                        "agg_method": method,
                        "agg_interval": interval,
                        "agg_dimension": dimensions,
                        "agg_condition": conditions,
                        "metric_field": query["field_name"],
                        "alias": query["reference_name"],
                    }
                )
            else:
                query_config.update(
                    {
                        "result_table_id": result_table_id,
                        "data_label": data_label,
                        "method": method,
                        "interval": interval,
                        "group_by": dimensions,
                        "where": conditions,
                        "metric_field": query["field_name"],
                    }
                )

            config["query_configs"].append(query_config)
        return config

    def perform_request(self, params):
        promql = params["promql"]
        query_config_format = params["query_config_format"]
        try:
            origin_config = api.unify_query.promql_to_struct(promql=promql)["data"]
        except Exception:
            raise ValidationError(_("解析promql失败，请检查是否存在语法错误"))
        origin_config = self.check(origin_config)
        return self.convert_to_query_config(origin_config, query_config_format)


class ListIntelligentModelsResource(Resource):
    """
    获取模型列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        algorithm = serializers.ChoiceField(required=True, label="算法类型", choices=AlgorithmModel.AIOPS_ALGORITHMS)

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        algorithm = validated_request_data["algorithm"]
        plans = AlgorithmChoiceConfig.objects.filter(algorithm=algorithm)

        # 判断该算法是否在ai设置中，如果在ai设置中则需要挑选出开启默认配置的plan_id进行赋值
        default_plan_id = None
        if algorithm in AI_SETTING_ALGORITHMS:
            ai_setting = AiSetting(bk_biz_id=bk_biz_id)
            config = None
            is_enabled = False
            # 单指标异常检测，对应监控中的智能异常检测
            if algorithm == AlgorithmModel.AlgorithmChoices.IntelligentDetect:
                config = ai_setting.kpi_anomaly_detection
                is_enabled = True
            # 多指标异常检测
            elif algorithm == AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection:
                config = ai_setting.multivariate_anomaly_detection.host
                is_enabled = config.is_enabled

            # 判断如果如果是开启的话，从配置中拿到默认的plan_id
            if is_enabled:
                default_plan_id = config.to_dict().get("default_plan_id")

        model_list = []
        for plan in plans:
            if algorithm == AlgorithmModel.AlgorithmChoices.TimeSeriesForecasting and "hour" not in plan.name:
                # TODO: 时序预测目前只支持小时级别的模型
                continue
            model_list.append(
                {
                    "name": plan.alias,
                    "id": plan.id,
                    "document": plan.document,
                    "is_default": default_plan_id == plan.id if default_plan_id else plan.is_default,
                    "description": plan.description,
                    "ts_freq": plan.ts_freq,
                    "instruction": plan.instruction,
                }
            )
        # 默认is_default在最前面，除此外，按照ID降序排序
        model_list = sorted(model_list, key=lambda x: (not x["is_default"], int(x["id"])))
        return model_list


class GetIntelligentModelResource(Resource):
    """
    获取单个模型详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.CharField(required=True, label="模型ID")

    def perform_request(self, validated_request_data):
        plan_id = validated_request_data["id"]
        plan = AlgorithmChoiceConfig.objects.filter(id=plan_id).first()
        if not plan:
            raise ValidationError(_("未找到当前智能算法的方案配置，请联系系统管理员"))
        result = {
            "name": plan.alias,
            "id": plan.id,
            "document": plan.document,
            "description": plan.description,
            "ts_freq": plan.ts_freq,
            "instruction": plan.instruction,
            "args": plan.variable_info.get("parameter", []),
        }
        return result


class GetIntelligentModelTaskStatusResource(Resource):
    """
    获取应用模型结果表信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        result_table_id = serializers.CharField(required=True, label="结果表ID")

    def perform_request(self, validated_request_data):
        try:
            return api.bkdata.get_serving_result_table_info(result_table_id=validated_request_data["result_table_id"])
        except Exception as e:
            logger.error(
                "get intelligent model task status error: %s, result_table_id(%s)",
                e,
                validated_request_data["result_table_id"],
            )
            return {"status": "", "status_detail": ""}


class GetIntelligentDetectAccessStatusResource(Resource):
    """
    获取智能异常检测接入状态
    """

    class Status:
        WAITING = "waiting"
        RUNNING = "running"
        FAILED = "failed"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        strategy_id = serializers.IntegerField(required=True, label="策略ID")

    def perform_request(self, params):
        try:
            strategy = StrategyModel.objects.get(bk_biz_id=params["bk_biz_id"], id=params["strategy_id"])
        except StrategyModel.DoesNotExist:
            raise ValidationError(_("策略({})不存在)".format(params["strategy_id"])))

        result = {
            "status": self.Status.FAILED,
            "status_detail": _("该策略未接入智能异常检测，请确认"),
            "flow_id": 0,
            "message": "",
            "result_table_id": "",
        }

        strategy_obj = Strategy.from_models([strategy])[0]

        if not settings.IS_ACCESS_BK_DATA:
            return result

        intelligent_detect_config = None

        for query_config in chain(*[item.query_configs for item in strategy_obj.items]):
            if query_config.data_type_label not in (DataTypeLabel.TIME_SERIES, DataTypeLabel.EVENT, DataTypeLabel.LOG):
                continue

            intelligent_detect_config = getattr(query_config, "intelligent_detect", None)

        # 使用SDK检测的策略状态默认是运行中
        if intelligent_detect_config.get("use_sdk", False):
            result["status"] = AccessStatus.RUNNING
            result["status_detail"] = None
            return result

        algorithm_name = None
        for algorithm in chain(*[item.algorithms for item in strategy_obj.items]):
            algorithm_type = algorithm.type
            if algorithm_type not in AlgorithmModel.AIOPS_ALGORITHMS:
                continue
            algorithm_name = dict(AlgorithmModel.ALGORITHM_CHOICES)[algorithm_type]
            break

        if not intelligent_detect_config or not algorithm_name:
            return result

        result["message"] = intelligent_detect_config.get("message", "")

        access_status = intelligent_detect_config.get("status", "")

        access_status_mapping = {
            "": {
                "status": self.Status.FAILED,
                "status_detail": _("{}接入任务未创建，请尝试重新保存策略，若问题仍然存在请联系系统管理员").format(
                    algorithm_name
                ),
            },
            AccessStatus.PENDING: {
                "status": self.Status.WAITING,
                "status_detail": _("{}接入任务等待创建中，预计10分钟生效，如超过30分钟未生效请联系系统管理员").format(
                    algorithm_name
                ),
            },
            AccessStatus.CREATED: {
                "status": self.Status.WAITING,
                "status_detail": _("{}接入任务创建中，预计10分钟生效，如超过30分钟未生效请联系系统管理员").format(
                    algorithm_name
                ),
            },
            AccessStatus.RUNNING: {
                "status": self.Status.WAITING,
                "status_detail": _("{}接入中，预计10分钟生效，如超过30分钟未生效请联系系统管理员").format(
                    algorithm_name
                ),
            },
            AccessStatus.FAILED: {
                "status": self.Status.FAILED,
                "status_detail": _("{}接入失败，请联系系统管理员").format(algorithm_name),
            },
        }

        # 如果 flow status 不是 success 的话，那么问题就出在监控这边
        if access_status != AccessStatus.SUCCESS:
            result.update(access_status_mapping[access_status])
            return result

        # 如果 AccessStatus 是 SUCCESS 的话，说明 flow 肯定是创建好了。接下来就看 flow 的状态
        flow_id = intelligent_detect_config["data_flow_id"]
        result["flow_id"] = flow_id

        flow = api.bkdata.get_data_flow(flow_id=flow_id)

        flow_status = ""

        if flow:
            flow_status = flow["status"]

        flow_status_mapping = {
            "": {
                "status": self.Status.FAILED,
                "status_detail": _("未创建，请尝试重新保存策略，若问题仍然存在请联系系统管理员"),
            },
            DataFlow.Status.NoStart: {"status": self.Status.FAILED, "status_detail": _("未启动，请重新保存策略")},
            DataFlow.Status.Starting: {"status": self.Status.WAITING, "status_detail": _("启动中，预计10分钟内生效")},
            DataFlow.Status.Warning: {"status": self.Status.FAILED, "status_detail": _("运行异常，请联系系统管理员")},
            DataFlow.Status.Failure: {"status": self.Status.FAILED, "status_detail": _("运行失败，请联系系统管理员")},
            DataFlow.Status.Stopping: {"status": self.Status.FAILED, "status_detail": _("重启中，预计10分钟内生效")},
        }

        # 如果 flow status 不是 SUCCESS 的话，那么问题就出在 flow 这边，要找计算平台一起看
        if flow_status != DataFlow.Status.Running:
            result.update(flow_status_mapping[flow_status])
            result["status_detail"] = f"Dataflow ({flow_id}) {result['status_detail']}"
            return result

        result_table_id = intelligent_detect_config["result_table_id"]
        result["result_table_id"] = result_table_id

        try:
            table_info = api.bkdata.get_serving_result_table_info(result_table_id=result_table_id)
            result["status"] = table_info["status"]
            result["status_detail"] = table_info["status_detail"]
        except Exception as e:
            logger.error(
                "get intelligent model task status error: %s, result_table_id(%s)",
                e,
                result_table_id,
            )
            result["status"] = self.Status.FAILED
            result["message"] = str(e)
        return result


class UpdateMetricListByBizResource(Resource):
    """
    按业务更新指标缓存列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        # 查询该任务是否已有执行任务
        try:
            config = ApplicationConfig.objects.get(
                cc_biz_id=validated_request_data["bk_biz_id"],
                key=f"{validated_request_data['bk_biz_id']}_update_metric_cache",
            )
            if arrow.get(time.time()).timestamp - arrow.get(config.data_updated).timestamp > 20 * 60:
                task_result = update_metric_list_by_biz.apply_async(
                    args=(validated_request_data["bk_biz_id"],), expires=20 * 60
                )
                config.value = task_result.task_id
                config.save()
        except ApplicationConfig.DoesNotExist:
            task_result = update_metric_list_by_biz.apply_async(
                args=(validated_request_data["bk_biz_id"],), expires=20 * 60
            )
            config = ApplicationConfig.objects.create(
                cc_biz_id=validated_request_data["bk_biz_id"],
                key=f"{validated_request_data['bk_biz_id']}_update_metric_cache",
                value=task_result.task_id,
            )
        return config.value


class GetDevopsStrategyListResource(Resource):
    """
    蓝盾插件专用策略列表接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def perform_request(self, params: dict[str, str]) -> dict[str, Any]:
        # bk_biz_id 必须是数字
        try:
            bk_biz_id = int(params["bk_biz_id"])
        except (ValueError, TypeError):
            return {"result": False, "status": 1, "data": [], "message": "bk_biz_id必须是数字"}

        # bk_biz_id 不能为0
        if bk_biz_id == 0:
            return {"result": False, "status": 1, "data": [], "message": "bk_biz_id不能为0"}

        # 用户名不能为空
        username = get_request_username()
        if not username:
            return {"result": False, "status": 1, "data": [], "message": "无法获取当前用户"}

        # 检查用户是否有权限访问指定业务
        p = Permission(username=username, bk_tenant_id=get_request_tenant_id())
        # 强制检查权限
        p.skip_check = False
        if not p.is_allowed_by_biz(bk_biz_id, ActionEnum.VIEW_RULE):
            return {"result": False, "status": 1, "data": [], "message": f"当前用户无权限查看{bk_biz_id}业务策略列表"}

        # 获取指定业务下启用的策略
        strategies = StrategyModel.objects.filter(bk_biz_id=bk_biz_id).values("id", "name").order_by("-update_time")
        strategy_list: list = [
            {"optionId": str(strategy["id"]), "optionName": strategy["name"]} for strategy in strategies
        ]
        return {"result": True, "status": 0, "data": strategy_list, "message": "success"}
