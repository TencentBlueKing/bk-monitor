"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import itertools
from itertools import chain

from alarm_backends.constants import NO_DATA_TAG_DIMENSION
from alarm_backends.core.cache.assign import AssignCacheManager
from alarm_backends.core.cache.cmdb import HostManager, ServiceInstanceManager
from alarm_backends.core.control.item import Item
from alarm_backends.core.detect_result import CheckResult
from alarm_backends.service.nodata.scenarios.filters import DimensionRangeFilter
from bkmonitor.utils.cache import mem_cache
from constants.strategy import HOST_SCENARIO, SERVICE_SCENARIO

SCENARIO_CLS = {}


def register_scenario(cls):
    scenarios_type = cls.scenarios_type
    for sce_type in scenarios_type:
        SCENARIO_CLS[sce_type] = cls
    return cls


class BaseScenario:
    def __init__(self, item: Item):
        """
        :param Item 对象
        """
        self.item = item
        self.filter = DimensionRangeFilter()
        self.strategy = item.strategy
        self.no_data_config = item.no_data_config or {"is_enabled": False, "continuous": 5, "agg_dimension": []}

        agg_dimensions = set()
        for query_config in item.query_configs:
            agg_dimensions.update(query_config.get("agg_dimension", []))
        self.agg_dimensions = list(agg_dimensions)

    def get_no_data_dimensions(self):
        """
        :summary: 原始无数据维度，不包含无数据维度tag
        :return:
        """
        return self.no_data_config.get("agg_dimension", [])

    def get_target_instances_dimensions(self):
        """
        :summary: 根据监控目标和历史维度获取无数据检测维度集合（包含无数据维度tag）
        :return:
        """
        target_instances = self.get_target_instances()
        history_dimensions = self.get_history_dimensions()
        missing_target_instances = []

        # 如果有配置监控目标
        if len(self.item.target[0]) > 0:
            if not target_instances:
                # 配置的监控范围不存在实例，则不做无数据告警后续处理
                return [], missing_target_instances
            # 如果无数据维度和监控目标维度一致，则使用监控目标作为无数据维度
            if set(self.get_no_data_dimensions()) == set(target_instances[0].keys()):
                self.add_no_data_tag(target_instances)
                target_instance_dimensions = target_instances
            else:
                # 历史维度按照当前配置过滤，得到待检测的无数据维度（目的是在减少监控目标或者变更监控条件后，过滤掉历史维度数据中该部分数据）
                target_instance_dimensions = []
                target_instances_exist = set()
                for instance in target_instances:
                    for k in list(instance.keys()):
                        if k not in set(self.get_no_data_dimensions()):
                            instance.pop(k)
                target_keys = set(target_instances[0].keys())
                target_instances_set = {
                    target for target in {tuple(sorted(instance.items())) for instance in target_instances}
                }
                for hist in history_dimensions:
                    hist_items = [(key, value) for key, value in hist.items() if key in target_keys]
                    target_filters = tuple(sorted(hist_items))
                    # 按监控目标过滤
                    if target_filters in target_instances_set:
                        target_instance_dimensions.append(hist)
                        target_instances_exist.add(target_filters)
                # 历史维度中不存在的目标实例
                missing_target_instances = [
                    dict(instance, **{NO_DATA_TAG_DIMENSION: True})
                    for instance in target_instances_set - target_instances_exist
                ]
        else:
            target_instance_dimensions = history_dimensions

        # 无数据维度按监控条件过滤
        target_instance_dimensions = [
            instance_dimensions
            for instance_dimensions in target_instance_dimensions
            if not self.filter.filter(instance_dimensions, self.item)
        ]

        return target_instance_dimensions, missing_target_instances

    @staticmethod
    def format_dicts_value_to_str(dimensions):
        if not isinstance(dimensions, list):
            return dimensions

        for dms in dimensions:
            for k in dms:
                dms[k] = str(dms[k])
        return dimensions

    @staticmethod
    def add_no_data_tag(dimensions):
        for dimension in dimensions:
            dimension.update({NO_DATA_TAG_DIMENSION: True})

    def get_target_instances(self):
        """
        :summary: 获取监控目标实例
        """
        raise NotImplementedError()

    def get_history_dimensions(self):
        no_data_dimensions = set(self.get_no_data_dimensions())
        no_data_dimensions.add(NO_DATA_TAG_DIMENSION)
        history_dimensions_keys = CheckResult.get_dimensions_keys(
            service_type="nodata", strategy_id=self.strategy.id, item_id=self.item.id
        )
        history_dimensions = []
        for dms_key in history_dimensions_keys:
            dimension = CheckResult.get_dimension_by_key(
                service_type="nodata",
                strategy_id=self.strategy.id,
                item_id=self.item.id,
                dimensions_md5=dms_key,
            )
            if dimension:
                if set(dimension.keys()) == no_data_dimensions:
                    history_dimensions.append(dimension)
                else:
                    # 清理旧维度数据
                    CheckResult.remove_dimension_by_key(
                        service_type="nodata",
                        strategy_id=self.strategy.id,
                        item_id=self.item.id,
                        dimensions_md5=dms_key,
                    )
        return history_dimensions


@register_scenario
class HostScenario(BaseScenario):
    scenarios_type = HOST_SCENARIO

    def get_target_instances(self):
        mem_cache.clear()
        target = self.item.target
        if len(target[0]) == 0:
            return []
        # 这里只取原始配置的告警范围
        target_data = target[0][0]

        # 静态 IP
        if "bk_target_ip" not in self.get_no_data_dimensions():
            return None

        if target_data["field"] == "bk_target_ip":
            hosts = set(HostManager.refresh_by_biz(self.strategy.bk_biz_id).keys())
            target_instances = [
                inst
                for inst in target_data["value"]
                if "{}|{}".format(inst["bk_target_ip"], inst["bk_target_cloud_id"]) in hosts
            ]
        # 动态拓扑
        elif target_data["field"] == "host_topo_node":
            target_instances = []
            target_topo = {"{}|{}".format(inst["bk_obj_id"], inst["bk_inst_id"]) for inst in target_data["value"]}
            hosts = HostManager.refresh_by_biz(self.strategy.bk_biz_id)
            for host_info in hosts.values():
                host_topo = {node.id for node in chain(*list(host_info.topo_link.values()))}
                if host_topo & target_topo:
                    target_instances.append(
                        {"bk_target_ip": host_info.bk_host_innerip, "bk_target_cloud_id": host_info.bk_cloud_id}
                    )
        # 动态分组
        elif target_data["field"] == "dynamic_group":
            condition = {}
            condition.update(target_data)
            condition["value"] = []
            for group in target_data["value"]:
                condition["value"] += list(group.values())
            bk_host_ids = AssignCacheManager.parse_dynamic_group(condition)["value"]
            hosts = HostManager.refresh_by_biz(self.strategy.bk_biz_id)
            target_instances = [
                {"bk_target_ip": host.bk_host_innerip, "bk_target_cloud_id": host.bk_cloud_id}
                for host in hosts.values()
                if host.bk_host_id in bk_host_ids
            ]
        else:
            target_instances = None
        return self.format_dicts_value_to_str(target_instances)


@register_scenario
class ServiceScenario(BaseScenario):
    scenarios_type = SERVICE_SCENARIO

    def get_target_instances(self):
        mem_cache.clear()
        if not list(itertools.chain(*self.item.target)):
            return []
        target_data = self.item.target[0][0]

        if "bk_target_service_instance_id" in self.get_no_data_dimensions():
            target_topo = {"{}|{}".format(inst["bk_obj_id"], inst["bk_inst_id"]) for inst in target_data["value"]}
            all_services = ServiceInstanceManager.refresh_by_biz(self.strategy.bk_biz_id)
            ServiceInstanceManager.cache_by_biz(self.strategy.bk_biz_id, all_services)
            target_services = []
            for service in list(all_services.values()):
                service_topo = set({node.id for node in chain(*list(service.topo_link.values()))})
                if service_topo & target_topo:
                    target_services.append(service)
            target_instances = [
                {"bk_target_service_instance_id": service.service_instance_id} for service in target_services
            ]
        elif "bk_inst_id" in self.get_no_data_dimensions():
            target_instances = target_data["value"]
        else:
            target_instances = None
        return self.format_dicts_value_to_str(target_instances)


@register_scenario
class UptimeCheckScenario(BaseScenario):
    scenarios_type = ["uptimecheck"]

    def get_target_instances(self):
        return None


@register_scenario
class OtherScenario(BaseScenario):
    scenarios_type = ["other_rt", "application_check", "default"]

    def get_target_instances(self):
        return None


@register_scenario
class KubernetesScenario(BaseScenario):
    scenarios_type = ["kubernetes"]

    def get_target_instances(self):
        return None
