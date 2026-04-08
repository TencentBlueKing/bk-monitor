"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _

from constants.common import CustomEnum
from constants.data_source import DataSourceLabel, DataTypeLabel, ResultTableLabelObj

EVENT_SPECIAL_LIST = ["uptime", "proc_exists", ""]

SYSTEM_PROC_PORT_METRIC_ID = "bk_monitor.proc_port"
SYSTEM_PROC_PORT_DYNAMIC_DIMENSIONS = ["listen", "nonlisten", "not_accurate_listen", "protocol", "bind_ip"]

# 原table_id存入extend_filed字段名
ORIGIN_RESULT_TABLE_ID = "origin_result_table_id"


class DataTarget:
    NONE_TARGET = "none_target"
    SERVICE_TARGET = "service_target"
    HOST_TARGET = "host_target"
    DEVICE_TARGET = "device_target"


# 二级标签  ->  来源标签   ->  数据类型   —>  数据目标

DATA_TARGET_MAP = {
    ResultTableLabelObj.HostObject.os: {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {
            DataTypeLabel.TIME_SERIES: DataTarget.HOST_TARGET,
            DataTypeLabel.EVENT: DataTarget.HOST_TARGET,
            DataTypeLabel.LOG: DataTarget.HOST_TARGET,
        },
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: DataTarget.NONE_TARGET,
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
    },
    ResultTableLabelObj.HostObject.host_process: {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {
            DataTypeLabel.TIME_SERIES: DataTarget.HOST_TARGET,
            DataTypeLabel.EVENT: DataTarget.HOST_TARGET,
            DataTypeLabel.LOG: DataTarget.HOST_TARGET,
        },
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: DataTarget.HOST_TARGET,
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
    },
    ResultTableLabelObj.HostObject.host_device: {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {
            DataTypeLabel.TIME_SERIES: DataTarget.DEVICE_TARGET,
            DataTypeLabel.EVENT: DataTarget.HOST_TARGET,
            DataTypeLabel.LOG: DataTarget.HOST_TARGET,
        },
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: DataTarget.NONE_TARGET,
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
    },
    ResultTableLabelObj.ServicesObj.service_process: {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {
            DataTypeLabel.TIME_SERIES: DataTarget.HOST_TARGET,
            DataTypeLabel.EVENT: DataTarget.HOST_TARGET,
            DataTypeLabel.LOG: DataTarget.HOST_TARGET,
        },
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: DataTarget.NONE_TARGET,
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
    },
    ResultTableLabelObj.ServicesObj.component: {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {
            DataTypeLabel.TIME_SERIES: DataTarget.SERVICE_TARGET,
            DataTypeLabel.LOG: DataTarget.SERVICE_TARGET,
        },
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: DataTarget.NONE_TARGET,
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
    },
    ResultTableLabelObj.ServicesObj.service_module: {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {
            DataTypeLabel.TIME_SERIES: DataTarget.SERVICE_TARGET,
            DataTypeLabel.LOG: DataTarget.SERVICE_TARGET,
        },
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: DataTarget.NONE_TARGET,
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
    },
    ResultTableLabelObj.ApplicationsObj.uptimecheck: {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET},
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: DataTarget.NONE_TARGET,
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
    },
    ResultTableLabelObj.DataCenterObj.hardware_device: {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {
            DataTypeLabel.TIME_SERIES: DataTarget.DEVICE_TARGET,
            DataTypeLabel.EVENT: DataTarget.HOST_TARGET,
            DataTypeLabel.LOG: DataTarget.HOST_TARGET,
        },
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: DataTarget.NONE_TARGET,
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
    },
    ResultTableLabelObj.OthersObj.other_rt: {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {
            DataTypeLabel.TIME_SERIES: DataTarget.HOST_TARGET,
            DataTypeLabel.LOG: DataTarget.HOST_TARGET,
        },
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: DataTarget.NONE_TARGET,
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
        DataSourceLabel.BK_DATA: {
            DataTypeLabel.TIME_SERIES: DataTarget.HOST_TARGET,
        },
    },
    ResultTableLabelObj.ApplicationsObj.application_check: {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {
            DataTypeLabel.TIME_SERIES: DataTarget.HOST_TARGET,
            DataTypeLabel.LOG: DataTarget.HOST_TARGET,
        },
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: DataTarget.NONE_TARGET,
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
    },
    ResultTableLabelObj.ApplicationsObj.apm: {
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.TIME_SERIES: DataTarget.NONE_TARGET,
        },
    },
}


class TargetFieldType:
    host_topo = "host_topo_node"
    service_topo = "service_topo_node"
    host_ip = "ip"
    host_target_ip = "bk_target_ip"

    host_set_template = "host_set_template"
    service_set_template = "service_set_template"
    host_service_template = "host_service_template"
    service_service_template = "service_service_template"
    dynamic_group = "dynamic_group"


class TargetMethodType:
    eq = "eq"
    neq = "neq"
    lte = "lte"
    gte = "gte"
    lt = "lt"
    gt = "gt"
    reg = "reg"
    nreg = "nreg"
    include = "include"
    exclude = "exclude"


AdvanceConditionMethod = ["reg", "nreg", "include", "exclude"]

TargetFieldList = [
    TargetFieldType.host_topo,
    TargetFieldType.service_topo,
    TargetFieldType.host_ip,
    TargetFieldType.host_target_ip,
    TargetFieldType.host_set_template,
    TargetFieldType.service_set_template,
    TargetFieldType.host_service_template,
    TargetFieldType.service_service_template,
]
TargetMethodList = [
    TargetMethodType.eq,
    TargetMethodType.neq,
    TargetMethodType.lte,
    TargetMethodType.gte,
    TargetMethodType.gt,
    TargetMethodType.lt,
    TargetMethodType.reg,
    TargetMethodType.nreg,
    TargetMethodType.include,
    TargetMethodType.exclude,
]


class SourceType:
    BKMONITOR = ("BKMONITOR", _("监控采集"))
    BASEALARM = ("BASEALARM", _("系统事件"))
    BKDATA = ("BKDATA", _("计算平台"))
    CUSTOMEVENT = ("CUSTOMEVENT", _("自定义事件"))
    CUSTOMTIMINGDATA = ("CUSTOMTIMINGDATA", _("自定义时序数据"))


# 无需拆分表维度列表
NOT_SPLIT_DIMENSIONS = ["bk_target_ip", "bk_target_service_instance_id"]

# 拆分表默认维度列表
SPLIT_DIMENSIONS = ["bk_obj_id", "bk_inst_id"]

# 拆分表cmdb_level映射
SPLIT_CMDB_LEVEL_MAP = {"biz": "bk_biz_id", "set": "bk_set_id", "module": "bk_module_id"}

# 集群、服务模板映射
TEMPLATE_MAP = {"SET_TEMPLATE": "set", "SERVICE_TEMPLATE": "module"}

# 实时计算标识
AGG_METHOD_REAL_TIME = "REAL_TIME"


class DimensionFieldType:
    """
    维度字段类型
    """

    Number = "number"
    String = "string"


OS_RESTART_METRIC_ID = "bk_monitor.os_restart"

# 系统时间主机重启、进程端口、PING不可达、自定义字符型对应query_config
EVENT_QUERY_CONFIG_MAP = {
    "ping-gse": {
        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id", "ip", "bk_cloud_id"],
        "agg_interval": 60,
        "agg_method": "MAX",
        "unit": "",
        "result_table_id": "pingserver.base",
        "metric_field": "loss_percent",
        "metric_id": "bk_monitor.ping-gse",
    },
    "os_restart": {
        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
        "agg_interval": 60,
        "agg_method": "MAX",
        "result_table_id": "system.env",
        "unit": "",
        "metric_field": "uptime",
        "metric_id": OS_RESTART_METRIC_ID,
    },
    "proc_port": {
        "agg_dimension": [
            "bk_target_ip",
            "bk_target_cloud_id",
            "display_name",
            "protocol",
            "listen",
            "nonlisten",
            "not_accurate_listen",
            "bind_ip",
        ],
        "agg_interval": 60,
        "agg_method": "MAX",
        "result_table_id": "system.proc_port",
        "unit": "",
        "metric_field": "proc_exists",
        "metric_id": "bk_monitor.proc_port",
    },
}

# 系统时间主机重启、进程端口对应检测算法
EVENT_DETECT_LIST = {
    "os_restart": [{"type": "OsRestart", "config": []}],
    "proc_port": [{"type": "ProcPort", "config": []}],
    "ping-gse": [{"type": "PingUnreachable", "config": []}],
}

# 系统事件的result_table_id代号
SYSTEM_EVENT_RT_TABLE_ID = "system.event"

# gse进程托管指标ID
GSE_PROCESS_REPORT_METRIC_ID = "bk_monitor.gse_process_event"

GSE_EVENT_REPORT_BASE = "gse_event_report_base"

# 拨测指标对应的错误码
UPTIMECHECK_ERROR_CODE_MAP = {"response_code": 3003, "message": 3002}

MAX_RETRIEVE_NUMBER = 10000

# 进程托管事件对应的枚举值
GSE_PROCESS_EVENT_NAME = {
    "process_restart_success": _("进程重启成功"),
    "process_restart_failed": _("进程重启失败"),
    "process_cancel_restart": _("进程不再托管"),
    "process_resource_limit_exceed": _("进程资源超限（单进程维度）"),
    "process_group_resource_limit_exceed": _("进程资源超限（进程组维度）"),
}

# 多指标数据源
MULTI_METRIC_DATA_SOURCES = {
    (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
    (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
    (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
}

HOST_SCENARIO = ["os", "host_process", "host_device"]
SERVICE_SCENARIO = ["service_module", "component", "service_process"]

DATALINK_SOURCE = "__datalink_collecting__"


class StrategySyncType(CustomEnum):
    """策略事件同步类型."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


# 自定义优先级分组前缀
CUSTOM_PRIORITY_GROUP_PREFIX = "PGK:"
