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

from django.utils.translation import ugettext_lazy as _lazy

GLOBAL_BIZ_ID = 0


class AssignMode:
    BY_RULE = "by_rule"
    ONLY_NOTICE = "only_notice"

    ASSIGN_MODE_CHOICE = [(BY_RULE, _lazy("分派")), (ONLY_NOTICE, _lazy("仅通知"))]


class ActionPluginType:
    NOTICE = "notice"
    WEBHOOK = "webhook"
    JOB = "job"
    SOPS = "sops"
    ITSM = "itsm"
    COMMON = "common"
    COLLECT = "collect"
    MESSAGE_QUEUE = "message_queue"
    AUTHORIZE = "authorize"

    PLUGIN_TYPE_DICT = {
        NOTICE: _lazy("通知"),
        WEBHOOK: _lazy("HTTP回调"),
        JOB: _lazy("作业平台"),
        SOPS: _lazy("标准运维"),
        ITSM: _lazy("流程服务"),
        COMMON: _lazy("通用插件"),
        COLLECT: _lazy("汇总"),
        MESSAGE_QUEUE: _lazy("消息队列"),
        AUTHORIZE: _lazy("授权"),
    }


class ConvergeFunction:
    SKIP_WHEN_SUCCESS = "skip_when_success"
    SKIP_WHEN_PROCEED = "skip_when_proceed"
    WAIT_WHEN_PROCEED = "wait_when_proceed"
    SKIP_WHEN_EXCEED = "skip_when_exceed"
    DEFENSE = "defense"
    COLLECT = "collect"
    COLLECT_ALARM = "collect_alarm"


CONVERGE_FUNCTION = {
    ConvergeFunction.SKIP_WHEN_SUCCESS: _lazy("成功后跳过"),
    ConvergeFunction.SKIP_WHEN_PROCEED: _lazy("执行中跳过"),
    ConvergeFunction.WAIT_WHEN_PROCEED: _lazy("执行中等待"),
    ConvergeFunction.SKIP_WHEN_EXCEED: _lazy("超出后忽略"),
    ConvergeFunction.DEFENSE: _lazy("异常防御审批"),
    ConvergeFunction.COLLECT: _lazy("超出后汇总"),
    ConvergeFunction.COLLECT_ALARM: _lazy("汇总通知"),
}

CONVERGE_FUNCTION_DESCRIPTION = {
    ConvergeFunction.SKIP_WHEN_SUCCESS: _lazy("触发规则后，如果当前策略存在其他的告警已经处理成功，则跳过当前告警的处理"),
    ConvergeFunction.SKIP_WHEN_PROCEED: _lazy("触发规则后，如果当前策略存在其他正在处理的告警，则跳过当前告警的处理"),
    ConvergeFunction.WAIT_WHEN_PROCEED: _lazy("触发规则后，如果当前策略存在其他正在处理的告警，则等其他告警处理完成后再继续处理当前告警"),
    ConvergeFunction.SKIP_WHEN_EXCEED: _lazy("触发规则后，超出数量的告警将不进行处理"),
    ConvergeFunction.DEFENSE: _lazy("触发规则后，对于每个处理动作，都会产生一个审批单据，让负责人审批决定是否需要执行，如同意则继续执行，拒绝或者超时30分钟未审批则直接收敛不处理"),
    ConvergeFunction.COLLECT: _lazy("触发规则后，超出数量的告警将不进行处理，并发送汇总通知"),
}

HIDDEN_CONVERGE_FUNCTION = {"trigger": _lazy("收敛后处理"), "collect_alarm": _lazy("汇总通知")}


class ConvergeStatus:
    SKIPPED = "skipped"
    EXECUTED = "executed"

    CHOICES = [(SKIPPED, _lazy("跳过")), (EXECUTED, _lazy("执行"))]


class FailureType:
    FRAMEWORK_CODE = "framework_code_failure"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    EXECUTE_ERROR = "execute_failure"
    CREATE_ERROR = "create_failure"
    CALLBACK_ERROR = "callback_failure"
    USER_ABORT = "user_abort"
    SYSTEM_ABORT = "system_abort"


FAILURE_TYPE_CHOICES = (
    (FailureType.UNKNOWN, _lazy("处理出错（未分类）")),
    (FailureType.FRAMEWORK_CODE, _lazy("自愈系统异常")),
    (FailureType.TIMEOUT, _lazy("超时")),
    (FailureType.EXECUTE_ERROR, _lazy("事件执行出错")),
    (FailureType.CREATE_ERROR, _lazy("任务创建失败")),
    (FailureType.CALLBACK_ERROR, _lazy("任务回调失败")),
    (FailureType.USER_ABORT, _lazy("用户终止流程")),
)

HIDDEN_CONVERGE_FUNCTION_CHOICES = [(function, desc) for function, desc in HIDDEN_CONVERGE_FUNCTION.items()]

CONVERGE_FUNC_CHOICES = [
    (function, desc) for function, desc in CONVERGE_FUNCTION.items()
] + HIDDEN_CONVERGE_FUNCTION_CHOICES

CONVERGE_DIMENSION = {
    "strategy_id": _lazy("策略"),
    "alert_name": _lazy("告警名称"),
    "bk_set_ids": _lazy("集群"),
    "bk_module_ids": _lazy("模块"),
    "bk_host_id": _lazy("主机"),
    "dimensions": _lazy("维度"),
    "target": _lazy("目标"),
    "rack_id": _lazy("机架"),
    "net_device_id": _lazy("交换机"),
    "idc_unit_name": _lazy("机房"),
    "process": _lazy("进程名称"),
    "port": _lazy("端口"),
    "alarm_attr_id": _lazy("告警特性"),
}

ALL_CONVERGE_DIMENSION = {
    "dimensions": _lazy("维度"),
    "strategy_id": _lazy("策略"),
    "alert_name": _lazy("告警名称"),
    "bk_biz_id": _lazy("业务"),
    "alert_level": _lazy("告警级别"),
    "signal": _lazy("告警信号"),
    "notice_receiver": _lazy("通知人员"),
    "notice_way": _lazy("通知方式"),
    "group_notice_way": _lazy("带组员类型的通知方式"),
    "alert_info": _lazy("告警信息"),
    "notice_info": _lazy("通知信息"),
    "action_info": _lazy("告警套餐信息"),
}

COMPARED_CONVERGE_DIMENSION = {
    "alert_info": _lazy("告警信息"),
    "notice_info": _lazy("通知信息"),
    "action_info": _lazy("告警套餐信息"),
}

SUB_CONVERGE_DIMENSION = {
    "bk_biz_id": _lazy("业务"),
    "alert_level": _lazy("告警级别"),
    "signal": _lazy("告警信号"),
    "notice_receiver": _lazy("通知人员"),
    "notice_way": _lazy("通知方式"),
    "group_notice_way": _lazy("带组员类型的通知方式"),
}

# 默认的通知关联关系
DEFAULT_NOTICE_INTERVAL = 24 * 60 * 60
DEFAULT_NOTICE_ID = 0
DEFAULT_NOTICE_ACTION = {
    "id": DEFAULT_NOTICE_ID,
    "config_id": DEFAULT_NOTICE_ID,
    "user_groups": [],  # 告警组ID
    "signal": ["abnormal", "recovered", "closed"],
    "options": {
        "converge_config": {
            "is_enabled": True,
            "converge_func": "collect",
            "timedelta": 60,
            "count": 1,
            "condition": [
                {"dimension": "strategy_id", "value": ["self"]},
                {"dimension": "dimensions", "value": ["self"]},
                {"dimension": "alert_level", "value": ["self"]},
                {"dimension": "signal", "value": ["self"]},
                {"dimension": "bk_biz_id", "value": ["self"]},
                {"dimension": "notice_receiver", "value": ["self"]},
                {"dimension": "notice_way", "value": ["self"]},
                {"dimension": "notice_info", "value": ["self"]},
            ],
            "need_biz_converge": True,
            "sub_converge_config": {
                "timedelta": 60,
                "count": 2,
                "condition": [
                    {"dimension": "bk_biz_id", "value": ["self"]},
                    {"dimension": "notice_receiver", "value": ["self"]},
                    {"dimension": "notice_way", "value": ["self"]},
                    {"dimension": "alert_level", "value": ["self"]},
                    {"dimension": "signal", "value": ["self"]},
                ],
                "converge_func": "collect_alarm",
            },
        },
        "noise_reduce_config": {},
        "assign_mode": [AssignMode.BY_RULE],
        "start_time": "00:00:00",
        "end_time": "23:59:59",
    },
}


class NotifyStep:
    FAILURE = 1
    SUCCESS = 2
    BEGIN = 3
    APPROVAL = 4
    SKIPPED = 5
    FINISHED = 6


STATUS_NOTIFY_DICT = {
    "received": NotifyStep.BEGIN,
    "converged": NotifyStep.BEGIN,
    "sleep": NotifyStep.BEGIN,
    "running": NotifyStep.BEGIN,
    "waiting": NotifyStep.APPROVAL,
    "failure": NotifyStep.FAILURE,
    "success": NotifyStep.SUCCESS,
    "partial_success": "partial_success",
    "skipped": NotifyStep.SKIPPED,
    "for_notice": "notice",
    "for_reference": NotifyStep.SUCCESS,
    "authorized": NotifyStep.SUCCESS,
    "unauthorized": NotifyStep.SUCCESS,
    "checking": NotifyStep.SUCCESS,
    "finished": NotifyStep.FINISHED,
}

NOTIFY_DESC = {
    NotifyStep.BEGIN: _lazy("开始"),
    NotifyStep.SUCCESS: _lazy("成功"),
    NotifyStep.SKIPPED: _lazy("跳过"),
    "timeout": _lazy("超时"),
    NotifyStep.FAILURE: _lazy("失败"),
    "framework_code_failure": _lazy("内部异常"),
    NotifyStep.APPROVAL: _lazy("等待审批"),
    NotifyStep.FINISHED: _lazy("结束"),
}

VARIABLES = [
    {
        "group": "CMDB_VAR",
        "name": _lazy("CMDB变量"),
        "prefix": "target",
        "desc": {
            "format": _lazy("{{target.对象.字段名}}"),
            "object": [
                {"name": "business", "desc": _lazy("业务")},
                {"name": "host", "desc": _lazy("主机")},
                {"name": "process", "desc": _lazy("进程")},
                {"name": "service", "desc": _lazy("服务实例")},
            ],
            "field": _lazy("CMDB中定义的字段名"),
        },
        "items": [
            {"name": "target.business.bk_biz_id", "desc": _lazy("业务ID"), "example": "2"},
            {"name": "target.business.bk_biz_name", "desc": _lazy("业务名称"), "example": _lazy("蓝鲸")},
            {
                "name": "target.business.bk_biz_developer_string",
                "desc": _lazy("开发人员字符串"),
                "example": "admin,user1,user2",
            },
            {
                "name": "target.business.bk_biz_maintainer_string",
                "desc": _lazy("运维人员字符串"),
                "example": "admin,user1",
            },
            {"name": "target.business.bk_biz_tester_string", "desc": _lazy("测试人员字符串"), "example": "admin,user1"},
            {
                "name": "target.business.bk_biz_productor_string",
                "desc": _lazy("产品人员字符串"),
                "example": "admin,user1",
            },
            {"name": "target.business.operator_string", "desc": _lazy("操作人员字符串"), "example": "admin,user1"},
            {"name": "target.host.module_string", "desc": _lazy("模块名"), "example": "module1,module2"},
            {"name": "target.host.set_string", "desc": _lazy("集群名"), "example": "set1,set2"},
            {"name": "target.host.bk_world_id", "desc": _lazy("主机所在大区ID"), "example": "131"},
            {"name": "target.host.bk_host_id", "desc": _lazy("主机ID"), "example": "1"},
            {"name": "target.host.bk_cloud_id", "desc": _lazy("云区域ID"), "example": "0"},
            {"name": "target.host.bk_cloud_name", "desc": _lazy("云区域名称"), "example": _lazy("默认区域")},
            {"name": "target.host.bk_host_innerip", "desc": _lazy("内网IP"), "example": "127.0.0.1"},
            {"name": "target.host.bk_host_outerip", "desc": _lazy("外网IP"), "example": "127.0.1.11"},
            {"name": "target.host.bk_host_name", "desc": _lazy("主机名"), "example": ""},
            {"name": "target.host.bk_os_name", "desc": _lazy("操作系统名称"), "example": "linux"},
            {"name": "target.host.bk_os_type", "desc": _lazy("操作系统类型(枚举数值)"), "example": "1"},
            {"name": "target.host.operator_string", "desc": _lazy("负责人"), "example": "admin,user1"},
            {"name": "target.host.bk_bak_operator_string", "desc": _lazy("备份负责人"), "example": "admin,user1"},
            {"name": "target.host.bk_comment", "desc": _lazy("备注信息"), "example": "comment"},
            {"name": "target.host.bk_host_name", "desc": _lazy("主机名"), "example": "VM_1,VM_2"},
            {"name": "target.service_instance.service_instance_id", "desc": _lazy("服务实例ID"), "example": "1"},
            {"name": "target.service_instance.name", "desc": _lazy("服务实例名"), "example": "xxx_127.0.1.11"},
            {"name": "target.service_instances.service_instance_id", "desc": _lazy("服务实例ID"), "example": "1,2"},
            {
                "name": "target.service_instances.name",
                "desc": _lazy("服务实例名"),
                "example": "xxx_127.0.1.11,xxx_127.0.1.12",
            },
            {"name": "target.processes[0].port", "desc": _lazy("第i个进程的端口"), "example": "80"},
            {"name": 'target.process["process_name"].bk_process_id', "desc": _lazy("进程ID"), "example": "1"},
            {
                "name": 'target.process["process_name"].bk_process_name',
                "desc": _lazy("进程名称"),
                "example": _lazy("进程1"),
            },
            {"name": 'target.process["process_name"].bk_func_name', "desc": _lazy("进程功能名称"), "example": "java"},
            {"name": 'target.process["process_name"].bind_ip', "desc": _lazy("绑定IP"), "example": "127.0.1.10"},
            {"name": 'target.process["process_name"].port', "desc": _lazy("绑定端口"), "example": "1,2,3-5,7-10"},
        ],
    },
    {
        "group": "CONTENT_VAR",
        "name": _lazy("内容变量"),
        "prefix": "content",
        "desc": {"format": "{{a.b}}", "object": None, "field": None},
        "items": [
            {"name": "content.level", "desc": _lazy("告警级别"), "example": ""},
            {"name": "content.time", "desc": _lazy("最近异常时间"), "example": ""},
            {"name": "content.duration", "desc": _lazy("告警持续时间"), "example": ""},
            {"name": "content.target_type", "desc": _lazy("告警目标类型"), "example": ""},
            {"name": "content.data_source", "desc": _lazy("告警数据来源"), "example": ""},
            {"name": "content.content", "desc": _lazy("告警内容"), "example": ""},
            {"name": "content.biz", "desc": _lazy("告警业务"), "example": ""},
            {"name": "content.target", "desc": _lazy("告警目标"), "example": ""},
            {"name": "content.dimension", "desc": _lazy("告警维度"), "example": ""},
            {"name": "content.detail", "desc": _lazy("告警详情"), "example": ""},
            {"name": "content.related_info", "desc": _lazy("关联信息"), "example": ""},
            {"name": "content.begin_time", "desc": _lazy("首次异常时间"), "example": ""},
            {"name": "content.sms_forced_related_info", "desc": _lazy("关联信息(短信强制发送)"), "example": ""},
            {"name": "content.anomaly_dimensions", "desc": _lazy("维度下钻"), "example": ""},
            {"name": "content.recommended_metrics", "desc": _lazy("关联指标"), "example": ""},
            {"name": "content.appointees", "desc": _lazy("负责人"), "example": "admin,leader"},
            {"name": "content.assign_reason", "desc": _lazy("分派原因"), "example": "system problem"},
            {
                "name": "content.assign_detail",
                "desc": _lazy("分派详情"),
                "example": "http://www.bk.com/?bizId=2#/alarm-dispatch?group_id=1",
            },
            {"name": "content.ack_operators", "desc": _lazy("确认人"), "example": "admin"},
            {"name": "content.ack_reason", "desc": _lazy("确认原因"), "example": "Process Later"},
            {"name": "content.receivers", "desc": _lazy("通知人"), "example": "lisa,tony"},
        ],
    },
    {
        "group": "ALARM_VAR",
        "prefix": "alarm",
        "name": _lazy("告警变量"),
        "desc": {"format": "{{a.b}}", "object": None, "field": None},
        "items": [
            {"name": "alarm.id", "desc": _lazy("告警ID"), "example": "163800442000001"},
            {"name": "alarm.name", "desc": _lazy("告警名称"), "example": "CPU总使用率告警"},
            {"name": 'alarm.dimensions["dimension_name"].display_name', "desc": _lazy("维度名"), "example": "目标IP"},
            {
                "name": 'alarm.dimensions["dimension_name"].display_value',
                "desc": _lazy("维度值"),
                "example": "127.0.0.1",
            },
            {"name": "alarm.level", "desc": _lazy("告警级别"), "example": "1"},
            {"name": "alarm.level_name", "desc": _lazy("告警级别名称"), "example": "致命"},
            {"name": "alarm.begin_time", "desc": _lazy("告警开始时间"), "example": "1970-01-01 00:00:00"},
            {"name": "alarm.duration", "desc": _lazy("告警持续时间(秒)"), "example": "130"},
            {"name": "alarm.duration_string", "desc": _lazy("告警持续时间字符串"), "example": "2m 10s"},
            {"name": "alarm.description", "desc": _lazy("告警内容"), "example": "AVG(CPU使用率) >= 95.0%, 当前值96.317582%"},
            {"name": "alarm.target_string", "desc": _lazy("告警目标"), "example": "127.0.1.10,127.0.1.11"},
            {"name": "alarm.dimension_string", "desc": _lazy("告警维度(除目标)"), "example": _lazy("磁盘=C,主机名=xxx")},
            {"name": "alarm.collect_count", "desc": _lazy("汇总事件数量"), "example": "10"},
            {"name": "alarm.notice_from", "desc": _lazy("消息来源"), "example": _lazy("蓝鲸监控")},
            {"name": "alarm.company", "desc": _lazy("企业标识"), "example": _lazy("蓝鲸")},
            {"name": "alarm.data_source_name", "desc": _lazy("数据来源名称"), "example": _lazy("计算平台")},
            {"name": "alarm.data_source", "desc": _lazy("数据来源"), "example": "BKMONITOR"},
            {"name": "alarm.current_value", "desc": _lazy("当前值"), "example": "1.1"},
            {"name": "alarm.target_type", "desc": _lazy("目标类型"), "example": "IP/INSTANCE/TOPO"},
            {"name": "alarm.target_type_name", "desc": _lazy("目标类型名称"), "example": _lazy("IP/实例/节点")},
            {
                "name": "alarm.detail_url",
                "desc": _lazy("告警详情链接"),
                "example": "http://paas.blueking.com/o/bk_monitorv3/?bizId=1&actionId=2#event-center",
            },
            {"name": "alarm.related_info", "desc": _lazy("关联信息"), "example": _lazy("集群(公共组件) 模块(consul)")},
            {
                "name": "alarm.callback_message",
                "desc": _lazy("回调数据"),
                "example": _lazy(json.dumps({"alarm": "json文本格式"})),
            },
            {
                "name": "alarm.log_related_info",
                "desc": _lazy("日志关联信息"),
                "example": "ERROR 25854 metadata space_table_id_redis.py[330] "
                "space_type: bkci, space_id:_evanxu not found table_id and data_id...",
            },
            {
                "name": "alarm.topo_related_info",
                "desc": _lazy("TOPO关联信息"),
                "example": _lazy("集群(公共组件) 模块(consul)"),
            },
            {
                "name": "alarm.alert_info",
                "desc": _lazy("回调数据【new】"),
                "example": _lazy(json.dumps({"alarm": "the new version content of webhook"})),
            },
            {
                "name": "alarm.bkm_info",
                "desc": _lazy("智能异常检测额外信息"),
                "example": json.dumps(
                    {"anomaly_alert": 1, "anomaly_score": 0.7, "anomaly_uncertainty": 1.43e-05, "alert_msg": "上升异常"}
                ),
            },
            {
                "name": "alarm.anomaly_dimensions",
                "desc": _lazy("维度下钻"),
                "example": "异常维度 2，异常维度值 2",
            },
            {
                "name": "alarm.recommended_metrics",
                "desc": _lazy("关联指标"),
                "example": "0 个指标,0 个维度",
            },
            {
                "name": "alarm.receivers",
                "desc": _lazy("通知人"),
                "example": ["lisa", "tony"],
            },
            {
                "name": "alarm.appointees",
                "desc": _lazy("负责人"),
                "example": ["admin", "leader"],
            },
        ],
    },
    {
        "group": "STRATEGY_VAR",
        "prefix": "strategy",
        "name": _lazy("策略变量"),
        "desc": {"format": "{{a.b}}", "object": None, "field": None},
        "items": [
            {"name": "strategy.strategy_id", "desc": _lazy("策略ID"), "example": "1"},
            {"name": "strategy.name", "desc": _lazy("策略名称"), "example": _lazy("CPU总使用率")},
            {"name": "strategy.scenario", "desc": _lazy("场景"), "example": "os"},
            {"name": "strategy.source_type", "desc": _lazy("数据来源"), "example": "BKMONITOR"},
            {"name": "strategy.bk_biz_id", "desc": _lazy("业务ID"), "example": "2"},
            {"name": "strategy.item.result_table_id", "desc": _lazy("结果表名称"), "example": "system.cpu_detail"},
            {"name": "strategy.item.name", "desc": _lazy("指标名称"), "example": _lazy("空闲率")},
            {"name": "strategy.item.metric_field", "desc": _lazy("指标字段"), "example": "idle"},
            {"name": "strategy.item.unit", "desc": _lazy("单位"), "example": "%"},
            {"name": "strategy.item.agg_interval", "desc": _lazy("周期"), "example": "60"},
            {"name": "strategy.item.agg_method", "desc": _lazy("聚合方法"), "example": "AVG"},
        ],
    },
    {
        "group": "SOLUTION_VAR",
        "prefix": "action_instance",
        "name": _lazy("套餐变量"),
        "desc": {"format": "{{a.b}}", "object": None, "field": None},
        "items": [
            {"name": "action_instance.name", "desc": _lazy("套餐名称"), "example": "机器重启"},
            {"name": "action_instance.plugin_type_name", "desc": _lazy("套餐类型"), "example": _lazy("作业平台")},
            {"name": "action_instance.assignees", "desc": _lazy("负责人"), "example": "admin,tony"},
            {"name": "action_instance.operate_target_string", "desc": _lazy("执行对象"), "example": "127.0.0.1"},
            {"name": "action_instance.bk_biz_id", "desc": _lazy("业务ID"), "example": "2"},
            {"name": "action_instance.start_time", "desc": _lazy("开始时间"), "example": "1970-08-01 10:00:00+08:00"},
            {"name": "action_instance.duration", "desc": _lazy("执行耗时(秒)"), "example": "130"},
            {"name": "action_instance.duration_string", "desc": _lazy("执行耗时字符串"), "example": "2m 10s"},
            {"name": "action_instance.status_display", "desc": _lazy("执行状态"), "example": "执行中"},
            {
                "name": "action_instance.opt_content",
                "desc": _lazy("具体内容"),
                "example": "已经创建作业平台任务，点击查看详情http://www.job.com/",
            },
        ],
    },
]

DEMO_CONTEXT = {
    group_item["prefix"]: {
        var_item["name"].replace("{}.".format(group_item["prefix"]), ""): var_item["example"]
        for var_item in group_item["items"]
    }
    for group_item in VARIABLES
}

DEFAULT_CONVERGE_CONFIG = {
    "is_enabled": True,
    "need_biz_converge": True,
    "timedelta": 60,
    "count": 1,
    "condition": [
        {"dimension": "strategy_id", "value": ["self"]},
        {"dimension": "dimensions", "value": ["self"]},
        {"dimension": "alert_level", "value": ["self"]},
        {"dimension": "signal", "value": ["self"]},
        {"dimension": "bk_biz_id", "value": ["self"]},
        {"dimension": "notice_receiver", "value": ["self"]},
        {"dimension": "notice_way", "value": ["self"]},
    ],
    "converge_func": "collect",
    "sub_converge_config": {
        "timedelta": 60,
        "max_timedelta": 60,
        "count": 2,
        "condition": [
            {"dimension": "bk_biz_id", "value": ["self"]},
            {"dimension": "notice_receiver", "value": ["self"]},
            {"dimension": "notice_way", "value": ["self"]},
            {"dimension": "alert_level", "value": ["self"]},
            {"dimension": "signal", "value": ["self"]},
        ],
        "converge_func": "collect_alarm",
    },
}


class ActionLogLevel:
    DEBUG = 10
    NOT_SET = 0
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class ConvergeType:
    CONVERGE = "converge"
    ACTION = "action"


class ActionDisplayStatus:
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    PARTIAL_FAILURE = "partial_failure"
    FAILURE = "failure"
    SKIPPED = "skipped"
    SHIELD = "shield"


class ActionStatus:
    RECEIVED = "received"
    WAITING = "waiting"
    CONVERGING = "converging"
    SLEEP = "sleep"
    CONVERGED = "converged"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    PARTIAL_FAILURE = "partial_failure"
    SKIPPED = "skipped"
    FOR_NOTICE = "for_notice"
    FOR_REFERENCE = "for_reference"
    SHIELD = "shield"
    RETRYING = "retrying"
    AUTHORIZED = "authorized"
    UNAUTHORIZED = "unauthorized"
    CHECKING = "checking"

    # 执行中的状态
    PROCEED_STATUS = [RECEIVED, WAITING, CONVERGING, SLEEP, CONVERGED, RUNNING]

    END_STATUS = [SUCCESS, PARTIAL_SUCCESS, FAILURE, PARTIAL_FAILURE, SKIPPED, SHIELD]

    CAN_EXECUTE_STATUS = [RECEIVED, CONVERGED, RUNNING, RETRYING]

    IGNORE_STATUS = {RUNNING, SLEEP, SKIPPED, SHIELD}

    CAN_SYNC_STATUS = [
        WAITING,
        CONVERGING,
        SLEEP,
        CONVERGED,
        RUNNING,
        SUCCESS,
        PARTIAL_SUCCESS,
        PARTIAL_FAILURE,
        FAILURE,
        SKIPPED,
        SHIELD,
    ]
    COLLECT_SYNC_STATUS = [WAITING, RUNNING, SUCCESS, PARTIAL_SUCCESS, FAILURE, SKIPPED]


ACTION_DISPLAY_STATUS_CHOICES = (
    (ActionDisplayStatus.RUNNING, _lazy("执行中")),
    (ActionStatus.CONVERGED, _lazy("执行中")),
    (ActionStatus.WAITING, _lazy("异常防御审批中")),
    # 结束状态
    (ActionDisplayStatus.SUCCESS, _lazy("成功")),  # 处理成功
    (ActionDisplayStatus.PARTIAL_SUCCESS, _lazy("部分成功")),  # 部分成功
    (ActionDisplayStatus.FAILURE, _lazy("失败")),  # 处理失败
    (ActionDisplayStatus.PARTIAL_FAILURE, _lazy("部分失败")),  # 部分失败
    (ActionDisplayStatus.SKIPPED, _lazy("已收敛")),  # 已收敛
    (ActionDisplayStatus.SHIELD, _lazy("已屏蔽")),
)

ACTION_DISPLAY_STATUS_DICT = {status: desc for (status, desc) in ACTION_DISPLAY_STATUS_CHOICES}

ACTION_STATUS_CHOICES = (
    # 处理中的状态
    (ActionStatus.RECEIVED, _lazy("收到")),  # 已收到告警
    (ActionStatus.WAITING, _lazy("审批中")),  # 等待审批
    (ActionStatus.CONVERGING, _lazy("收敛中")),  # 正在收敛
    (ActionStatus.SLEEP, _lazy("收敛处理等待")),  # 正在收敛
    (ActionStatus.CONVERGED, _lazy("收敛结束")),  # 正在收敛
    (ActionStatus.RUNNING, _lazy("处理中")),  # 正在处理
    # 结束状态
    (ActionStatus.SUCCESS, _lazy("成功")),  # 处理成功
    (ActionStatus.PARTIAL_SUCCESS, _lazy("部分成功")),  # 主要关键步骤成功，但部分非关键步骤失败
    (ActionStatus.FAILURE, _lazy("失败")),  # 处理失败
    (ActionStatus.PARTIAL_FAILURE, _lazy("部分失败")),  # 子任务有部分不成功
    (ActionStatus.SKIPPED, _lazy("跳过")),  # 处理跳过
    (ActionStatus.SHIELD, _lazy("已屏蔽")),
)

ACTION_STATUS_DICT = {status: desc for (status, desc) in ACTION_STATUS_CHOICES}

ACTION_END_STATUS = [
    ActionStatus.SUCCESS,
    ActionStatus.PARTIAL_SUCCESS,
    ActionStatus.FAILURE,
    ActionStatus.SKIPPED,
    ActionStatus.FOR_NOTICE,
    ActionStatus.FOR_REFERENCE,
    ActionStatus.AUTHORIZED,
    ActionStatus.UNAUTHORIZED,
    ActionStatus.CHECKING,
    ActionStatus.SHIELD,
]


class NoticeWay:
    SMS = "sms"
    MAIL = "mail"
    WEIXIN = "weixin"
    QY_WEIXIN = "qy_weixin"
    VOICE = "voice"
    WX_BOT = "wxwork-bot"
    BK_CHAT = "bkchat"

    NOTICE_WAY_MAPPING = {
        SMS: _lazy("短信"),
        MAIL: _lazy("邮件"),
        WEIXIN: _lazy("微信"),
        QY_WEIXIN: _lazy("企业微信"),
        VOICE: _lazy("电话"),
        WX_BOT: _lazy("企业微信机器人"),
        BK_CHAT: _lazy("蓝鲸信息流"),
        "bkchat|wxwork-bot": _lazy("蓝鲸信息流(企业微信机器人)"),
        "bkchat|WEWORK": _lazy("蓝鲸信息流(企业微信服务号)"),
        "bkchat|SLACK": _lazy("蓝鲸信息流(SLACK机器人)"),
        "bkchat|SLACK_WEBHOOK": _lazy("蓝鲸信息流(SLACK)"),
        "bkchat|QQ": _lazy("蓝鲸信息流(QQ群机器人)"),
        "bkchat|mini_program": _lazy("蓝鲸信息流(微信公众号)"),
        "bkchat|LARK_WEBHOOK": _lazy("蓝鲸信息流(飞书)"),
        "bkchat|DING_WEBHOOK": _lazy("蓝鲸信息流(钉钉)"),
        "bkchat|mail": _lazy("蓝鲸信息流(邮件)"),
    }


class NoticeChannel:
    USER = "user"
    WX_BOT = "wxwork-bot"
    BK_CHAT = "bkchat"

    NOTICE_CHANNEL_MAPPING = {USER: _lazy("内部用户"), WX_BOT: _lazy("企业微信机器人"), BK_CHAT: _lazy("蓝鲸信息流")}

    NOTICE_CHANNEL_CHOICE = [(key, value) for key, value in NOTICE_CHANNEL_MAPPING.items()]

    DEFAULT_CHANNELS = [USER, WX_BOT]

    RECEIVER_CHANNELS = [WX_BOT, BK_CHAT]


BKCHAT_TRIGGER_TYPE_MAPPING = {"WEWORK_BOT": NoticeWay.WX_BOT, "EMAIL": NoticeWay.MAIL, "MINI_PROGRAM": "mini_program"}


class NoticeWayChannel:
    MAPPING = {
        NoticeWay.SMS: NoticeChannel.USER,
        NoticeWay.MAIL: NoticeChannel.USER,
        NoticeWay.WEIXIN: NoticeChannel.USER,
        NoticeWay.QY_WEIXIN: NoticeChannel.USER,
        NoticeWay.VOICE: NoticeChannel.USER,
        NoticeWay.WX_BOT: NoticeChannel.WX_BOT,
        NoticeWay.BK_CHAT: NoticeChannel.BK_CHAT,
    }


class NoticeType:
    """# NOCC:function-redefined(工具误报:没有重复定义)
    策略通知的类型
    ALERT_NOTICE： 告警通知
    ACTION_NOTICE： 处理的通知
    """

    ALERT_NOTICE = "alert_notice"
    ACTION_NOTICE = "action_notice"


class UserGroupType:
    """
    通知组用户的类型
    """

    MAIN = "main"
    FOLLOWER = "follower"

    CHOICE = [(MAIN, "负责人"), (FOLLOWER, "关注人")]


class MessageQueueSignal:
    ANOMALY_PUSH = "ANOMALY_PUSH"
    RECOVERY_PUSH = "RECOVERY_PUSH"
    CLOSE_PUSH = "CLOSE_PUSH"


class ActionSignal:
    MANUAL = "manual"
    ABNORMAL = "abnormal"
    RECOVERED = "recovered"
    CLOSED = "closed"
    ACK = "ack"
    NO_DATA = "no_data"
    COLLECT = "collect"
    EXECUTE = "execute"
    EXECUTE_SUCCESS = "execute_success"
    EXECUTE_FAILED = "execute_failed"
    DEMO = "demo"
    UNSHIELDED = "unshielded"
    UPGRADE = "upgrade"

    NORMAL_SIGNAL = [ABNORMAL, RECOVERED, CLOSED, NO_DATA, MANUAL, ACK]
    ABNORMAL_SIGNAL = [ABNORMAL, NO_DATA]

    ACTION_SIGNAL_DICT = {
        MANUAL: _lazy("手动处理时"),
        ABNORMAL: _lazy("告警触发时"),
        RECOVERED: _lazy("告警恢复时"),
        CLOSED: _lazy("告警关闭时"),
        ACK: _lazy("告警确认时"),
        NO_DATA: _lazy("无数据时"),
        COLLECT: _lazy("汇总"),
        EXECUTE: _lazy("执行动作时"),
        EXECUTE_SUCCESS: _lazy("执行成功时"),
        EXECUTE_FAILED: _lazy("执行失败时"),
        DEMO: _lazy("调试时"),
        UNSHIELDED: _lazy("解除屏蔽时"),
        UPGRADE: _lazy("告警升级"),
    }

    ACTION_SIGNAL_MAPPING = {
        ABNORMAL: "ANOMALY_NOTICE",
        RECOVERED: "RECOVERY_NOTICE",
        NO_DATA: "ANOMALY_NOTICE",
        CLOSED: CLOSED,
    }

    MESSAGE_QUEUE_OPERATE_TYPE_MAPPING = {
        ABNORMAL: MessageQueueSignal.ANOMALY_PUSH,
        RECOVERED: MessageQueueSignal.RECOVERY_PUSH,
        NO_DATA: MessageQueueSignal.ANOMALY_PUSH,
        CLOSED: MessageQueueSignal.CLOSE_PUSH,
    }

    ACTION_SIGNAL_CHOICE = [(key, value) for key, value in ACTION_SIGNAL_DICT.items()]


NOTIFY_STEP_ACTION_SIGNAL_MAPPING = {
    NotifyStep.BEGIN: ActionSignal.EXECUTE,
    NotifyStep.SUCCESS: ActionSignal.EXECUTE_SUCCESS,
    NotifyStep.FAILURE: ActionSignal.EXECUTE_FAILED,
}


class IntervalNotifyMode:
    INCREASING = "increasing"
    STANDARD = "standard"

    DICT = {INCREASING: _lazy("递增"), STANDARD: _lazy("固定间隔")}

    CHOICES = [(key, value) for key, value in DICT.items()]


class ChatMessageType:
    DETAIL_URL = "detail_url"
    ALARM_CONTENT = "alarm_content"


DEFAULT_TITLE_TEMPLATE = "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}"

DEFAULT_TEMPLATE = (
    "{{content.level}}\n"
    "{{content.begin_time}}\n"
    "{{content.time}}\n"
    "{{content.duration}}\n"
    "{{content.target_type}}\n"
    "{{content.data_source}}\n"
    "{{content.content}}\n"
    "{{content.current_value}}\n"
    "{{content.biz}}\n"
    "{{content.target}}\n"
    "{{content.dimension}}\n"
    "{{content.detail}}\n"
    "{{content.assign_detail}}\n"
    "{{content.related_info}}\n"
)

DEFAULT_ACTION_TEMPLATE = (
    "{{action_instance_content.name}}\n"
    "{{action_instance_content.plugin_type_name}}\n"
    "{{action_instance_content.assignees}}\n"
    "{{action_instance_content.start_time}}\n"
    "{{action_instance_content.end_time}}\n"
    "{{action_instance_content.duration_string}}\n"
    "{{action_instance_content.status_display}}\n"
    "{{action_instance_content.opt_content}}\n"
    "{{action_instance_content.detail_link}}\n"
)

ASSIGN_CONDITION_KEYS = {
    "alert.event_source": _lazy("告警源"),
    "alert.scenario": _lazy("监控对象"),
    "alert.strategy_id": _lazy("策略"),
    "alert.name": _lazy("告警名称"),
    "alert.metric": _lazy("指标"),
    "labels": _lazy("策略标签"),
    "is_empty_users": _lazy("通知人员为空"),
    "notice_users": _lazy("通知人员"),
    "dimensions": _lazy("维度"),
    "ip": _lazy("告警IP"),
    "bk_cloud_id": _lazy("云区域ID"),
    "set": _lazy("集群属性"),
    "module": _lazy("模块属性"),
    "host": _lazy("主机属性"),
}


class ActionNoticeType:
    NORMAL = "normal"
    UNSHILEDED = "unshielded"
    UPGRADE = "upgrade"
