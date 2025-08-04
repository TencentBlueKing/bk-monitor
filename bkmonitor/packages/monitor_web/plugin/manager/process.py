"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from django.utils.translation import gettext as _

from constants.strategy import DataTarget
from core.drf_resource import api, resource
from core.errors.api import BKAPIError
from monitor_web.models.plugin import CollectorPluginMeta
from monitor_web.plugin.manager import BuiltInPluginManager
from monitor_web.plugin.serializers import ProcessSerializer


class BuildInProcessDimension:
    """内置进程采集维度"""

    dimension_info_map = {
        "bk_target_ip": _("目标IP"),
        "bk_target_cloud_id": _("目标机器云区域ID"),
        "bk_collect_config_id": _("采集配置"),
        "bk_biz_id": _("业务ID"),
        "process_name": _("进程名"),
        "pid": _("进程序号"),
        "listen_address": _("监听地址"),
        "listen_port": _("监听端口"),
    }

    def __init__(self, field_name):
        self.field_name = field_name
        self.field_name_description = self.dimension_info_map.get(field_name, field_name)


class BuildInProcessMetric:
    """
    内置进程采集指标
    """

    # 完善内置进程采集指标的单位和描述
    metric_info_map = {
        "process.perf.cpu_total_pct": (_("进程CPU使用率"), "percentunit"),
        "process.perf.io_read_bytes": (_("进程io累计读"), "bytes"),
        "process.perf.io_read_speed": (_("进程io读速率"), "Bps"),
        "process.perf.io_write_bytes": (_("进程io累计写"), "bytes"),
        "process.perf.io_write_speed": (_("进程io写速率"), "Bps"),
        "process.perf.memory_rss_bytes": (_("物理内存"), "bytes"),
        "process.perf.memory_rss_pct": (_("物理内存使用率"), "percentunit"),
        "process.perf.memory_share": (_("共享内存"), "bytes"),
        "process.perf.memory_size": (_("虚拟内存"), "bytes"),
        "process.perf.fd_limit_hard": ("fd_limit_hard", "short"),
        "process.perf.fd_limit_soft": ("fd_limit_soft", "short"),
        "process.perf.fd_open": (_("打开的文件描述符数量"), "short"),
        "process.perf.cpu_system": (_("进程占用系统态时间"), "ms"),
        "process.perf.cpu_total_ticks": (_("整体占用时间"), "ms"),
        "process.perf.cpu_user": (_("进程占用用户态时间"), "ms"),
        "process.perf.cpu_start_time": (_("进程启动时间"), "none"),
        "process.port.alive": (_("端口存活"), "none"),
    }

    def __init__(self, metric_id):
        self.unit = ""
        self.metric_field_name = metric_id.rsplit(".", 1)[-1]
        self.on_init(metric_id)

    def on_init(self, metric_id):
        metric_info = self.metric_info_map.get(metric_id)
        if metric_info:
            self.metric_field_name, self.unit = metric_info

    def to_dict(self):
        return {"unit": self.unit, "metric_field_name": self.metric_field_name, "data_target": DataTarget.HOST_TARGET}

    @classmethod
    def result_table_list(cls):
        return [f"process.{table_name}" for table_name in ProcessPluginManager.metric_info.keys()]


class ProcessPluginManager(BuiltInPluginManager):
    serializer_class = ProcessSerializer
    label = "host_process"

    build_in_dimensions = ["bk_target_ip", "bk_target_cloud_id", "bk_collect_config_id", "bk_biz_id"]

    metric_info = {
        "perf": {
            "metric_list": [
                "cpu_start_time",
                "cpu_system",
                "cpu_total_pct",
                "cpu_total_ticks",
                "cpu_user",
                "fd_limit_hard",
                "fd_limit_soft",
                "fd_open",
                "io_read_bytes",
                "io_read_speed",
                "io_write_bytes",
                "io_write_speed",
                "memory_rss_bytes",
                "memory_rss_pct",
                "memory_share",
                "memory_size",
            ],
            "dimensions": ["process_name", "pid"],
        },
        "port": {"metric_list": ["alive"], "dimensions": ["listen_address", "listen_port", "process_name", "pid"]},
    }

    def gen_metric_info(self) -> list[dict]:
        metrics = []
        for table_name, field_info in self.metric_info.items():
            field_list = []
            for metric_field in field_info["metric_list"]:
                build_in_metric = BuildInProcessMetric(f"process.{table_name}.{metric_field}")
                field_list.append(
                    {
                        "name": metric_field,
                        "is_active": True,
                        "is_diff_metric": False,
                        "type": "double",
                        "monitor_type": "metric",
                        "unit": build_in_metric.unit,
                        "description": getattr(build_in_metric, "metric_field_name", metric_field),
                    }
                )
            for dimension_field in field_info["dimensions"]:
                field_list.append(
                    {
                        "name": dimension_field,
                        "is_active": True,
                        "is_diff_metric": False,
                        "type": "string",
                        "monitor_type": "dimension",
                        "unit": "none",
                        "description": BuildInProcessDimension(dimension_field).field_name_description,
                    }
                )
            metrics.append({"fields": field_list, "table_name": table_name, "table_desc": table_name})
        return metrics

    def get_metric_info_list(self, ts_name):
        metric_info_list = []
        for metric_field in self.metric_info[ts_name]["metric_list"]:
            metric_dict = {
                "field_name": metric_field,
                "tag_list": [
                    {"field_name": dimension, "unit": "none", "type": "string", "description": dimension}
                    for dimension in self.metric_info[ts_name]["dimensions"] + self.build_in_dimensions
                ],
            }
            metric_info_list.append(metric_dict)
        return metric_info_list

    def touch(self, bk_biz_id: int):
        # 确认插件是否被初始化过，如没有创建过，则初始化全局bkprocessbeat虚拟插件
        if self.plugin.create_time is None:
            self.setup()

        # 接入数据源
        self.access(bk_biz_id)

    def get_data_id(self, bk_biz_id: int, ts_name: str):
        if bk_biz_id not in settings.PROCESS_INDEPENDENT_DATAID_BIZ_IDS:
            bk_biz_id = 0
        data_name = resource.custom_report.create_custom_time_series.data_name(bk_biz_id, f"process_{ts_name}")
        return api.metadata.get_data_id({"data_name": data_name, "with_rt_info": False})["bk_data_id"]

    def perf_data_id(self, bk_biz_id: int):
        if bk_biz_id not in settings.PROCESS_INDEPENDENT_DATAID_BIZ_IDS:
            bk_biz_id = 0
        return self.get_data_id(bk_biz_id, "perf")

    def port_data_id(self, bk_biz_id: int):
        if bk_biz_id not in settings.PROCESS_INDEPENDENT_DATAID_BIZ_IDS:
            bk_biz_id = 0
        return self.get_data_id(bk_biz_id, "port")

    def setup(self):
        plugin_setup_dict = {
            "label": self.label,
            "plugin_id": self.plugin.plugin_id,
            "plugin_type": self.plugin.plugin_type,
            "bk_biz_id": 0,
            "plugin_display_name": _("进程采集"),
            "description_md": "",
            "logo": "",
            "version_log": "",
            "metric_json": self.gen_metric_info(),
        }
        # 安装并初始化本采集插件
        resource.plugin.create_plugin(plugin_setup_dict)

    def create_version(self, data):
        version, need_debug = super().create_version(data)
        plugin = CollectorPluginMeta.objects.get(
            bk_tenant_id=version.plugin.bk_tenant_id, plugin_id=version.plugin.plugin_id
        )
        plugin_manager = self.__class__(plugin, self.operator)
        plugin_manager.release_collector_plugin(version)
        return version, need_debug

    def access(self, bk_biz_id: int):
        """
        接入数据源
        """
        for ts_name in self.metric_info:
            # 独立数据源模式
            if bk_biz_id in settings.PROCESS_INDEPENDENT_DATAID_BIZ_IDS:
                table_id = ""
                data_label = f"process.{ts_name},process"
                is_split_measurement = True
            else:
                bk_biz_id = 0
                table_id = f"process.{ts_name}"
                data_label = "process"
                is_split_measurement = False

            # 检查数据源是否存在
            try:
                self.get_data_id(bk_biz_id, ts_name)
                if table_id:
                    api.metadata.get_result_table(table_id=table_id)
                continue
            except BKAPIError:
                pass

            params = {
                "bk_biz_id": bk_biz_id,
                "name": f"process_{ts_name}",
                "scenario": self.label,
                "metric_info_list": self.get_metric_info_list(ts_name),
                "data_label": data_label,
                "is_split_measurement": is_split_measurement,
            }

            if table_id:
                params["table_id"] = table_id

            # 创建自定义上报
            resource.custom_report.create_custom_time_series(params)

    def get_deploy_steps_params(self, plugin_version, param, target_nodes):
        match_type = param["process"]["match_type"]
        collector_params = param["collector"]

        if match_type == "command":
            collector_params.pop("pid_path", "")
        else:
            # 进程匹配参数： 匹配
            collector_params.pop("match_pattern", "")
            # 进程匹配参数：排除
            collector_params.pop("exclude_pattern", "")
            # 维度提取参数， 用正则提取进程启动命令里的维度
            collector_params.pop("extract_pattern", "")
        collector_params = {"config": collector_params}

        deploy_steps = [
            self._get_bkprocessbeat_deploy_step("monitor_process.conf", {"context": collector_params}),
        ]
        return deploy_steps
