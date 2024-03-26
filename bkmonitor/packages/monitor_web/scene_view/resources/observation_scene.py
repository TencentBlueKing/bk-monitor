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
import collections
import logging
import time
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from django.utils.translation import ugettext as _
from rest_framework import serializers

from bkmonitor.commons.tools import get_host_view_display_fields
from bkmonitor.data_source import (
    BkMonitorLogDataSource,
    CustomEventDataSource,
    UnifyQuery,
    load_data_source,
)
from bkmonitor.models import QueryConfigModel, StrategyModel
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.common_utils import to_dict
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from constants.cmdb import TargetNodeType, TargetObjectType
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import CacheResource, Resource, api
from monitor_web.collecting.constant import OperationType
from monitor_web.commons.data_access import ResultTable
from monitor_web.constants import EVENT_TYPE
from monitor_web.models import (
    CollectConfigMeta,
    CollectorPluginMeta,
    CustomEventGroup,
    CustomTSTable,
    PluginVersionHistory,
)
from monitor_web.plugin.constant import PluginType
from monitor_web.plugin.manager import PluginManagerFactory

logger = logging.getLogger(__name__)


class ObservationSceneStatus(Enum):
    SUCCESS: str = "SUCCESS"
    # 检测过程出现异常
    CHECK_ERROR: str = "CHECK_ERROR"
    # 未知的检测对象
    UNKNOWN: str = "UNKNOWN"
    # 无数据
    NODATA: str = "NODATA"


class GetPluginCollectConfigIdList(Resource):
    """
    获取插件的未停用采集配置ID列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        plugin_id = serializers.CharField(label="分组ID", required=False, allow_null=True, allow_blank=True)

    def perform_request(self, params):
        collect_configs = (
            CollectConfigMeta.objects.filter(plugin_id=params["plugin_id"], bk_biz_id=params["bk_biz_id"])
            .exclude(last_operation=OperationType.STOP)
            .only("id", "name")
        )

        return [{"id": collect_config.id, "name": collect_config.name} for collect_config in collect_configs]


class GetObservationSceneStatusList(CacheResource):
    """
    获取观测场景状态列表
    """

    cache_type = CacheType.SCENE_VIEW

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        scene_view_ids = serializers.ListField(child=serializers.CharField())

    @classmethod
    def check_custom_metric(cls, bk_biz_id: int, time_series_group_id: int) -> bool:
        custom_metric = CustomTSTable.objects.filter(
            bk_biz_id=bk_biz_id, time_series_group_id=time_series_group_id
        ).first()
        if not custom_metric:
            return False

        sampling_duration = 60 * 3  # 计算三个采集周期
        metrics = [
            {"field": metric["name"], "method": "count"}
            for metric in custom_metric.get_metrics().values()
            if metric["monitor_type"] == "metric"
        ]
        data_source_class = load_data_source(DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES)
        data_source = data_source_class(
            table=custom_metric.table_id,
            metrics=metrics,
            interval=sampling_duration,  # 步长设置为整个时间段，模拟即时查询
        )
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=[data_source], expression="")
        now_ts = int(time.time())
        records = query.query_data(start_time=(now_ts - sampling_duration) * 1000, end_time=now_ts * 1000)

        return records[0]["_result_"] > 0

    @classmethod
    def check_custom_event(cls, bk_biz_id: int, bk_event_group_id: int) -> bool:
        event_group = CustomEventGroup.objects.filter(bk_event_group_id=bk_event_group_id, bk_biz_id=bk_biz_id).first()
        if not event_group:
            return False

        data_source = CustomEventDataSource(table=event_group.table_id)
        records, total = data_source.query_log(start_time=(int(time.time()) - 180) * 1000, limit=1)
        return bool(records)

    @classmethod
    def check_plugin(cls, bk_biz_id: int, plugin_id: str = None, collect_config_id: int = None) -> bool:
        if plugin_id:
            plugin = CollectorPluginMeta.objects.filter(bk_biz_id__in=[0, bk_biz_id], plugin_id=plugin_id).first()
            if not plugin:
                return False

            collect_configs = CollectConfigMeta.objects.filter(bk_biz_id=bk_biz_id, plugin_id=plugin_id)
            collect_config = collect_configs.first()
            if not collect_config:
                return False

            period = 60
            for collect_config in collect_configs:
                period = max(collect_config.deployment_config.params["collector"]["period"], period)
        else:
            collect_config = CollectConfigMeta.objects.filter(id=collect_config_id, bk_biz_id=bk_biz_id).first()
            if not collect_config:
                return False

            plugin = collect_config.plugin
            period = collect_config.deployment_config.params["collector"]["period"]

        if collect_config_id:
            filter_dict = {"bk_collect_config_id": str(collect_config_id)}
        else:
            filter_dict = {}

        # 日志关键字无数据判断
        if plugin.plugin_type == PluginType.LOG or plugin.plugin_type == PluginType.SNMP_TRAP:
            event_group_name = "{}_{}".format(plugin.plugin_type, plugin.plugin_id)
            group_info = CustomEventGroup.objects.filter(name=event_group_name).first()

            if not group_info:
                return False

            try:
                data_source = BkMonitorLogDataSource(
                    bk_biz_id=bk_biz_id,
                    table=group_info.table_id,
                    group_by=[],
                    filter_dict=filter_dict,
                )
                records, total = data_source.query_log(start_time=int(time.time()) * 1000 - period * 3000, limit=1)
            except Exception as e:
                logger.exception(e)
                records = []
            return bool(records)

        filter_dict["bk_biz_id"] = str(bk_biz_id)

        # 指标无数据判断
        if plugin.plugin_type == PluginType.PROCESS:
            db_name = "process"
            metric_info = PluginManagerFactory.get_manager(
                plugin=plugin.plugin_id, plugin_type=plugin.plugin_type
            ).gen_metric_info()
            metric_json = [table for table in metric_info if table["table_name"] == "perf"]
        else:
            db_name = "{plugin_type}_{plugin_id}".format(plugin_type=plugin.plugin_type, plugin_id=plugin.plugin_id)
            metric_json = plugin.release_version.info.metric_json

        sampling_duration = period * 3  # 计算三个采集周期
        result_tables = [ResultTable.new_result_table(table) for table in metric_json]
        for table in result_tables:
            metrics = [
                {"field": field["field_name"], "method": "count"} for field in table.fields if field["tag"] == "metric"
            ]
            data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
            data_source = data_source_class(
                table=f"{db_name.lower()}.{table.table_name}",
                metrics=metrics,
                filter_dict=filter_dict,
                interval=sampling_duration,  # 步长设置为整个时间段，模拟即时查询
            )
            query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=[data_source], expression="")
            now_ts = int(time.time())
            try:
                records = query.query_data(start_time=(now_ts - sampling_duration) * 1000, end_time=now_ts * 1000)
            except Exception as e:
                logger.exception(e)
                continue

            if records[0]["_result_"] > 0:
                return True

        return False

    def get_observation_scene_status(self, bk_biz_id: int, scene_view_id: str) -> str:
        if scene_view_id.startswith("scene_plugin_"):
            checked = self.check_plugin(bk_biz_id=bk_biz_id, plugin_id=scene_view_id.split("scene_plugin_", 1)[-1])
        elif scene_view_id.startswith("scene_collect_"):
            checked = self.check_plugin(
                bk_biz_id=bk_biz_id, collect_config_id=int(scene_view_id.lstrip("scene_collect_"))
            )
        elif scene_view_id.startswith("scene_custom_event_"):
            checked = self.check_custom_event(
                bk_biz_id=bk_biz_id, bk_event_group_id=int(scene_view_id.lstrip("scene_custom_event_"))
            )
        elif scene_view_id.startswith("scene_custom_metric_"):
            checked = self.check_custom_metric(
                bk_biz_id=bk_biz_id, time_series_group_id=int(scene_view_id.lstrip("scene_custom_metric_"))
            )
        else:
            return ObservationSceneStatus.UNKNOWN.value

        return (ObservationSceneStatus.NODATA.value, ObservationSceneStatus.SUCCESS.value)[checked]

    def collect_scene_view_id__status_map(
        self, bk_biz_id: int, scene_view_id: str, scene_view_id__status_map: Dict[str, Dict[str, str]]
    ):
        try:
            status: str = self.get_observation_scene_status(bk_biz_id, scene_view_id)
        except Exception:
            logger.exception(
                "[collect_scene_view_id__status_map] failed to get_observation_scene_status: "
                "bk_biz_id -> %s, collect_scene_view_id -> %s",
                bk_biz_id,
                scene_view_id,
            )
            return

        if status in [ObservationSceneStatus.NODATA.value, ObservationSceneStatus.SUCCESS.value]:
            scene_view_id__status_map[scene_view_id] = {"status": status}

    def perform_request(self, params):
        scene_view_id__status_map: Dict[str, str] = {}
        th_list: List[InheritParentThread] = [
            InheritParentThread(
                target=self.collect_scene_view_id__status_map,
                args=(params["bk_biz_id"], scene_view_id, scene_view_id__status_map),
            )
            for scene_view_id in params["scene_view_ids"]
        ]
        run_threads(th_list)

        return scene_view_id__status_map


class GetObservationSceneList(Resource):
    """
    获取观测场景列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    @classmethod
    def strategy_count_group_by_table(cls, bk_biz_id: int):
        strategy_ids: Set[int] = set(StrategyModel.objects.filter(bk_biz_id=bk_biz_id).values_list("id", flat=True))
        query_configs = QueryConfigModel.objects.filter(strategy_id__in=strategy_ids).only("config")
        table_counter = collections.Counter([qc.config.get("result_table_id", "") for qc in query_configs])
        return table_counter

    @classmethod
    def collect_config_count_group_by_biz_plugin(cls, bk_biz_id: int, plugin_ids: List[str]) -> Dict[str, int]:
        collect_config_metas: List[Dict[str, int]] = (
            CollectConfigMeta.objects.filter(bk_biz_id=bk_biz_id, plugin_id__in=plugin_ids)
            .exclude(last_operation=OperationType.STOP)
            .values("bk_biz_id", "plugin_id")
        )
        return collections.Counter(
            [
                f"{collect_config_meta['bk_biz_id']}-{collect_config_meta['plugin_id']}"
                for collect_config_meta in collect_config_metas
            ]
        )

    @classmethod
    def get_collect_plugin_list(cls, bk_biz_id: int) -> List[Dict[str, Any]]:
        plugins: List[CollectorPluginMeta] = list(
            CollectorPluginMeta.objects.filter(bk_biz_id__in=[0, bk_biz_id]).exclude(
                plugin_type__in=[PluginType.SNMP_TRAP, PluginType.LOG]
            )
        )
        plugin_ids: List[str] = list({plugin.plugin_id for plugin in plugins})
        table_counter: Dict[str, int] = cls.strategy_count_group_by_table(bk_biz_id)
        collect_config_counter: Dict[str, int] = cls.collect_config_count_group_by_biz_plugin(bk_biz_id, plugin_ids)

        plugin_versions: List[PluginVersionHistory] = PluginVersionHistory.objects.filter(
            id__in=CollectorPluginMeta.fetch_id__current_version_id_map(plugin_ids).values()
        ).select_related("info")
        plugin_id__current_version_map: Dict[str, PluginVersionHistory] = {
            plugin_version.plugin_id: plugin_version for plugin_version in plugin_versions
        }

        collect_plugin_list: List[Dict[str, Any]] = []
        for plugin in plugins:
            # 如果存在未停用的采集任务才进行展示
            collect_config_count: int = collect_config_counter.get(f"{bk_biz_id}-{plugin.plugin_id}", 0)
            if collect_config_count == 0:
                continue

            try:
                version: PluginVersionHistory = plugin_id__current_version_map[plugin.plugin_id]
            except KeyError:
                version: PluginVersionHistory = plugin.generate_version(config_version=1, info_version=1)

            table_ids: List[str] = []
            for table in version.info.metric_json:
                table_ids.append(version.get_result_table_id(plugin, table["table_name"]).lower())

            # 基于插件进行策略统计
            strategy_count: int = sum([table_counter.get(table_id, 0) for table_id in table_ids])

            collect_plugin_list.append(
                {
                    "id": plugin.plugin_id,
                    "name": version.info.plugin_display_name or plugin.plugin_id,
                    "sub_name": plugin.plugin_id,
                    "plugin_type": plugin.plugin_type,
                    "scene_type": "plugin",
                    "scenario": plugin.label,
                    "collect_config_count": collect_config_count,
                    "strategy_count": strategy_count,
                    "scene_view_id": f"scene_plugin_{plugin.plugin_id}",
                }
            )

        collect_configs: List[CollectConfigMeta] = list(
            CollectConfigMeta.objects.filter(
                bk_biz_id=bk_biz_id, collect_type__in=[PluginType.SNMP_TRAP, PluginType.LOG]
            ).select_related("plugin")
        )
        id__event_group_name_map: Dict[int, str] = {}
        for collect_config in collect_configs:
            id__event_group_name_map[collect_config.id] = "{}_{}".format(
                collect_config.plugin.plugin_type, collect_config.plugin.plugin_id
            )

        event_group_name__info_map: Dict[str, Dict[str, Any]] = {}
        for event_group_info in CustomEventGroup.objects.filter(name__in=id__event_group_name_map.values()).values(
            "name", "table_id"
        ):
            event_group_name__info_map[event_group_info["name"]] = event_group_info

        for collect_config in collect_configs:
            event_group_name: str = "{}_{}".format(collect_config.plugin.plugin_type, collect_config.plugin.plugin_id)
            group_info: Optional[Dict[str, Any]] = event_group_name__info_map.get(event_group_name)
            if not group_info:
                continue

            collect_plugin_list.append(
                {
                    "id": collect_config.id,
                    "name": collect_config.name,
                    "sub_name": "",
                    "plugin_type": collect_config.collect_type,
                    "scene_type": "plugin",
                    "scenario": collect_config.label,
                    "metric_id": f"bk_monitor.log.{group_info['table_id']}",
                    "collect_config_count": 1,
                    "strategy_count": table_counter.get(group_info["table_id"], 0),
                    "scene_view_id": f"scene_collect_{collect_config.id}",
                }
            )

        return collect_plugin_list

    @classmethod
    def get_custom_metric_list(cls, bk_biz_id: int):
        from monitor_web.custom_report.resources import CustomTimeSeriesList

        tables = CustomTSTable.objects.filter(bk_biz_id=bk_biz_id)
        strategy_counts = CustomTimeSeriesList.get_strategy_count([t.table_id for t in tables])
        return [
            {
                "id": table.time_series_group_id,
                "name": table.name,
                "sub_name": table.data_label if table.data_label else table.bk_data_id,
                "scene_type": "custom_metric",
                "scenario": table.scenario,
                "collect_config_count": 1,
                "strategy_count": strategy_counts.get(table.table_id, 0),
                "scene_view_id": f"scene_custom_metric_{table.time_series_group_id}",
            }
            for table in tables
        ]

    @classmethod
    def get_custom_event_list(cls, bk_biz_id: int):
        from monitor_web.custom_report.resources import QueryCustomEventGroup

        tables = CustomEventGroup.objects.filter(bk_biz_id=bk_biz_id, type=EVENT_TYPE.CUSTOM_EVENT)
        strategy_counts = QueryCustomEventGroup.get_strategy_count_for_each_group([table.table_id for table in tables])
        return [
            {
                "id": table.bk_event_group_id,
                "name": table.name,
                "sub_name": table.data_label if table.data_label else table.bk_data_id,
                "scene_type": "custom_event",
                "scenario": table.scenario,
                "collect_config_count": 1,
                "strategy_count": strategy_counts.get(table.table_id, 0),
                "scene_view_id": f"scene_custom_event_{table.bk_event_group_id}",
            }
            for table in tables
        ]

    def perform_request(self, params):
        result = []
        result.extend(self.get_collect_plugin_list(params["bk_biz_id"]))
        result.extend(self.get_custom_metric_list(params["bk_biz_id"]))
        result.extend(self.get_custom_event_list(params["bk_biz_id"]))
        return result


class GetPluginTargetTopo(Resource):
    """
    获取插件目标拓扑
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        plugin_id = serializers.CharField(label="插件ID")

    @classmethod
    def remove_empty_nodes(cls, node):
        if "ip" in node or "service_instance_id" in node:
            return

        children = []
        for child_node in node.get("children", []):
            if "ip" in child_node or "service_instance_id" in child_node:
                children.append(child_node)
                continue

            cls.remove_empty_nodes(child_node)

            if child_node.get("children"):
                children.append(child_node)
        node["children"] = children

    def perform_request(self, params):
        field, alias_field = get_host_view_display_fields(params["bk_biz_id"])
        collect_configs = CollectConfigMeta.objects.filter(
            plugin_id=params["plugin_id"], bk_biz_id=params["bk_biz_id"]
        ).exclude(last_operation=OperationType.STOP)

        if not collect_configs:
            return []

        target_type = collect_configs[0].target_object_type

        # 查询全部实例
        instances = set()
        for collect_config in collect_configs:
            target_nodes = collect_config.deployment_config.target_nodes
            target_node_type = collect_config.deployment_config.target_node_type

            if not target_nodes:
                continue

            if target_node_type in [TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE]:
                template_ids = [target_node["bk_inst_id"] for target_node in target_nodes]

                if target_type == TargetObjectType.SERVICE:
                    instances.update(
                        api.cmdb.get_service_instance_by_template(
                            bk_biz_id=params["bk_biz_id"], bk_obj_id=target_node_type, template_ids=template_ids
                        )
                    )
                else:
                    instances.update(
                        api.cmdb.get_host_by_template(
                            bk_biz_id=params["bk_biz_id"], bk_obj_id=target_node_type, template_ids=template_ids
                        )
                    )
            elif target_node_type == TargetNodeType.TOPO:
                topo_dict = defaultdict(list)
                for topo_node in target_nodes:
                    topo_dict[topo_node["bk_obj_id"]].append(topo_node["bk_inst_id"])

                if target_type == TargetObjectType.SERVICE:
                    instances.update(
                        api.cmdb.get_service_instance_by_topo_node(bk_biz_id=params["bk_biz_id"], topo_nodes=topo_dict)
                    )
                else:
                    instances.update(
                        api.cmdb.get_host_by_topo_node(bk_biz_id=params["bk_biz_id"], topo_nodes=topo_dict)
                    )
            else:
                bk_host_ids = []
                ips = []
                for target_node in target_nodes:
                    if "bk_host_id" in target_node:
                        bk_host_ids.append(target_node["bk_host_id"])
                    else:
                        ips.append(target_node)

                if ips:
                    instances.update(api.cmdb.get_host_by_ip(bk_biz_id=params["bk_biz_id"], ips=target_nodes))
                else:
                    instances.update(api.cmdb.get_host_by_id(bk_biz_id=params["bk_biz_id"], bk_host_ids=bk_host_ids))

        # 将实例按模块分组
        module_to_dict = defaultdict(list)
        for instance in instances:
            if target_type == TargetObjectType.SERVICE:
                service = {
                    "service_instance_id": instance.service_instance_id,
                    "id": instance.service_instance_id,
                    "name": instance.name,
                    "instance_id": f"service|instance|service|{instance.service_instance_id}",
                    "instance_name": instance.name,
                    "bk_host_id": instance.bk_host_id,
                    "bk_host_name": "",
                    "ip": instance.service_instance_id,
                }
                module_to_dict[instance.bk_module_id].append(service)
            else:
                host = {
                    "bk_cloud_id": instance.bk_cloud_id,
                    "bk_host_name": instance.bk_host_name,
                    "id": instance.bk_host_id,
                    "instance_id": f"host|instance|host|{instance.bk_host_id}",
                    "instance_name": getattr(instance, field, instance.display_name),
                    "bk_host_id": instance.bk_host_id,
                    "ip": instance.bk_host_innerip,
                    "name": getattr(instance, field, instance.display_name),
                    "alias_name": getattr(instance, alias_field, ""),
                }
                for bk_module_id in instance.bk_module_ids:
                    module_to_dict[bk_module_id].append(host)

        if not instances:
            return []

        topo_tree = to_dict(api.cmdb.get_topo_tree(bk_biz_id=params["bk_biz_id"]))
        queue = [topo_tree]
        while queue:
            node = queue.pop()
            node["children"] = node.pop("child")
            queue.extend(node["children"].copy())

            if node["bk_obj_id"] == "module":
                node["children"] = module_to_dict.get(node["bk_inst_id"], [])

        self.remove_empty_nodes(topo_tree)

        return topo_tree["children"]


class GetPluginInfoByResultTable(Resource):
    """
    根据result table id获取采集插件场景信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        result_table_id = serializers.CharField(label="结果表ID", required=True, allow_blank=False)
        data_label = serializers.CharField(label="db标识", required=False, allow_blank=True)

    def perform_request(self, validated_request_data):
        """
        根据结果表名解析插件场景信息
        """
        data_label = validated_request_data.get("data_label", "")
        result_table_id = validated_request_data["result_table_id"]
        filter_params = {}
        if data_label:
            filter_params["data_label"] = data_label
        else:
            filter_params["table_id"] = result_table_id
        # 针对日志等类型的需要通过从DB表获取到table_name
        custom_event = CustomEventGroup.objects.filter(table_id=result_table_id).first()
        plugin_type = plugin_id = ""
        db_name = ""
        scene_view_id = ""
        scene_view_name = ""
        try:
            if custom_event:
                if custom_event.type == "custom_event":
                    # 自定义事件
                    plugin_id = custom_event.bk_event_group_id
                    plugin_type = "custom_event"
                    scene_view_id = f"scene_custom_event_{plugin_id}"
                    scene_view_name = custom_event.name
                else:
                    db_name = custom_event.name
            else:
                custom_metric = CustomTSTable.objects.filter(**filter_params).first()
                if custom_metric:
                    plugin_id = custom_metric.time_series_group_id
                    plugin_type = "custom_metric"
                    scene_view_id = f"scene_custom_metric_{plugin_id}"
                    scene_view_name = custom_metric.name
                else:
                    dbname_separator_index = result_table_id.index(".")
                    db_name = result_table_id[:dbname_separator_index]

            if db_name == "process":
                plugin_id = "bkprocessbeat"
                plugin_type = PluginType.PROCESS
                scene_view_id = f"scene_plugin_{plugin_id}"
                scene_view_name = _("进程采集")
            elif db_name.startswith(PluginType.SNMP_TRAP):
                plugin_type = PluginType.SNMP_TRAP
                plugin_id = db_name[len(PluginType.SNMP_TRAP) + 1 :]
            elif db_name:
                plugin_separator_index = db_name.index("_")
                plugin_type = db_name[:plugin_separator_index]
                plugin_id = db_name[plugin_separator_index + 1 :]
                scene_view_id = f"scene_plugin_{plugin_id}"

            if plugin_id in [PluginType.SNMP_TRAP, PluginType.LOG]:
                collect_config = CollectConfigMeta.objects.filter(
                    plugin_id=plugin_id, bk_biz_id=validated_request_data["bk_biz_id"]
                ).first()
                scene_view_id = f"scene_collect_{collect_config.id}"
                scene_view_name = collect_config.name

            if not scene_view_name:
                # 如果没有场景名称， 通过最新发布版本信息来获取
                scene_view_name = plugin_id
                plugin_version = PluginVersionHistory.objects.filter(
                    plugin_id=plugin_id, stage=PluginVersionHistory.Stage.RELEASE
                ).last()
                if plugin_version:
                    scene_view_name = plugin_version.info.plugin_display_name
                else:
                    # 没有找到对应的插件版本，直接返回空内容
                    plugin_id = scene_view_id = ""
                    plugin_type = scene_view_name = ""
        except BaseException as error:
            logger.warning("decode plugin info by result_table({}) failed, {}".format(result_table_id, str(error)))

        return {
            "plugin_id": plugin_id,
            "plugin_type": plugin_type,
            "result_table_id": result_table_id,
            "data_label": data_label,
            "scene_view_id": scene_view_id,
            "scene_view_name": scene_view_name,
        }
