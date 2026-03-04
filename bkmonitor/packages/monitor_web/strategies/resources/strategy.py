import logging
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import reduce
from itertools import chain, product, zip_longest
from typing import Any, cast

import arrow
from bk_monitor_base.strategy import (
    AlgorithmSerializer,
    FilterCondition,
    QueryConfigSerializerMapping,
    StrategyQueryEngine,
    StrategySerializer,
    delete_strategies,
    get_metric_id,
    get_strategy,
    list_plain_strategy,
    list_strategy,
    parse_metric_id,
    save_strategy,
    update_partial_strategy,
)
from django.conf import settings
from django.db.models import Count, Q, QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.cmdb.define import Host, Module, Set, TopoTree
from bkm_ipchooser.handlers import template_handler
from bkmonitor.action.utils import get_strategy_user_group_dict
from bkmonitor.aiops.utils import AiSetting
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import Functions, UnifyQuery, load_data_source
from bkmonitor.dataflow.constant import AI_SETTING_ALGORITHMS, AccessStatus
from bkmonitor.dataflow.flow import DataFlow
from bkmonitor.documents import AlertDocument
from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.permission import Permission
from bkmonitor.models import (
    ActionConfig,
    AlgorithmModel,
    DetectModel,
    ItemModel,
    MetricListCache,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyLabel,
    StrategyModel,
    UserGroup,
)
from bkmonitor.models.strategy import AlgorithmChoiceConfig
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.request import get_request_tenant_id, get_request_username, get_source_app
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.time_format import duration_string, parse_duration
from bkmonitor.utils.user import get_global_user
from common.decorators import db_safe_wrapper
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
from monitor_web.models import CustomEventGroup, CustomTSTable, DataTargetMapping
from monitor_web.shield.utils import ShieldDetectManager
from monitor_web.strategies.constant import DEFAULT_TRIGGER_CONFIG_MAP, GLOBAL_TRIGGER_CONFIG
from monitor_web.strategies.serializers import handle_target
from monitor_web.tasks import update_metric_list_by_biz
from utils.strategy import fill_user_groups

logger = logging.getLogger(__name__)


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

    @staticmethod
    def _normalize_v2_condition_value(value: Any) -> list[Any]:
        """按 v2 语义规范化条件 value。

        Notes:
            - 兼容 v2 入参：非 list -> 包装成 list
            - 单元素 list 支持 `"a | b"` 拆分为多值
        """
        if not isinstance(value, list):
            values: list[Any] = [value]
        else:
            values = value
        if len(values) == 1:
            values = [i.strip() for i in str(values[0]).split(" | ") if i.strip()]
        return values

    @classmethod
    def _convert_v2_conditions_to_filterspec(
        cls, *, bk_biz_id: int, conditions: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, list[Any]]]:
        """将 v2 `conditions=[{\"key\":...,\"value\":...}]` 转换为 base `FilterSpec` 风格条件。

        Returns:
            - engine_conditions: 可直接用于 `StrategyQueryEngine.filter_strategies` 的条件列表（不含 scenario/ip/status 等）
            - heavy_values: heavy 条件原始值（用于外层先按现网逻辑解析，再降维为 id 过滤）
        """
        # 复用 v2 现有 field_mapping（保持与旧版 `filter_by_conditions` 一致：仅做 key 映射，不额外扩展操作符能力）
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

        # 先聚合：同一 key 的 value 合并（保持旧版 v2 “多条件可叠加”为同一维度多值”）
        #
        # 重要：旧版 `filter_by_conditions` 并不会通用解析 `__suffix`（例如 name__and / result_table_id__icontains），
        # 这些后缀 key 在旧版中通常“不生效”。唯一例外是 `source` 过滤（支持 source/source__in/source__neq），
        # 因此此处仅保留 source 的后缀语义，其余带 `__suffix` 的 key 直接忽略，避免引入新功能导致语义变化。
        grouped: defaultdict[str, list[Any]] = defaultdict(list)
        source_condition: tuple[str, list[Any]] | None = None  # (operator, values)
        for condition in conditions or []:
            raw_key = str(condition.get("key", "")).strip().lower()
            if not raw_key:
                continue

            values = cls._normalize_v2_condition_value(condition.get("value"))

            # 仅保留旧版 source 的后缀语义（source/source__in/source__neq）
            if raw_key.startswith("source"):
                if source_condition is not None:
                    # 旧版实现对 source 仅会取一个 key（按字典遍历顺序的第一个），后续同类 key 不生效；
                    # 这里也只采纳第一条 source 相关条件，避免扩展语义。
                    continue
                if "__" not in raw_key:
                    source_condition = ("eq", values)
                    continue
                _, suffix = raw_key.split("__", 1)
                if suffix in {"in"}:
                    source_condition = ("eq", values)
                    continue
                if suffix == "neq":
                    source_condition = ("neq", values)
                    continue
                # 旧版对 source 其他后缀会将候选集收敛为空（不支持的操作）
                source_condition = ("__unsupported__", values)
                continue

            # 其它 key：带 `__suffix` 的一律忽略（旧版不支持），避免引入新功能
            if "__" in raw_key:
                continue

            mapped_key = field_mapping.get(raw_key, raw_key)
            grouped[mapped_key].extend(values)

        heavy_values: dict[str, list[Any]] = {"ip": [], "bk_cloud_id": [], "strategy_status": []}
        engine_conditions: list[dict] = []

        # === heavy/特殊条件收集（外层解析）===
        for k, values in list(grouped.items()):
            if k in {"ip", "bk_cloud_id", "strategy_status"}:
                heavy_values[k].extend(values)
                grouped.pop(k, None)

        # === plugin_id：转换为 result_table_id startswith `<plugin_id>.` ===
        for k, values in list(grouped.items()):
            if k != "plugin_id":
                continue
            prefixes = [f"{str(v).strip()}." for v in values if str(v).strip()]
            if prefixes:
                engine_conditions.append({"key": "result_table_id", "values": prefixes, "operator": "startswith"})
            grouped.pop(k, None)

        # === metric_field_name：沿用现网 MetricListCache，将别名映射为 metric_field，再降维为 metric_field 条件 ===
        for k, values in list(grouped.items()):
            if k != "metric_field_name":
                continue
            aliases = [str(v) for v in values if str(v).strip()]
            if aliases:
                metric_qs = MetricListCache.objects.filter(
                    bk_tenant_id=get_request_tenant_id(),
                    metric_field_name__in=aliases,
                )
                metric_qs = metric_qs.filter(bk_biz_id__in=[0, bk_biz_id])
                metric_fields = list(metric_qs.values_list("metric_field", flat=True).distinct())
                if metric_fields:
                    engine_conditions.append({"key": "metric_field", "values": metric_fields, "operator": "eq"})
                else:
                    # 传了别名但无法解析：与 v2 “无匹配”一致，直接收敛为空
                    engine_conditions.append({"key": "id", "values": [0], "operator": "eq"})
            grouped.pop(k, None)

        # === 自定义分组：沿用现网模型解析为 table_id，再降维为 result_table_id 条件 ===
        # custom_event_group_id / bk_event_group_id -> CustomEventGroup.table_id
        for group_key in ("custom_event_group_id", "bk_event_group_id"):
            values = []
            for k, vlist in list(grouped.items()):
                if k == group_key:
                    values.extend(vlist)
                    grouped.pop(k, None)
            group_ids = [str(v) for v in values if str(v).strip()]
            if group_ids:
                event_qs = CustomEventGroup.objects.filter(bk_event_group_id__in=group_ids, bk_biz_id=bk_biz_id)
                table_ids = list(event_qs.values_list("table_id", flat=True).distinct())
                if table_ids:
                    engine_conditions.append({"key": "result_table_id", "values": table_ids, "operator": "eq"})
                else:
                    engine_conditions.append({"key": "id", "values": [0], "operator": "eq"})

        # time_series_group_id -> CustomTSTable.table_id
        values = []
        for k, vlist in list(grouped.items()):
            if k == "time_series_group_id":
                values.extend(vlist)
                grouped.pop(k, None)
        ts_group_ids = [str(v) for v in values if str(v).strip()]
        if ts_group_ids:
            ts_qs = CustomTSTable.objects.filter(time_series_group_id__in=ts_group_ids, bk_biz_id=bk_biz_id)
            table_ids = list(ts_qs.values_list("table_id", flat=True).distinct())
            if table_ids:
                engine_conditions.append({"key": "result_table_id", "values": table_ids, "operator": "eq"})
            else:
                engine_conditions.append({"key": "id", "values": [0], "operator": "eq"})

        # === data_source：旧版 v2 传的是 DATA_CATEGORY.type（如 custom_time_series），需要映射为 `<ds>|<dt>` ===
        #
        # QueryEngine 的 data_source 解析规则是 `<data_source_label>|<data_type_label>` 或 `<ds>,<dt>`；
        # 如果直接把 `custom_time_series` 传入，会解析失败并导致过滤异常（常见表现：无结果/不符合预期）。
        #
        # 这里优先按 DATA_CATEGORY 做“权威映射”；兜底支持按最后一个 `_` 拆分。
        ds_pairs: list[str] = []
        ds_raw_values = grouped.pop("data_source", [])
        if ds_raw_values:
            type_to_pair = {ds["type"]: (ds["data_source_label"], ds["data_type_label"]) for ds in DATA_CATEGORY}
            for raw in ds_raw_values:
                s = str(raw).strip()
                if not s:
                    continue
                if "|" in s or "," in s:
                    ds_pairs.append(s)
                    continue
                if s in type_to_pair:
                    ds_label, dt_label = type_to_pair[s]
                    ds_pairs.append(f"{ds_label}|{dt_label}")
                    continue
                # 兜底：按最后一个 `_` 拆分（兼容少量不在 DATA_CATEGORY 的组合值）
                if "_" in s:
                    left, right = s.rsplit("_", 1)
                    if left and right:
                        ds_pairs.append(f"{left}|{right}")
                        continue
                ds_pairs.append(s)
        if ds_pairs:
            grouped["data_source"] = ds_pairs

        # === 其余条件：转换为 base FilterSpec ===
        for key, values in grouped.items():
            if not values:
                continue

            if key == "name":
                # 旧版 v2：仅支持 name icontains（多值 OR）
                engine_conditions.append({"key": "name", "values": values, "operator": "icontains"})
                continue

            if key == "user_group_name":
                # 旧版 v2：UserGroup.name__contains，多值 OR
                engine_conditions.append(
                    {"key": "user_group_name", "values": [str(v) for v in values], "operator": "contains"}
                )
                continue

            if key == "action_name":
                # 旧版 v2：ActionConfig.name__contains，多值 OR；特殊语义（空串 => without_actions）由引擎处理
                engine_conditions.append({"key": "action_name", "values": values, "operator": "eq"})
                continue

            # 其它字段：旧版 v2 都是精确匹配维度（IN/OR），统一交给 base 引擎按 eq 处理
            engine_conditions.append({"key": key, "values": values, "operator": "eq"})

        # source 条件（唯一保留 `__suffix` 语义的 key）
        if source_condition is not None:
            op, values = source_condition
            if op == "__unsupported__":
                engine_conditions.append({"key": "id", "values": [0], "operator": "eq"})
            else:
                engine_conditions.append({"key": "source", "values": values, "operator": op})

        return engine_conditions, heavy_values

    def _empty_response(self) -> dict[str, Any]:
        """空响应"""
        return {
            "scenario_list": [],
            "strategy_config_list": [],
            "data_source_list": [],
            "strategy_label_list": [],
            "strategy_status_list": [],
            "user_group_list": [],
            "action_config_list": [],
            "alert_level_list": [],
            "invalid_type_list": [],
            "algorithm_type_list": [],
            "total": 0,
        }

    def filter_by_conditions(self, bk_biz_id: int, conditions: list[dict]) -> set[int]:
        engine_conditions, heavy_values = self._convert_v2_conditions_to_filterspec(
            bk_biz_id=bk_biz_id, conditions=conditions
        )
        # 先用 base 查询引擎完成“核心条件交集”（不含 scenario/ip/status）
        core_qs = StrategyQueryEngine.filter_strategies(
            bk_biz_id, conditions=cast(list[FilterCondition], engine_conditions)
        )
        candidates: set[int] = set(core_qs.values_list("id", flat=True).distinct())
        if not candidates:
            return candidates

        # heavy：strategy_status（ALERT/SHIELDED/ON/OFF/INVALID）仍按现网实现解析为 id 再收敛
        status_values = [str(v).upper() for v in heavy_values.get("strategy_status", []) if str(v).strip()]
        if status_values:
            status_hit: set[int] = set()
            for s in status_values:
                status_hit.update(self.filter_by_status(s, filter_strategy_ids=list(candidates), bk_biz_id=bk_biz_id))
            candidates &= status_hit
            if not candidates:
                return candidates

        # heavy：ip/bk_cloud_id 仍按现网实现解析为 id 再收敛
        ip_values = [str(v) for v in heavy_values.get("ip", []) if str(v).strip()]
        if ip_values:
            bk_cloud_values: list[int] = []
            for v in heavy_values.get("bk_cloud_id", []):
                try:
                    bk_cloud_values.append(int(v))
                except (TypeError, ValueError):
                    continue
            ips = []
            if bk_cloud_values:
                for ip, bk_cloud_id in product(ip_values, bk_cloud_values):
                    ips.append({"ip": ip, "bk_cloud_id": bk_cloud_id})
            else:
                ips = [{"ip": ip} for ip in ip_values]

            ip_qs = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=candidates)
            ip_qs = self.filter_by_ip(ips=ips, strategies=ip_qs, bk_biz_id=bk_biz_id)
            candidates &= set(ip_qs.values_list("id", flat=True).distinct())

        return candidates

    def add_scenario_condition(self, conditions: list[dict[str, Any]], scenario: str | None) -> list[dict[str, Any]]:
        """
        将场景条件添加到条件列表中
        """
        # 如果没有场景条件，则直接返回原条件列表
        if not scenario:
            return conditions

        new_conditions: list[dict[str, Any]] = []
        for condition in conditions:
            if condition.get("key") == "scenario":
                new_conditions.append({"key": "scenario", "values": [scenario], "operator": "eq"})
            else:
                new_conditions.append(condition)
        return new_conditions

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_biz_id = validated_request_data["bk_biz_id"]
        conditions: list[dict] = validated_request_data.get("conditions") or []

        # 添加场景条件
        conditions = self.add_scenario_condition(conditions, validated_request_data.get("scenario"))

        # 条件过滤，返回策略ID集合
        candidates = self.filter_by_conditions(bk_biz_id=bk_biz_id, conditions=conditions)
        if not candidates:
            return self._empty_response()

        # 构造 bkmonitor 侧 queryset 以复用现网 facet 统计逻辑
        strategies = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=candidates)

        # 在过滤监控对象前统计数量（facet）
        scenario_list = self.get_scenario_list(strategies)

        # 统计其他分类数量（基于最终筛选结果，包含场景选择）
        all_strategy_ids = list(strategies.values_list("id", flat=True).distinct())

        executor = ThreadPoolExecutor()
        user_group_list_future = executor.submit(db_safe_wrapper(self.get_user_group_list), all_strategy_ids, bk_biz_id)
        action_config_list_future = executor.submit(
            db_safe_wrapper(self.get_action_config_list), all_strategy_ids, bk_biz_id
        )
        data_source_list_future = executor.submit(db_safe_wrapper(self.get_data_source_list), all_strategy_ids)
        strategy_label_list_future = executor.submit(
            db_safe_wrapper(self.get_strategy_label_list), all_strategy_ids, bk_biz_id
        )
        strategy_status_list_future = executor.submit(
            db_safe_wrapper(self.get_strategy_status_list), all_strategy_ids, bk_biz_id
        )
        alert_level_list_future = executor.submit(db_safe_wrapper(self.get_alert_level_list), all_strategy_ids)
        invalid_type_list_future = executor.submit(db_safe_wrapper(self.get_invalid_type_list), all_strategy_ids)
        algorithm_type_list_future = executor.submit(db_safe_wrapper(self.get_algorithm_type_list), all_strategy_ids)

        # 分页计算
        offset, limit = 0, None
        page, page_size = validated_request_data.get("page"), validated_request_data.get("page_size")
        if page and page_size:
            offset = (page - 1) * page_size
            limit = page * page_size

        # 生成策略配置
        strategies_result = list_strategy(
            bk_biz_id=bk_biz_id,
            conditions=[{"key": "id", "values": list(candidates), "operator": "eq"}],
            offset=offset,
            limit=limit,
        )
        strategy_configs = strategies_result["data"]
        total = strategies_result["count"]

        # 补充告警组信息
        if validated_request_data["with_user_group"]:
            fill_user_groups(strategy_configs, validated_request_data["with_user_group_detail"])

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

    def perform_request(self, validated_request_data: dict[str, Any]):
        strategy = get_strategy(bk_biz_id=validated_request_data["bk_biz_id"], strategy_id=validated_request_data["id"])
        # 补充告警组配置
        fill_user_groups([strategy])
        return strategy


class PlainStrategyListResource(Resource):
    """获取轻量的策略列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        ids = serializers.ListField(
            label=_("策略 ID 列表"), child=serializers.IntegerField(min_value=1), default=[], allow_empty=True
        )

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
        strategies = list_plain_strategy(
            bk_biz_id=validated_request_data["bk_biz_id"], strategy_ids=validated_request_data["ids"]
        )

        # 获取分类标签
        labels = resource.commons.get_label()
        strategy_list = []
        for strategy in strategies["data"]:
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

    def perform_request(self, validated_request_data: dict[str, Any]):
        strategy_ids = validated_request_data["ids"]
        return delete_strategies(validated_request_data["bk_biz_id"], strategy_ids, operator=get_request_username())


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

        if metric["data_type_label"] != "event" or metric["data_source_label"] != "bk_monitor":
            return []

        if metric["metric_field"] == "disk-full-gse":
            return [
                _("依赖bkmonitorbeat采集器, 在节点管理安装"),
            ]
        elif metric["metric_field"] == "disk-readonly-gse":
            return [
                _("依赖bkmonitorbeat采集器, 在节点管理安装"),
                _("通过对挂载磁盘的文件状态ro进行判断，类似Linux命令：fgrep ' ro,' /proc/mounts"),
            ]
        elif metric["metric_field"] == "corefile-gse":
            return [
                _(
                    "查看corefile生成路径：cat /proc/sys/kernel/core_pattern，确保在某一个目录下，例如 /data/corefile/core_%e_%t"
                ),
                _("依赖bkmonitorbeat采集器, 在节点管理安装,会自动根据core_pattern监听文件目录"),
            ]
        elif metric["metric_field"] == "gse_custom_event":
            return [
                _("【已废弃】"),
                _("功能通过上报 自定义事件 覆盖").format(
                    settings.LINUX_GSE_AGENT_PATH, settings.GSE_CUSTOM_EVENT_DATAID
                ),
            ]
        elif metric["metric_field"] == "agent-gse":
            return [_("gse每隔60秒检查一次agent心跳数据。"), _("心跳数据持续未更新，24小时后将不再上报失联事件。")]
        elif metric["metric_field"] == "oom-gse":
            return [
                _("通过调用内核syslog接口获取系统日志，对out of memory:关键字匹配告警，应用进程触发的OOM告警"),
                _("通过对/proc/vmstat的oom_kill计数器进行判断告警，如递增则判断产生OOM告警，操作系统触发的OOM告警"),
            ]
        elif metric["metric_field"] == "os_restart":
            return [
                _("依赖bkmonitorbeat采集器的安装 ，在节点管理进行安装"),
                _("检测原理：通过最近2次的uptime数据对比，满足cur_uptime < pre_uptime，则判断为重启"),
            ]
        elif metric["metric_field"] == "ping-gse":
            return [
                _("依赖bk-collector采集器的安装，在节点管理进行安装"),
                _("由监控后台部署的bk-collector去探测目标IP是否存活。"),
            ]
        elif metric["metric_field"] == "proc_port":
            return [
                _("依赖bkmonitorbeat采集器的安装，在节点管理进行安装"),
                _("对CMDB中的进程端口存活状态判断，如不满足预定义数据状态，则产生告警"),
            ]

        return []

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

        strategies_result = list_strategy(
            bk_biz_id=params["bk_biz_id"],
            conditions=[{"key": "id", "values": strategy_ids, "operator": "eq"}],
        )
        strategies = strategies_result["data"]
        metric_id_by_strategy = {}
        for strategy in strategies:
            for query_config in strategy["items"][0]["query_configs"]:
                if (query_config["data_source_label"], query_config["data_type_label"]) != (
                    DataSourceLabel.BK_MONITOR_COLLECTOR,
                    DataTypeLabel.ALERT,
                ):
                    metric_id_by_strategy[strategy["id"]] = query_config["metric_id"]

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

        def validate(self, attrs: dict[str, Any]):
            result = list_plain_strategy(bk_biz_id=attrs["bk_biz_id"], search=attrs["name"])

            # 如果策略不存在，则直接返回
            if not result["data"]:
                return super().validate(attrs)

            strategy_id = result["data"][0]["id"]
            strategy_name = result["data"][0]["name"]

            # 如果存在同名策略且策略ID不相同，则抛出策略名称已存在异常
            if strategy_id != attrs["id"] and strategy_name == attrs["name"]:
                raise StrategyNameExist(name=attrs["name"])

            return super().validate(attrs)

    def perform_request(self, validated_request_data: dict[str, Any]):
        return "ok"


class BulkSwitchStrategyResource(Resource):
    """
    批量启停特定标签的策略(目前仅在kernel_api中使用, 为BCS内置策略专门开发)
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        labels = serializers.ListField(required=True, child=serializers.CharField())
        action = serializers.ChoiceField(required=True, label="操作类型", choices=("on", "off"))
        force = serializers.BooleanField(label="是否强制操作", default=False)

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_biz_id = validated_request_data["bk_biz_id"]

        # 过滤策略标签
        conditions: list[FilterCondition] = [
            {"key": "label", "values": validated_request_data["labels"], "operator": "eq"},
        ]

        # 默认只更新创建后未修改过的策略
        if not validated_request_data["force"]:
            conditions.append({"key": "updated_after_create", "values": [False], "operator": "eq"})

        qs = StrategyQueryEngine.filter_strategies(bk_biz_id, conditions=conditions)
        target_ids = set(qs.values_list("id", flat=True).distinct())
        if not target_ids:
            return []

        # 更新策略启停状态
        update_params = {
            "ids": list(target_ids),
            "edit_data": {"is_enabled": validated_request_data["action"] == "on"},
            "bk_biz_id": bk_biz_id,
        }
        return resource.strategies.update_partial_strategy_v2(**update_params)


class SaveStrategyV2Resource(Resource):
    """
    保存策略
    """

    RequestSerializer = StrategySerializer

    @classmethod
    def validate_cmdb_level(cls, strategy: dict[str, Any]):
        """
        校验cmdb节点聚合配置是否合法
        """
        metric_count = len(strategy["items"][0]["query_configs"])

        # 单指标一定合法
        if metric_count == 1:
            return

        for item in strategy["items"]:
            for query_config in item["query_configs"]:
                if (query_config["data_source_label"], query_config["data_type_label"]) != (
                    DataSourceLabel.BK_MONITOR_COLLECTOR,
                    DataTypeLabel.TIME_SERIES,
                ):
                    continue

                used_dimensions = set(query_config.get("agg_dimension", []))
                agg_condition = query_config.get("agg_condition", [])

                for c in agg_condition:
                    used_dimensions.add(c["key"])

                if used_dimensions & set(SPLIT_DIMENSIONS):
                    raise CmdbLevelValidateError()

    @classmethod
    def validate_realtime_kafka(cls, strategy: dict[str, Any]):
        """
        校验实时策略对应插件的kafka存储是否存在
        """
        is_realtime_table_id = []
        for item in strategy["items"]:
            for query_config in item["query_configs"]:
                agg_method = query_config.get("agg_method", "")
                result_table_id = query_config.get("result_table_id", "")
                if agg_method == "REAL_TIME":
                    is_realtime_table_id.append(result_table_id)

        if is_realtime_table_id:
            api.metadata.check_or_create_kafka_storage(table_ids=is_realtime_table_id)

    @classmethod
    def validate_upgrade_user_groups(cls, strategy: dict[str, Any]):
        notice_info: dict[str, Any] = strategy["notice"]
        upgrade_config = notice_info.get("options", {}).get("upgrade_config", {})
        if not upgrade_config.get("is_enabled"):
            return
        if set(upgrade_config["user_groups"]) & set(notice_info["user_groups"]):
            raise ValidationError(detail=_("通知升级的用户组不能包含第一次接收告警的用户组"))

    def perform_request(self, validated_request_data: dict[str, Any]):
        operator = get_request_username()
        strategy = validated_request_data
        self.validate_realtime_kafka(strategy)
        self.validate_cmdb_level(strategy)
        self.validate_upgrade_user_groups(strategy)
        return save_strategy(bk_biz_id=validated_request_data["bk_biz_id"], strategy_json=strategy, operator=operator)


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
            algorithms = AlgorithmSerializer(many=True, required=False)

            def validate_target(self, target):
                if target and target[0]:
                    handle_target(target)
                return target

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        ids = serializers.ListField(required=True, label="批量修改的策略ID列表")
        edit_data = ConfigSerializer(required=True)

    def perform_request(self, validated_request_data: dict[str, Any]):
        return update_partial_strategy(
            bk_biz_id=validated_request_data["bk_biz_id"],
            ids=validated_request_data["ids"],
            edit_data=validated_request_data["edit_data"],
            operator=get_global_user() or "unknown",
        )


class GetTargetDetailWithCache(CacheResource):
    """获取监控目标详情，具有缓存功能"""

    backend_cache_type = CacheType.CC_CACHE_ALWAYS
    cache_user_related = False

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        strategy_id = serializers.IntegerField(required=True, label="策略ID")

    def perform_request(self, validated_request_data: dict[str, Any]):
        """
        为了获取最佳的性能，在执行request()方法之前，请先执行set_mapping()方法，传入策略和监控目标的映射关系字典，以避免频繁查询数据库。
        并且请显示使用instance.request()的方式执行perform_request，而非使用instance()方式，
        使用instance()方式执行时会重新实例化，导致先前执行的set_mapping失效。

        example:
            >>instance = GetTargetDetailWithCache()
            >>instance.set_mapping({xxx})
            >>instance.request(xxx)
        """

        strategy_id = validated_request_data["strategy_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        if not hasattr(self, "strategy_target_mapping"):
            strategy = get_strategy(bk_biz_id=bk_biz_id, strategy_id=strategy_id)
            target = strategy["items"][0]["target"]
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
                info = get_target_detail_with_cache.request.refresh(
                    {"bk_biz_id": bk_biz_id, "strategy_id": item.strategy_id}
                )
            else:
                info = get_target_detail_with_cache.request({"bk_biz_id": bk_biz_id, "strategy_id": item.strategy_id})

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

    def perform_request(self, validated_request_data: dict[str, Any]):
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

                serializer_class = QueryConfigSerializerMapping.get(data_source)
                if not serializer_class:
                    raise ValidationError(f"not support data_source({data_source})")
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

    def perform_request(self, validated_request_data: dict[str, Any]):
        data_sources = []
        data_source_label = "bkmonitor"
        data_source_label_mapping = {
            "bk_monitor": "bkmonitor",
            "custom": "custom",
            "bk_data": "bkdata",
            "bk_log_search": "bklog",
        }
        for query_config in validated_request_data["query_configs"]:
            data_source_label = data_source_label_mapping.get(query_config["data_source_label"], data_source_label)
            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            init_params = dict(query_config=query_config)
            init_params.update({"bk_biz_id": validated_request_data["bk_biz_id"]})
            data_sources.append(data_source_class.init_by_query_config(**init_params))

        # 构造统一查询配置
        query = UnifyQuery(
            bk_biz_id=validated_request_data["bk_biz_id"],
            data_sources=data_sources,
            expression=validated_request_data["expression"],
        )
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

    def perform_request(self, validated_request_data: dict[str, Any]) -> list[dict[str, Any]]:
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        algorithm: str = validated_request_data["algorithm"]
        plans: QuerySet[AlgorithmChoiceConfig] = AlgorithmChoiceConfig.objects.filter(algorithm=algorithm)

        # 判断该算法是否在ai设置中，如果在ai设置中则需要挑选出开启默认配置的plan_id进行赋值
        default_plan_id: int | None = None
        if algorithm in AI_SETTING_ALGORITHMS:
            ai_setting = AiSetting(bk_biz_id=bk_biz_id)
            config: Any = None
            is_enabled: bool = False
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

        model_list: list[dict[str, Any]] = []
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
            StrategyModel.objects.get(bk_biz_id=params["bk_biz_id"], id=params["strategy_id"])
        except StrategyModel.DoesNotExist:
            raise ValidationError(_("策略({})不存在)".format(params["strategy_id"])))

        result = {
            "status": self.Status.FAILED,
            "status_detail": _("该策略未接入智能异常检测，请确认"),
            "flow_id": 0,
            "message": "",
            "result_table_id": "",
        }

        strategy_config: dict[str, Any] = get_strategy(params["bk_biz_id"], params["strategy_id"])

        if not settings.IS_ACCESS_BK_DATA:
            return result

        intelligent_detect_config: dict[str, Any] = {}
        for query_config in chain(*[item["query_configs"] for item in strategy_config["items"]]):
            data_type_label: str | None = query_config.get("data_type_label")
            if data_type_label not in (DataTypeLabel.TIME_SERIES, DataTypeLabel.EVENT, DataTypeLabel.LOG):
                continue
            intelligent_detect_config = query_config.get("intelligent_detect", {})

        # 使用SDK检测的策略状态默认是运行中
        if intelligent_detect_config.get("use_sdk", False):
            result["status"] = AccessStatus.RUNNING
            result["status_detail"] = None
            return result

        algorithm_name: str | None = None
        for algorithm in chain(*[item["algorithms"] for item in strategy_config["items"]]):
            algorithm_type: str = algorithm["type"]
            if algorithm_type not in AlgorithmModel.AIOPS_ALGORITHMS:
                continue
            algorithm_name = str(dict(AlgorithmModel.ALGORITHM_CHOICES)[algorithm_type])
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
            flow_status: str = flow["status"]

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

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        # bk_biz_id 必须是数字
        try:
            bk_biz_id = int(validated_request_data["bk_biz_id"])
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
