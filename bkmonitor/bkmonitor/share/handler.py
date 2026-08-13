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
import json

from django.db.models import Q

from bkmonitor.models import ApiAuthToken, MetricListCache
from bkmonitor.utils.request import get_request, get_request_tenant_id
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from core.errors.share import (
    InvalidParamsError,
    ParamsPermissionDeniedError,
    SearchLockedError,
)
from fta_web.alert.handlers.alert_log import AlertLogHandler
from monitor_web.models import (
    CollectConfigMeta,
    CollectorPluginMeta,
    CustomEventGroup,
    CustomTSTable,
)
from monitor_web.plugin.constant import PluginType

scene_params_mapping = {"sceneId": "scene_id", "sceneType": "type", "dashboardId": "id"}
HOST_SCOPE_VERSION = 1


def validate_host_share_scope(data: dict) -> dict:
    scope = data.get("scope") if isinstance(data, dict) else None
    if not isinstance(scope, dict):
        raise InvalidParamsError({"key": "data.scope"})
    if scope.get("version") != HOST_SCOPE_VERSION:
        raise InvalidParamsError({"key": "data.scope.version"})

    target_type = scope.get("target_type")
    if target_type == "host":
        if not isinstance(scope.get("bk_host_id"), int) or isinstance(scope.get("bk_host_id"), bool):
            raise InvalidParamsError({"key": "data.scope.bk_host_id"})
        return {
            "version": HOST_SCOPE_VERSION,
            "target_type": target_type,
            "bk_host_id": scope["bk_host_id"],
        }
    if target_type == "topo":
        if not scope.get("bk_obj_id"):
            raise InvalidParamsError({"key": "data.scope.bk_obj_id"})
        if not isinstance(scope.get("bk_inst_id"), int) or isinstance(scope.get("bk_inst_id"), bool):
            raise InvalidParamsError({"key": "data.scope.bk_inst_id"})
        return {
            "version": HOST_SCOPE_VERSION,
            "target_type": target_type,
            "bk_obj_id": str(scope["bk_obj_id"]),
            "bk_inst_id": scope["bk_inst_id"],
        }
    raise InvalidParamsError({"key": "data.scope.target_type"})


class BaseApiAuthChecker:
    """
    基础场景视图API权限校验
    """

    target_eq_map = {}
    target_cont_map = {}

    def __init__(self, token: ApiAuthToken):
        self.request = get_request(peaceful=True)
        # api权限令牌
        self.token = token
        self.bk_biz_id: int = int(token.namespaces[0][4:])
        self.bk_tenant_id: str = token.bk_tenant_id
        # 时间校验参数
        self.time_params: dict = self.get_time_params()
        # 过滤校验参数、场景校验参数、额外校验参数
        self.filter_params, self.scene_params, self.extra_params = self.get_query_params()
        # 基于过滤校验参数，创建的目标相关参数
        self.target_params: dict = copy.deepcopy(self.filter_params)
        self.set_target_params()

    def check(self, request_data):
        # 锁定查询时间并传递了时间参数，则校验时间查询参数，动态查询暂不校验
        if (
            self.time_params["lock_search"]
            and not self.time_params["default_time_range"]
            and request_data.get("start_time")
            and request_data.get("end_time")
        ):
            self.time_check(request_data["start_time"], request_data["end_time"])
        # 校验基础接口参数
        self.params_check(request_data)
        # 校验通用图表数据查询接口unify_query的查询参数query_configs
        if request_data.get("query_configs"):
            self.query_configs_check(request_data["query_configs"])

    def time_check(self, start_time, end_time):
        if int(start_time) != int(self.time_params["start_time"]) or int(end_time) != int(self.time_params["end_time"]):
            raise SearchLockedError(
                {
                    "error_params": f"{start_time}-{end_time}",
                    "correct_params": f"{self.time_params['start_time']}-{self.time_params['end_time']}",
                }
            )

    def params_check(self, request_data):
        for key, value in {**self.filter_params, **self.target_params, **self.scene_params}.items():
            if request_data.get(key) and str(request_data[key]) != str(value):
                raise ParamsPermissionDeniedError(
                    {"key": key, "error_params": request_data[key], "correct_params": value}
                )

    def strict_params_check(self, target, check_params_keys=None, check_part="targets"):
        if not check_params_keys:
            check_params_keys = self.filter_params.keys()
        for key in check_params_keys:
            if not target.get(key):
                raise InvalidParamsError({"key": f"{check_part}.{key}"})
            origin_params = {**self.filter_params, **self.target_params}
            if str(target[key]) != str(origin_params.get(key, None)):
                raise ParamsPermissionDeniedError(
                    {
                        "key": f"{check_part}.{key}",
                        "error_params": target[key],
                        "correct_params": self.filter_params[key],
                    }
                )

    def query_configs_check(self, query_configs):
        filter_dict = query_configs[0]["filter_dict"]
        if self.filter_params and not filter_dict.get("targets", []):
            raise InvalidParamsError({"key": "query_configs.filter_dict.targets"})
        self.strict_params_check(filter_dict["targets"][0])

    def get_query_params(self):
        # 获取查询参数
        filter_params = {}
        scene_params = {}
        extra_params = self.token.params.get("data", {})
        for key, value in self.token.params.get("data", {}).get("query", {}).items():
            if key.startswith("filter-"):
                new_key = key[7:]
                filter_params[new_key] = value
                extra_params[new_key] = value
            elif key in ["sceneId", "sceneType", "dashboardId"]:
                scene_params[scene_params_mapping[key]] = value
            else:
                extra_params[key] = value

        return filter_params, scene_params, extra_params

    def get_time_params(self):
        time_params = {
            "lock_search": self.token.params["lock_search"],
            "default_time_range": self.token.params.get("default_time_range", []),
            "start_time": self.token.params["start_time"],
            "end_time": self.token.params["end_time"],
        }
        return time_params

    def set_target_params(self):
        for key, mapping_keys in self.target_eq_map.items():
            if not self.extra_params.get(key):
                continue
            for mapping_key in mapping_keys:
                self.target_params[mapping_key] = self.extra_params[key]
        for key, mapping_keys in self.target_cont_map.items():
            for mapping_key in mapping_keys:
                self.target_params[mapping_key] = [self.extra_params[key]]


class HostApiAuthChecker(BaseApiAuthChecker):
    """
    主机视图API权限校验
    """

    TARGET_INDEPENDENT_PANEL_ACTIONS = {
        "get_host_views_panels",
        "get_host_metric_group_panel_order",
        "get_process_views_panels",
        "get_process_metric_group_panel_order",
    }

    def __init__(self, token):
        super().__init__(token)
        self.scope = validate_host_share_scope(token.params.get("data", {}))
        self.allowed_hosts = self.get_allowed_hosts()

    def get_allowed_hosts(self):
        if self.scope["target_type"] == "host":
            hosts = api.cmdb.get_host_by_id(
                bk_biz_id=self.bk_biz_id,
                bk_host_ids=[self.scope["bk_host_id"]],
            )
        else:
            hosts = api.cmdb.get_host_by_topo_node(
                bk_biz_id=self.bk_biz_id,
                topo_nodes={self.scope["bk_obj_id"]: [self.scope["bk_inst_id"]]},
            )
        if not hosts:
            raise ParamsPermissionDeniedError(
                {"key": "data.scope", "error_params": self.scope, "correct_params": "existing host target"}
            )
        return hosts

    @property
    def scope_target(self):
        if self.scope["target_type"] == "host":
            return {"bk_host_id": self.scope["bk_host_id"]}
        return {
            "bk_obj_id": self.scope["bk_obj_id"],
            "bk_inst_id": self.scope["bk_inst_id"],
        }

    def is_target_independent_panel_request(self):
        resolver_match = getattr(self.request, "resolver_match", None)
        view = getattr(resolver_match, "func", None)
        view_cls = getattr(view, "cls", None)
        view_name = f"{getattr(view_cls, '__module__', '')}.{getattr(view_cls, '__name__', '')}"
        method = getattr(self.request, "method", "").lower()
        action = getattr(view, "actions", {}).get(method)
        return (
            view_name == "monitor_web.scene_view.views.SceneViewViewSet"
            and action in self.TARGET_INDEPENDENT_PANEL_ACTIONS
        )

    def check(self, request_data):
        if self.is_target_independent_panel_request():
            # Panel definitions do not contain business target data. Only the four
            # target-independent routes may skip host scope and time checks.
            return

        if self.time_params["lock_search"] and not self.time_params["default_time_range"]:
            if request_data.get("start_time") is None or request_data.get("end_time") is None:
                raise InvalidParamsError({"key": "start_time,end_time"})
            self.time_check(request_data["start_time"], request_data["end_time"])

        if request_data.get("query_configs"):
            self.query_configs_check(request_data["query_configs"])
        else:
            self.params_check(request_data)

    def params_check(self, request_data):
        request_target_keys = {
            key
            for key in ("bk_host_id", "bk_obj_id", "bk_inst_id")
            if key in request_data and request_data[key] not in (None, "")
        }
        unexpected_target_keys = request_target_keys - self.scope_target.keys()
        if unexpected_target_keys:
            raise ParamsPermissionDeniedError(
                {
                    "key": ",".join(sorted(unexpected_target_keys)),
                    "error_params": {key: request_data[key] for key in sorted(unexpected_target_keys)},
                    "correct_params": self.scope_target,
                }
            )

        for key, value in self.scope_target.items():
            if key not in request_data or request_data[key] in (None, ""):
                raise InvalidParamsError({"key": key})
            if str(request_data[key]) != str(value):
                raise ParamsPermissionDeniedError(
                    {"key": key, "error_params": request_data[key], "correct_params": value}
                )

    def query_target_check(self, target, check_part):
        allowed_host_ids = {str(host.bk_host_id) for host in self.allowed_hosts}
        allowed_ip_cloud_ids = {
            (str(ip), str(host.bk_cloud_id))
            for host in self.allowed_hosts
            for ip in {
                getattr(host, "ip", None),
                getattr(host, "bk_host_innerip", None),
                getattr(host, "bk_host_innerip_v6", None),
            }
            if ip
        }

        if target.get("bk_host_id") is not None:
            if str(target["bk_host_id"]) not in allowed_host_ids:
                raise ParamsPermissionDeniedError(
                    {
                        "key": f"{check_part}.bk_host_id",
                        "error_params": target["bk_host_id"],
                        "correct_params": sorted(allowed_host_ids),
                    }
                )
            if target.get("bk_target_ip") is not None or target.get("bk_target_cloud_id") is not None:
                pair = (str(target.get("bk_target_ip")), str(target.get("bk_target_cloud_id")))
                if pair not in allowed_ip_cloud_ids:
                    raise ParamsPermissionDeniedError(
                        {
                            "key": f"{check_part}.bk_target_ip,bk_target_cloud_id",
                            "error_params": pair,
                            "correct_params": sorted(allowed_ip_cloud_ids),
                        }
                    )
            return

        if target.get("bk_target_ip") is not None or target.get("bk_target_cloud_id") is not None:
            if target.get("bk_target_ip") is None or target.get("bk_target_cloud_id") is None:
                raise InvalidParamsError({"key": f"{check_part}.bk_target_ip,bk_target_cloud_id"})
            pair = (str(target["bk_target_ip"]), str(target["bk_target_cloud_id"]))
            if pair not in allowed_ip_cloud_ids:
                raise ParamsPermissionDeniedError(
                    {
                        "key": f"{check_part}.bk_target_ip,bk_target_cloud_id",
                        "error_params": pair,
                        "correct_params": sorted(allowed_ip_cloud_ids),
                    }
                )
            return

        if target.get("bk_obj_id") is not None or target.get("bk_inst_id") is not None:
            if self.scope["target_type"] != "topo":
                raise ParamsPermissionDeniedError(
                    {"key": check_part, "error_params": target, "correct_params": self.scope_target}
                )
            for key, value in self.scope_target.items():
                if key not in target or target[key] in (None, ""):
                    raise InvalidParamsError({"key": f"{check_part}.{key}"})
                if str(target[key]) != str(value):
                    raise ParamsPermissionDeniedError(
                        {"key": f"{check_part}.{key}", "error_params": target[key], "correct_params": value}
                    )
            return

        raise InvalidParamsError({"key": check_part})

    def query_configs_check(self, query_configs):
        # 增加主机指标范围校验
        host_metrics = set(
            MetricListCache.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id__in=[0, self.bk_biz_id],
                result_table_label="os",
                data_source_label="bk_monitor",
                data_type_label="time_series",
            ).values_list("result_table_id", "metric_field")
        )
        process_metrics = set(
            MetricListCache.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id__in=[0, self.bk_biz_id],
                result_table_id="system.proc",
                data_source_label="bk_monitor",
                data_type_label="time_series",
            ).values_list("result_table_id", "metric_field")
        )

        for index, query_config in enumerate(query_configs):
            if not isinstance(query_config, dict):
                raise InvalidParamsError({"key": f"query_configs.{index}"})
            metrics = query_config.get("metrics", [])
            data_source_label = query_config.get("data_source_label")
            data_type_label = query_config.get("data_type_label")
            promql = query_config.get("promql", "")
            if (
                data_source_label != DataSourceLabel.BK_MONITOR_COLLECTOR
                or data_type_label != DataTypeLabel.TIME_SERIES
                or not isinstance(promql, str)
                or bool(promql.strip())
                or not isinstance(metrics, list)
                or not metrics
            ):
                raise ParamsPermissionDeniedError(
                    {
                        "key": f"query_configs.{index}",
                        "error_params": {
                            "data_source_label": data_source_label,
                            "data_type_label": data_type_label,
                            "promql": promql,
                            "metrics": metrics,
                        },
                        "correct_params": {
                            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                            "data_type_label": DataTypeLabel.TIME_SERIES,
                            "promql": "",
                            "metrics": "non-empty",
                        },
                    }
                )

            table = query_config.get("table", "")
            if not table or not table.startswith("system."):
                raise ParamsPermissionDeniedError(
                    {
                        "key": f"query_configs.{index}.table",
                        "error_params": table,
                        "correct_params": "system.*",
                    }
                )

            filter_dict = query_config.get("filter_dict", {})
            if not isinstance(filter_dict, dict):
                raise InvalidParamsError({"key": f"query_configs.{index}.filter_dict"})
            targets = filter_dict.get("targets")
            if not isinstance(targets, list) or not targets:
                raise InvalidParamsError({"key": f"query_configs.{index}.filter_dict.targets"})
            for target_index, target in enumerate(targets):
                if not isinstance(target, dict):
                    raise InvalidParamsError({"key": f"query_configs.{index}.filter_dict.targets.{target_index}"})
                self.query_target_check(
                    target,
                    check_part=f"query_configs.{index}.filter_dict.targets.{target_index}",
                )

            allowed_metrics = process_metrics if table == "system.proc" else host_metrics
            for metric_index, metric in enumerate(metrics):
                if not isinstance(metric, dict):
                    raise InvalidParamsError({"key": f"query_configs.{index}.metrics.{metric_index}"})
                metric_field = metric.get("field")
                if not metric_field or (table, metric_field) not in allowed_metrics:
                    raise ParamsPermissionDeniedError(
                        {
                            "key": f"query_configs.{index}.metrics.{metric_index}.field",
                            "error_params": metric_field,
                            "correct_params": list(allowed_metrics),
                        }
                    )


class UptimeCheckApiAuthChecker(BaseApiAuthChecker):
    """
    拨测视图API权限校验
    """

    def query_configs_check(self, request_data):
        # 无查询参数接口，跳过
        pass


class EventApiAuthChecker(BaseApiAuthChecker):
    """
    事件详情API权限校验
    """

    target_eq_map = {"eventId": ["id", "event_id", "alert_id"]}
    target_cont_map = {"eventId": ["alert_ids"]}

    def __init__(self, token):
        super().__init__(token)
        # 范围校验参数
        self.range_params = self.get_range_params()

    def get_range_params(self):
        handler = AlertLogHandler(self.extra_params["eventId"])
        actions = handler.search(operate_list=["ACTION"])
        return {"parent_action_id": [str(action["action_id"]) for action in actions]}

    def range_params_check(self, request_data):
        # 校验请求参数是否在有权限参数范围内
        for key, value in self.range_params.items():
            if request_data.get(key) and str(request_data[key]) not in value:
                raise ParamsPermissionDeniedError(
                    {"key": key, "error_params": request_data[key], "correct_params": value}
                )

    def check(self, request_data):
        # 校验基础接口参数
        self.scene_params["search_type"] = "event"
        self.params_check(request_data)
        self.range_params_check(request_data)
        # 暂不处理unify_query & 获取关联场景接口


class CollectApiAuthChecker(BaseApiAuthChecker):
    """
    采集检查视图API权限校验
    """

    def query_configs_check(self, query_configs):
        if self.scene_params["scene_id"].startswith("collect_"):
            bk_collect_config_id = int(self.scene_params["scene_id"].lstrip("collect_"))
            plugin = CollectConfigMeta.objects.get(bk_tenant_id=self.bk_tenant_id, id=bk_collect_config_id).plugin
            # targets校验
            filter_dict = query_configs[0]["filter_dict"]
            if self.filter_params and filter_dict.get("targets", []):
                self.strict_params_check(filter_dict["targets"][0])
            # filter_dict校验
            self.filter_params["bk_collect_config_id"] = [str(bk_collect_config_id)]
            self.params_check(filter_dict)
        else:
            plugin_id = self.scene_params["scene_id"].lstrip("scene_plugin_")
            plugin = CollectorPluginMeta.objects.get(bk_tenant_id=self.bk_tenant_id, plugin_id=plugin_id)

        # 结果表范围校验，暂不校验内部
        plugin_type = plugin.plugin_type.lower()
        if plugin_type not in [PluginType.PUSHGATEWAY, PluginType.SCRIPT, PluginType.EXPORTER]:
            pass
        plugin_id = plugin.plugin_id
        table = query_configs[0].get("table", "")
        if table and not table.startswith(f"{plugin_type}_{plugin_id}."):
            raise ParamsPermissionDeniedError(
                {"key": "query_configs.table", "error_params": table, "correct_params": f"{plugin_type}_{plugin_id}."}
            )


class CustomMetricApiAuthChecker(BaseApiAuthChecker):
    """
    自定义指标视图API权限校验
    """

    def query_configs_check(self, query_configs):
        custom_metric_id = int(self.scene_params["scene_id"].split("_")[-1])
        config = CustomTSTable.objects.get(
            Q(bk_biz_id=self.bk_biz_id) | Q(is_platform=True),
            pk=custom_metric_id,
            bk_tenant_id=get_request_tenant_id(),
        )
        table = query_configs[0].get("table", "")
        if table and not table.startswith(config.table_id):
            raise ParamsPermissionDeniedError(
                {"key": "query_configs.table", "error_params": table, "correct_params": config.table_id}
            )


class CustomEventApiAuthChecker(BaseApiAuthChecker):
    """
    自定义事件视图API权限校验
    """

    def query_configs_check(self, query_configs):
        custom_event_id = int(self.scene_params["scene_id"].lstrip("custom_event_"))
        config = CustomEventGroup.objects.get(
            Q(bk_biz_id=self.bk_biz_id) | Q(is_platform=True), bk_tenant_id=self.bk_tenant_id, pk=custom_event_id
        )
        table = query_configs[0].get("table", "")
        if table and not table.startswith(config.table_id):
            raise ParamsPermissionDeniedError(
                {"key": "query_configs.table", "error_params": table, "correct_params": config.table_id}
            )
        super().query_configs_check(query_configs)

    def log_query_check(self, request_data):
        custom_event_id = int(self.scene_params["scene_id"].lstrip("custom_event_"))
        config = CustomEventGroup.objects.get(
            Q(bk_biz_id=self.bk_biz_id) | Q(is_platform=True), bk_tenant_id=self.bk_tenant_id, pk=custom_event_id
        )
        table = request_data.get("result_table_id", "")
        if table != config.table_id:
            raise ParamsPermissionDeniedError(
                {"key": "result_table_id", "error_params": table, "correct_params": config.table_id}
            )
        if self.filter_params and not request_data["filter_dict"].get("targets", []):
            raise InvalidParamsError({"key": "query_configs.filter_dict.targets"})
        self.strict_params_check(request_data["filter_dict"]["targets"][0])

    def check(self, request_data):
        super().check(request_data)
        if request_data.get("filter_dict"):
            self.log_query_check(request_data)


class KubernetesApiAuthChecker(BaseApiAuthChecker):
    """
    容器视图API权限校验
    """

    target_eq_map = {
        "pod_name_list": ["pod_name"],
        "workload_type": ["workload_kind"],
        "bk_cloud_id": ["bk_target_cloud_id"],
        "node_ip": ["bk_target_ip"],
    }
    where_params_map = {
        "cluster": ["bcs_cluster_id"],
        "workload": ["bcs_cluster_id", "workload_kind", "workload_name", "namespace"],
        "service": ["bcs_cluster_id", "namespace", "pod_name"],
        "pod": ["bcs_cluster_id", "namespace", "pod_name"],
        "container": ["bcs_cluster_id", "container_name", "namespace"],
        "node": ["bk_target_ip", "bk_target_cloud_id"],
        "service_monitor": ["bcs_cluster_id", "bk_monitor_name", "bk_monitor_type"],
        "pod_monitor": ["bcs_cluster_id"],
    }
    query_paths = ["get_kubernetes_workload_status"]

    def set_target_params(self):
        for key, mapping_keys in self.target_eq_map.items():
            if not self.extra_params.get(key):
                continue
            if key == "pod_name_list":
                self.extra_params[key] = json.loads(self.filter_params[key])
                self.filter_params[key] = json.loads(self.filter_params[key])
            for mapping_key in mapping_keys:
                self.target_params[mapping_key] = self.extra_params[key]
        for key, mapping_keys in self.target_cont_map.items():
            for mapping_key in mapping_keys:
                self.target_params[mapping_key] = [self.extra_params[key]]

    def check(self, request_data):
        super().check(request_data)
        # 校验图表查询参数view_options
        if self.scene_params["type"] == "detail":
            if request_data.get("view_options"):
                view_options = request_data["view_options"]
                self.strict_params_check(view_options["filters"])
                self.strict_params_check(view_options)
            if request_data.get("filter_fields"):
                self.strict_params_check(request_data["filter_fields"])

    def query_configs_check(self, query_configs):
        # k8s场景详情视图校验where参数
        if self.scene_params["type"] != "detail":
            return
        else:
            need_check_params = {
                k: v
                for k, v in {**self.filter_params, **self.target_params}.items()
                if k in self.where_params_map.get(self.scene_params["id"], [])
            }
        where = query_configs[0].get("where", [])
        need_check_params_key: list = self.where_params_map[self.scene_params["id"]]
        for key, value in need_check_params.items():
            for where_item in where:
                if where_item["key"] != key:
                    continue
                check_value = [value] if not isinstance(value, list) else value
                if where_item["value"] == check_value:
                    need_check_params_key.remove(key)
                    continue
                else:
                    raise ParamsPermissionDeniedError(
                        {"key": f"where.{key}", "error_params": where_item["value"], "correct_params": check_value}
                    )
        if need_check_params_key:
            raise InvalidParamsError({"key": "query_configs.where"})

    def params_check(self, request_data):
        # 通用参数校验
        for path in self.query_paths:
            # 不校验场景参数的接口，存在冲突参数名
            if path in self.request.path:
                for key, value in {**self.filter_params, **self.target_params}.items():
                    if request_data.get(key) and request_data[key] != value:
                        raise ParamsPermissionDeniedError(
                            {"key": key, "error_params": request_data[key], "correct_params": value}
                        )
                return
        super().params_check(request_data)


class ApmApiAuthChecker(BaseApiAuthChecker):
    """
    APM视图api权限校验
    """

    strict_params_scene_map = {"apm_service": ["service_name"], "endpoint": ["service_name", "span_name"]}
    target_eq_map = {"endpoint_name": ["span_name"]}
    # 请求参数和场景参数有冲突的接口
    query_paths = ["apdex_query", "unify_query"]
    # 强制校验filter_dict的接口
    strict_params_path_map = {"filter_dict": ["top_n_query"], "filter_fields": ["endpoint_list", "error_list"]}
    filter_dict_map = {"error": ["resource.service.name"]}

    def check(self, request_data):
        super().check(request_data)
        for strict_param, paths in self.strict_params_path_map.items():
            for path in paths:
                if path in self.request.path and self.scene_params["type"] != "overview":
                    filter_dict = request_data.get(strict_param, {})
                    if not filter_dict:
                        raise InvalidParamsError({"key": strict_param})
                    self.strict_params_check(filter_dict, check_part=strict_param)

    def params_check(self, request_data):
        # 通用参数校验
        for path in self.query_paths:
            # 不校验场景参数的接口，存在冲突参数名
            if path in self.request.path:
                for key, value in {**self.filter_params, **self.target_params}.items():
                    if request_data.get(key) and request_data[key] != value:
                        raise ParamsPermissionDeniedError(
                            {"key": key, "error_params": request_data[key], "correct_params": value}
                        )
                return
        super().params_check(request_data)

    def query_configs_check(self, query_configs):
        # 校验query_configs的table表名
        table = query_configs[0].get("table", "").split(".")[0]
        if table and not "_".join(table.split("_")[3:]) == self.filter_params["app_name"]:
            raise ParamsPermissionDeniedError(
                {
                    "key": "query_configs.table",
                    "error_params": "_".join(table.split("_")[3:]),
                    "correct_params": self.filter_params["app_name"],
                }
            )

        # 指定场景id或场景类型为详请，则校验query_configs的filter_dict，增加目标参数的严格校验
        if self.scene_params["scene_id"] in self.strict_params_scene_map or self.scene_params["type"] == "detail":
            filter_dict = query_configs[0].get("filter_dict", {})
            if not filter_dict:
                raise InvalidParamsError({"key": "query_configs.filter_dict"})
            check_params_keys = self.strict_params_scene_map.get(
                self.scene_params["scene_id"], []
            ) or self.strict_params_scene_map.get(self.scene_params["id"], [])
            self.strict_params_check(filter_dict, check_params_keys, "filter_dict")


class GrafanaApiAuthChecker(BaseApiAuthChecker):
    # 仪表盘api鉴权暂不支持
    def check(self, request_data):
        pass


class TraceApiAuthChecker(BaseApiAuthChecker):
    # Trace检索视图api鉴权暂不支持
    def check(self, request_data):
        pass
