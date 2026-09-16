from typing import Any, final


@final
class AlgorithmChoices:
    Threshold = "Threshold"
    NewSeries = "NewSeries"
    SimpleRingRatio = "SimpleRingRatio"
    AdvancedRingRatio = "AdvancedRingRatio"
    SimpleYearRound = "SimpleYearRound"
    AdvancedYearRound = "AdvancedYearRound"
    PartialNodes = "PartialNodes"
    OsRestart = "OsRestart"
    ProcPort = "ProcPort"
    PingUnreachable = "PingUnreachable"
    YearRoundAmplitude = "YearRoundAmplitude"
    YearRoundRange = "YearRoundRange"
    RingRatioAmplitude = "RingRatioAmplitude"
    IntelligentDetect = "IntelligentDetect"
    TimeSeriesForecasting = "TimeSeriesForecasting"
    AbnormalCluster = "AbnormalCluster"
    MultivariateAnomalyDetection = "MultivariateAnomalyDetection"
    HostAnomalyDetection = "HostAnomalyDetection"


@final
class SourceApp:
    """来源应用常量"""

    # 监控应用
    MONITOR = "monitor"

    # 故障自愈应用
    FTA = "fta"


@final
class DataTypeLabel:
    """数据类型标签常量"""

    # 时序数据
    TIME_SERIES = "time_series"

    # 事件数据
    EVENT = "event"

    # 日志数据
    LOG = "log"

    # 告警数据
    ALERT = "alert"

    # 链路追踪数据
    TRACE = "trace"


@final
class DataSourceLabel:
    """数据来源标签常量"""

    # 监控采集器
    BK_MONITOR_COLLECTOR = "bk_monitor"

    # 计算平台
    BK_DATA = "bk_data"

    # 自定义指标
    CUSTOM = "custom"

    # 日志平台
    BK_LOG_SEARCH = "bk_log_search"

    # 告警平台
    BK_FTA = "bk_fta"

    # APM平台
    BK_APM = "bk_apm"

    # Prometheus
    PROMETHEUS = "prometheus"

    # DASHBOARD
    DASHBOARD = "dashboard"


@final
class DataTarget:
    """数据目标常量"""

    # 无目标
    NONE_TARGET = "none_target"

    # 服务目标
    SERVICE_TARGET = "service_target"

    # 主机目标
    HOST_TARGET = "host_target"

    # 设备目标
    DEVICE_TARGET = "device_target"


@final
class TargetFieldType:
    """目标字段类型常量"""

    host_topo = "host_topo_node"
    service_topo = "service_topo_node"
    host_ip = "ip"
    host_target_ip = "bk_target_ip"

    host_set_template = "host_set_template"
    service_set_template = "service_set_template"
    host_service_template = "host_service_template"
    service_service_template = "service_service_template"
    dynamic_group = "dynamic_group"


@final
class VisualType:
    """可视化类型常量"""

    # 只显示异常点
    NONE = "none"

    # 上下界
    BOUNDARY = "boundary"

    # 异常分值
    SCORE = "score"

    # 时序预测
    FORECASTING = "forecasting"


# 系统时间主机重启、进程端口对应检测算法
EVENT_DETECT_LIST: dict[str, list[dict[str, Any]]] = {
    "os_restart": [{"type": "OsRestart", "config": []}],
    "proc_port": [{"type": "ProcPort", "config": []}],
    "ping-gse": [{"type": "PingUnreachable", "config": []}],
}

# 主机场景列表
HOST_SCENARIO = ["os", "host_process", "host_device"]

# 服务场景列表
SERVICE_SCENARIO = ["service_module", "component", "service_process"]

# 自定义优先级分组前缀
CUSTOM_PRIORITY_GROUP_PREFIX = "PGK:"

# 数据链路数据源标识
DATALINK_SOURCE = "__datalink_collecting__"

# 系统事件的result_table_id代号
SYSTEM_EVENT_RT_TABLE_ID = "system.event"

# 系统进程端口指标ID
SYSTEM_PROC_PORT_METRIC_ID = "bk_monitor.proc_port"

# 拨测指标错误码映射
UPTIMECHECK_ERROR_CODE_MAP = {"response_code": 3003, "message": 3002}

# 无需拆分表维度列表
NOT_SPLIT_DIMENSIONS = ["bk_target_ip", "bk_target_service_instance_id"]

# 拆分表默认维度列表
SPLIT_DIMENSIONS = ["bk_obj_id", "bk_inst_id"]

# 拆分表cmdb_level映射
SPLIT_CMDB_LEVEL_MAP: dict[str, str] = {"biz": "bk_biz_id", "set": "bk_set_id", "module": "bk_module_id"}

# 集群、服务模板映射
TEMPLATE_MAP = {"SET_TEMPLATE": "set", "SERVICE_TEMPLATE": "module"}

# 系统时间主机重启指标ID
OS_RESTART_METRIC_ID = "bk_monitor.os_restart"

# 系统时间主机重启、进程端口、PING不可达、自定义字符型对应query_config
EVENT_QUERY_CONFIG_MAP: dict[str, dict[str, Any]] = {
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


@final
class SDKDetectStatus:
    """SDK检测状态常量"""

    READY = "ready"
    PREPARING = "preparing"


@final
class UserGroupType:
    """
    通知组用户的类型
    """

    # 负责人
    MAIN = "main"
    # 关注人
    FOLLOWER = "follower"

    # 选择列表
    CHOICE: list[tuple[str, str]] = [(MAIN, "负责人"), (FOLLOWER, "关注人")]


@final
class AssignMode:
    """分派模式常量"""

    BY_RULE = "by_rule"
    ONLY_NOTICE = "only_notice"

    ASSIGN_MODE_CHOICE: list[tuple[str, str]] = [(BY_RULE, "分派"), (ONLY_NOTICE, "仅通知")]


@final
class MessageQueueSignal:
    ANOMALY_PUSH = "ANOMALY_PUSH"
    RECOVERY_PUSH = "RECOVERY_PUSH"
    CLOSE_PUSH = "CLOSE_PUSH"


@final
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
    INCIDENT = "incident"

    NORMAL_SIGNAL = [ABNORMAL, RECOVERED, CLOSED, NO_DATA, MANUAL, ACK]
    ABNORMAL_SIGNAL = [ABNORMAL, NO_DATA]

    ACTION_SIGNAL_DICT = {
        MANUAL: "手动处理时",
        ABNORMAL: "告警触发时",
        RECOVERED: "告警恢复时",
        CLOSED: "告警关闭时",
        ACK: "告警确认时",
        NO_DATA: "无数据时",
        COLLECT: "汇总",
        EXECUTE: "执行动作时",
        EXECUTE_SUCCESS: "执行成功时",
        EXECUTE_FAILED: "执行失败时",
        DEMO: "调试时",
        UNSHIELDED: "解除屏蔽时",
        UPGRADE: "告警升级",
        INCIDENT: "故障生成时",
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


@final
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
        NOTICE: "通知",
        WEBHOOK: "HTTP回调",
        JOB: "作业平台",
        SOPS: "标准运维",
        ITSM: "流程服务",
        COMMON: "通用插件",
        COLLECT: "汇总",
        MESSAGE_QUEUE: "消息队列",
        AUTHORIZE: "授权",
    }


# 数据源标签别名
DATA_SOURCE_LABEL_ALIAS = {
    DataSourceLabel.BK_MONITOR_COLLECTOR: "监控采集指标",
    DataSourceLabel.BK_DATA: "计算平台指标",
    DataSourceLabel.CUSTOM: "自定义指标",
    DataSourceLabel.BK_LOG_SEARCH: "日志平台指标",
    DataSourceLabel.BK_FTA: "关联告警",
    DataSourceLabel.BK_APM: "Trace明细指标",
    DataSourceLabel.PROMETHEUS: "Prometheus",
    DataSourceLabel.DASHBOARD: "DASHBOARD",
}


@final
class AccessStatus:
    """数据接入的状态

    注意：这里不是指 flow 的状态，而是监控对 flow 接入流程的自身状态流转
    """

    # 等待中
    PENDING = "pending"

    # 已创建
    CREATED = "created"

    # 执行中
    RUNNING = "running"

    # 成功
    SUCCESS = "success"

    # 失败
    FAILED = "failed"


# 全部汇聚维度配置
ALL_CONVERGE_DIMENSION = {
    "dimensions": "维度",
    "strategy_id": "策略",
    "alert_name": "告警名称",
    "bk_biz_id": "业务",
    "alert_level": "告警级别",
    "signal": "告警信号",
    "notice_receiver": "通知人员",
    "notice_way": "通知方式",
    "group_notice_way": "带组员类型的通知方式",
    "alert_info": "告警信息",
    "notice_info": "通知信息",
    "action_info": "告警套餐信息",
}

# 汇聚维度配置
CONVERGE_DIMENSION = {
    "strategy_id": "策略",
    "alert_name": "告警名称",
    "bk_set_ids": "集群",
    "bk_module_ids": "模块",
    "bk_host_id": "主机",
    "dimensions": "维度",
    "target": "目标",
    "rack_id": "机架",
    "net_device_id": "交换机",
    "idc_unit_name": "机房",
    "process": "进程名称",
    "port": "端口",
    "alarm_attr_id": "告警特性",
}


@final
class ConvergeFunction:
    """汇聚功能常量"""

    SKIP_WHEN_SUCCESS = "skip_when_success"
    SKIP_WHEN_PROCEED = "skip_when_proceed"
    WAIT_WHEN_PROCEED = "wait_when_proceed"
    SKIP_WHEN_EXCEED = "skip_when_exceed"
    DEFENSE = "defense"
    COLLECT = "collect"
    COLLECT_ALARM = "collect_alarm"


# 汇聚功能映射
CONVERGE_FUNCTION = {
    ConvergeFunction.SKIP_WHEN_SUCCESS: "成功后跳过",
    ConvergeFunction.SKIP_WHEN_PROCEED: "执行中跳过",
    ConvergeFunction.WAIT_WHEN_PROCEED: "执行中等待",
    ConvergeFunction.SKIP_WHEN_EXCEED: "超出后忽略",
    ConvergeFunction.DEFENSE: "异常防御审批",
    ConvergeFunction.COLLECT: "超出后汇总",
    ConvergeFunction.COLLECT_ALARM: "汇总通知",
}


@final
class IntervalNotifyMode:
    """间隔通知模式常量"""

    # 递增模式
    INCREASING = "increasing"

    # 固定间隔模式
    STANDARD = "standard"

    CHOICES: list[tuple[str, str]] = [(INCREASING, "递增"), (STANDARD, "固定间隔")]


@final
class VoiceNoticeMode:
    """语音通知模式常量"""

    # 串行通知
    SERIAL = "serial"

    # 并行通知
    PARALLEL = "parallel"


# 智能异常检测算法配置
IntelligentDetectAlgorithms: dict[int, dict[str, Any]] = {
    1: {
        "id": 1,
        "alias": "单指标异常检测",
        "name": "general_anomaly_detection",
        "document": "敏感度越高，检测出的异常越多；敏感度越低，检测出的异常越少- 数据频率：```任意```- 历史数据长度：```2天```。充足的历史数据能使模型提取到更准确的异常特征，历史数据不足2天时，检测准确度会有所下降。- 模型生效时间：后台创建策略耗时```10分钟```，创建后即时生效。- 效果不满意？   + 对于成功率和失败率类数据，用简单的阈值可能更直接更准确   + 对于波动很强的时序数据，不妨试着调低敏感度（1-2），可以减少过于敏感的告警   + 通过反馈页面的 *反馈* 进行反馈",
        "description": "单指标异常检测考虑了不同类型曲线（周期型、稳定型、稀疏型）的特征，可以满足机器指标、业务指标等时序数据的异常检测需求",
        "is_default": True,
        "is_new_version": True,
        "version_no": "",
        "instruction": ">**单指标异常检测**是采用了时间序列特征提取和深度贝叶斯学习的异常检测方案\n\n**单指标异常检测**考虑了不同类型曲线（```周期型```、```稳定型```、```稀疏型```）的特征，可以满足```机器指标```、```业务指标```等时序数据的异常检测需求。\n\n**单指标异常检测**的检测流程分为```异常模式提取```和```有监督异常检测```两部分：\n\n- 在```异常模式提取```阶段，基于概率论、极值理论、残差理论等，从时序数据中提取能多方面表征数据异常模式的特征。\n- 在```有监督异常检测```阶段，采用基于主动学习的深度贝叶斯模型，能够在异常检测的同时，根据用户反馈学习未知的异常模式和部分用户偏好。",
        "variable_info": {
            "parameter": [
                {
                    "constraint": [[{"allow_null": False, "input_type": "int"}]],
                    "properties": {
                        "closed": None,
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "switch",
                        "is_advanced": False,
                        "is_required": False,
                        "placeholder": "检测到下降异常时进行告警",
                        "allow_modified": True,
                        "allowed_values_map": [
                            {"description": "否", "allowed_alias": "否", "allowed_value": 0},
                            {"description": "是", "allowed_alias": "是", "allowed_value": 1},
                        ],
                    },
                    "value_type": "int",
                    "description": "若不希望收到下降异常告警，请关闭",
                    "sensitivity": "public",
                    "default_value": "1",
                    "variable_name": "$alert_down",
                    "variable_type": "parameter",
                    "variable_alias": "下降告警",
                    "variable_value": "1",
                },
                {
                    "constraint": [[{"allow_null": False, "input_type": "int"}]],
                    "properties": {
                        "closed": None,
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "switch",
                        "is_advanced": False,
                        "is_required": False,
                        "placeholder": "若希望收到轻微抖动异常告警，请打开",
                        "allow_modified": True,
                        "allowed_values_map": [
                            {"description": "否", "allowed_alias": "否", "allowed_value": 0},
                            {"description": "是", "allowed_alias": "是", "allowed_value": 1},
                        ],
                    },
                    "value_type": "int",
                    "description": "若希望收到轻微抖动异常告警，请打开",
                    "sensitivity": "public",
                    "default_value": "0",
                    "variable_name": "$alert_slight_shake",
                    "variable_type": "parameter",
                    "variable_alias": "轻微抖动告警",
                    "variable_value": "0",
                },
                {
                    "constraint": [[{"allow_null": False, "input_type": "int"}]],
                    "properties": {
                        "closed": None,
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "switch",
                        "is_advanced": False,
                        "is_required": False,
                        "placeholder": "检测到上升异常时进行告警",
                        "allow_modified": True,
                        "allowed_values_map": [
                            {"description": "否", "allowed_alias": "否", "allowed_value": 0},
                            {"description": "是", "allowed_alias": "是", "allowed_value": 1},
                        ],
                    },
                    "value_type": "int",
                    "description": "若不希望收到上升异常告警，请关闭",
                    "sensitivity": "public",
                    "default_value": "1",
                    "variable_name": "$alert_upward",
                    "variable_type": "parameter",
                    "variable_alias": "上升告警",
                    "variable_value": "1",
                },
                {
                    "constraint": [[{"allow_null": False, "input_type": "double"}]],
                    "properties": {
                        "max": 10,
                        "min": 0,
                        "closed": "all",
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "range",
                        "is_advanced": False,
                        "is_required": False,
                        "placeholder": "敏感度越高告警越多，敏感度越低告警越少",
                        "allow_modified": True,
                        "allowed_values_map": [],
                    },
                    "value_type": "double",
                    "description": "敏感度越高，告警越多。对于平滑曲线，建议使用默认敏感度；对于波动曲线，建议调低敏感度",
                    "sensitivity": "public",
                    "default_value": "5",
                    "variable_name": "$sensitivity",
                    "variable_type": "parameter",
                    "variable_alias": "敏感度",
                    "variable_value": "5",
                },
            ]
        },
        "ts_freq": 0,
        "algorithm": "IntelligentDetect",
        "config": {},
    },
    2: {
        "id": 2,
        "alias": "离群点检测",
        "name": "abnormal_cluster",
        "document": "**数据频率：** 任意**依赖历史数据长度：** 无需依赖历史数据**什么时候能看到检测结果数据：** 即时可以看到，注意Flow接入大概要10分钟训练周期**手动触发效果不满意怎么办：** ① 尝试更改参数；② 通过告警单的【误警】进行反馈；③ 联系算法开发人员算法开发人员",
        "description": "离群检测用于检测在一组提供服务的节点中，CPU或者内存使用量与其余节点产生较大差距的节点。",
        "is_default": False,
        "is_new_version": True,
        "version_no": "",
        "instruction": "**适用情况**：适用于需要根据单指标数据各维度的数据分布情况来判断异常的情况。\n**如何使用**：用户可以通过调整敏感度来对应不同离散程度的指标值分布情况，共11档。模型会实时计算当前指标在各维度的分布情况，当某个维度的指标值超出了用户设置的敏感度对应的范围区间时，便会触发告警。\n",
        "variable_info": {
            "parameter": [
                {
                    "constraint": [[{"allow_null": False, "input_type": "int"}]],
                    "properties": {
                        "max": 10,
                        "min": 0,
                        "closed": "all",
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "range",
                        "is_advanced": False,
                        "is_required": False,
                        "placeholder": "u8d8au5c0fu8d8au5bb9u6613u68c0u6d4bu51fau79bbu7fa4",
                        "allow_modified": True,
                        "allowed_values_map": [],
                    },
                    "value_type": "int",
                    "description": "越大越容易检测出离群",
                    "sensitivity": "public",
                    "default_value": "5",
                    "variable_name": "$sensitivity",
                    "variable_type": "parameter",
                    "variable_alias": "敏感度",
                    "variable_value": None,
                }
            ]
        },
        "ts_freq": 0,
        "algorithm": "AbnormalCluster",
        "config": {},
    },
    3: {
        "id": 3,
        "alias": "通用时间序列预测_小时粒度",
        "name": "general_time_series_forecasting_hour",
        "document": "- 数据频率：```任意```- 历史数据长度：```14天```。充足的历史数据能使模型获得更丰富的时序信息，历史数据不足```14天```时，预测效果会有所下降。- 模型生效时间：后台创建策略耗时```10分钟```，创建后即时生效。",
        "description": "general_time_series_forecasting 是一种基于Transformer的时间序列预测方法。可以满足如CPU、磁盘利用、在线人数等各类大型在线业务的时序预测需求。",
        "is_default": False,
        "is_new_version": True,
        "version_no": "",
        "instruction": "**通用时间序列预测**是一种基于Transformer的通用长时间序列预测方案\n\n**通用时间序列预测**方案利用大量的不同类型曲线（```周期型```、```稳定型```、```趋势型```）训练得到，可以满足```机器指标```、```业务指标```等时序数据的长时间预测需求。\n\n**通用时间序列预测_小时粒度**可以预测未来最长```7天```的时序数据，预测值为```当前时间点```到```7天后```的时序数据，以```小时```为最小粒度。",
        "variable_info": {
            "parameter": [
                {
                    "constraint": [[{"allow_null": False, "input_type": "string"}]],
                    "properties": {
                        "closed": None,
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "select",
                        "is_advanced": False,
                        "is_required": True,
                        "placeholder": "趋势预测提供对未来数据的线性趋势预测；准确预测提供对未来数据尽可能准确的波动预测",
                        "allow_modified": True,
                        "allowed_values_map": [
                            {
                                "description": "精确预测（提供对未来数据尽可能准确的波动预测 ）",
                                "allowed_alias": "精确预测（提供对未来数据尽可能准确的波动预测 ）",
                                "allowed_value": "accurate",
                            },
                            {
                                "description": "趋势预测（提供对未来数据的线性趋势预测）",
                                "allowed_alias": "趋势预测（提供对未来数据的线性趋势预测）",
                                "allowed_value": "trend",
                            },
                        ],
                    },
                    "value_type": "string",
                    "description": "",
                    "sensitivity": "public",
                    "default_value": "accurate",
                    "variable_name": "$forecast_mode",
                    "variable_type": "parameter",
                    "variable_alias": "预测模式",
                    "variable_value": "accurate",
                },
                {
                    "constraint": [[{"allow_null": False, "input_type": "string"}]],
                    "properties": {
                        "closed": None,
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "select",
                        "is_advanced": False,
                        "is_required": True,
                        "placeholder": "指定预测上下界范围的程度，提供了大、中、小三档",
                        "allow_modified": True,
                        "allowed_values_map": [
                            {"description": "小", "allowed_alias": "小", "allowed_value": "small"},
                            {"description": "中", "allowed_alias": "中", "allowed_value": "middle"},
                            {"description": "大", "allowed_alias": "大", "allowed_value": "large"},
                        ],
                    },
                    "value_type": "string",
                    "description": "",
                    "sensitivity": "public",
                    "default_value": "middle",
                    "variable_name": "$range_level",
                    "variable_type": "parameter",
                    "variable_alias": "上下界范围",
                    "variable_value": "middle",
                },
            ]
        },
        "ts_freq": 0,
        "algorithm": "TimeSeriesForecasting",
        "config": {},
    },
    4: {
        "id": 4,
        "alias": "主机多指标异常检测评级",
        "name": "host_ad_multi_level",
        "document": "**适用情况**：适用于需要对指定的多个主机内的多个指标数据的异常波动进行批量检测的情况。\n\n**使用方法**：在策略配置页指定好待检测的指标和主机即可。模型会实时扫描目标主机的多个指标数据（目前是指定的十个主要指标，包含CPU、MEM、DISK、IO等，按avg方式聚合至IP维度），如果检出多个指标异常，将以发生异常的主机为单位生成告警。\n\n**数据频率**：任意\n**数据长度**：新接入的业务，前24小时会累积历史数据用来做预测，所以前24小时不会检出异常，但是会有正常数据输出。充足的历史数据能使模型提取到更准确的异常特征，历史数据不足2天时，检测准确度会小幅下降。\n**什么时候能看到检测结果数据**：即时可以看到（依赖历史数据足够的情况下），注意Flow接入大概要5分钟\n\n**额外规则**：\n- 单个指标的异常不会检出，需要机器多个指标同时波动才有可能检出异常，其中CPU、MEM、DISK、IO使用率只有超过50%才可能检出对应指标的异常\n- 对于常数值指标(包括全0指标)，不会检测出异常\n\n- 周期性的异常只有第一次会产生告警，后续将不会被检出，如周期性的主机重启 ",
        "description": "",
        "is_default": False,
        "is_new_version": True,
        "version_no": "",
        "instruction": "### 算法说明\n\nmultivariate_anomaly_detection是一种采用时间序列特征提取和VAE变分自编码器的多指标异常检测框架。\n\nmultivariate_anomaly_detection通过对单个实体的多个指标进行并行处理，提取异常特征与学习异常模式，本方案创新性的引入了主动学习的方法，能够有效的通过反馈样本来提升模型的检测效果，适合大型在线实体的异常数据检测。\n\nmultivariate_anomaly_detection会根据数据本身的异常情况，对告警进行定级（严重、轻微等）\n\n### 算法原理\n\nmultivariate_anomaly_detection多指标异常检测流程分为异常模式提取和半监督模型异常检测两部分。\n\n在异常模式提取阶段，基于周期窗口、极值理论、残差理论等，从待检测时间序列数据中提取各类能全面表征数据异常模式的特征。\n\n在异常检测阶段，采用基于主动学习的般监督VAE模型，对多指标数据进行同步异常识别。通过数据回流和主动学习的方法，使得能够兼容各类数据模式和用户偏好，从而达到最优的异常检测效果。 ",
        "variable_info": {
            "parameter": [
                {
                    "constraint": [[{"allow_null": False, "input_type": "string"}]],
                    "properties": {"is_required": True},
                    "value_type": "string",
                    "description": "",
                    "sensitivity": "public",
                    "default_value": "1,2,3",
                    "variable_name": "$alert_levels",
                    "variable_type": "parameter",
                    "variable_alias": "告警级别",
                    "variable_value": "1,2,3",
                },
                {
                    "constraint": [
                        [
                            {"max": None, "min": "0", "closed": "left", "input_type": "int"},
                            {"max": "1", "min": None, "closed": "right", "input_type": "int"},
                        ]
                    ],
                    "properties": {"is_required": False},
                    "value_type": "int",
                    "description": "",
                    "sensitivity": "public",
                    "default_value": "1",
                    "variable_name": "$ignore_periodic",
                    "variable_type": "parameter",
                    "variable_alias": "忽略周期型告警",
                    "variable_value": "1",
                },
                {
                    "constraint": [[{"allow_null": False, "input_type": "text"}]],
                    "properties": {"is_required": True},
                    "value_type": "text",
                    "description": "",
                    "sensitivity": "public",
                    "default_value": "system__cpu_detail__usage,system__load__load5,system__mem__pct_used,system__mem__psc_pct_used,system__net__speed_recv,system__net__speed_sent,system__swap__pct_used,system__disk__in_use,system__io__util,system__env__procs",
                    "variable_name": "$metric_list",
                    "variable_type": "parameter",
                    "variable_alias": "待检测指标名",
                    "variable_value": "system__cpu_detail__usage,system__load__load5,system__mem__pct_used,system__mem__psc_pct_used,system__net__speed_recv,system__net__speed_sent,system__swap__pct_used,system__disk__in_use,system__io__util,system__env__procs",
                },
                {
                    "constraint": [
                        [
                            {"max": None, "min": "0", "closed": "left", "input_type": "double"},
                            {"max": "10", "min": None, "closed": "right", "input_type": "double"},
                        ]
                    ],
                    "properties": {"is_required": True},
                    "value_type": "double",
                    "description": "",
                    "sensitivity": "public",
                    "default_value": "5",
                    "variable_name": "$sensitivity",
                    "variable_type": "parameter",
                    "variable_alias": "敏感度",
                    "variable_value": "5",
                },
            ]
        },
        "ts_freq": 0,
        "algorithm": "HostAnomalyDetection",
        "config": {},
    },
    5: {
        "id": 5,
        "alias": "单指标异常检测_严格模式",
        "name": "general_anomaly_detection_for_crash_failure_metric",
        "document": "能够检测出轻微波动数据中存在的异常，敏感度越高，检测出的异常越多；敏感度越低，检测出的异常越少- 数据频率：```任意```- 历史数据长度：```2天```。充足的历史数据能使模型提取到更准确的异常特征，历史数据不足2天时，检测准确度会有所下降。- 模型生效时间：后台创建策略耗时```10分钟```，创建后即时生效。- 效果不满意？   + 对于成功率和失败率类数据，用简单的阈值可能更直接更准确   + 对于波动很强的时序数据，不妨试着调低敏感度（1-2），可以减少过于敏感的告警   + 通过反馈页面的 *反馈* 进行反馈 ",
        "description": "单指标异常检测_严格模式在单指标异常检测模式的基础上，新增了对阴跌（缓慢下降）情况的识别。",
        "is_default": False,
        "is_new_version": True,
        "version_no": "",
        "instruction": ">**单指标异常检测_严格模式**在单指标指标检测的方案基础上，能够更敏感地检测出轻微波动数据中存在的异常\n\n**单指标异常检测_严格模式**考虑了不同类型曲线（```周期型```、```稳定型```、```稀疏型```）的特征，可以满足```机器指标```、```业务指标```等时序数据的异常检测需求。\n\n**单指标异常检测_严格模式**的检测流程分为```异常模式提取```和```有监督异常检测```两部分：\n\n- 在```异常模式提取```阶段，基于概率论、极值理论、残差理论等，从时序数据中提取能多方面表征数据异常模式的特征。\n- 在```有监督异常检测```阶段，采用基于主动学习的深度贝叶斯模型，能够在异常检测的同时，根据用户反馈学习未知的异常模式和部分用户偏好。 ",
        "variable_info": {
            "parameter": [
                {
                    "constraint": [
                        [
                            {"max": None, "min": "0", "closed": "left", "input_type": "int"},
                            {"max": "1", "min": None, "closed": "right", "input_type": "int"},
                        ]
                    ],
                    "properties": {
                        "closed": None,
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "switch",
                        "is_advanced": False,
                        "is_required": False,
                        "placeholder": "检测到下降异常时进行告警",
                        "allow_modified": True,
                        "allowed_values_map": [
                            {"description": "否", "allowed_alias": "否", "allowed_value": 0},
                            {"description": "是", "allowed_alias": "是", "allowed_value": 1},
                        ],
                    },
                    "value_type": "int",
                    "description": "若不希望收到下降异常告警，请关闭",
                    "sensitivity": "public",
                    "default_value": "1",
                    "variable_name": "$alert_down",
                    "variable_type": "parameter",
                    "variable_alias": "下降异常",
                    "variable_value": "1",
                },
                {
                    "constraint": [
                        [
                            {"max": None, "min": "0", "closed": "left", "input_type": "int"},
                            {"max": "1", "min": None, "closed": "right", "input_type": "int"},
                        ]
                    ],
                    "properties": {
                        "closed": None,
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "switch",
                        "is_advanced": False,
                        "is_required": False,
                        "placeholder": "若希望收到轻微抖动异常告警，请打开",
                        "allow_modified": True,
                        "allowed_values_map": [
                            {"description": "否", "allowed_alias": "否", "allowed_value": 0},
                            {"description": "是", "allowed_alias": "是", "allowed_value": 1},
                        ],
                    },
                    "value_type": "int",
                    "description": "若希望收到轻微抖动异常告警，请打开",
                    "sensitivity": "public",
                    "default_value": "0",
                    "variable_name": "$alert_slight_shake",
                    "variable_type": "parameter",
                    "variable_alias": "轻微抖动异常",
                    "variable_value": "0",
                },
                {
                    "constraint": [
                        [
                            {"max": None, "min": "0", "closed": "left", "input_type": "int"},
                            {"max": "1", "min": None, "closed": "right", "input_type": "int"},
                        ]
                    ],
                    "properties": {
                        "closed": None,
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "switch",
                        "is_advanced": False,
                        "is_required": False,
                        "placeholder": "检测到上升异常时进行告警",
                        "allow_modified": True,
                        "allowed_values_map": [
                            {"description": "否", "allowed_alias": "否", "allowed_value": 0},
                            {"description": "是", "allowed_alias": "是", "allowed_value": 1},
                        ],
                    },
                    "value_type": "int",
                    "description": "若不希望收到上升异常告警，请关闭",
                    "sensitivity": "public",
                    "default_value": "1",
                    "variable_name": "$alert_upward",
                    "variable_type": "parameter",
                    "variable_alias": "上升异常",
                    "variable_value": "1",
                },
                {
                    "constraint": [
                        [
                            {"max": None, "min": "0", "closed": "left", "input_type": "double"},
                            {"max": "10", "min": None, "closed": "right", "input_type": "double"},
                        ]
                    ],
                    "properties": {
                        "max": 10,
                        "min": 0,
                        "closed": "all",
                        "support": True,
                        "used_by": "user",
                        "multiple": False,
                        "allow_null": False,
                        "input_type": "range",
                        "is_advanced": False,
                        "is_required": False,
                        "placeholder": "敏感度越高告警越多，敏感度越低告警越少",
                        "allow_modified": True,
                        "allowed_values_map": [],
                    },
                    "value_type": "double",
                    "description": "敏感度越高，告警越多。对于平滑曲线，建议使用默认敏感度；对于波动曲线，建议调低敏感度",
                    "sensitivity": "public",
                    "default_value": "5",
                    "variable_name": "$sensitivity",
                    "variable_type": "parameter",
                    "variable_alias": "敏感度",
                    "variable_value": "5",
                },
            ]
        },
        "ts_freq": 0,
        "algorithm": "IntelligentDetect",
        "config": {},
    },
    6: {
        "id": 6,
        "alias": "日志新类检测",
        "name": "log_patterns_anomaly_detection_with_dimensions",
        "document": "日志模式数异常检测是针对最近m天出现的日志新类进行检测，同时也提供日志新类出现后在持续关注的n天内进行规模检测的功能",
        "description": "",
        "is_default": False,
        "is_new_version": True,
        "version_no": "",
        "instruction": ">**日志模式数异常检测**是针对最近m天出现的日志新类进行检测，同时也提供日志新类出现后在持续关注的n天内进行规模检测的功能\n ",
        "variable_info": {
            "parameter": [
                {
                    "constraint": [[{"allow_null": False, "input_type": "string"}]],
                    "properties": {},
                    "value_type": "string",
                    "description": "日志聚类模型应用的RT",
                    "sensitivity": "public",
                    "default_value": "",
                    "variable_name": "$model_file_id",
                    "variable_type": "parameter",
                    "variable_alias": "模型文件ID",
                    "variable_value": "639_after_treat_model_20230704154315604_online_3",
                },
                {
                    "constraint": [[{"allow_null": False, "input_type": "int"}]],
                    "properties": {},
                    "value_type": "int",
                    "description": "新类对应的日志产生多少条会告警",
                    "sensitivity": "public",
                    "default_value": "1",
                    "variable_name": "$new_class_alert_th",
                    "variable_type": "parameter",
                    "variable_alias": "新类告警阈值",
                    "variable_value": "1",
                },
                {
                    "constraint": [[{"allow_null": False, "input_type": "int"}]],
                    "properties": {},
                    "value_type": "int",
                    "description": "日志距离上一次出现间隔多久产生告警，单位：天",
                    "sensitivity": "public",
                    "default_value": "30",
                    "variable_name": "$new_class_interval",
                    "variable_type": "parameter",
                    "variable_alias": "新类告警间隔",
                    "variable_value": "30",
                },
                {
                    "constraint": [[{"allow_null": False, "input_type": "int"}]],
                    "properties": {},
                    "value_type": "int",
                    "description": "",
                    "sensitivity": "public",
                    "default_value": "0",
                    "variable_name": "$new_class_scale_alert",
                    "variable_type": "parameter",
                    "variable_alias": "是否进行新类规模告警",
                    "variable_value": "1",
                },
                {
                    "constraint": [[{"allow_null": False, "input_type": "int"}]],
                    "properties": {},
                    "value_type": "int",
                    "description": "产生新类告警后，持续关注多久，单位：天",
                    "sensitivity": "public",
                    "default_value": "1",
                    "variable_name": "$new_class_scale_alert_interval",
                    "variable_type": "parameter",
                    "variable_alias": "新类规模告警持续关注时间",
                    "variable_value": "1",
                },
                {
                    "constraint": [[{"allow_null": False, "input_type": "int"}]],
                    "properties": {},
                    "value_type": "int",
                    "description": "新类告警生成后，在「新类规模告警持续关注时间」内，日志条数大于多少条，产生告警",
                    "sensitivity": "public",
                    "default_value": "500",
                    "variable_name": "$new_class_scale_alert_th",
                    "variable_type": "parameter",
                    "variable_alias": "新类规模阈值",
                    "variable_value": "500",
                },
            ]
        },
        "ts_freq": 0,
        "algorithm": "IntelligentDetect",
        "config": {"bkbase_plan_id": 22},
    },
}
