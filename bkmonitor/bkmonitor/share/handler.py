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

    target_eq_map = {"bk_target_ip": ["ip"], "bk_target_cloud_id": ["bk_cloud_id"]}

    def query_configs_check(self, query_configs):
        # 增加主机指标范围校验
        host_metrics = MetricListCache.objects.filter(
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id__in=[0, self.bk_biz_id],
            result_table_label="os",
            data_source_label="bk_monitor",
            data_type_label="time_series",
        ).values_list("metric_field", flat=True)
        process_metrics = MetricListCache.objects.filter(
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id__in=[0, self.bk_biz_id],
            result_table_id="system.proc",
            data_source_label="bk_monitor",
            data_type_label="time_series",
        ).values_list("metric_field", flat=True)
        metrics = query_configs[0].get("metrics", [])
        table = query_configs[0].get("table", "")
        check_metrics = host_metrics
        if self.scene_params["id"] == "process":
            check_metrics = process_metrics

        if not table or not table.startswith("system."):
            raise ParamsPermissionDeniedError(
                {
                    "key": "query_configs.table",
                    "error_params": table,
                    "correct_params": f"system.{table.split('.')[1:]}",
                }
            )
        if metrics and metrics[0]["field"] not in check_metrics:
            raise ParamsPermissionDeniedError(
                {
                    "key": "query_configs.metric.field",
                    "error_params": metrics[0]["field"],
                    "correct_params": list(check_metrics),
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
