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
import json
from typing import Dict, List, Optional, Set, Tuple

from django.utils.translation import gettext as _

from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.models import MetricListCache
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.models.scene_view import SceneViewModel
from monitor_web.scene_view.builtin import BuiltinProcessor
from monitor_web.scene_view.builtin.utils import sort_panels

# 默认主机排序
DEFAULT_HOST_ORDER = [
    {
        "id": "cpu",
        "title": "CPU",
        "panels": [
            {"id": "bk_monitor.time_series.system.load.load5", "hidden": False},
            {"id": "bk_monitor.time_series.system.cpu_summary.usage", "hidden": False},
            {"id": "bk_monitor.time_series.system.cpu_detail.usage", "hidden": False},
        ],
    },
    {
        "id": "memory",
        "title": _("内存"),
        "panels": [
            {"id": "bk_monitor.time_series.system.mem.free", "hidden": False},
            {"id": "bk_monitor.time_series.system.swap.used", "hidden": False},
            {"id": "bk_monitor.time_series.system.mem.psc_pct_used", "hidden": False},
            {"id": "bk_monitor.time_series.system.mem.psc_used", "hidden": False},
            {"id": "bk_monitor.time_series.system.mem.used", "hidden": False},
            {"id": "bk_monitor.time_series.system.mem.pct_used", "hidden": False},
            {"id": "bk_monitor.time_series.system.swap.pct_used", "hidden": False},
        ],
    },
    {
        "id": "network",
        "title": _("网络"),
        "panels": [
            {"id": "bk_monitor.time_series.system.net.speed_recv_bit", "hidden": False},
            {"id": "bk_monitor.time_series.system.net.speed_sent_bit", "hidden": False},
            {"id": "bk_monitor.time_series.system.net.speed_recv", "hidden": False},
            {"id": "bk_monitor.time_series.system.net.speed_sent", "hidden": False},
            {"id": "bk_monitor.time_series.system.net.speed_packets_sent", "hidden": False},
            {"id": "bk_monitor.time_series.system.net.speed_packets_recv", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_estab", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_timewait", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_listen", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_lastack", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_syn_recv", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_syn_sent", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_finwait1", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_finwait2", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_closing", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_closed", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_udp_indatagrams", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_udp_outdatagrams", "hidden": False},
            {"id": "bk_monitor.time_series.system.netstat.cur_tcp_closewait", "hidden": False},
        ],
    },
    {
        "id": "disk",
        "title": _("磁盘"),
        "panels": [
            {"id": "bk_monitor.time_series.system.disk.in_use", "hidden": False},
            {"id": "bk_monitor.time_series.system.io.r_s", "hidden": False},
            {"id": "bk_monitor.time_series.system.io.w_s", "hidden": False},
            {"id": "bk_monitor.time_series.system.io.util", "hidden": False},
        ],
    },
    {
        "id": "process",
        "title": _("系统进程"),
        "panels": [{"id": "bk_monitor.time_series.system.env.procs", "hidden": False}],
    },
]

# 默认进程图表排序
DEFAULT_PROCESS_ORDER = [
    {
        "id": "__UNGROUP__",
        "title": _("未分组的指标"),
        "panels": [
            {"id": "port_status", "title": _("端口状态"), "hidden": False},
            {"id": "run_time", "title": _("运行时长"), "hidden": False},
            {"id": "bk_monitor.time_series.system.proc.uptime", "title": _("进程运行时间"), "hidden": False},
            {"id": "bk_monitor.time_series.system.proc.cpu_usage_pct", "hidden": False},
            {"id": "bk_monitor.time_series.system.proc.mem_usage_pct", "hidden": False},
            {"id": "bk_monitor.time_series.system.proc.mem_res", "hidden": False},
            {"id": "bk_monitor.time_series.system.proc.mem_virt", "hidden": False},
            {"id": "bk_monitor.time_series.system.proc.fd_num", "hidden": False},
        ],
    },
]

# 聚合方法
DEFAULT_METHOD = "MAX"
METRIC_METHOD = {
    "bk_monitor.time_series.system.proc.mem_res": "sum_without_time",
    "bk_monitor.time_series.system.proc.mem_virt": "sum_without_time",
    "bk_monitor.time_series.system.proc.fd_num": "sum_without_time",
}
METRIC_OS_TYPE = {"bk_monitor.time_series.system.load.load5": "linux"}

# 进程特殊图表
PROCESS_EXTERNAL_PANELS = [
    {
        "id": "port_status",
        "type": "port-status",
        "title": _("端口状态"),
        "targets": [
            {
                "data": {
                    "bk_host_id": "$bk_host_id",
                    "display_name": "$display_name",
                },
                "datasource": "port_status",
                "data_type": "port-status",
                "api": "scene_view.getHostProcessPortStatus",
            }
        ],
    },
    {
        "id": "run_time",
        "type": "text-unit",
        "title": _("运行时长"),
        "targets": [
            {
                "data": {
                    "bk_host_id": "$bk_host_id",
                    "display_name": "$display_name",
                },
                "datasource": "process_uptime",
                "data_type": "text-unit",
                "api": "scene_view.getHostProcessUptime",
            }
        ],
        "calc": "MAX",
    },
]


def get_default_order(view: SceneViewModel):
    """
    获取默认配置
    """
    if view.id == "process":
        return DEFAULT_PROCESS_ORDER
    else:
        # sql查询表名
        row_result_table_ids = [
            ["system.load", "system.cpu_summary", "system.cpu_detail"],  # cpu
            ["system.mem", "system.swap"],  # memory
            ["system.net"],  # network
            ["system.disk", "system.io", "system.netstat"],  # disk
        ]

        for index, result_table_ids in enumerate(row_result_table_ids):
            exists_metric_id = set()
            for panel in DEFAULT_HOST_ORDER[index]["panels"]:
                exists_metric_id.add(panel["id"])
            # 获得已经上报的指标名
            for metric in MetricListCache.objects.filter(
                data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,  # 数据源标签
                data_type_label=DataTypeLabel.TIME_SERIES,  # 数据类型标签
                result_table_id__in=result_table_ids,  # sql查询表名
            ).values("result_table_id", "metric_field"):
                metric_id = f"bk_monitor.time_series.{metric['result_table_id']}.{metric['metric_field']}"
                if metric_id in exists_metric_id:
                    continue
                # 添加非默认的指标
                DEFAULT_HOST_ORDER[index]["panels"].append({"id": metric_id, "hidden": True})
        return DEFAULT_HOST_ORDER


def get_order_config(view: SceneViewModel):
    """
    获取排序配置
    """
    if view and view.order:
        return view.order
    else:
        # 获得需要展示的指标
        default_order = get_default_order(view).copy()
        for row in default_order:
            row["title"] = str(row["title"])
        return default_order


def get_panels(view: SceneViewModel) -> List[Dict]:
    """
    获取指标信息，包含指标信息及该指标需要使用的聚合方法、聚合维度、聚合周期等
    """
    metrics = MetricListCache.objects.filter(
        bk_biz_id__in=[0, view.bk_biz_id],
        result_table_label="host_process" if view.id == "process" else "os",
        data_source_label="bk_monitor",
        data_type_label="time_series",
    )
    if view.id == "process":
        metrics.filter(result_table_id__startswith="system")

    panels = []
    for metric in metrics:
        panel = get_metric_panel(bk_biz_id=view.bk_biz_id, metric=metric, view_id=view.id)
        panels.append(panel)
    return panels


def get_metric_panel(bk_biz_id: int, metric: MetricListCache, view_id: str = "", type: str = "graph") -> Dict:
    metric_id = (
        f"{metric.data_source_label}.{metric.data_type_label}" f".{metric.result_table_id}.{metric.metric_field}"
    )

    method = METRIC_METHOD.get(metric_id, "$method")
    os_type = METRIC_OS_TYPE.get(metric_id)

    # 添加默认维度
    group_by = ["display_name"] if view_id == "process" else []
    filter_dict = {"display_name": "$display_name"} if view_id == "process" else {}
    for dimension in metric.default_dimensions:
        if dimension in group_by or dimension in ["bk_target_ip", "bk_target_cloud_id", "bk_host_id"]:
            continue
        group_by.append(dimension)

    panel = {
        "id": metric_id,
        "type": type,
        "title": metric.metric_field_name,
        "subTitle": f"{metric.result_table_id}.{metric.metric_field}",
        "targets": [
            {
                "data": {
                    "expression": "A",
                    "query_configs": [
                        {
                            "metrics": [{"field": metric.metric_field, "method": method, "alias": "A"}],
                            "interval": "$interval",
                            "table": metric.result_table_id,
                            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                            "data_type_label": DataTypeLabel.TIME_SERIES,
                            "group_by": ["$group_by", *group_by],
                            "where": [],
                            "functions": [{"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}],
                            "filter_dict": {"targets": ["$current_target", "$compare_targets"], **filter_dict},
                        }
                    ],
                },
                "ignore_group_by": ["bk_target_ip", "bk_target_cloud_id"] if is_ipv6_biz(bk_biz_id) else ["bk_host_id"],
                "alias": "",
                "datasource": "time_series",
                "data_type": "time_series",
                "api": "grafana.graphUnifyQuery",
            }
        ],
    }

    if os_type:
        panel["matchDisplay"] = {"os_type": os_type}

    return panel


def get_auto_view_panels(view: SceneViewModel) -> Tuple[List[Dict], List[Dict]]:
    """
    获取平铺视图配置
    """
    panels = get_panels(view)
    if view.id == "process":
        extend_panels: List[Dict] = PROCESS_EXTERNAL_PANELS.copy()
        for panel in extend_panels:
            panel["title"] = str(panel["title"])
        extend_panels = json.loads(json.dumps(extend_panels))
        panels = extend_panels + panels
    panels, order = sort_panels(panels, get_order_config(view))
    return panels, order


class HostBuiltinProcessor(BuiltinProcessor):
    builtin_views: Dict = None

    @classmethod
    def load_builtin_views(cls):
        if cls.builtin_views is None:
            cls.builtin_views = {}
            for filename in ["host", "process"]:
                cls.builtin_views[filename] = cls._read_builtin_view_config(filename)

    @classmethod
    def create_default_views(cls, bk_biz_id: int, scene_id: str, view_type: str, existed_views):
        if view_type != "detail":
            return

        cls.load_builtin_views()

        existed_view_ids: Set[str] = {v.id for v in existed_views}
        create_view_ids = set(cls.builtin_views.keys()) - existed_view_ids
        new_views = []
        for view_id in create_view_ids:
            view_config = cls.builtin_views[view_id]
            new_views.append(
                SceneViewModel(
                    bk_biz_id=bk_biz_id,
                    scene_id=scene_id,
                    type=view_type,
                    id=view_id,
                    name=view_config["name"],
                    mode=view_config["mode"],
                    variables=view_config.get("variables", []),
                    panels=view_config.get("panels", []),
                    list=view_config.get("list", []),
                    order=view_config.get("order", []),
                    options=view_config.get("options", {}),
                )
            )
        if new_views:
            SceneViewModel.objects.bulk_create(new_views)

        # 删除多余的视图
        delete_view_ids = existed_view_ids - set(cls.builtin_views.keys())
        if delete_view_ids:
            SceneViewModel.objects.filter(
                bk_biz_id=bk_biz_id, scene_id=scene_id, type=view_type, id__in=delete_view_ids
            ).delete()

    @classmethod
    def get_view_config(cls, view: SceneViewModel, *args, **kwargs) -> Dict:
        cls.load_builtin_views()

        if view.id not in ["host", "process"]:
            raise TypeError(f"host scene don't have view({view.id})")

        view_config = json.loads(json.dumps(cls.builtin_views[view.id]))
        view_config["panels"], view_config["order"] = get_auto_view_panels(view)

        return view_config

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id == "host"

    @classmethod
    def create_or_update_view(
        cls, bk_biz_id: int, scene_id: str, view_type: str, view_id: str, view_config: Dict
    ) -> Optional[SceneViewModel]:
        view = SceneViewModel.objects.get(bk_biz_id=bk_biz_id, scene_id=scene_id, type=view_type, id=view_id)
        if "order" in view_config:
            view.order = view_config["order"]
        view.save()
        return view
