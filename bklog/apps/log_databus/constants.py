"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import markdown
from django.conf import settings
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _

from apps.utils import ChoicesEnum

META_PARAMS_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
RESTORE_INDEX_SET_PREFIX = "restore_"

BKLOG_RESULT_TABLE_PATTERN = rf"(({settings.TABLE_SPACE_PREFIX}_)?\d*?_{settings.TABLE_ID_PREFIX}_.*)_.*_.*"

NOT_FOUND_CODE = "[404]"

# ESB返回节点管理check_task_ready API 404异常或非json内容
CHECK_TASK_READY_NOTE_FOUND_EXCEPTION_CODE = "1306201"

COLLECTOR_CONFIG_NAME_EN_REGEX = r"^[A-Za-z0-9_]+$"
CLUSTER_NAME_EN_REGEX = r"^[A-Za-z0-9_]+$"

BULK_CLUSTER_INFOS_LIMIT = 20

# ES集群类型配置特性开关key
FEATURE_TOGGLE_ES_CLUSTER_TYPE = "es_cluster_type_setup"

DEFAULT_RETENTION = 14

# 节点管理支持的cmdb 主机信息
CC_HOST_FIELDS = [
    "bk_host_id",
    "bk_agent_id",
    "bk_cloud_id",
    "bk_addressing",
    "bk_host_innerip",
    "bk_host_outerip",
    "bk_host_innerip_v6",
    "bk_host_outerip_v6",
    "bk_host_name",
    "bk_os_type",
    "bk_os_name",
    "bk_os_bit",
    "bk_os_version",
    "bk_cpu_module",
    "operator",
    "bk_bak_operator",
    "bk_isp_name",
    "bk_biz_id",
    "bk_province_name",
    "bk_state",
    "bk_state_name",
    "bk_supplier_account",
    "bk_cpu_architecture",
]

# 节点管理支持的cmdb 集群信息
CC_SCOPE_FIELDS = ["bk_set_id", "bk_module_id", "bk_set_name", "bk_module_name"]


class CmdbFieldType(ChoicesEnum):
    HOST = "host"
    SCOPE = "scope"

    _choices_labels = ((HOST, _("主机")), (SCOPE, _("集群")))


class VisibleEnum(ChoicesEnum):
    # 当前业务可见
    CURRENT_BIZ = "current_biz"
    # 多业务可见
    MULTI_BIZ = "multi_biz"
    # 当前租户可见
    CURRENT_TENANT = "current_tenant"
    # 全业务
    ALL_BIZ = "all_biz"
    # 业务属性可见
    BIZ_ATTR = "biz_attr"

    _choices_labels = (
        (CURRENT_BIZ, _("当前业务")),
        (MULTI_BIZ, _("多业务")),
        (CURRENT_TENANT, _("当前租户")),
        (ALL_BIZ, _("全业务")),
        (BIZ_ATTR, _("业务属性")),
    )


class EsSourceType(ChoicesEnum):
    OTHER = "other"
    PRIVATE = "private"
    AWS = "aws"
    QCLOUD = "qcloud"
    ALIYUN = "aliyun"
    GOOGLE = "google"

    _choices_labels = (
        (OTHER, _("其他")),
        (AWS, _("AWS")),
        (QCLOUD, _("腾讯云")),
        (ALIYUN, _("阿里云")),
        (GOOGLE, _("Google")),
        (PRIVATE, _("私有自建")),
    )

    help_md = {
        AWS: _(
            "OpenSearch 是一种分布式开源搜索和分析套件，可用于一组广泛的使用案例，如实时应用程序监控、日志分析和网站搜索。"
            "OpenSearch 提供了一个高度可扩展的系统，通过集成的可视化工具 OpenSearch 控制面板为大量数据提供快速访问和响应，"
            "使用户可以轻松地探索他们的数据。与 Elasticsearch 和 Apache Solr 相同的是，"
            "OpenSearch 由 Apache Lucene 搜索库提供支持。"
        ),
        QCLOUD: _(
            "腾讯云 Elasticsearch Service（ES）是基于开源搜索引擎 Elasticsearch 打造的高可用、"
            "可伸缩的云端全托管的 Elasticsearch 服务，包含 Kibana 及常用插件，并集成了安全、SQL、机器学习、告警、"
            "监控等高级特性（X-Pack）。使用腾讯云 ES，您可以快速部署、轻松管理、按需扩展您的集群，简化复杂运维操作，"
            "快速构建日志分析、异常监控、网站搜索、企业搜索、BI 分析等各类业务。"
        ),
        GOOGLE: _(
            "Elastic 和 Google Cloud 已建立稳固的合作关系，可以帮助各种规模的企业在 Google Cloud 上部署 Elastic 企业搜索、"
            "可观测性和安全解决方案，让您能够在数分钟内从数据中获得强大的实时见解。"
        ),
    }

    button_list = {
        AWS: [
            {
                "type": "blank",
                "url": "https://aws.amazon.com/cn/opensearch-service/the-elk-stack/what-is-opensearch/",
            }
        ],
        QCLOUD: [{"type": "blank", "url": "https://cloud.tencent.com/document/product/845"}],
        GOOGLE: [{"type": "blank", "url": "https://www.elastic.co/cn/partners/google-cloud"}],
    }

    @classmethod
    def get_choices(cls):
        # config: (id, name), choices: [(id, name)]
        return [[config[0], config[1]] for config in cls._choices_labels.value]

    @classmethod
    def get_choices_list_dict(cls):
        # config: (id, name)
        return [
            {
                "id": config[0],
                "name": config[1],
                "help_md": markdown.markdown(cls.get_help_md(config[0])),
                "button_list": cls.get_button_list(config[0]),
            }
            for config in cls._choices_labels.value
        ]

    @classmethod
    def get_help_md(cls, _id: str):
        return getattr(cls, "help_md").value.get(_id, "")

    @classmethod
    def get_button_list(cls, _id: str):
        return getattr(cls, "button_list").value.get(_id, [])


class StrategyKind(ChoicesEnum):
    CLUSTER_NODE = "cluster_node"
    COLLECTOR_CAP = "collector_cap"

    _choices_labels = ((CLUSTER_NODE, _("集群节点")), (COLLECTOR_CAP, _("采集项容量")))


class CollectItsmStatus(ChoicesEnum):
    NOT_APPLY = "not_apply"
    APPLYING = "applying"
    FAIL_APPLY = "fail_apply"
    SUCCESS_APPLY = "success_apply"

    _choices_labels = (
        (NOT_APPLY, _("未申请采集接入")),
        (APPLYING, _("采集接入进行中")),
        (FAIL_APPLY, _("采集接入失败")),
        (SUCCESS_APPLY, _("采集接入完成")),
    )


STORAGE_CLUSTER_TYPE = "elasticsearch"
KAFKA_CLUSTER_TYPE = "kafka"
TRANSFER_CLUSTER_TYPE = "transfer"
REGISTERED_SYSTEM_DEFAULT = "_default"
ETL_DELIMITER_IGNORE = "i"
ETL_DELIMITER_DELETE = "d"
ETL_DELIMITER_END = "e"
# 添加空闲机获取
BK_SUPPLIER_ACCOUNT = "0"
# 添加ES默认schema
DEFAULT_ES_SCHEMA = "http"
META_DATA_ENCODING = "utf-8"

# ADMIN请求用户名
ADMIN_REQUEST_USER = "admin"
EMPTY_REQUEST_USER = ""

# 内置dataid范围，划分出的1w个dataid，用来给蓝鲸平台作为内置的采集dataid
BUILT_IN_MIN_DATAID = 1110001
BUILT_IN_MAX_DATAID = 1119999

# 创建bkdata_data_id 配置
BKDATA_DATA_SCENARIO = "custom"
BKDATA_DATA_SCENARIO_ID = 47
BKDATA_TAGS = []
BKDATA_DATA_SOURCE_TAGS = ["server"]
BKDATA_DATA_REGION = "inland"
BKDATA_DATA_SOURCE = "data_source"
BKDATA_DATA_SENSITIVITY = "private"
BKDATA_PERMISSION = "permission"

# 创建bkdata_data_id允许错误最大数，超过该数值则需要人工介入
MAX_CREATE_BKDATA_DATA_ID_FAIL_COUNT = 3

# 获取biz_topo请求level
SEARCH_BIZ_INST_TOPO_LEVEL = -1

# 获取internal_topo并插入的默认节点位置
INTERNAL_TOPO_INDEX = 0

# biz_topo空闲节点默认index
BIZ_TOPO_INDEX = 0

# 高级清洗创建索引集默认时间格式
DEFAULT_TIME_FORMAT = _("微秒（microsecond）")
# 高级清洗默认创建业务应用型索引集
DEFAULT_CATEGORY_ID = "application_check"
DEFAULT_ETL_CONFIG = "bkdata_clean"

# 同步清洗最长ttl时间 60*10
MAX_SYNC_CLEAN_TTL = 600

# 缓存-集群信息key
CACHE_KEY_CLUSTER_INFO = "bulk_cluster_info_{}"

DEFAULT_COLLECTOR_LENGTH = 2

# 解析失败字段名
PARSE_FAILURE_FIELD = "__parse_failure"


class AsyncStatus:
    RUNNING = "RUNNING"
    DONE = "DONE"


FIELD_TEMPLATE = {
    "field_name": "",
    "alias_name": "",
    "field_type": "",
    "description": "",
    "is_analyzed": False,
    "is_dimension": False,
    "is_time": False,
    "is_delete": True,
    "is_built_in": False,
}


class TargetObjectTypeEnum(ChoicesEnum):
    """
    CMDB对象类型，可选 `SERVICE`, `HOST`
    """

    SERVICE = "SERVICE"
    HOST = "HOST"

    _choices_labels = (
        (HOST, _("主机")),
        (SERVICE, _("服务实例")),
    )


class TargetNodeTypeEnum(ChoicesEnum):
    """
    CMDB节点类型，可选 `TOPO`, `INSTANCE`
    """

    TOPO = "TOPO"
    INSTANCE = "INSTANCE"
    SERVICE_TEMPLATE = "SERVICE_TEMPLATE"
    SET_TEMPLATE = "SET_TEMPLATE"
    DYNAMIC_GROUP = "DYNAMIC_GROUP"

    _choices_labels = (
        (TOPO, _("拓扑")),
        (INSTANCE, _("主机实例")),
        (SERVICE_TEMPLATE, _("服务模板")),
        (SET_TEMPLATE, _("集群模板")),
        (DYNAMIC_GROUP, _("动态分组")),
    )


class CleanProviderEnum(ChoicesEnum):
    """
    清洗能力
    """

    TRANSFER = "transfer"
    BKDATA = "bkdata"

    _choices_labels = (
        (TRANSFER, _("Transfer")),
        (BKDATA, _("数据平台")),
    )


class CollectStatus:
    """
    采集任务状态-结合以下两种状态
    subscription_instance_status.instances[0].status
     - PENDING
     - RUNNING
     - SUCCESS
     - FAILED
    subscription_instance_status.instances[0].host_statuses.status
     - RUNNING
     - TERMINATED
     - UNKNOWN
    """

    PREPARE = "PREPARE"
    SUCCESS = "SUCCESS"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    PENDING = "PENDING"
    TERMINATED = "TERMINATED"  # SUCCESS + 空
    UNKNOWN = "UNKNOWN"


class LogPluginInfo:
    """
    采集插件信息
    """

    NAME = "bkunifylogbeat"
    VERSION = "latest"


class ActionStatus:
    START = "START"
    INSTALL = "INSTALL"


class RunStatus:
    RUNNING = _("部署中")
    SUCCESS = _("正常")
    FAILED = _("失败")
    PARTFAILED = _("部分失败")
    TERMINATED = _("已停用")
    UNKNOWN = _("未知")
    PREPARE = _("准备中")


class EtlConfig:
    BK_LOG_TEXT = "bk_log_text"
    BK_LOG_JSON = "bk_log_json"
    BK_LOG_DELIMITER = "bk_log_delimiter"
    BK_LOG_REGEXP = "bk_log_regexp"
    CUSTOM = "custom"


class MetadataTypeEnum(ChoicesEnum):
    PATH = "path"

    _choices_labels = ((PATH, _("路径元数据")),)


class EtlConfigChoices(ChoicesEnum):
    _choices_labels = (
        (EtlConfig.BK_LOG_TEXT, _("直接入库")),
        (EtlConfig.BK_LOG_JSON, _("Json")),
        (EtlConfig.BK_LOG_DELIMITER, _("分隔符")),
        (EtlConfig.BK_LOG_REGEXP, _("正则")),
        (EtlConfig.CUSTOM, _("自定义")),
    )


# 节点属性字段过滤黑名单
NODE_ATTR_PREFIX_BLACKLIST = [
    "ml.",
    "xpack.",
]

BKDATA_ES_TYPE_MAP = {
    "integer": "int",
    "long": "long",
    "keyword": "string",
    "text": "text",
    "double": "double",
    "object": "text",
    "nested": "text",
}

ETL_PARAMS = {"retain_original_text": True, "separator_regexp": "", "separator": "", "retain_extra_json": False}


class ETLProcessorChoices(ChoicesEnum):
    """
    数据处理器
    """

    TRANSFER = "transfer"
    BKBASE = "bkbase"

    _choices_labels = (
        (TRANSFER, _("Transfer")),
        (BKBASE, _("数据平台")),
    )


DEFAULT_ES_TRANSPORT = 9300

DEFAULT_ES_TAGS = ["BK-LOG"]


class Environment:
    LINUX = "linux"
    WINDOWS = "windows"
    CONTAINER = "container"


class ContainerCollectorType:
    CONTAINER = "container_log_config"
    NODE = "node_log_config"
    STDOUT = "std_log_config"


class ContainerCollectStatus(ChoicesEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"

    _choices_labels = (
        (PENDING, _("等待中")),
        (RUNNING, _("部署中")),
        (SUCCESS, _("成功")),
        (FAILED, _("失败")),
        (TERMINATED, _("已停用")),
    )


class TopoType(ChoicesEnum):
    NODE = "node"
    POD = "pod"

    _choices_labels = (
        (NODE, _("节点")),
        (POD, _("pod")),
    )


class WorkLoadType:
    DEPLOYMENT = "Deployment"
    DAEMON_SET = "DaemonSet"
    JOB = "Job"
    STATEFUL_SET = "StatefulSet"


class LabelSelectorOperator:
    IN = "In"
    NOT_IN = "NotIn"
    EXISTS = "Exists"
    DOES_NOT_EXIST = "DoesNotExist"


# 容器采集配置项转yaml时需要排除的字段
CONTAINER_CONFIGS_TO_YAML_EXCLUDE_FIELDS = ("container", "label_selector", "annotation_selector")


class CheckStatusEnum(ChoicesEnum):
    WAIT: str = "wait"
    STARTED: str = "started"
    FINISH: str = "finish"

    _choices_labels = (
        (WAIT, _("等待")),
        (STARTED, _("开始")),
        (FINISH, _("完成")),
    )


class InfoTypeEnum(ChoicesEnum):
    INFO: str = "info"
    WARNING: str = "warning"
    ERROR: str = "error"

    _choices_labels = (
        (INFO, _("信息")),
        (WARNING, _("告警")),
        (ERROR, _("错误")),
    )


INFO_TYPE_PREFIX_MAPPING = {
    InfoTypeEnum.INFO.value: "✅",
    InfoTypeEnum.WARNING.value: "⚠️",
    InfoTypeEnum.ERROR.value: "❌",
}

CHECK_COLLECTOR_CACHE_KEY_PREFIX = "check_collector"

CHECK_COLLECTOR_ITEM_CACHE_TIMEOUT = 1800

# gse agent
IPC_PATH = "/var/run/ipc.state.report"
GSE_PATH = "/usr/local/gse/"

DEFAULT_BK_USERNAME = "admin"
DEFAULT_EXECUTE_SCRIPT_ACCOUNT = "root"

JOB_SUCCESS_STATUS = 9
JOB_FAILED_AGENT_EXCEPTION = 310
JOB_STATUS = {
    JOB_SUCCESS_STATUS: _("成功"),
    JOB_FAILED_AGENT_EXCEPTION: _("Agent异常"),
}

RETRY_TIMES = 5
WAIT_FOR_RETRY = 20
INDEX_WRITE_PREFIX = "write_"
INDEX_READ_SUFFIX = "_read"

CHECK_AGENT_STEP = {
    "bin_file": _("检查二进制文件是否存在"),
    "process": _("检查进程是否存在"),
    "main_config": _("检查主配置是否存在及正确"),
    "config": _("检查配置是否正确"),
    "hosted": _("检查采集插件是否被gse_agent托管"),
    "socket": _("检查socket文件是否存在"),
    "healthz": _("执行healthz自检查查看结果"),
    "socket_queue_status": _("检查socket队列状态"),
    "dataserver_port": _("检查data server端口是否存在"),
}

# kafka ssl配置项
KAFKA_SSL_USERNAME = "sasl_username"
KAFKA_SSL_PASSWORD = "sasl_passwd"
KAFKA_SSL_MECHANISM = "sasl_mechanisms"
KAFKA_SSL_PROTOCOL = "security_protocol"

KAFKA_SSL_CONFIG_ITEMS = {KAFKA_SSL_USERNAME, KAFKA_SSL_PASSWORD, KAFKA_SSL_MECHANISM, KAFKA_SSL_PROTOCOL}

KAFKA_TEST_GROUP = "kafka_test_group"
DEFAULT_KAFKA_SECURITY_PROTOCOL = "PLAINTEXT"
DEFAULT_KAFKA_SASL_MECHANISM = "PLAIN"

# 调用GSE的'接收端配置接口'以及'路由接口'时使用
DEFAULT_GSE_API_PLAT_NAME = "bkmonitor"  # GSE分配给监控的平台名称，不随APP_CODE变更，请不要修改

# transfer metrics
TRANSFER_METRICS = [
    "transfer_pipeline_backend_handled_total",
    "transfer_pipeline_frontend_handled_total",
    "transfer_pipeline_processor_handled_total",
    "transfer_pipeline_backend_dropped_total",
    "transfer_pipeline_frontend_dropped_total",
    "transfer_pipeline_processor_dropped_total",
    "transfer_kafka_request_latency_milliseconds_bucket",
    "transfer_kafka_request_latency_milliseconds_sum",
    "transfer_kafka_request_latency_milliseconds_count",
]

META_DATA_CRON_REFRESH_TASK_NAME_LIST = [
    "metadata.task.config_refresh.refresh_datasource",
    "metadata.task.config_refresh.refresh_consul_storage",
    "metadata.task.config_refresh.refresh_es_storage",
]


# Archive
class ArchiveInstanceType(TextChoices):
    COLLECTOR_CONFIG = "collector_config", _("采集项")
    COLLECTOR_PLUGIN = "collector_plugin", _("采集插件")
    INDEX_SET = "index_set", _("索引集")


class ArchiveExpireTime:
    PERMANENT = _("永久")


# 一键检测工具执行脚本超时时间
CHECK_COLLECTOR_SCRIPT_TIMEOUT = 7200

# 一键检测工具容器采集项常量
BK_LOG_COLLECTOR_NAMESPACE = "kube-system"
CRD_NAME = "bklogconfigs.bk.tencent.com"
CONFIGMAP_NAME = "bk-log-bkunifylogbeat"
DAEMONSET_NAME: str = "bk-log-collector"
DAEMONSET_POD_LABELS: str = "name=bkunifylogbeat-bklog"
BK_LOG_COLLECTOR_CONTAINER_NAME = "bkunifylogbeat-bklog"
# 采集器主配置文件
BK_LOG_COLLECTOR_MAIN_CONFIG_NAME = "bkunifylogbeat.conf"
# 采集器子配置路径
BK_LOG_COLLECTOR_SUB_CONFIG_PATH = "bkunifylogbeat"


class PluginParamLogicOpEnum(ChoicesEnum):
    AND = "and"
    OR = "or"

    _choices_labels = (
        (AND, _("and")),
        (OR, _("or")),
    )


class PluginParamOpEnum(ChoicesEnum):
    OP_OLD_EQ = "="
    OP_OLD_NEQ = "!="
    OP_EQ = "eq"
    OP_NEQ = "neq"
    OP_INCLUDE = "include"
    OP_EXCLUDE = "exclude"
    OP_REGEX = "regex"
    OP_NREGEX = "nregex"

    _choices_labels = (
        (OP_EQ, _("等于")),
        (OP_NEQ, _("不等于")),
        (OP_INCLUDE, _("包含")),
        (OP_EXCLUDE, _("排除")),
        (OP_REGEX, _("正则匹配")),
        (OP_NREGEX, _("正则不匹配")),
    )


class SyslogProtocolEnum(ChoicesEnum):
    TCP = "tcp"
    UDP = "udp"

    _choices_labels = (
        (TCP, _("tcp协议")),
        (UDP, _("udp协议")),
    )


class SyslogFilterFieldEnum(ChoicesEnum):
    ADDRESS = "address"
    PORT = "port"
    PRIORITY = "priority"
    FACILITY = "facility"
    FACILITY_LABEL = "facility_label"
    SEVERITY = "severity"
    SEVERITY_LABEL = "severity_label"
    PROGRAM = "program"
    PID = "pid"

    _choices_labels = (
        (ADDRESS, _("地址")),
        (PORT, _("端口")),
        (PRIORITY, _("优先级")),
        (FACILITY, _("设备")),
        (FACILITY_LABEL, _("设备标签")),
        (SEVERITY, _("严重性")),
        (SEVERITY_LABEL, _("严重级别")),
        (PROGRAM, _("进程")),
        (PID, _("进程标识符")),
    )


class KafkaInitialOffsetEnum(ChoicesEnum):
    """
    1. 控制是否从头开始消费 默认为 newest（消费最新的数据）
    2. 只针对初始化一个新的消费组时生效
    """

    OLDEST = "oldest"
    NEWEST = "newest"

    _choices_labels = (
        (OLDEST, _("最旧")),
        (NEWEST, _("最新")),
    )


class CollectorBatchOperationType(ChoicesEnum):
    STOP = "stop"
    START = "start"
    MODIFY_STORAGE = "modify_storage"

    _choices_labels = (
        (STOP, _("停用")),
        (START, _("启用")),
        (MODIFY_STORAGE, _("修改存储配置")),
    )


class OTLPProxyHostConfig:
    """
    OTLP代理主机配置信息
    """

    GRPC = "grpc"
    GRPC_TRACE_PATH = ":4317"
    HTTP = "http"
    HTTP_TRACE_PATH = ":4318/v1/logs"
    HTTP_SCHEME = "http://"


RETRIEVE_CHAIN = [
    "set_itsm_info",
    "set_split_rule",
    "set_target",
    "set_default_field",
    "set_categorie_name",
    "complement_metadata_info",
    "complement_nodeman_info",
    "fields_is_empty",
    "deal_time",
    "add_container_configs",
    "encode_yaml_config",
]
