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

from django.utils.translation import ugettext as _
from rest_framework import serializers

from bkmonitor.commons.tools import get_host_view_display_fields
from bkmonitor.data_source import (
    BkMonitorLogDataSource,
    BkMonitorTimeSeriesDataSource,
    CustomEventDataSource,
    CustomTimeSeriesDataSource,
)
from bkmonitor.models import QueryConfigModel, StrategyModel
from bkmonitor.utils.common_utils import to_dict
from constants.cmdb import TargetNodeType, TargetObjectType
from core.drf_resource import Resource, api
from monitor_web.collecting.constant import OperationType
from monitor_web.constants import EVENT_TYPE
from monitor_web.models import (
    CollectConfigMeta,
    CollectorPluginMeta,
    CustomEventGroup,
    CustomTSTable,
    PluginVersionHistory,
)
from monitor_web.plugin.constant import PluginType

logger = logging.getLogger(__name__)


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


class GetObservationSceneStatusList(Resource):
    """
    获取观测场景状态列表
    """

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

        data_source = CustomTimeSeriesDataSource(
            bk_biz_id=bk_biz_id,
            table=custom_metric.table_id,
            metrics=[{"field": "COUNT(*)"}],
        )
        records = data_source.query_data(start_time=(int(time.time()) - 180) * 1000, limit=1)
        return bool(records)

    @classmethod
    def check_custom_event(cls, bk_biz_id: int, bk_event_group_id: int) -> bool:
        event_group = CustomEventGroup.objects.filter(bk_event_group_id=bk_event_group_id, bk_biz_id=bk_biz_id).first()
        if not event_group:
            return False

        data_source = CustomEventDataSource(table=event_group.table_id)
        records, total = data_source.query_log(start_time=(int(time.time()) - 180) * 1000, limit=1)
        return bool(records)

    @classmethod
    def check_plugin(cls, bk_biz_id: int, plugin_id: int = None, collect_config_id: int = None) -> bool:
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
        # 获取结果表配置
        if plugin.plugin_type == PluginType.PROCESS:
            db_name = "process"
            table_ids = ["perf"]
        else:
            db_name = "{plugin_type}_{plugin_id}".format(plugin_type=plugin.plugin_type, plugin_id=plugin.plugin_id)
            table_ids = [table["table_name"] for table in plugin.release_version.info.metric_json]

        for table_id in table_ids:
            try:
                data_source = BkMonitorTimeSeriesDataSource(
                    table=f"{db_name.lower()}.{table_id.lower()}",
                    metrics=[{"field": "count(*)"}],
                    filter_dict=filter_dict,
                    group_by=[],
                )
                records = data_source.query_data(
                    start_time=(int(time.time()) - period * 3) * 1000, end_time=int(time.time()) * 1000, limit=1
                )
            except Exception as e:
                logger.exception(e)
                records = []
            if records:
                return True
        return False

    def perform_request(self, params):
        result = {}
        for scene_view_id in params["scene_view_ids"]:
            if scene_view_id.startswith("scene_plugin_"):
                checked = self.check_plugin(
                    bk_biz_id=params["bk_biz_id"], plugin_id=scene_view_id.split("scene_plugin_", 1)[-1]
                )
            elif scene_view_id.startswith("scene_collect_"):
                checked = self.check_plugin(
                    bk_biz_id=params["bk_biz_id"], collect_config_id=scene_view_id.lstrip("scene_collect_")
                )
            elif scene_view_id.startswith("scene_custom_event_"):
                checked = self.check_custom_event(
                    bk_biz_id=params["bk_biz_id"], bk_event_group_id=scene_view_id.lstrip("scene_custom_event_")
                )
            elif scene_view_id.startswith("scene_custom_metric_"):
                checked = self.check_custom_metric(
                    bk_biz_id=params["bk_biz_id"], time_series_group_id=scene_view_id.lstrip("scene_custom_metric_")
                )
            else:
                continue

            result[scene_view_id] = {"status": "SUCCESS" if checked else "NODATA"}

        return result


class GetObservationSceneList(Resource):
    """
    获取观测场景列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    @classmethod
    def strategy_count_group_by_table(cls, bk_biz_id: int):
        strategy_ids = list(StrategyModel.objects.filter(bk_biz_id=bk_biz_id).values_list("id", flat=True))
        query_configs = QueryConfigModel.objects.filter(strategy_id__in=strategy_ids).only("config")
        table_counter = collections.Counter([qc.config.get("result_table_id", "") for qc in query_configs])
        return table_counter

    @classmethod
    def get_collect_plugin_list(cls, bk_biz_id: int):
        plugins = CollectorPluginMeta.objects.filter(bk_biz_id__in=[0, bk_biz_id]).exclude(
            plugin_type__in=[PluginType.SNMP_TRAP, PluginType.LOG]
        )

        table_counter = cls.strategy_count_group_by_table(bk_biz_id)
        result = []
        for plugin in plugins:
            version = plugin.current_version
            table_ids = []
            for table in version.info.metric_json:
                table_ids.append(version.get_result_table_id(plugin, table["table_name"]).lower())

            # 基于插件进行策略统计
            strategy_count = 0
            if table_ids:
                for table_id in table_ids:
                    strategy_count += table_counter.get(table_id, 0)

            # 如果存在未停用的采集任务才进行展示
            collect_config_count = (
                CollectConfigMeta.objects.filter(plugin_id=plugin.plugin_id, bk_biz_id=bk_biz_id)
                .exclude(last_operation=OperationType.STOP)
                .count()
            )

            if collect_config_count == 0:
                continue

            result.append(
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

        collect_configs = CollectConfigMeta.objects.filter(
            bk_biz_id=bk_biz_id, collect_type__in=[PluginType.SNMP_TRAP, PluginType.LOG]
        )
        for collect_config in collect_configs:
            event_group_name = "{}_{}".format(collect_config.plugin.plugin_type, collect_config.plugin.plugin_id)
            group_info = CustomEventGroup.objects.get(name=event_group_name)
            strategy_ids = (
                QueryConfigModel.objects.filter(config__result_table_id=group_info.table_id)
                .values_list("strategy_id", flat=True)
                .distinct()
            )
            strategy_count = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=list(strategy_ids)).count()
            result.append(
                {
                    "id": collect_config.id,
                    "name": collect_config.name,
                    "sub_name": "",
                    "plugin_type": collect_config.collect_type,
                    "scene_type": "plugin",
                    "scenario": collect_config.label,
                    "metric_id": f"bk_monitor.log.{group_info.table_id}",
                    "collect_config_count": 1,
                    "strategy_count": strategy_count,
                    "scene_view_id": f"scene_collect_{collect_config.id}",
                }
            )

        return result

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
