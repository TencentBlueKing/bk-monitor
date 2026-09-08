import os

from django.conf import settings as django_settings

from bk_monitor_base.config import get_config

settings = get_config()

# META配置的Consul路径
CONSUL_PATH = "{}_{}_{}/{}".format(
    settings.blueking.app_code, settings.blueking.platform, settings.blueking.environment, "metadata"
)
# SERVICE 配置的Consul路径
CONSUL_SERVICE_PATH = "{}_{}_{}/{}".format(
    settings.blueking.app_code, settings.blueking.platform, settings.blueking.environment, "service"
)

# consul data_id 路径模板
CONSUL_DATA_ID_PATH_FORMAT = f"{CONSUL_PATH}/v1/{{transfer_cluster_id}}/data_id/{{data_id}}"

# consul transfer 路径模板
CONSUL_TRANSFER_PATH = f"{CONSUL_SERVICE_PATH}/v1/"

# 内置DATAID
APACHE_METRIC_DATAID = 1004
CUSTOM_REPORT_DEFAULT_DATAID = 1100011
GSE_CUSTOM_EVENT_DATAID = 1100000
GSE_PROCESS_REPORT_DATAID = 1100008
MYSQL_METRIC_DATAID = 1002
NGINX_METRIC_DATAID = 1005
PING_SERVER_DATAID = 1100005
PROCESS_PERF_DATAID = 1007
PROCESS_PORT_DATAID = 1013
REDIS_METRIC_DATAID = 1003
SNAPSHOT_DATAID = 1001
TOMCAT_METRIC_DATAID = 1006
UPTIMECHECK_HEARTBEAT_DATAID = 1008
UPTIMECHECK_HTTP_DATAID = 1011
UPTIMECHECK_ICMP_DATAID = 1100003
UPTIMECHECK_TCP_DATAID = 1009
UPTIMECHECK_UDP_DATAID = 1010

# 监控ID区间为 [500, 600)
ZK_GSE_DATA_CLUSTER_ID = 500

# 调用GSE的'接收端配置接口'以及'路由接口'时使用
DEFAULT_GSE_API_PLAT_NAME = "bkmonitor"  # GSE分配给监控的平台名称，不随APP_CODE变更，请不要修改

# kafka的topic前缀
# 与gse对接的kafka topic，由于会存在data_id隔离，因此前缀一致可以接受
# 保持一致，是为了使得3.1和3.2可以并存同样的topic，降低基础性能上报占用kafka空间
KAFKA_TOPIC_PREFIX = "0bkmonitor_"
# 自行存储的topic需要区别，主要是因为topic拼接与table_id相关
# 3.1与3.2环境可能存在table_id冲突，因此需要增加app_code隔离
KAFKA_TOPIC_PREFIX_STORAGE = f"0{settings.blueking.app_code}_storage_"

# Redis的key前缀
# 配置理由，同KAFKA_TOPIC_PREFIX_STORAGE
REDIS_KEY_PREFIX = settings.blueking.app_code

# GSE DATA_ID最大值和最小值的判断
MIN_DATA_ID = 1500000  # 3.2版本将该值增大20w，防止与3.1版本冲突
MAX_DATA_ID = 2097151

# 允许ES转发的URL
ES_ROUTE_ALLOW_URL = ["_cat", "_cluster", "_nodes", "_stats"]


def is_built_in_data_id(bk_data_id):
    return 1000 <= bk_data_id <= 1020 or 1100000 <= bk_data_id <= 1199999


# CMDB层级拆分的公共配置项内容
# 源结果表输出的数据源名称
RT_CMDB_LEVEL_DATA_SOURCE_NAME = "{}_cmdb_level_split"
# CMDB层级差费的RT分配名
RT_CMDB_LEVEL_RT_NAME = "{}_cmdb_level"

# 获取需要增加事务的DB链接名
DATABASE_CONNECTION_NAME = settings.metadata.backend_database_name

# ES存储默认版本
ES_CLUSTER_VERSION_DEFAULT = 7

ES_SHARDS_CONFIG = os.environ.get("ES_SHARDS_NUMBER", 1)
ES_REPLICAS_CONFIG = os.environ.get("ES_REPLICAS_CONFIG", 0)

# 容器配置相关内容
# 资源组名
BCS_RESOURCE_GROUP_NAME = "monitoring.bk.tencent.com"
# 资源版本号
BCS_RESOURCE_VERSION = "v1beta1"
# data_id注入资源类型
BCS_RESOURCE_DATA_ID_RESOURCE_KIND = "DataID"
# data_id注入类型查询名
BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL = "dataids"

# BCS集群相关数据源
k8s_metric_name = "K8SMetric"
cluster_custom_metric_name = "CustomMetric"
k8s_event_name = "K8SEvent"

# 周期任务锁的超时时间
PERIODIC_TASK_DEFAULT_TTL = 7200

# 默认kafka sasl配置
KAFKA_SASL_MECHANISM = "SCRAM-SHA-512"
KAFKA_SASL_PROTOCOL = "SASL_PLAINTEXT"

# vm 存储类型
VM_STORAGE_TYPE = "vm"
# metadata 结果表白名单 key
METADATA_RESULT_TABLE_WHITE_LIST = "metadata:query_metric:table_id_list"

# 结果表保留字精确匹配列表
RT_RESERVED_WORD_EXACT = [
    "SERVER",
    "REPO",
    "VIEW",
    "TAGKEY",
    "ILLEGAL",
    "EOF",
    "WS",
    "IDENT",
    "BOUNDPARAM",
    "NUMBER",
    "INTEGER",
    "DURATIONVAL",
    "STRING",
    "BADSTRING",
    "BADESCAPE",
    "TRUE",
    "FALSE",
    "REGEX",
    "BADREGEX",
    "ADD",
    "SUB",
    "MUL",
    "DIV",
    "AND",
    "OR",
    "EQ",
    "NEQ",
    "EQREGEX",
    "NEQREGEX",
    "LT",
    "LTE",
    "GT",
    "GTE",
    "LPAREN",
    "RPAREN",
    "COMMA",
    "COLON",
    "DOUBLECOLON",
    "SEMICOLON",
    "DOT",
    "ALL",
    "ALTER",
    "ANY",
    "AS",
    "ASC",
    "BEGIN",
    "BY",
    "CREATE",
    "CONTINUOUS",
    "DATABASE",
    "DATABASES",
    "DEFAULT",
    "DELETE",
    "DESC",
    "DESTINATIONS",
    "DIAGNOSTICS",
    "DISTINCT",
    "DROP",
    "DURATION",
    "END",
    "EVERY",
    "EXISTS",
    "EXPLAIN",
    "FIELD",
    "FOR",
    "FROM",
    "GROUP",
    "GROUPS",
    "IF",
    "IN",
    "INF",
    "INSERT",
    "INTO",
    "KEY",
    "KEYS",
    "KILL",
    "LIMIT",
    "MEASUREMENT",
    "MEASUREMENTS",
    "NAME",
    "NOT",
    "OFFSET",
    "ON",
    "ORDER",
    "PASSWORD",
    "POLICY",
    "POLICIES",
    "PRIVILEGES",
    "QUERIES",
    "QUERY",
    "READ",
    "REPLICATION",
    "RESAMPLE",
    "RETENTION",
    "REVOKE",
    "SELECT",
    "SERIES",
    "SET",
    "SHOW",
    "SHARD",
    "SHARDS",
    "SLIMIT",
    "SOFFSET",
    "STATS",
    "SUBSCRIPTION",
    "SUBSCRIPTIONS",
    "TAG",
    "TO",
    "TIME",
    "VALUES",
    "WHERE",
    "WITH",
    "WRITE",
    "TIMESTAMP",
    "TIME",
    # 内置字段
    "BK_BIZ_ID",
    "IP",
    "PLAT_ID",
    "BK_CLOUD_ID",
    "CLOUD_ID",
    "COMPANY_ID",
    "BK_SUPPLIER_ID",
]

db_collation: str = (
    "BINARY" if django_settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3" else "utf8_bin"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CRONTAB = [
    # metadata 更新 bkcc 空间名称任务，因为不要求实时性，每6分钟执行一次
    ("bk_monitor_base.metadata.task.sync_space.refresh_bkcc_space_name", "*/6 * * * *", "global"),
    # metadata更新每个influxdb的存储RP，UTC时间的22点进行更新，待0点influxdb进行清理
    ("bk_monitor_base.metadata.task.refresh_default_rp", "0 22 * * *", "global"),
    # metadata同步pingserver配置，下发iplist到proxy机器，每10分钟执行一次
    ("bk_monitor_base.metadata.task.ping_server.refresh_ping_server_2_node_man", "*/10 * * * *", "global"),
    # metadata同步自定义上报配置到节点管理，完成配置订阅，理论上，在配置变更的时候，会执行一次，所以这里运行周期可以放大
    ("bk_monitor_base.metadata.task.custom_report.refresh_all_custom_report_2_node_man", "*/5 * * * *", "global"),
    # metadata同步自定义日志配置到节点管理，虽然 1 分钟一次，实际只会运行ID对30取模后和当前分钟对齐的任务
    ("bk_monitor_base.metadata.task.custom_report.refresh_all_log_config", "* * * * *", "global"),
    # metadata同步自定义日志k8s批量配置，每5分钟触发，获取全部数据进行批量调度
    ("bk_monitor_base.metadata.task.custom_report.refresh_all_log_config_to_k8s", "*/10 * * * *", "global"),
    # metadata自动部署bkmonitorproxy
    ("bk_monitor_base.metadata.task.auto_deploy_proxy", "30 */2 * * *", "global"),
    ("bk_monitor_base.metadata.task.config_refresh.refresh_consul_es_info", "*/10 * * * *", "global"),
    ("bk_monitor_base.metadata.task.config_refresh.refresh_consul_storage", "*/10 * * * *", "global"),
    # 检查V4数据源是否存在对应的Consul配置，若存在则删除
    ("bk_monitor_base.metadata.task.config_refresh.check_and_delete_ds_consul_config", "*/5 * * * *", "global"),
    ("bk_monitor_base.metadata.task.config_refresh.refresh_bcs_info", "*/10 * * * *", "global"),
    # 刷新回溯配置
    ("bk_monitor_base.metadata.task.config_refresh.refresh_es_restore", "* * * * *", "global"),
    # 上报自采集指标--每分钟一次
    ("bk_monitor_base.metadata.task.custom_report.report_custom_metrics", "* * * * *", "global"),
    # bcs信息刷新
    ("bk_monitor_base.metadata.task.bcs.refresh_bcs_metrics_label", "*/10 * * * *", "global"),
    ("bk_monitor_base.metadata.task.bcs.refresh_bcs_monitor_info", "*/10 * * * *", "global"),
    ("bk_monitor_base.metadata.task.bcs.discover_bcs_clusters", "*/5 * * * *", "global"),
    # BkBase信息同步,一小时一次
    ("bk_monitor_base.metadata.task.bkbase.sync_all_bkbase_cluster_info", "0 */1 * * *", "global"),
    # 检查并执行接入vm命令, 每5分钟执行一次
    ("bk_monitor_base.metadata.task.vm.check_access_vm_task", "*/5 * * * *", "global"),
    # 同步空间信息
    ("bk_monitor_base.metadata.task.sync_space.sync_bkcc_space", "*/10 * * * *", "global"),
    ("bk_monitor_base.metadata.task.sync_space.sync_bcs_space", "*/10 * * * *", "global"),
    ("bk_monitor_base.metadata.task.sync_space.refresh_bcs_project_biz", "*/10 * * * *", "global"),
    # 关联协议数据同步--cmdb_relation
    ("bk_monitor_base.metadata.task.sync_cmdb_relation.sync_relation_redis_data", "0 * * * *", "global"),
    # 计算平台元数据一致性 Redis Watch
    ("bk_monitor_base.metadata.task.bkbase.watch_bkbase_meta_redis_task", "* * * * *", "global"),
    # ES集群关键配置检查,六小时检查一次
    ("bk_monitor_base.metadata.task.config_refresh.check_es_clusters_key_settings", "0 */6 * * *", "global"),
    # metadata 全量刷新 ResourceDefinition/RelationDefinition 到 Redis 兜底任务，每10分钟一次
    ("bk_monitor_base.metadata.task.entity_relation.refresh_entity_definition_to_redis", "*/10 * * * *", "global"),
]

LONG_TASK_CRONTAB = [
    # 清理任务耗时较久，半个小时执行一次
    # ("bk_monitor_base.metadata.task.config_refresh.clean_influxdb_tag", "*/30 * * * *", "global"),
    # ("bk_monitor_base.metadata.task.config_refresh.clean_influxdb_storage", "*/30 * * * *", "global"),
    # ("bk_monitor_base.metadata.task.config_refresh.clean_influxdb_cluster", "*/30 * * * *", "global"),
    # ("bk_monitor_base.metadata.task.config_refresh.clean_influxdb_host", "*/30 * * * *", "global"),
    # 刷新 storage 信息给unify-query使用
    # TODO: 待确认是否还有使用，如没使用可以删除
    ("bk_monitor_base.metadata.task.config_refresh.refresh_consul_influxdb_tableinfo", "*/10 * * * *", "global"),
    # 刷新结果表路由配置
    ("bk_monitor_base.metadata.task.config_refresh.refresh_influxdb_route", "*/10 * * * *", "global"),
    # 刷新空间信息，业务、BCS的关联资源
    ("bk_monitor_base.metadata.task.sync_space.refresh_cluster_resource", "*/30 * * * *", "global"),
    ("bk_monitor_base.metadata.task.sync_space.sync_bkcc_space_data_source", "* */1 * * *", "global"),
    # metadata 同步自定义事件维度及事件，每三分钟将会从ES同步一次
    ("bk_monitor_base.metadata.task.custom_report.check_event_update", "*/3 * * * *", "global"),
    # metadata 同步 bkci 空间名称任务，因为不要求实时性，每天3点执行一次
    ("bk_monitor_base.metadata.task.sync_space.refresh_bkci_space_name", "0 3 * * *", "global"),
    # metadata 刷新 unify_query 视图需要的字段，因为变动性很低，每天 4 点执行一次
    # ("bk_monitor_base.metadata.task.config_refresh.refresh_unify_query_additional_config", "0 4 * * *", "global"),
    # 删除数据库中已经不存在的数据源
    ("bk_monitor_base.metadata.task.config_refresh.clean_datasource_from_consul", "30 4 * * *", "global"),
    # 每天同步一次蓝鲸应用的使用的集群
    ("bk_monitor_base.metadata.task.sync_space.refresh_bksaas_space_resouce", "0 1 * * *", "global"),
    # 自定义事件休眠检查，对长期没有数据的自定义事件进行休眠
    ("bk_monitor_base.metadata.task.custom_report.check_custom_event_group_sleep", "0 4 * * *", "global"),
    # ES 周期性任务 从report_cron 队列迁回 LONG_TASK_CRONTAB (周期调整 10-> 15min)
    ("bk_monitor_base.metadata.task.config_refresh.refresh_es_storage", "*/15 * * * *", "global"),
    # BkBase数据兜底任务,2h一次
    ("bk_monitor_base.metadata.task.bkbase.sync_bkbase_metadata_all", "0 */2 * * *", "global"),
    # BkBase RT 路由同步任务，6h一次
    ("bk_monitor_base.metadata.task.bkbase.sync_bkbase_rt_meta_info_all", "0 */6 * * *", "global"),
    # 禁用采集项索引清理任务，30min
    ("bk_monitor_base.metadata.task.config_refresh.manage_disable_es_storage", "*/30 * * * *", "global"),
    # 新版链路状态自动兜底刷新,15min 一次
    ("bk_monitor_base.metadata.task.refresh_data_link.refresh_data_link_status", "*/15 * * * *", "global"),
]
