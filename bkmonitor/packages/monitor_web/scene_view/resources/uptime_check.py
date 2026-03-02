"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict
from typing import Any, cast

from bk_monitor_base.uptime_check import (
    UPTIME_CHECK_TASK_STATUS_NAME_MAP,
    get_task,
    list_groups,
    list_nodes,
    list_tasks,
)
from django.utils.translation import gettext as _
from rest_framework import serializers

from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.time_tools import strftime_local
from bkmonitor.utils.user import get_user_display_name
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import Resource, api, resource
from monitor.models import NODE_IP_TYPE_DICT
from monitor_web.uptime_check.utils import get_uptime_check_task_url_list


class GetUptimeCheckTaskList(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        group_id = serializers.CharField(label="分组ID", required=False, allow_null=True, allow_blank=True)

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = cast(str, get_request_tenant_id())
        query: dict[str, Any] | None = None
        if validated_request_data.get("group_id"):
            query = {"group_ids": [int(validated_request_data["group_id"])]}
        tasks = list_tasks(bk_tenant_id=bk_tenant_id, bk_biz_id=validated_request_data["bk_biz_id"], query=query)
        return [{"id": task.id, "name": task.name} for task in tasks]


class UptimeCheckTaskQuerySerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    task_id = serializers.IntegerField(required=False)
    location = serializers.ListField(required=False, label="地区")
    carrieroperator = serializers.ListField(required=False, label="运营商")
    node = serializers.ListField(required=False, label="节点")


class GetUptimeCheckTaskInfo(ApiAuthResource):
    RequestSerializer = UptimeCheckTaskQuerySerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> Any:
        bk_tenant_id = cast(str, get_request_tenant_id())
        task = get_task(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=validated_request_data["bk_biz_id"],
            task_id=validated_request_data["task_id"],
        )
        groups = list_groups(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=validated_request_data["bk_biz_id"],
            query={"group_ids": task.group_ids},
        )
        nodes = list_nodes(
            bk_tenant_id=bk_tenant_id, bk_biz_id=validated_request_data["bk_biz_id"], query={"node_ids": task.node_ids}
        )
        result = [
            {"name": _("任务名"), "type": "string", "value": task.name},
            {"name": _("拨测类型"), "type": "string", "value": task.protocol},
            {"name": _("拨测分组"), "type": "list", "value": [group.name for group in groups]},
            {"name": _("拨测节点"), "type": "list", "value": [node.name for node in nodes]},
        ]

        if task.protocol == "HTTP":
            if task.config.get("url_list"):
                url_list = task.config["url_list"]
            else:
                url_list = [task.config["urls"]]
            result.append({"name": _("拨测地址"), "type": "list", "value": url_list})

        result.append(
            {
                "name": _("目标地址"),
                "type": "list",
                "value": get_uptime_check_task_url_list(task.model_dump()),
            }
        )

        result.extend(
            [
                {"name": _("状态"), "type": "string", "value": UPTIME_CHECK_TASK_STATUS_NAME_MAP[task.status.value]},
                {"name": _("创建人"), "type": "string", "value": get_user_display_name(task.create_user or "")},
                {"name": _("创建时间"), "type": "string", "value": strftime_local(task.create_time)},
            ]
        )

        return result


class GetUptimeCheckTaskDataResource(ApiAuthResource):
    """
    获取拨测任务数据
    """

    class RequestSerializer(UptimeCheckTaskQuerySerializer):
        metric_field = serializers.ChoiceField(choices=("available", "task_duration"))
        data_format = serializers.ChoiceField(
            choices=("status_map", "percentage_bar", "time_series_chart"), default="status_map"
        )
        top = serializers.IntegerField(required=False)
        bottom = serializers.IntegerField(required=False)
        start_time = serializers.IntegerField(required=False, label="开始时间")
        end_time = serializers.IntegerField(required=False, label="结束时间")

    @classmethod
    def get_status_map(cls, params: dict, series: list[dict]):
        max_value = None
        min_value = None
        for row in series:
            value = row["value"]
            if params["metric_field"] == "task_duration":
                if value < 100:
                    status = 1
                elif 200 > value >= 100:
                    status = 2
                elif 300 > value >= 200:
                    status = 3
                else:
                    status = 4
            else:
                if value >= 0.99:
                    status = 1
                elif 0.99 > value >= 0.95:
                    status = 2
                elif 0.95 > value >= 0.8:
                    status = 3
                else:
                    status = 4
            row["status"] = status
            min_value = value if min_value is None or min_value > value else min_value
            max_value = value if max_value is None or max_value < value else max_value

        if params["metric_field"] == "task_duration":
            extend_value = [
                {"name": _("最快响应时长"), "value": min_value, "unit": "ms"},
                {"name": _("最慢响应时长"), "value": max_value, "unit": "ms"},
            ]
            legend = [
                {"status": 1, "name": "< 100ms"},
                {"status": 2, "name": "< 200ms"},
                {"status": 3, "name": "< 300ms"},
                {"status": 4, "name": ">= 300ms"},
            ]
        else:
            extend_value = [
                {"name": _("最大可用率"), "value": max_value, "unit": "%"},
                {"name": _("最小可用率"), "value": min_value, "unit": "%"},
            ]
            legend = [
                {"status": 1, "name": "99%~100%"},
                {"status": 2, "name": "95%~98%"},
                {"status": 3, "name": "80%~94%"},
                {"status": 4, "name": "0%~79%"},
            ]

        return {
            "series": series,
            "legend": legend,
            "extend_data": extend_value if series else [],
        }

    @classmethod
    def get_percentage_bar(cls, params: dict, series: list[dict]):
        if "top" in params:
            reverse = True
            limit = params["top"]
        elif "bottom" in params:
            reverse = False
            limit = params["bottom"]
        else:
            reverse = True
            limit = None

        series.sort(key=lambda x: x["value"], reverse=reverse)

        if limit:
            series = series[:limit]

        return {"more_data_url": "", "data": series}

    @classmethod
    def get_time_series_chart(cls, params: dict, host_keys, host_to_node):
        bk_tenant_id = cast(str, get_request_tenant_id())
        task = get_task(bk_tenant_id=bk_tenant_id, bk_biz_id=params["bk_biz_id"], task_id=params["task_id"])
        query_params = {
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "interval": task.config.get("period", 60),
                    "filter_dict": {"task_id": str(task.id)},
                    "where": [],
                    "data_label": f"uptimecheck_{task.protocol.lower()}",
                    "table": "",
                    "metrics": [{"field": params["metric_field"], "method": "AVG", "alias": "A"}],
                    "group_by": ["bk_host_id", "ip", "bk_cloud_id"],
                }
            ],
            "bk_biz_id": task.bk_biz_id,
            "expression": "",
            "start_time": params["start_time"],
            "end_time": params["end_time"],
        }

        result = resource.grafana.graph_unify_query(query_params)
        series_list = []
        for series in result["series"]:
            if series["dimensions"].get("bk_host_id"):
                host_key = int(series["dimensions"]["bk_host_id"])
                host_key_name = ["bk_host_id", str(host_key)]
            else:
                ip = series["dimensions"]["ip"]
                bk_cloud_id = int(series["dimensions"]["bk_cloud_id"])
                host_key = (ip, bk_cloud_id)
                host_key_name = [ip, str(bk_cloud_id)]
            if host_key in host_to_node:
                node = host_to_node[host_key]
                # 存在的节点，图例展示使用节点名称
                series["dimensions"] = {"name": node.name}
            else:
                series["dimensions"] = {"name": "|".join(host_key_name) + _("(其他)")}
            if host_key in host_keys:
                series["datapoints"] = [point for point in series["datapoints"]]
                series_list.append(series)
        result["series"] = series_list
        return result

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = validated_request_data["bk_biz_id"]
        task = get_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=validated_request_data["task_id"])

        data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
        datasource_params = {
            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "bk_biz_id": task.bk_biz_id,
            "interval": task.config.get("period", 60),
            "data_label": f"uptimecheck_{task.protocol.lower()}",
            "table": "",
            "filter_dict": {"task_id": str(task.id)},
            "metrics": [{"field": validated_request_data["metric_field"], "method": "AVG", "alias": "A"}],
            "group_by": ["bk_host_id", "ip", "bk_cloud_id"],
        }
        # 通过independent_dataid判断是否是独立数据源
        if task.independent_dataid:
            datasource_params["data_label"] = f"uptimecheck_{task.protocol.lower()}"

        data_source = data_source_class(**datasource_params)
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=[data_source], expression="A")

        records = query.query_data(
            start_time=validated_request_data["start_time"] * 1000, end_time=validated_request_data["end_time"] * 1000
        )

        host_to_node = {}
        # 过滤业务下所有节点时，同时还应该加上通用节点
        # todo: 过滤增加指定业务可见节点
        nodes = list_nodes(bk_tenant_id=bk_tenant_id, bk_biz_id=task.bk_biz_id, query={"include_common": True})

        ip_to_hostid = {}
        hostid_to_ip = {}
        if is_ipv6_biz(bk_biz_id):
            ips = [node.ip for node in nodes if node.ip]
            node_hosts = api.cmdb.get_host_without_biz(bk_tenant_id=bk_tenant_id, ips=ips)["hosts"]
            ip_to_hostid = {(h.ip, h.bk_cloud_id): h.bk_host_id for h in node_hosts}
        else:
            bk_host_ids = [node.bk_host_id for node in nodes if node.bk_host_id]
            node_hosts = api.cmdb.get_host_without_biz(bk_tenant_id=bk_tenant_id, bk_host_ids=bk_host_ids)["hosts"]
            hostid_to_ip = {h.bk_host_id: (h.ip, h.bk_cloud_id) for h in node_hosts}

        for node in nodes:
            if is_ipv6_biz(bk_biz_id):
                if node.bk_host_id:
                    host_to_node[node.bk_host_id] = node
                else:
                    bk_host_id = ip_to_hostid.get(
                        (
                            node.ip,
                            node.plat_id,
                        )
                    )
                    if bk_host_id:
                        host_to_node[bk_host_id] = node
            else:
                if node.ip:
                    host_to_node[(node.ip, node.plat_id)] = node
                else:
                    ip_key = hostid_to_ip.get(node.bk_host_id)
                    if ip_key:
                        host_to_node[ip_key] = node

        location_values = defaultdict(list)
        node_values = defaultdict(list)
        host_keys = set()
        for record in records:
            if record.get("bk_host_id"):
                host_key = int(record["bk_host_id"])
            else:
                host_key = (record["ip"], int(record["bk_cloud_id"]))
            if host_key in host_to_node:
                location = host_to_node[host_key].location.get("city", _("其他"))
                if not location:
                    location = _("其他")
                carrieroperator = host_to_node[host_key].carrieroperator
                node = host_to_node[host_key].name
                ip_type = host_to_node[host_key].ip_type
            else:
                location = _("其他")
                carrieroperator = _("其他")
                node = _("其他")
                ip_type = None

            location_filter = validated_request_data.get("location", [])
            carrieroperator_filter = validated_request_data.get("carrieroperator", [])
            node_filter = validated_request_data.get("node", [])
            ip_type_filter = validated_request_data.get("ip_type", [])

            if location_filter:
                if location not in location_filter:
                    continue
            if carrieroperator_filter:
                if carrieroperator not in carrieroperator_filter:
                    continue
            if node_filter:
                if node not in node_filter:
                    continue
            if ip_type_filter:
                if ip_type and ip_type not in ip_type_filter:
                    continue
            if record["_result_"] is not None:
                location_values[location].append(record["_result_"])
                node_values[node].append(record["_result_"])
                host_keys.add(host_key)

        if validated_request_data["metric_field"] == "available":
            unit = "%"
        else:
            unit = "ms"

        if validated_request_data["data_format"] == "time_series_chart":
            return self.get_time_series_chart(validated_request_data, host_keys, host_to_node)
        data_format_map = {
            "status_map": {"series": location_values, "function": "get_status_map"},
            "percentage_bar": {"series": node_values, "function": "get_percentage_bar"},
        }
        series = []
        for name, values in data_format_map[validated_request_data["data_format"]]["series"].items():
            value = sum(values) / len(values)
            if validated_request_data["metric_field"] == "available":
                value *= 100  # 百分比
            value = round(value, 2)
            series.append({"name": name, "value": value, "unit": unit})
        get_chart = getattr(self, data_format_map[validated_request_data["data_format"]]["function"])
        return get_chart(validated_request_data, series)


class GetUptimeCheckVarListResource(ApiAuthResource):
    """
    获取拨测变量列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.CharField(required=True, label="业务ID")
        var_type = serializers.ChoiceField(choices=("location", "carrieroperator", "node", "ip_type"))

    def perform_request(self, validated_request_data: dict[str, Any]) -> Any:
        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = validated_request_data["bk_biz_id"]
        var_type = validated_request_data["var_type"]
        nodes = list_nodes(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, query={"include_common": True})
        var_list: list[Any] = list(
            [
                getattr(
                    node,
                    var_type if var_type != "node" else "name",
                )
                for node in nodes
            ]
        )

        if validated_request_data["var_type"] == "location":
            var_list = [{"id": item["city"], "name": item["city"]} for item in var_list if item.get("city")]
        else:
            var_list = [{"id": item, "name": NODE_IP_TYPE_DICT.get(item, item)} for item in var_list if item]

        if validated_request_data["var_type"] != "ip_type":
            var_list.append({"id": _("其他"), "name": _("其他")})

        # 按id去重
        existing_ids: set[str] = set()
        unique_var_list: list[dict[str, Any]] = []
        for item in var_list:
            if item["id"] not in existing_ids:
                existing_ids.add(item["id"])
                unique_var_list.append(item)
        return unique_var_list
