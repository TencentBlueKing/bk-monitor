"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import chain, groupby
from operator import itemgetter
from typing import Any
from collections.abc import Callable, Iterable

import arrow
from django.conf import settings

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.cache.cmdb import (
    BusinessManager,
    ServiceTemplateManager,
    SetTemplateManager,
    TopoManager,
)
from alarm_backends.core.storage.redis import Cache
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.models import (
    AlgorithmModel,
    MetricListCache,
    StrategyHistoryModel,
    StrategyModel,
)
from bkmonitor.strategy.new_strategy import Strategy, parse_metric_id
from bkmonitor.utils.common_utils import chunks, count_md5
from bkmonitor.utils.kubernetes import is_k8s_target
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.cmdb import TargetNodeType
from constants.data_source import DataSourceLabel, DataTypeLabel, UnifyQueryDataSources
from constants.strategy import (
    AGG_METHOD_REAL_TIME,
    AdvanceConditionMethod,
    TargetFieldType,
)
from core.drf_resource import api
from core.prometheus import metrics
from core.unit import load_unit

logger = logging.getLogger("cache")


class StrategyCacheManager(CacheManager):
    """
    告警策略缓存
    """

    CACHE_TIMEOUT = CONST_ONE_DAY
    # 策略详情的缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".strategy_{strategy_id}"
    # 策略ID列表缓存key
    IDS_CACHE_KEY = CacheManager.CACHE_KEY_PREFIX + ".strategy_ids"
    # 业务ID列表缓存key
    BK_BIZ_IDS_CACHE_KEY = CacheManager.CACHE_KEY_PREFIX + ".bk_biz_ids"
    # real time 走实时数据相关的策略
    REAL_TIME_CACHE_KEY = CacheManager.CACHE_KEY_PREFIX + ".real_time_strategy_ids"
    # no data 策略
    NO_DATA_CACHE_KEY = CacheManager.CACHE_KEY_PREFIX + ".no_data_strategy_ids"
    # 启用 aiops sdk 策略
    AIOPS_SDK_CACHE_KEY = CacheManager.CACHE_KEY_PREFIX + ".aiops_sdk_strategy_ids"
    # gse事件
    GSE_ALARM_CACHE_KEY = CacheManager.CACHE_KEY_PREFIX + ".gse_alarm_strategy_ids"
    # 自愈关联告警策略
    FTA_ALERT_CACHE_KEY = CacheManager.CACHE_KEY_PREFIX + ".fta_alert_strategy_ids"
    # 策略分组
    STRATEGY_GROUP_CACHE_KEY = CacheManager.CACHE_KEY_PREFIX + ".strategy_group"
    # 最近增量更新时间
    LAST_UPDATED_CACHE_KEY = CacheManager.CACHE_KEY_PREFIX + ".last_updated"
    # 事件型时序检测周期(默认60s)
    fake_event_agg_interval = 60
    # 实例维度
    instance_dimensions = {"bk_target_ip", "bk_target_service_instance_id", "bk_host_id"}
    cache = Cache("cache-strategy")

    @classmethod
    def transform_template_to_topo_nodes(cls, target, template_node_type, cache_manager):
        """
        转化模板为节点
        :param target: 监控目标
        :param template_node_type: 模板类型，可选[SET_TEMPLATE, SERVICE_TEMPLATE]
        :param cache_manager: 模板缓存管理器
        :return: 修改target后的监控项, 模板失效标识
        """
        if template_node_type == TargetNodeType.SET_TEMPLATE:
            bk_obj_id = "set"
        else:
            bk_obj_id = "module"

        new_value = []
        if target["value"]:
            is_invalid_template = True
            for node in target["value"]:
                instances = cache_manager.get(node["bk_inst_id"])
                if instances:
                    is_invalid_template = False
                else:
                    instances = []
                for instance in instances:
                    new_value.append(
                        {
                            "bk_obj_id": bk_obj_id,
                            "bk_inst_id": instance
                            if isinstance(instance, int)
                            else instance["bk_inst_id"],  # 新老缓存兼容
                        }
                    )
        else:
            # 目标值为空，不做失效判定
            is_invalid_template = False
        target["field"] = target["field"].replace(template_node_type.lower(), "topo_node")
        target["value"] = new_value
        return target, is_invalid_template

    @classmethod
    def check_biz(cls, strategy, invalid_strategy_dict):
        """
        检测策略所属业务是否存在
        """
        if strategy["bk_biz_id"] not in invalid_strategy_dict["existed_biz_list"]:
            invalid_strategy_dict[StrategyModel.InvalidType.INVALID_BIZ].add(strategy["id"])
            strategy["is_invalid"] = True

    @classmethod
    def check_metrics(cls, strategy: dict[str, Any], item: dict[str, Any], invalid_strategy_dict: dict[str, Any]):
        """
        检测指标是否失效
        """
        try:
            bk_tenant_id = bk_biz_id_to_bk_tenant_id(strategy["bk_biz_id"])
        except ValueError:
            logger.warning(f"strategy({strategy['id']}) bk_biz_id({strategy['bk_biz_id']}) not found")
            return

        data_type_map = {
            DataTypeLabel.TIME_SERIES: StrategyModel.InvalidType.INVALID_METRIC,
            DataTypeLabel.ALERT: StrategyModel.InvalidType.DELETED_RELATED_STRATEGY,
        }

        need_check_type = [DataTypeLabel.ALERT, DataTypeLabel.TIME_SERIES]
        # 检测单位与数据单位是否同族，多指标无需检测
        if item["algorithms"]:
            if item["algorithms"][0]["type"] == AlgorithmModel.AlgorithmChoices.HostAnomalyDetection:
                # 主机智能异常检测不检测指标项
                return

            unit_prefix = item["algorithms"][0].get("unit_prefix", "")
            unit = item["query_configs"][0].get("unit", "")
            if invalid_strategy_dict["loaded_unit"].get(unit):
                metric_unit = invalid_strategy_dict["loaded_unit"][unit]
            else:
                metric_unit = load_unit(unit)
                invalid_strategy_dict["loaded_unit"][unit] = metric_unit
            suffix_list = [unit["suffix"] for unit in metric_unit.fn.unit_series()]
            if unit_prefix not in suffix_list:
                invalid_strategy_dict[StrategyModel.InvalidType.INVALID_UNIT].add(strategy["id"])
                strategy["is_invalid"] = True

        for query_config in item["query_configs"]:
            metric_id = query_config["metric_id"]
            data_type = query_config["data_type_label"]
            data_source = query_config["data_source_label"]
            # fix bk_data time_field字段问题
            if data_type == DataTypeLabel.TIME_SERIES and data_source == DataSourceLabel.BK_DATA:
                if "time_field" in query_config and query_config["time_field"] != "dtEventTimeStamp":
                    logger.warning(
                        f"strategy cache conflict: strategy: {strategy['id']}, source form bk_data"
                        f" but time_field is not [dtEventTimeStamp]"
                    )
                    query_config["time_field"] = "dtEventTimeStamp"
            # 时序型指标、关联告警指标判定是否失效
            if data_type in need_check_type and data_source != DataSourceLabel.PROMETHEUS:
                if data_type == DataTypeLabel.ALERT and data_source == DataSourceLabel.BK_MONITOR_COLLECTOR:
                    # 关联的策略待验证是否失效
                    invalid_strategy_dict["related_ids_map"][query_config["bkmonitor_strategy_id"]].add(strategy["id"])
                if metric_id in invalid_strategy_dict["checked_metric_ids"]["exists"]:
                    continue
                elif metric_id in invalid_strategy_dict["checked_metric_ids"]["not_exists"]:
                    invalid_strategy_dict[data_type_map[data_type]].add(strategy["id"])
                    strategy["is_invalid"] = True
                else:
                    metric_params = parse_metric_id(metric_id)
                    if "index_set_id" in metric_params:
                        metric_params["related_id"] = metric_params["index_set_id"]
                        del metric_params["index_set_id"]
                    if MetricListCache.objects.filter(bk_tenant_id=bk_tenant_id, **metric_params).exists():
                        invalid_strategy_dict["checked_metric_ids"]["exists"].add(metric_id)
                    else:
                        invalid_strategy_dict["checked_metric_ids"]["not_exists"].add(metric_id)
                        invalid_strategy_dict[data_type_map[data_type]].add(strategy["id"])
                        strategy["is_invalid"] = True

    @classmethod
    def check_related_strategy(cls, result_map, invalid_strategy_dict):
        """
        检测关联策略是否失效
        """
        # 关联策略失效，该策略判定为失效策略
        invalid_ids_set = invalid_strategy_dict[StrategyModel.InvalidType.INVALID_METRIC].union(
            invalid_strategy_dict[StrategyModel.InvalidType.INVALID_TARGET],
            invalid_strategy_dict[StrategyModel.InvalidType.DELETED_RELATED_STRATEGY],
        )
        invalid_related_ids = invalid_strategy_dict["related_ids_map"].keys() & invalid_ids_set
        for invalid_related_id in invalid_related_ids:
            for invalid_id in invalid_strategy_dict["related_ids_map"][invalid_related_id]:
                strategy_config = result_map.get(invalid_id)
                if strategy_config:
                    strategy_config["is_invalid"] = True
                invalid_strategy_dict[StrategyModel.InvalidType.INVALID_RELATED_STRATEGY].add(invalid_id)

        invalid_ids_set = invalid_ids_set | invalid_strategy_dict[StrategyModel.InvalidType.INVALID_RELATED_STRATEGY]
        # 策略失效检测完毕，更新至数据库
        origin_invalid_ids_set = set(
            StrategyModel.objects.filter(is_invalid=True).values_list("id", flat=True).distinct()
        )
        for invalid_type in StrategyModel.InvalidType.Choices:
            if invalid_type[0]:
                StrategyModel.objects.filter(id__in=list(invalid_strategy_dict[invalid_type[0]])).update(
                    is_invalid=True, invalid_type=invalid_type[0]
                )
            else:
                StrategyModel.objects.filter(id__in=list(origin_invalid_ids_set - invalid_ids_set)).update(
                    is_invalid=False, invalid_type=""
                )
        return result_map

    @classmethod
    def check_target(cls, strategy, target, invalid_strategy_dict):
        # 判定集群/服务模板是否失效
        is_invalid_template = False
        # 转化集群/服务模板为拓扑节点
        target_field = target["field"].upper()
        if TargetNodeType.SET_TEMPLATE in target_field:
            _, is_invalid_template = cls.transform_template_to_topo_nodes(
                target, TargetNodeType.SET_TEMPLATE, SetTemplateManager
            )
        elif TargetNodeType.SERVICE_TEMPLATE in target_field:
            _, is_invalid_template = cls.transform_template_to_topo_nodes(
                target, TargetNodeType.SERVICE_TEMPLATE, ServiceTemplateManager
            )
        if is_invalid_template:
            # 模板id全部不存在，目标失效
            invalid_strategy_dict[StrategyModel.InvalidType.INVALID_TARGET].add(strategy["id"])
            strategy["is_invalid"] = True
        else:
            # 判断模板下的拓扑节点id是否存在
            if TargetNodeType.TOPO in target["field"].upper() and target["value"]:
                is_invalid_topo = True
                for node in target["value"]:
                    if TopoManager.get(node["bk_obj_id"], node["bk_inst_id"]):
                        is_invalid_topo = False
                        break
                # 拓扑节点id全部不存在，目标失效
                if is_invalid_topo:
                    invalid_strategy_dict[StrategyModel.InvalidType.INVALID_TARGET].add(strategy["id"])
                    strategy["is_invalid"] = True

    @classmethod
    def handle_special_query_config(cls, bk_biz_id: int, is_ip_target, item):
        """
        预处理特殊情况的查询配置
        1. 根据目标类型补全特殊维度
        2. 伪事件型策略的metric_id处理
        """
        for query_config in item["query_configs"]:
            # promql类型策略无需处理
            if query_config.get("promql"):
                continue

            data_source_label = query_config["data_source_label"]
            data_type_label = query_config["data_type_label"]

            # 伪事件型策略的metric_id需要调整为事件型metric_id
            fake_event_metric_id_mapping = {
                "bk_monitor.system.env.uptime": "bk_monitor.os_restart",
                "bk_monitor.pingserver.base.loss_percent": "bk_monitor.ping-gse",
                "bk_monitor.system.proc_port.proc_exists": "bk_monitor.proc_port",
            }
            if query_config["metric_id"] in fake_event_metric_id_mapping:
                query_config["metric_id"] = fake_event_metric_id_mapping[query_config["metric_id"]]
            # hack agg_interval with fake_event
            if query_config["metric_id"] in fake_event_metric_id_mapping.values():
                query_config["agg_interval"] = query_config.get("agg_interval", cls.fake_event_agg_interval)

            query_config.setdefault("agg_dimension", [])
            is_instance_dimension = cls.instance_dimensions & set(query_config["agg_dimension"])

            # 如果是静态IP监控目标，需要补全维度，避免监控目标失效
            if is_ip_target:
                if data_source_label == DataSourceLabel.BK_FTA and data_type_label == DataTypeLabel.EVENT:
                    query_config["agg_dimension"].extend(["ip", "bk_cloud_id"])
                elif not is_instance_dimension:
                    if is_ipv6_biz(bk_biz_id):
                        query_config["agg_dimension"].extend(["bk_host_id"])
                    else:
                        query_config["agg_dimension"].extend(["bk_target_ip", "bk_target_cloud_id"])

                query_config["agg_dimension"] = list(set(query_config["agg_dimension"]))

            # 日志关键字告警按节点聚合需要使用bk_obj_id和bk_inst_id
            if data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR and data_type_label == DataTypeLabel.LOG:
                if not is_ip_target and not is_instance_dimension:
                    query_config["agg_dimension"].extend(["bk_obj_id", "bk_inst_id"])

    @classmethod
    def transform_targets(cls, item):
        """
        转换为ip的监控目标字段
        """
        for condition in chain(*item["target"]):
            if condition["field"] == "ip":
                condition["field"] = "bk_target_ip"

            for value in condition["value"]:
                if "ip" in value:
                    value["bk_target_ip"] = value["ip"]
                    del value["ip"]

                if "bk_cloud_id" in value:
                    value["bk_target_cloud_id"] = value["bk_cloud_id"]
                    del value["bk_cloud_id"]

    @classmethod
    def get_strategies_map(cls, filter_dict: dict | None = None) -> dict:
        """
        获取全部策略配置, 返回字典格式
        """
        filter_dict: dict = filter_dict or {}
        # 初始化策略失效检测信息
        invalid_strategy_dict = {
            # 已检测的指标id缓存
            "checked_metric_ids": {"exists": set(), "not_exists": set()},
            # 已检测的单位缓存
            "loaded_unit": defaultdict(),
            # 现存业务id列表缓存
            "existed_biz_list": list(BusinessManager.keys()),
            # 失效策略类型集合
            StrategyModel.InvalidType.INVALID_METRIC: set(),
            StrategyModel.InvalidType.INVALID_BIZ: set(),
            StrategyModel.InvalidType.INVALID_UNIT: set(),
            StrategyModel.InvalidType.INVALID_TARGET: set(),
            StrategyModel.InvalidType.DELETED_RELATED_STRATEGY: set(),
            StrategyModel.InvalidType.INVALID_RELATED_STRATEGY: set(),
            StrategyModel.InvalidType.INVALID_DASHBOARD_PANEL: set(),
            # 关联策略id映射
            "related_ids_map": defaultdict(set),
        }

        # 根据给定的过滤条件，从数据库中筛选出所有启用的策略模型，并将它们转换为字典形式
        # 这个映射的键是策略的唯一标识符，值是策略的内容，便于进一步处理和使用
        strategy_configs_map = {
            strategy.id: strategy.to_dict()
            for strategy in Strategy.from_models(StrategyModel.objects.filter(is_enabled=True).filter(**filter_dict))
        }

        result_map = {}
        cls.fake_event_agg_interval = getattr(settings, "FAKE_EVENT_AGG_INTERVAL", 60)
        for strategy_id, strategy_config in strategy_configs_map.items():
            # 过滤没有item的策略
            if not strategy_config["items"]:
                logger.warning(f"strategy({strategy_config['id']}) items is empty")
                continue

            # 过滤没有query_config的监控项
            if not all(item["query_configs"] for item in strategy_config["items"]):
                logger.warning(f"strategy({strategy_config['id']}) query_config is empty")
                continue

            try:
                if cls.handle_strategy(strategy_config, invalid_strategy_dict):
                    result_map[strategy_id] = strategy_config
            except Exception as e:
                logger.exception("refresh strategy error when handle_strategy[%s]: %s", strategy_id, e)
        # 检测关联策略是否失效
        cls.check_related_strategy(result_map, invalid_strategy_dict)
        return result_map

    @classmethod
    def get_strategies(cls, filter_dict: dict | None = None) -> list[dict]:
        """
        获取全部策略配置
        """
        # 获取字典格式的全部策略配置
        result_map = cls.get_strategies_map(filter_dict)

        # 提取所有的策略配置重新组成一个列表
        result = []
        for strategy_id, strategy_config in result_map.items():
            result.append(strategy_config)

        return result

    @classmethod
    def get_query_md5(cls, bk_biz_id: int, item: dict) -> str:
        """
        生成监控项查询MD5
        """
        item = copy.deepcopy(item)

        configs = []
        for query_config in item["query_configs"]:
            params = {
                "bk_biz_id": int(bk_biz_id),
                "data_source_label": query_config["data_source_label"],
                "data_type_label": query_config["data_type_label"],
                "agg_method": query_config.get("agg_method"),
                "agg_interval": query_config.get("agg_interval"),
                "agg_dimension": query_config.get("agg_dimension"),
                "agg_condition": query_config.get("agg_condition"),
                "result_table_id": query_config.get("result_table_id"),
                "metric_field": query_config.get("metric_field"),
                "keywords_query_string": query_config.get("query_string"),
            }

            # 计算函数加入md5计算
            if query_config.get("functions"):
                params["functions"] = query_config["functions"]

            if query_config.get("promql"):
                params["promql"] = query_config["promql"]

            # 日志平台来源数据需要加上index_set_id作为查询条件
            if params["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH:
                params["index_set_id"] = query_config["index_set_id"]
            elif (
                params["data_source_label"] == DataSourceLabel.CUSTOM
                and params["data_type_label"] == DataTypeLabel.EVENT
            ):
                if query_config["custom_event_name"]:
                    params["custom_event_name"] = query_config["custom_event_name"]
            elif params["data_source_label"] == DataSourceLabel.BK_FTA:
                params["alert_name"] = query_config["alert_name"]
            elif (
                params["data_source_label"] == DataSourceLabel.BK_MONITOR_COLLECTOR
                and params["data_type_label"] == DataTypeLabel.ALERT
            ):
                params["bkmonitor_strategy_id"] = query_config["bkmonitor_strategy_id"]

            # 除了统一查询模块支持的数据源外，时序数据如果含有复杂查询条件，则查询时不添加该条件
            if (
                (params["data_source_label"], params["data_type_label"]) not in UnifyQueryDataSources
                and params["data_type_label"] == DataTypeLabel.TIME_SERIES
                and params.get("agg_condition")
            ):
                for condition in query_config["agg_condition"]:
                    if condition["method"] in AdvanceConditionMethod:
                        params["agg_condition"] = []
                        break

            configs.append(params)

        # 只有一个查询配置时与单指标时保持一致，避免策略大幅波动
        return count_md5(
            configs[0]
            if len(configs) == 1 and len(item.get("expression", "").strip(" ")) <= 1
            else {"expression": item["expression"], "query_configs": configs}
        )

    @classmethod
    def is_disabled_strategy(cls, strategy: dict) -> bool:
        """
        判断策略是否被规则禁用
        {"strategy_ids":[],"bk_biz_ids":[],"data_source_label":"","data_type_label":""}
        """

        query_config = strategy["items"][0]["query_configs"][0]
        data_source_label = query_config["data_source_label"]
        data_type_label = query_config["data_type_label"]

        for disabled_rule in settings.ALARM_DISABLE_STRATEGY_RULES:
            # 判断数据源是否被禁用
            if (
                disabled_rule.get("data_source_label")
                and disabled_rule.get("data_type_label")
                and (data_source_label, data_type_label)
                != (
                    disabled_rule["data_source_label"],
                    disabled_rule["data_type_label"],
                )
            ):
                continue
            # 判断是否为被禁用业务
            if disabled_rule.get("bk_biz_id") and strategy["bk_biz_id"] not in disabled_rule["bk_biz_id"]:
                continue
            # 判断是否为禁用策略
            if disabled_rule.get("strategy_ids") and strategy["id"] not in disabled_rule["strategy_ids"]:
                continue
            return True

        return False

    @classmethod
    def handle_strategy(cls, strategy: dict, invalid_strategy_dict=None) -> bool:
        """
        策略预处理
        """
        strategy["update_time"] = arrow.get(strategy["update_time"]).timestamp
        strategy["create_time"] = arrow.get(strategy["create_time"]).timestamp

        for item in strategy["items"]:
            # 补充item的更新时间
            item["update_time"] = arrow.get(strategy["update_time"]).timestamp

            query_config = item["query_configs"][0]
            data_source_label = query_config["data_source_label"]
            data_type_label = query_config["data_type_label"]

            # 判断策略是否被禁用
            try:
                if cls.is_disabled_strategy(strategy):
                    return False
            except Exception as e:
                logger.warning(e)

            # 修改监控目标字段为ip的情况
            cls.transform_targets(item)

            # 策略所属业务不存在检测
            cls.check_biz(strategy, invalid_strategy_dict)

            # 指标失效检测
            cls.check_metrics(strategy, item, invalid_strategy_dict)

            # 监控目标预处理
            if item["target"] and item["target"][0]:
                target = item["target"][0][0]
                is_ip_target = target["field"] == "bk_target_ip"

                # 根据目标类型补全特殊维度
                cls.handle_special_query_config(strategy["bk_biz_id"], is_ip_target, item)

                # 目标失效检测
                cls.check_target(strategy, target, invalid_strategy_dict)

                # 如果value为空，则说明模板下不存在节点，过滤掉
                if not target["value"]:
                    logger.info(f"skip strategy({strategy['id']}) because target is empty")
                    return False

            # 智能异常检测算法，结果表是存在intelligent_detect中，需要用这个配置
            if query_config.get("intelligent_detect") and not query_config["intelligent_detect"].get("use_sdk", False):
                raw_query_config = query_config.copy()
                raw_query_config.pop("intelligent_detect")
                query_config["raw_query_config"] = raw_query_config
                query_config.update(query_config["intelligent_detect"])

                if query_config.get("extend_fields") and isinstance(query_config["extend_fields"], dict):
                    query_config.update(query_config["extend_fields"])

            # 补充查询配置md5，后续进行分组查询
            is_series = data_type_label in [DataTypeLabel.TIME_SERIES, DataTypeLabel.LOG]
            is_custom_event = data_source_label == DataSourceLabel.CUSTOM and data_type_label == DataTypeLabel.EVENT
            is_fta_event = data_source_label == DataSourceLabel.BK_FTA and data_type_label == DataTypeLabel.EVENT
            if not any([is_series, is_custom_event, is_fta_event]):
                item["query_md5"] = ""
            else:
                item["query_md5"] = cls.get_query_md5(strategy["bk_biz_id"], item)

            return True

    @classmethod
    def get_strategy_ids(cls):
        """
        从缓存获取策略ID列表
        :return: 策略ID列表
        :rtype: list[int]
        """
        return json.loads(cls.cache.get(cls.IDS_CACHE_KEY) or "[]")

    @classmethod
    def get_strategy_by_ids(cls, strategy_ids: list[int]) -> list[dict]:
        """
        从缓存中获取策略详情
        """
        if not strategy_ids:
            return []
        keys = [cls.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id) for strategy_id in strategy_ids]
        strategies = []
        for sub_keys in chunks(keys, 1000):
            strategies.extend(cls.cache.mget(sub_keys))
        return [Strategy.convert_v1_to_v2(json.loads(strategy)) for strategy in strategies if strategy]

    @classmethod
    def get_strategy_by_id(cls, strategy_id: int) -> dict:
        """
        从缓存中获取策略详情
        """
        strategy = json.loads(cls.cache.get(cls.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id)) or "null")
        # 兼容旧版策略
        strategy = Strategy.convert_v1_to_v2(strategy)
        return strategy

    @classmethod
    def get_all_bk_biz_ids(cls) -> list:
        """
        获取有策略的全部业务ID
        """
        bk_biz_ids = json.loads(cls.cache.get(cls.BK_BIZ_IDS_CACHE_KEY) or "[]")
        if not bk_biz_ids:
            strategies = StrategyModel.objects.filter(is_enabled=True).only("bk_biz_id").distinct()
            bk_biz_ids = [strategy.bk_biz_id for strategy in strategies]
        return bk_biz_ids

    @classmethod
    def get_time_series_strategy_ids(cls) -> Iterable:
        """
        获取时序性策略ID列表
        """
        # 1. 所有的配置的策略
        all_strategy_ids = set(map(int, cls.get_strategy_ids()))

        # 2. 系统事件、自定义字符型、进程托管事件相关策略
        custom_event_strategy_ids = set(map(int, chain(*list(cls.get_gse_alarm_strategy_ids().values()))))

        # 3. 实时数据相关策略
        real_time = cls.get_real_time_data_strategy_ids()
        real_time_strategy_ids = set(map(int, chain(*[s for r in list(real_time.values()) for s in list(r.values())])))

        # 4. 自愈相关策略
        fta_alert = cls.get_fta_alert_strategy_ids()
        fta_alert_strategy_ids = set(map(int, chain(*[s for r in list(fta_alert.values()) for s in list(r.values())])))

        return all_strategy_ids - custom_event_strategy_ids - real_time_strategy_ids - fta_alert_strategy_ids

    @classmethod
    def get_real_time_data_strategy_ids(cls):
        """
        获取real time 走实时数据相关的策略

        type:dict(rt_id -> bk_biz_id -> strategy_ids)
        """
        return json.loads(cls.cache.get(cls.REAL_TIME_CACHE_KEY) or "{}")

    @classmethod
    def get_gse_alarm_strategy_ids(cls):
        """
        获取gse事件策略
        :return: 策略ID列表
        :rtype: dict
        """
        return json.loads(cls.cache.get(cls.GSE_ALARM_CACHE_KEY) or "{}")

    @classmethod
    def get_nodata_strategy_ids(cls) -> list[int]:
        """
        获取无数据策略ID列表
        """
        return json.loads(cls.cache.get(cls.NO_DATA_CACHE_KEY) or "[]")

    @classmethod
    def get_aiops_sdk_strategy_ids(cls) -> list[int]:
        """
        获取启用AIOPS SDK 相关策略
        """
        return json.loads(cls.cache.get(cls.AIOPS_SDK_CACHE_KEY) or "[]")

    @classmethod
    def get_fta_alert_strategy_ids(cls, strategy_id=None, alert_name=None) -> dict:
        """
        获取自愈关联告警策略
        :rtype: dict (bk_biz_id -> strategy_ids)
        """
        strategy_ids = None
        if strategy_id:
            strategy_ids = cls.cache.hget(cls.FTA_ALERT_CACHE_KEY, f"strategy|{strategy_id}")
        elif alert_name:
            strategy_ids = cls.cache.hget(cls.FTA_ALERT_CACHE_KEY, f"alert|{alert_name}")
        if not strategy_ids:
            return {}
        return json.loads(strategy_ids)

    @classmethod
    def get_all_groups(cls):
        """
        获取全部策略分组信息
        :return:
        """
        return cls.cache.hgetall(cls.STRATEGY_GROUP_CACHE_KEY)

    @classmethod
    def get_strategy_group_keys(cls):
        """
        获取全部策略分组key
        :return:
        """
        return cls.cache.hkeys(cls.STRATEGY_GROUP_CACHE_KEY)

    @classmethod
    def get_strategy_group_detail(cls, strategy_group_key):
        # 这个函数不要再调用了
        data = cls.cache.hget(cls.STRATEGY_GROUP_CACHE_KEY, strategy_group_key) or "{}"
        return json.loads(data)

    @classmethod
    def refresh_strategy_ids(cls, strategies: list[dict], to_be_deleted_strategy_ids=None):
        """
        刷新策略ID列表缓存

        该方法主要用于更新策略ID列表的缓存。它通过比较传入的策略ID列表与当前缓存中的ID列表，
        来更新缓存以反映最新的策略状态。如果指定了要删除的策略ID列表，则会相应地从当前缓存中
        移除这些ID，并根据新的策略列表更新缓存。

        :param strategies: 当前所有的策略信息列表，每条策略包含唯一的ID。
        :param to_be_deleted_strategy_ids: 可选参数，指定需要从缓存中删除的策略ID列表。
        """
        # 从传入的策略列表中提取所有策略的ID，形成一个新集合。
        updated_strategy_ids: set = {strategy["id"] for strategy in strategies}
        # 从缓存中获取当前保存的所有策略ID，形成一个集合。
        old_strategy_ids: set = set(cls.get_strategy_ids())

        # 如果指定了需要删除的策略ID列表，则进行增量更新。
        if to_be_deleted_strategy_ids is not None:
            # 增量更新
            # 原列表(old_strategy_ids) - 删除(to_be_deleted_strategy_ids) + 更新(updated_strategy_ids) -> 去重
            updated_strategy_ids |= old_strategy_ids - set(to_be_deleted_strategy_ids)

        # 更新缓存中的策略ID列表。
        cls.cache.set(cls.IDS_CACHE_KEY, json.dumps(list(updated_strategy_ids)), cls.CACHE_TIMEOUT)

        # 遍历旧的策略ID列表，检查是否有不再新策略列表中的ID。
        for strategy_id in old_strategy_ids:
            # 如果旧列表中的ID在新列表中找不到，则说明该策略已被删除或更改。
            if strategy_id not in updated_strategy_ids:
                logger.info(f"[smart_strategy_cache]: refresh_strategy_ids delete strategy: {strategy_id}")
                # 从缓存中删除该策略的相关信息。
                cls.cache.delete(cls.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id))

    @classmethod
    def refresh_bk_biz_ids(cls, strategies: list[dict], partial=None):
        """
        刷新配置了策略的业务ID列表
        """
        bk_biz_ids = {strategy["bk_biz_id"] for strategy in strategies}
        if partial is None:
            # 全量刷新
            return cls.cache.set(cls.BK_BIZ_IDS_CACHE_KEY, json.dumps(list(bk_biz_ids)), cls.CACHE_TIMEOUT)

        # 增量刷新
        old_bk_biz_ids = cls.get_all_bk_biz_ids()
        logger.info(f"[smart_strategy_cache]: refresh_bk_biz_ids old_bk_biz_ids: {len(old_bk_biz_ids)}")
        for biz_id in bk_biz_ids:
            # 发生变更的业务ID不在旧的业务ID列表中，则添加到旧的业务ID列表中
            if biz_id not in old_bk_biz_ids:
                old_bk_biz_ids.append(biz_id)
        logger.info(f"[smart_strategy_cache]: refresh_bk_biz_ids new_bk_biz_ids: {len(old_bk_biz_ids)}")
        return cls.cache.set(cls.BK_BIZ_IDS_CACHE_KEY, json.dumps(old_bk_biz_ids), cls.CACHE_TIMEOUT)

    @classmethod
    def refresh_real_time_strategy_ids(cls, strategies: list[dict]):
        """
        刷新实时数据的相关策略
        :param strategies: 策略列表
        :cache data: type:dict(rt_id -> bk_biz_id -> strategy_ids)
        """
        real_time_strategys = {}
        for strategy in strategies:
            try:
                bk_biz_id = strategy["bk_biz_id"]
                item = strategy["items"][0]
                query_config = item["query_configs"][0]
                data_type_label = query_config["data_type_label"]
                if (
                    data_type_label == DataTypeLabel.TIME_SERIES
                    and query_config.get("agg_method") == AGG_METHOD_REAL_TIME
                ):
                    real_time_strategys.setdefault(query_config["result_table_id"], {}).setdefault(
                        bk_biz_id, []
                    ).append(strategy["id"])
            except Exception as e:
                logger.exception("refresh strategy error when refresh_real_time_strategy_ids: %s", e)

        cls.cache.set(cls.REAL_TIME_CACHE_KEY, json.dumps(real_time_strategys), cls.CACHE_TIMEOUT)

    @classmethod
    def refresh_nodata_strategy_ids(cls, strategies: list[dict]):
        """
        刷新无数据策略ID列表缓存
        """
        nodata_strategy_ids = []
        for strategy in strategies:
            for item in strategy["items"]:
                no_data_config = item.get("no_data_config")
                if no_data_config and no_data_config.get("is_enabled"):
                    nodata_strategy_ids.append(strategy["id"])
                    continue

        cls.cache.set(cls.NO_DATA_CACHE_KEY, json.dumps(nodata_strategy_ids), cls.CACHE_TIMEOUT)

    @classmethod
    def refresh_aiops_sdk_strategy_ids(cls, strategies: list[dict]):
        """
        刷新启用了aiops sdk模块的策略ID列表缓存
        """
        aiops_sdk_strategy_ids = []
        for strategy in strategies:
            for item in strategy["items"]:
                query_config = item["query_configs"][0]
                intelligent_detect = query_config.get("intelligent_detect") or {}
                if intelligent_detect.get("use_sdk"):
                    aiops_sdk_strategy_ids.append(strategy["id"])

        cls.cache.set(cls.AIOPS_SDK_CACHE_KEY, json.dumps(aiops_sdk_strategy_ids), cls.CACHE_TIMEOUT)

    @classmethod
    def refresh_gse_alarm_strategy_ids(cls, strategies: list[dict]):
        """
        刷新gse事件策略ID列表缓存
        """
        gse_event_strategy_ids = defaultdict(list)
        for strategy in strategies:
            try:
                item = strategy["items"][0]
                query_config = item["query_configs"][0]
                data_source_label = query_config["data_source_label"]
                data_type_label = query_config["data_type_label"]
                if data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR and data_type_label == DataTypeLabel.EVENT:
                    gse_event_strategy_ids[strategy["bk_biz_id"]].append(strategy["id"])
            except Exception as e:
                logger.exception("refresh strategy error when refresh_gse_alarm_strategy_ids: %s", e)

        cls.cache.set(cls.GSE_ALARM_CACHE_KEY, json.dumps(gse_event_strategy_ids), cls.CACHE_TIMEOUT)

    @classmethod
    def refresh_fta_alert_strategy_ids(cls, strategies: list[dict]):
        """
        刷新自愈策略列表缓存
        """
        fta_alert_strategy_ids = {}
        for strategy in strategies:
            try:
                for item in strategy["items"]:
                    for query_config in item["query_configs"]:
                        data_source_label = query_config["data_source_label"]
                        data_type_label = query_config["data_type_label"]
                        if data_type_label != DataTypeLabel.ALERT:
                            continue

                        if data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR:
                            fta_alert_strategy_ids.setdefault(
                                f"strategy|{query_config['bkmonitor_strategy_id']}", {}
                            ).setdefault(strategy["bk_biz_id"], []).append(strategy["id"])
                        elif data_source_label == DataSourceLabel.BK_FTA:
                            fta_alert_strategy_ids.setdefault(f"alert|{query_config['alert_name']}", {}).setdefault(
                                strategy["bk_biz_id"], []
                            ).append(strategy["id"])

            except Exception as e:
                logger.exception("refresh strategy error when refresh_fta_alert_strategy_ids: %s", e)

        # 批量保存 Key
        if fta_alert_strategy_ids:
            cls.cache.hmset(
                cls.FTA_ALERT_CACHE_KEY, {key: json.dumps(value) for key, value in fta_alert_strategy_ids.items()}
            )

        # 差量删除多余的 Key
        old_keys = cls.cache.hkeys(cls.FTA_ALERT_CACHE_KEY)
        deleted_keys = set(old_keys) - set(fta_alert_strategy_ids.keys())
        if deleted_keys:
            cls.cache.hdel(cls.FTA_ALERT_CACHE_KEY, *deleted_keys)
        cls.cache.expire(cls.FTA_ALERT_CACHE_KEY, cls.CACHE_TIMEOUT)

    @classmethod
    def refresh_strategy(cls, strategies: list[dict], old_groups=None):
        """
        刷新策略缓存
        该方法用于更新策略的缓存，确保策略及其相关分组信息是最新的

        “策略详情信息”循环缓存，每个策略占用缓存中的一个key, 数据结构是string
        “策略分组信息”一次性缓存，含所有分组的信息占用缓存中的一个key, 数据结构是hash
        策略分组信息的结构为:
        {
        '623446abe6e6a4b6a9af6531bd45faeb': {1: [1], 'bk_biz_id': 2, 'interval_list': [60], 'default_factory': []},
        '623446abe6e6a4b6a9af6531bd45faec': {2: [2], 'bk_biz_id': 2, 'interval_list': [120], 'default_factory': []},
        }

        :param strategies: 新的策略列表，每个策略包含其详细信息
        :param old_groups: 旧的策略分组信息，如果为None，则进行全量更新。否则进行增量更新，删除不在新策略中的旧分组
        """
        # 初始化策略分组缓存结构
        strategy_groups = defaultdict(lambda: defaultdict(list))

        # 开启缓存pipeline以优化写入性能
        pipeline = cls.cache.pipeline()
        for strategy in strategies:
            # 将策略信息存储到缓存中
            pipeline.set(
                cls.CACHE_KEY_TEMPLATE.format(strategy_id=strategy["id"]), json.dumps(strategy), cls.CACHE_TIMEOUT
            )
            # 默认周期 50s
            for item in strategy["items"]:
                if item.get("query_md5"):
                    strategy_groups[item["query_md5"]][strategy["id"]].append(item["id"])
                    # 补充业务信息
                    strategy_groups[item["query_md5"]]["bk_biz_id"] = strategy["bk_biz_id"]
                    # interval
                    # 补充周期缓存
                    for config in item.get("query_configs", []):
                        interval = config.get("agg_interval")
                        if not interval:
                            continue
                        try:
                            interval = int(interval)
                            assert interval > 0, (
                                f"strategy({strategy['id']}) item({item['id']}) interval config is invalid: {config}"
                            )
                            strategy_groups[item["query_md5"]].setdefault("interval_list", []).append(interval)
                            # 新增设置数据源类型
                            if (
                                config.get("data_source_label")
                                and "strategy_source" not in strategy_groups[item["query_md5"]]
                            ):
                                strategy_groups[item["query_md5"]]["strategy_source"] = [
                                    (config.get("data_source_label"), config.get("data_type_label"))
                                ]
                        except (TypeError, ValueError, AssertionError):
                            continue

        # 判断是否是全量更新
        refresh_all = old_groups is None
        if refresh_all:
            # 全量更新，获取旧的分组信息
            old_groups = cls.cache.hkeys(cls.STRATEGY_GROUP_CACHE_KEY)

        # 删除不在新策略中的旧分组
        for query_md5 in old_groups:
            if query_md5 not in strategy_groups:
                if not refresh_all:
                    logger.info(f"[smart_strategy_cache]: refresh_strategy delete old group: {query_md5}")
                pipeline.hdel(cls.STRATEGY_GROUP_CACHE_KEY, query_md5)
        # 更新新的分组信息到缓存中
        for query_md5 in strategy_groups:
            pipeline.hset(cls.STRATEGY_GROUP_CACHE_KEY, query_md5, json.dumps(strategy_groups[query_md5]))
        # 设置缓存过期时间
        pipeline.expire(cls.STRATEGY_GROUP_CACHE_KEY, cls.CACHE_TIMEOUT)

        # 执行pipeline中的所有操作
        pipeline.execute()

    @classmethod
    def add_enabled_cluster_condition(cls, strategy_configs: list[dict]):
        """
        针对k8s策略添加启用集群范围生效条件
        """

        def add_condition(bcs_cluster_ids, strategy):
            """
            添加已启用bcs_cluster的过滤条件
            """
            # 启用集群id列表为空则不添加过滤条件
            if not bcs_cluster_ids:
                return

            for item in strategy["items"]:
                for query_config in item["query_configs"]:
                    if query_config.get("result_table_id", "not k8s"):
                        # 内置k8s采集的指标(result_table_id值为空字符串)
                        # 非内置的话，不需要限制 bcs_cluster_id 数据范围
                        return

                    query_config["agg_condition"] = query_config.get("agg_condition", [])
                    query_config["agg_condition"].append(
                        {"key": "bcs_cluster_id", "value": bcs_cluster_ids, "method": "eq", "condition": "and"}
                    )

        enabled_cluster_map = defaultdict(list)
        for strategy_config in strategy_configs:
            if is_k8s_target(strategy_config["scenario"]):
                bk_biz_id = strategy_config["bk_biz_id"]
                if bk_biz_id not in enabled_cluster_map:
                    try:
                        enabled_cluster_map[bk_biz_id] = api.kubernetes.fetch_bcs_cluster_alert_enabled_id_list(
                            {"bk_biz_id": bk_biz_id}
                        )
                    except Exception as e:
                        logger.exception("refresh strategy error when add_enabled_cluster_condition: %s", e)
                add_condition(enabled_cluster_map[bk_biz_id], strategy_config)

    @classmethod
    def add_target_shield_condition(cls, strategy_configs: list[dict]):
        """
        添加监控目标抑制条件
        1. 主机目标抑制拓扑目标
           如主机A属于模块B，同时配置两个查询条件相同的策略，模块B的策略不会产生主机A的告警
        2. 低层级拓扑目标抑制高层级拓扑目标
           如果模块A属于集群B，同时配置两个查询条件相同的策略，集群B不会产生模块A的告警
        """

        def get_query_sort_key(x):
            """
            获取查询配置排序字段
            """
            return x["items"][0]["query_md5"] or x["items"][0]["query_configs"][0]["metric_id"]

        # 过滤掉无目标，无查询分组的策略
        def is_valid_strategy_config(strategy_config):
            """
            判断是否是需要添加抑制条件的策略
            """
            item = strategy_config["items"][0]
            target = item["target"]
            query_config = item["query_configs"][0]

            is_system_event = (
                query_config["data_type_label"] == DataTypeLabel.EVENT
                and query_config["data_source_label"] == DataSourceLabel.BK_MONITOR_COLLECTOR
            )

            return (
                (item["query_md5"] or is_system_event) and target and target[0] and not strategy_config.get("priority")
            )

        strategy_configs = [
            strategy_config for strategy_config in strategy_configs if is_valid_strategy_config(strategy_config)
        ]

        cmdb_levels = [cmdb_level["bk_obj_id"] for cmdb_level in api.cmdb.get_mainline_object_topo()]

        # 按业务、查询配置md5分组添加抑制条件
        strategy_configs.sort(key=itemgetter("bk_biz_id"))
        for bk_biz_id, strategies_biz in groupby(strategy_configs, key=itemgetter("bk_biz_id")):
            try:
                strategies_biz = list(strategies_biz)
                strategies_biz.sort(key=get_query_sort_key)
                for query_md5, strategies_query in groupby(strategies_biz, get_query_sort_key):
                    strategies_query = list(strategies_query)

                    # 只有一条则不存抑制的可能
                    if len(strategies_query) <= 1:
                        continue

                    # 根据同组内的其他策略配置，在target中添加抑制条件
                    processor = TargetShieldProcessor(strategies_query, cmdb_levels)
                    for strategy in strategies_query:
                        processor.insert_target(strategy)
            except Exception as e:
                logger.exception("refresh strategy error when add_target_shield_condition: %s", e)

    @classmethod
    def refresh(cls):
        """
        全量更新策略缓存
        """
        start_time = time.time()
        exc = None

        # 获取策略列表并缓存
        try:
            strategies_map = cls.get_strategies_map()
        except Exception as e:
            logger.exception("refresh strategy error when get_strategies_map: %s", e)
            duration = time.time() - start_time
            metrics.ALARM_CACHE_TASK_TIME.labels("0", "strategy", str(e)).observe(duration)
            metrics.report_all()
            return

        # 获取策略历史数据
        process_time = time.time()
        histories = StrategyHistoryModel.objects.filter(create_time__gt=datetime.fromtimestamp(start_time))
        if not histories.exists():
            logger.info(
                f"[refresh_strategy_cache]: no changed strategy found in the past {time.time() - start_time} seconds"
            )
        else:
            target_biz_set, to_be_deleted_strategy_ids = cls.handle_history_strategies(histories, with_group_key=False)
            # 如果有策略待删除，则记录日志
            if to_be_deleted_strategy_ids:
                logger.info(f"[refresh_strategy_cache]: to_be_deleted_strategy_ids: {to_be_deleted_strategy_ids}")

                # 删除待删除的策略
                for strategy_id, _ in to_be_deleted_strategy_ids:
                    strategies_map.pop(strategy_id, None)
            try:
                changed_strategies_map = (
                    cls.get_strategies_map({"bk_biz_id__in": target_biz_set}) if target_biz_set else {}
                )
                strategies_map.update(changed_strategies_map)
            except Exception as e:
                logger.exception(f"[refresh_strategy_cache]: get data of changed_strategies_map failed: {e}")
                exc = e

        processors: list[Callable[[list[dict]], None]] = [
            cls.add_target_shield_condition,
            cls.add_enabled_cluster_condition,
            cls.refresh_strategy_ids,  # 刷新缓存策略ID
            cls.refresh_bk_biz_ids,  # 刷新缓存业务ID
            cls.refresh_strategy,  # 刷新缓存策略详细信息和策略分组信息
            cls.refresh_real_time_strategy_ids,  # 刷新实时数据的相关策略
            cls.refresh_gse_alarm_strategy_ids,  # 刷新gse事件策略ID列表缓存
            cls.refresh_fta_alert_strategy_ids,  # 刷新自愈策略列表缓存
            cls.refresh_nodata_strategy_ids,  # 刷新无数据策略ID列表缓存
            cls.refresh_aiops_sdk_strategy_ids,  # 刷新AIOPS SDK策略ID列表缓存
        ]

        # 获取策略列表, 执行缓存策略刷新操作
        strategies = list(strategies_map.values())
        for processor in processors:
            try:
                start = time.time()
                processor(strategies)
                logger.info(f"refresh strategy {processor.__name__} cost: {time.time() - start}")
            except Exception as e:
                logger.exception(f"refresh strategy error when {processor.__name__}")
                exc = e

        # 策略处理期间删除的策略，直接清理
        histories = StrategyHistoryModel.objects.filter(create_time__gt=datetime.fromtimestamp(process_time))
        if histories.exists():
            target_biz_set, to_be_deleted_strategy_ids = cls.handle_history_strategies(histories, with_group_key=False)
            for strategy_id, _ in to_be_deleted_strategy_ids:
                cls.cache.delete(cls.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id))

        duration = time.time() - start_time
        metrics.ALARM_CACHE_TASK_TIME.labels("0", "strategy", str(exc)).observe(duration)
        metrics.report_all()

    @classmethod
    def handle_history_strategies(cls, histories: list[StrategyHistoryModel], with_group_key=True) -> tuple[set, set]:
        """
        处理策略历史，确定受影响的业务和待删除的策略。

        :param histories: List[StrategyHistoryModel]，策略历史记录列表。
        :param with_group_key: bool，是否要求获取group key(在smart_refresh中，需要获取group key)
        :returns: Tuple[Set, Set]，包含受影响的业务ID集合和待删除的策略ID集合的元组。
        """
        target_biz_set = set()
        # 初始化待删除的策略ID集合
        to_be_deleted_strategy_ids: set[tuple] = set()
        # 遍历变更策略以确定受影响的业务和待删除的策略
        for history in histories:
            # 变更的策略，需要判定is_enabled变化
            if history.operate != "delete":
                # 本次增量更新的业务列表
                target_biz_set.add(history.content["bk_biz_id"])
                # 判断策略是否启用
                is_enabled = history.content["is_enabled"]
                if is_enabled:
                    continue
            # 删除的策略，需要记录对应的策略id和对应的group key
            strategy_id = history.strategy_id
            query_md5 = ""
            # 从缓存中获取策略详情
            strategy = cls.get_strategy_by_id(strategy_id)
            if not strategy:
                if not with_group_key:
                    # 被smart_refresh删除的策略, 在refresh流程中需要被再次删除
                    to_be_deleted_strategy_ids.add((strategy_id, ""))
                continue
            # 根据策略内容生成对应的查询MD5
            for item in strategy["items"]:
                query_config = item["query_configs"][0]
                data_source_label = query_config["data_source_label"]
                data_type_label = query_config["data_type_label"]
                is_series = data_type_label in [DataTypeLabel.TIME_SERIES, DataTypeLabel.LOG]
                is_custom_event = data_source_label == DataSourceLabel.CUSTOM and data_type_label == DataTypeLabel.EVENT
                is_fta_event = data_source_label == DataSourceLabel.BK_FTA and data_type_label == DataTypeLabel.EVENT
                if any([is_series, is_custom_event, is_fta_event]):
                    query_md5 = cls.get_query_md5(strategy["bk_biz_id"], item)
            # 添加待删除的策略ID和查询MD5到集合中
            to_be_deleted_strategy_ids.add((strategy_id, query_md5))

        return target_biz_set, to_be_deleted_strategy_ids

    @classmethod
    def smart_refresh(cls):
        """
        增量更新，默认300s内变更的业务将被更新。 更新后将设置最后更新时间。
        """
        start_time = time.time()
        exc = None
        # 拿最近更新成功时间
        last_updated = cls.cache.get(cls.LAST_UPDATED_CACHE_KEY) or 0
        # 增量更新范围（默认5min）
        timeshift = 300
        # 根据上次更新时间计算本次更新的时间范围
        if last_updated:
            timeshift = start_time - int(last_updated)
        # 获取策略列表并缓存
        histories = StrategyHistoryModel.objects.filter(create_time__gt=datetime.now() - timedelta(seconds=timeshift))
        # 若无变更策略，则记录日志并返回
        if not histories.exists():
            logger.info(f"[smart_strategy_cache]: no active strategy found in the past {timeshift} seconds, do nothing")
            # 记录执行时间并更新监控指标
            duration = time.time() - start_time
            metrics.ALARM_CACHE_TASK_TIME.labels("0", "smart_strategy", str(exc)).observe(duration)
            metrics.report_all()
            return
        logger.info(f"[smart_strategy_cache]: active strategy found in the past {timeshift} seconds")

        # 处理变更的策略
        target_biz_set, to_be_deleted_strategy_ids = cls.handle_history_strategies(histories)

        # 如果有策略待删除，则记录日志
        if to_be_deleted_strategy_ids:
            logger.info(f"[smart_strategy_cache]: to_be_deleted_strategy_ids: {to_be_deleted_strategy_ids}")

        # 尝试获取目标业务的策略
        try:
            strategies = cls.get_strategies({"bk_biz_id__in": target_biz_set})
        except Exception as e:  # noqa
            # 若获取策略失败，则记录日志并跳过
            logger.info(f"[smart_strategy_cache]: get target strategies error: {e}")
            strategies = []
            exc = e
        # 记录待处理的策略数量
        logger.info(f"[smart_strategy_cache]: {len(strategies)} strategy to be processed")

        # 定义更新策略的函数列表
        def refresh_strategy_ids(_strategies):
            return cls.refresh_strategy_ids(_strategies, [ids[0] for ids in to_be_deleted_strategy_ids])

        def refresh_bk_biz_ids(_strategies):
            return cls.refresh_bk_biz_ids(_strategies, partial=target_biz_set)

        def refresh_strategy(_strategies):
            return cls.refresh_strategy(
                _strategies, old_groups=[ids[1] for ids in to_be_deleted_strategy_ids if ids[1]]
            )

        def refresh_aiops_sdk_strategy_ids(_strategies):
            aiops_sdk_ids, none_aiops_sdk_ids = set(), set()
            for strategy in strategies:
                for item in strategy["items"]:
                    no_data_config = item.get("no_data_config")
                    if no_data_config and no_data_config.get("is_enabled"):
                        aiops_sdk_ids.add(strategy["id"])
                else:
                    none_aiops_sdk_ids.add(strategy["id"])
            old_aiops_sdk_ids = set(cls.get_aiops_sdk_strategy_ids())
            old_aiops_sdk_ids.update(aiops_sdk_ids)
            old_aiops_sdk_ids -= none_aiops_sdk_ids
            old_aiops_sdk_ids -= {ids[0] for ids in to_be_deleted_strategy_ids}

            cls.cache.set(cls.AIOPS_SDK_CACHE_KEY, json.dumps(list(old_aiops_sdk_ids)), cls.CACHE_TIMEOUT)

        def refresh_nodata_strategy_ids(_strategies):
            #
            nodata_strategy_ids, without_nodata_strategy_ids = set(), set()
            for s in strategies:
                for i in s["items"]:
                    no_data_config = i.get("no_data_config")
                    if no_data_config and no_data_config.get("is_enabled"):
                        nodata_strategy_ids.add(s["id"])
                        break
                else:
                    without_nodata_strategy_ids.add(s["id"])

            # 增量更新
            old_nodata_strategy_ids = set(cls.get_nodata_strategy_ids())
            old_nodata_strategy_ids.update(nodata_strategy_ids)
            old_nodata_strategy_ids -= without_nodata_strategy_ids
            old_nodata_strategy_ids -= {ids[0] for ids in to_be_deleted_strategy_ids}

            # 更新无数据策略的缓存
            cls.cache.set(cls.NO_DATA_CACHE_KEY, json.dumps(list(old_nodata_strategy_ids)), cls.CACHE_TIMEOUT)

        # 定义处理函数列表
        processors: list[Callable[[list[dict]], None]] = [
            cls.add_target_shield_condition,
            cls.add_enabled_cluster_condition,
            refresh_strategy_ids,
            refresh_bk_biz_ids,
            refresh_nodata_strategy_ids,
            refresh_aiops_sdk_strategy_ids,
            refresh_strategy,
        ]

        for processor in processors:
            try:
                processor(strategies)
            except Exception as e:
                # 若执行过程中出现异常，则记录日志
                logger.exception(f"[smart_strategy_cache]: refresh strategy error when {processor.__name__}")
                exc = e
        # 记录执行时间并更新最后更新时间的缓存
        duration = time.time() - start_time
        logger.info(f"[smart_strategy_cache]: cache strategy done, cost: {duration}")
        cls.cache.set(cls.LAST_UPDATED_CACHE_KEY, int(start_time), cls.CACHE_TIMEOUT)
        # 更新监控指标
        metrics.ALARM_CACHE_TASK_TIME.labels("0", "strategy", str(exc)).observe(duration)
        metrics.report_all()

        # 推送aiops策略变更至 sdk 依赖的 历史数据维护服务
        change_records = histories.values("operate", "strategy_id", "content", "create_time")
        for change_record in change_records:
            changed_time = change_record["create_time"].timestamp()
            if change_record["operate"] == "delete":
                sync_aiops_strategy_signal("deleted", change_record["strategy_id"], changed_time)
            else:
                # check strategy use aiops
                intelligent_detect = change_record["content"]["items"][0]["query_configs"][0].get(
                    "intelligent_detect", {}
                )
                if intelligent_detect and intelligent_detect.get("use_sdk", False):
                    sync_aiops_strategy_signal("modify", change_record["strategy_id"], changed_time)


class TargetShieldProcessor:
    """
    策略目标抑制处理器
    """

    def __init__(self, strategies: list, cmdb_levels: list[str]):
        self.strategies = strategies
        self.static_nodes = self.get_static_nodes()
        self.dynamic_nodes = self.get_dynamic_nodes()
        self.cmdb_levels = cmdb_levels

    def get_static_nodes(self) -> list[dict]:
        """
        静态节点所属模块列表
        """
        nodes = set()
        for strategy in self.strategies:
            target = strategy["items"][0]["target"][0][0]

            if target["field"] not in [TargetFieldType.host_target_ip, TargetFieldType.host_ip]:
                continue

            for host in target["value"]:
                ip = host.get("bk_target_ip") or host.get("ip", "")
                bk_cloud_id = host.get("bk_target_cloud_id") or host.get("bk_cloud_id", 0)
                bk_host_id = host.get("bk_host_id")
                nodes.add((ip, bk_cloud_id, bk_host_id))

        records = []
        for node in nodes:
            record = {}
            if node[0]:
                record.update({"bk_target_ip": node[0], "bk_target_cloud_id": node[1]})
            if node[2]:
                record["bk_host_id"] = node[2]
            if record:
                records.append(record)
        return records

    def get_dynamic_nodes(self) -> set[tuple]:
        """
        动态节点列表
        """
        nodes = set()
        for strategy in self.strategies:
            target = strategy["items"][0]["target"][0][0]

            if target["field"] not in ["host_topo_node", "service_topo_node"]:
                continue

            for node in target["value"]:
                nodes.add((node["bk_obj_id"], node["bk_inst_id"]))
        return nodes

    def insert_target(self, strategy):
        """
        根据其他策略添加屏蔽条件
        """
        target = strategy["items"][0]["target"][0][0]

        # 静态目标直接跳过
        if target["field"] in [TargetFieldType.host_ip, TargetFieldType.host_target_ip]:
            return

        # 将监控目标按节点类型进行条件分组，比分组节点类型层级低的抑制条件会被加入
        # 如同时存在set和module两种节点，则分为两组条件，set分组条件内会加入module类型的抑制条件
        new_conditions: list[list[dict]] = []
        if self.dynamic_nodes and target["field"] != TargetFieldType.dynamic_group:
            # 将监控目标节点及抑制节点分别按节点类型分组
            eq_targets: dict[str, set] = defaultdict(set)
            neq_targets: dict[str, set] = defaultdict(set)
            for node in target["value"]:
                eq_targets[node["bk_obj_id"]].add(node["bk_inst_id"])
            for dynamic_node in self.dynamic_nodes:
                neq_targets[dynamic_node[0]].add(dynamic_node[1])

            if not eq_targets:
                # 如果监控目标添加则将抑制节点全部加入
                new_conditions.append(
                    [
                        {
                            "field": target["field"],
                            "method": "neq",
                            "value": [
                                {"bk_obj_id": bk_obj_id, "bk_inst_id": bk_inst_id}
                                for bk_obj_id, bk_inst_ids in neq_targets.items()
                                for bk_inst_id in bk_inst_ids
                            ],
                        }
                    ]
                )
            else:
                for bk_obj_id, bk_inst_ids in eq_targets.items():
                    new_condition = [
                        {
                            "field": target["field"],
                            "method": "eq",
                            "value": [{"bk_obj_id": bk_obj_id, "bk_inst_id": bk_inst_id} for bk_inst_id in bk_inst_ids],
                        }
                    ]

                    # 获取比该分组层级低的拓扑节点作为条件
                    neq_nodes = []
                    matched = False
                    for cmdb_level in self.cmdb_levels:
                        if cmdb_level == bk_obj_id:
                            matched = True
                            continue

                        if not matched or cmdb_level not in neq_targets:
                            continue

                        neq_nodes.extend(
                            [
                                {"bk_obj_id": cmdb_level, "bk_inst_id": bk_inst_id}
                                for bk_inst_id in neq_targets[cmdb_level]
                            ]
                        )

                    if neq_nodes:
                        new_condition.append({"field": target["field"], "method": "neq", "value": neq_nodes})

                    new_conditions.append(new_condition)

        # 动态分组处理
        if target["field"] == TargetFieldType.dynamic_group:
            new_conditions.append([target])

        # 静态节点直接抑制
        if not new_conditions:
            new_conditions = [[]]

        if self.static_nodes:
            for condition in new_conditions:
                condition.append({"field": "bk_target_ip", "method": "neq", "value": self.static_nodes})

        strategy["items"][0]["target"] = new_conditions


def smart_refresh():
    StrategyCacheManager.smart_refresh()


def main():
    StrategyCacheManager.refresh()


def sync_aiops_strategy_signal(signal, strategy_id, update_time):
    """
    推送策略变更信号至rabbitmq
    {
        "sync_type": "modify", # "delete"
        "sync_time": 1700000000,
        "strategy_id": 1,
        "strategy_info": {}
    }
    signal: modify, delete

    delete: 已删除的策略（不论是否是aiops策略）, 修改后的策略不包含aiops算法
    modify: 新增的，修改后的 策略包含了aiops算法
    """
    from alarm_backends.service.preparation.tasks import refresh_aiops_sdk_depend_data

    logger.info(f"sync_aiops_strategy_signal: {strategy_id}, {signal}, {update_time}")
    if signal == "modify":
        refresh_aiops_sdk_depend_data.delay(strategy_id, update_time)
