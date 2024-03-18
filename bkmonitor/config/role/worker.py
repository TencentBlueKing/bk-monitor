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
import logging
import os
import sys

from jinja2 import DebugUndefined

from config.tools.consul import get_consul_settings
from config.tools.rabbitmq import get_rabbitmq_settings
from config.tools.redis import get_cache_redis_settings, get_redis_settings

from ..tools.environment import (
    DJANGO_CONF_MODULE,
    ENVIRONMENT,
    IS_CONTAINER_MODE,
    NEW_ENV,
    ROLE,
)

# 按照环境变量中的配置，加载对应的配置文件
try:
    _module = __import__(f"config.{NEW_ENV}", globals(), locals(), ["*"])
except ImportError as e:
    logging.exception(e)
    raise ImportError("Could not import config '{}' (Is it on sys.path?): {}".format(DJANGO_CONF_MODULE, e))

for _setting in dir(_module):
    if _setting == _setting.upper():
        locals()[_setting] = getattr(_module, _setting)

ROOT_URLCONF = "alarm_backends.urls"

# SUPERVISOR 配置
SUPERVISOR_PORT = 9001
SUPERVISOR_SERVER = "unix:///var/run/bkmonitorv3/monitor-supervisor.sock"
SUPERVISOR_USERNAME = ""
SUPERVISOR_PASSWORD = ""

INSTALLED_APPS += (  # noqa: F405
    "django_elasticsearch_dsl",
    "django_jinja",
    "bkmonitor",
    "bkm_space",
    "calendars",
    "metadata",
    "alarm_backends",
    "apm",
    "apm_ebpf",
    "core.drf_resource",
)

# 系统名称
BACKEND_NAME = "BK Monitor Backend"

# access最大向前拉取事件, second
MIN_DATA_ACCESS_CHECKPOINT = 30 * 60
# access 每次往前多拉取1个周期的数据
NUM_OF_COUNT_FREQ_ACCESS = 1

# 流控配置
QOS_DROP_ALARM_THREADHOLD = 3

TEMPLATES = [
    {
        "NAME": "jinja2",
        "BACKEND": "django_jinja.backend.Jinja2",
        "DIRS": ["templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "match_extension": ".jinja",
            "context_processors": [
                "django.template.context_processors.i18n",
                "django.contrib.messages.context_processors.messages",
            ],
            "undefined": DebugUndefined,
        },
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.i18n",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# 是否启用通知出图
GRAPH_RENDER_SERVICE_ENABLED = True

# 告警检测范围动态关联开关
DETECT_RANGE_DYNAMIC_ASSOCIATE = True

# 告警开关
ENABLE_PING_ALARM = True
ENABLE_AGENT_ALARM = True
ENABLE_DIRECT_AREA_PING_COLLECT = True  # 是否开启直连区域的PING采集

HEALTHZ_ALARM_CONFIG = {}

# CRONTAB
DEFAULT_CRONTAB = [
    # eg:
    # (module_name, every, run_type) like: ("fta.poll_alarm.main start", "* * * * *", "global")
    # Notice Notice Notice:
    # Use UTC's time zone to set your crontab instead of the local time zone
    # run_type: global/cluster
    # cmdb cache
    ("alarm_backends.core.cache.cmdb.host", "*/10 * * * *", "global"),
    ("alarm_backends.core.cache.cmdb.module", "*/10 * * * *", "global"),
    ("alarm_backends.core.cache.cmdb.set", "*/10 * * * *", "global"),
    ("alarm_backends.core.cache.cmdb.business", "*/10 * * * *", "global"),
    ("alarm_backends.core.cache.cmdb.service_instance", "*/10 * * * *", "global"),
    ("alarm_backends.core.cache.cmdb.topo", "*/10 * * * *", "global"),
    ("alarm_backends.core.cache.cmdb.service_template", "*/10 * * * *", "global"),
    ("alarm_backends.core.cache.cmdb.set_template", "*/10 * * * *", "global"),
    # model cache
    # 策略全量更新频率降低
    ("alarm_backends.core.cache.strategy", "*/6 * * * *", "global"),
    # 策略增量更新
    ("alarm_backends.core.cache.strategy.smart_refresh", "* * * * *", "global"),
    ("alarm_backends.core.cache.shield", "* * * * *", "global"),
    ("alarm_backends.core.cache.models.collect_config", "* * * * *", "global"),
    ("alarm_backends.core.cache.models.uptimecheck", "* * * * *", "global"),
    ("alarm_backends.core.cache.action_config.refresh_total", "*/60 * * * *", "global"),
    ("alarm_backends.core.cache.action_config.refresh_latest_5_minutes", "* * * * *", "global"),
    ("alarm_backends.core.cache.assign", "* * * * *", "global"),
    ("alarm_backends.core.cache.calendar", "* * * * *", "global"),
    # api cache
    ("alarm_backends.core.cache.result_table", "*/10 * * * *", "global"),
    # delay queue
    ("alarm_backends.core.cache.delay_queue", "* * * * *", "global"),
    # bcs cluster cache
    ("alarm_backends.core.cache.bcs_cluster", "*/10 * * * *", "global"),
    # clean detect result cache
    ("alarm_backends.core.detect_result.tasks.clean_expired_detect_result", "0 */2 * * *", "global"),
    ("alarm_backends.core.detect_result.tasks.clean_md5_to_dimension_cache", "0 23 * * *", "global"),
    # 定期清理超时未执行任务
    ("alarm_backends.service.fta_action.tasks.check_timeout_actions", "* * * * *", "global"),
    # 定期清理mysql内半个月前的数据
    ("alarm_backends.service.fta_action.tasks.clear_mysql_action_data", "* * * * *", "global"),
    # mail_report 配置管理和告警接收人信息缓存
    ("alarm_backends.core.cache.mail_report", "*/30 * * * *", "global"),
    # apm topo discover: 每分钟触发，每次分片处理1/10应用
    ("apm.task.tasks.topo_discover_cron", "* * * * *", "global"),
    # apm 配置下发: 每分钟触发，每次分片处理1/30应用
    ("apm.task.tasks.refresh_apm_config", "* * * * *", "global"),
    ("apm.task.tasks.refresh_apm_platform_config", "*/30 * * * *", "global"),
    # apm 检测预计算表字段是否有更新 1小时执行检测一次
    ("apm.task.tasks.check_pre_calculate_fields_update", "0 */1 * * *", "global"),
    # apm 检查consul配置是否有更新 1小时执行检测一次
    ("apm.task.tasks.check_apm_consul_config", "0 */1 * * *", "global"),
    # apm_ebpf 定时检查业务集群是否安装DeepFlow 每半小时触发
    ("apm_ebpf.task.tasks.ebpf_discover_cron", "*/30 * * * *", "global"),
    # apm_ebpf 定时检查集群和业务绑定关系 每十分钟触发
    ("apm_ebpf.task.tasks.cluster_discover_cron", "*/10 * * * *", "global"),
    # apm_profile 定时发现profile服务 每十分钟触发
    ("apm.task.tasks.profile_discover_cron", "*/10 * * * *", "global"),
]

if BCS_API_GATEWAY_HOST:
    DEFAULT_CRONTAB += [
        # bcs资源同步
        ("api.bcs.tasks.sync_bcs_cluster_to_db", "*/10 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_service_to_db", "*/10 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_workload_to_db", "*/10 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_pod_to_db", "*/10 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_node_to_db", "*/10 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_service_monitor_to_db", "*/10 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_pod_monitor_to_db", "*/10 * * * *", "global"),
        # bcs资源数据状态同步
        # TODO: 调整好后再开启
        ("api.bcs.tasks.sync_bcs_cluster_resource", "*/15 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_workload_resource", "*/15 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_service_resource", "*/15 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_pod_resource", "*/15 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_container_resource", "*/15 * * * *", "global"),
        ("api.bcs.tasks.sync_bcs_node_resource", "*/15 * * * *", "global"),
        # bcs集群安装operator信息，一天同步一次
        ("api.bcs.tasks.sync_bkmonitor_operator_info", "0 2 * * *", "global"),
    ]

ACTION_TASK_CRONTAB = [
    # 分集群任务
    # 定期检测异常告警
    ("alarm_backends.service.alert.manager.tasks.check_abnormal_alert", "* * * * *", "cluster"),
    # 定期关闭流控告警，避免与整点之类的任务并发，设置每12分钟执行一次
    ("alarm_backends.service.alert.manager.tasks.check_blocked_alert", "*/12 * * * *", "cluster"),
    # 定期检测屏蔽策略，进行告警的屏蔽
    ("alarm_backends.service.converge.shield.tasks.check_and_send_shield_notice", "* * * * *", "cluster"),
    # 全局任务
    # 定期同步数据至es
    ("alarm_backends.service.fta_action.tasks.sync_action_instances", "* * * * *", "global"),
    # 定期维护排班计划
    ("alarm_backends.service.fta_action.tasks.generate_duty_plan_task", "* * * * *", "global"),
    # 定期处理demo任务
    ("alarm_backends.service.fta_action.tasks.dispatch_demo_action_tasks", "* * * * *", "global"),
    # 定期进行告警索引轮转 隔天创建，时间稍微拉长一点，避免短时间任务堵塞的时候容易过期，导致创建不成功
    ("bkmonitor.documents.tasks.rollover_indices", "*/24 * * * *", "global"),
    # 定期清理停用的ai 策略对应的flow任务(每天2点半)
    ("bkmonitor.management.commands.clean_aiflow.run_clean", "30 2 * * *", "global"),
]

if os.getenv("DISABLE_METADATA_TASK") != "True":
    DEFAULT_CRONTAB += [
        # metadata
        # metadata更新每个influxdb的存储RP，UTC时间的22点进行更新，待0点influxdb进行清理
        ("metadata.task.refresh_default_rp", "0 22 * * *", "global"),
        # metadata同步pingserver配置，下发iplist到proxy机器，每10分钟执行一次
        ("metadata.task.ping_server.refresh_ping_server_2_node_man", "*/10 * * * *", "global"),
        # metadata同步自定义上报配置到节点管理，完成配置订阅，理论上，在配置变更的时候，会执行一次，所以这里运行周期可以放大
        ("metadata.task.custom_report.refresh_custom_report_2_node_man", "*/5 * * * *", "global"),
        # metadata自动部署bkmonitorproxy
        ("metadata.task.auto_deploy_proxy", "30 */2 * * *", "global"),
        ("metadata.task.config_refresh.refresh_kafka_storage", "*/10 * * * *", "global"),
        ("metadata.task.config_refresh.refresh_kafka_topic_info", "*/10 * * * *", "global"),
        ("metadata.task.config_refresh.refresh_consul_es_info", "*/10 * * * *", "global"),
        ("metadata.task.config_refresh.refresh_consul_storage", "*/10 * * * *", "global"),
        ("metadata.task.config_refresh.refresh_bcs_info", "*/10 * * * *", "global"),
        # 刷新metadata降精度配置，10分钟一次
        ("metadata.task.downsampled.refresh_influxdb_downsampled", "*/10 * * * *", "global"),
        # 降精度计算，5分钟一次检测一次
        ("metadata.task.downsampled.access_and_calc_for_downsample", "*/5 * * * *", "global"),
        # 刷新回溯配置
        ("metadata.task.config_refresh.refresh_es_restore", "* * * * *", "global"),
        # bcs信息刷新
        ("metadata.task.bcs.refresh_bcs_monitor_info", "*/10 * * * *", "global"),
        ("metadata.task.bcs.refresh_bcs_metrics_label", "*/10 * * * *", "global"),
        ("metadata.task.bcs.discover_bcs_clusters", "*/10 * * * *", "global"),
        # 同步空间信息
        ("metadata.task.sync_space.sync_bkcc_space", "*/10 * * * *", "global"),
        ("metadata.task.sync_space.sync_bcs_space", "*/10 * * * *", "global"),
        ("metadata.task.sync_space.refresh_bcs_project_biz", "*/10 * * * *", "global"),
        # metadata同步自定义时序维度信息, 每5分钟将会从consul同步一次
        ("metadata.task.custom_report.check_update_ts_metric", "*/5 * * * *", "global"),
    ]
    # 耗时任务单独队列处理
    LONG_TASK_CRONTAB = [
        # 清理任务耗时较久，半个小时执行一次
        # ("metadata.task.config_refresh.clean_influxdb_tag", "*/30 * * * *", "global"),
        # ("metadata.task.config_refresh.clean_influxdb_storage", "*/30 * * * *", "global"),
        # ("metadata.task.config_refresh.clean_influxdb_cluster", "*/30 * * * *", "global"),
        # ("metadata.task.config_refresh.clean_influxdb_host", "*/30 * * * *", "global"),
        # 刷新数据源信息到 consul
        ("metadata.task.config_refresh.refresh_datasource", "*/10 * * * *", "global"),
        # 刷新 storage 信息给unify-query使用
        # TODO: 待确认是否还有使用，如没使用可以删除
        ("metadata.task.config_refresh.refresh_consul_influxdb_tableinfo", "*/10 * * * *", "global"),
        # 刷新结果表路由配置
        ("metadata.task.config_refresh.refresh_influxdb_route", "*/10 * * * *", "global"),
        # 刷新空间信息，业务、BCS的关联资源
        ("metadata.task.sync_space.refresh_cluster_resource", "*/30 * * * *", "global"),
        ("metadata.task.sync_space.sync_bkcc_space_data_source", "* */1 * * *", "global"),
        # metadata 同步自定义事件维度及事件，每三分钟将会从ES同步一次
        ("metadata.task.custom_report.check_event_update", "*/3 * * * *", "global"),
        # metadata 同步 bkci 空间名称任务，因为不要求实时性，每天3点执行一次
        ("metadata.task.sync_space.refresh_bkci_space_name", "0 3 * * *", "global"),
        # metadata 更新 bkcc 空间名称任务，因为不要求实时性，每天3点半执行一次
        ("metadata.task.sync_space.refresh_bkcc_space_name", "30 3 * * *", "global"),
        # metadata 刷新 unify_query 视图需要的字段，因为变动性很低，每天 4 点执行一次
        # ("metadata.task.config_refresh.refresh_unify_query_additional_config", "0 4 * * *", "global"),
        # 删除数据库中已经不存在的数据源
        ("metadata.task.config_refresh.clean_datasource_from_consul", "30 4 * * *", "global"),
        # 每天同步一次蓝鲸应用的使用的集群
        ("metadata.task.sync_space.refresh_bksaas_space_resouce", "0 1 * * *", "global"),
        # 同步空间路由数据，1小时更新一次
        ("metadata.task.sync_space.push_and_publish_space_router_task", "* */1 * * *", "global"),
        # 检查并执行接入vm命令, 每天执行一次
        ("metadata.task.vm.check_access_vm_task", "0 2 * * *", "global"),
    ]

# Timeout for image exporter service, default set to 10 seconds
IMAGE_EXPORTER_TIMEOUT = 10

AES_X_KEY_FIELD = "SAAS_SECRET_KEY"

# gse alarm dataid
GSE_BASE_ALARM_DATAID = 1000
GSE_CUSTOM_EVENT_DATAID = 1100000

BKMONITOR_WORKER_INET_DEV = ""
BKMONITOR_WORKER_INCLUDE_LIST = []
BKMONITOR_WORKER_EXCLUDE_LIST = []

# ACTION
MESSAGE_QUEUE_MAX_LENGTH = 0

# SELF-MONITOR
SUPERVISOR_PROCESS_UPTIME = 10

SELFMONITOR_PORTS = {"gse-data": 58625}

# 计算平台localTime与UTC时间的差值
BKDATA_LOCAL_TIMEZONE_OFFSET = -8
# 计算平台数据的localTime与当前时间比较的阈值，小于该值时下次再拉取数据
BKDATA_LOCAL_TIME_THRESHOLD = 10

# 跳过权限中心检查
SKIP_IAM_PERMISSION_CHECK = True

# event 模块最大容忍无数据周期数
EVENT_NO_DATA_TOLERANCE_WINDOW_SIZE = 5

ANOMALY_RECORD_COLLECT_WINDOW = 100
ANOMALY_RECORD_CONVERGED_ACTION_WINDOW = 3

# access模块策略拉取耗时限制（每10分钟）
ACCESS_TIME_PER_WINDOW = 30

# 环境变量
PYTHON_HOME = sys.executable.rsplit("/", 1)[0]  # virtualenv path
PYTHON = PYTHON_HOME + "/python"  # python bin
GUNICORN = PYTHON_HOME + "/gunicorn"  # gunicorn bin

LOG_LOGFILE_MAXSIZE = 1024 * 1024 * 200  # 200m
LOG_LOGFILE_BACKUP_COUNT = 12
LOG_PROCESS_CHECK_TIME = 60 * 60 * 4
LOG_LOGFILE_BACKUP_GZIP = True

# LOGGING
LOGGER_LEVEL = os.environ.get("BKAPP_LOG_LEVEL", "INFO")
LOG_FILE_PATH = os.path.join(LOG_PATH, f"{LOG_FILE_PREFIX}kernel.log")
LOG_IMAGE_EXPORTER_FILE_PATH = os.path.join(LOG_PATH, f"{LOG_FILE_PREFIX}kernel_image_exporter.log")
LOG_METADATA_FILE_PATH = os.path.join(LOG_PATH, f"{LOG_FILE_PREFIX}kernel_metadata.log")
LOGGER_DEFAULT = {"level": LOGGER_LEVEL, "handlers": ["console", "file"]}


def get_logger_config(log_path, logger_level, log_file_prefix):
    return {
        "version": 1,
        "loggers": {
            "root": LOGGER_DEFAULT,
            "core": LOGGER_DEFAULT,
            "cron": LOGGER_DEFAULT,
            "cache": LOGGER_DEFAULT,
            "service": LOGGER_DEFAULT,
            "detect": LOGGER_DEFAULT,
            "nodata": LOGGER_DEFAULT,
            "access": LOGGER_DEFAULT,
            "trigger": LOGGER_DEFAULT,
            "event": LOGGER_DEFAULT,
            "alert": LOGGER_DEFAULT,
            "composite": LOGGER_DEFAULT,
            "recovery": LOGGER_DEFAULT,
            "fta_action": LOGGER_DEFAULT,
            "bkmonitor": LOGGER_DEFAULT,
            "apm_ebpf": LOGGER_DEFAULT,
            "apm": LOGGER_DEFAULT,
            "data_source": LOGGER_DEFAULT,
            "alarm_backends": LOGGER_DEFAULT,
            "self_monitor": LOGGER_DEFAULT,
            "calendars": LOGGER_DEFAULT,
            "celery": LOGGER_DEFAULT,
            "kubernetes": LOGGER_DEFAULT,
            "metadata": {"level": LOGGER_LEVEL, "propagate": False, "handlers": ["metadata"]},
            "image_exporter": {"level": LOGGER_LEVEL, "propagate": False, "handlers": ["image_exporter"]},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "level": "DEBUG", "formatter": "standard"},
            "file": {
                "class": "logging.handlers.WatchedFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": os.path.join(log_path, f"{log_file_prefix}kernel.log"),
                "encoding": "utf-8",
            },
            "image_exporter": {
                "class": "logging.handlers.WatchedFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": os.path.join(log_path, f"{log_file_prefix}kernel_image_exporter.log"),
                "encoding": "utf-8",
            },
            "metadata": {
                "class": "logging.handlers.WatchedFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": os.path.join(log_path, f"{log_file_prefix}kernel_metadata.log"),
                "encoding": "utf-8",
            },
        },
        "formatters": {
            "standard": {
                "format": (
                    "%(asctime)s %(levelname)-8s %(process)-8d" "%(name)-15s %(filename)20s[%(lineno)03d] %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
    }


LOGGING = LOGGER_CONF = get_logger_config(LOG_PATH, LOGGER_LEVEL, LOG_FILE_PREFIX)

if IS_CONTAINER_MODE:
    for logger in LOGGING["loggers"]:
        if "null" not in LOGGING["loggers"][logger]["handlers"]:
            LOGGING["loggers"][logger]["handlers"] = ["console"]

# Consul
(
    CONSUL_CLIENT_HOST,
    CONSUL_CLIENT_PORT,
    CONSUL_HTTPS_PORT,
    CONSUL_CLIENT_CERT_FILE,
    CONSUL_CLIENT_KEY_FILE,
    CONSUL_SERVER_CA_CERT,
) = get_consul_settings()

# Redis
CACHE_BACKEND_TYPE, REDIS_HOST, REDIS_PORT, REDIS_PASSWD, REDIS_MASTER_NAME, REDIS_SENTINEL_PASS = get_redis_settings()
(
    CACHE_REDIS_HOST,
    CACHE_REDIS_PORT,
    CACHE_REDIS_PASSWD,
    CACHE_REDIS_MASTER_NAME,
    CACHE_REDIS_SENTINEL_PASS,
) = get_cache_redis_settings(CACHE_BACKEND_TYPE)
CACHE_REDIS_HOST, CACHE_REDIS_PORT, CACHE_REDIS_PASSWD, CACHE_REDIS_MASTER_NAME, CACHE_REDIS_SENTINEL_PASS = (
    CACHE_REDIS_HOST or REDIS_HOST,
    CACHE_REDIS_PORT or REDIS_PORT,
    CACHE_REDIS_PASSWD if CACHE_REDIS_PASSWD is None else REDIS_PASSWD,
    CACHE_REDIS_MASTER_NAME or REDIS_MASTER_NAME,
    CACHE_REDIS_SENTINEL_PASS if CACHE_REDIS_SENTINEL_PASS is None else REDIS_SENTINEL_PASS,
)

# redis中的db分配[7，8，9，10]，共4个db
# 7.[不重要，可清理] 日志相关数据使用log配置
# 8.[一般，可清理]   配置相关缓存使用cache配置，例如：cmdb的数据、策略、屏蔽等配置数据
# 9.[重要，不可清理] 各个services之间交互的队列，使用queue配置
# 9.[重要，不可清理] celery的broker，使用celery配置
# 10.[重要，不可清理] service自身的数据，使用service配置
REDIS_LOG_CONF = {"host": REDIS_HOST, "port": REDIS_PORT, "db": 7, "password": REDIS_PASSWD}
REDIS_CACHE_CONF = {
    "host": CACHE_REDIS_HOST,
    "port": CACHE_REDIS_PORT,
    "db": 8,
    "password": CACHE_REDIS_PASSWD,
    "master_name": CACHE_REDIS_MASTER_NAME,
    "sentinel_password": CACHE_REDIS_SENTINEL_PASS,
}
REDIS_CELERY_CONF = REDIS_QUEUE_CONF = {"host": REDIS_HOST, "port": REDIS_PORT, "db": 9, "password": REDIS_PASSWD}
REDIS_SERVICE_CONF = {"host": REDIS_HOST, "port": REDIS_PORT, "db": 10, "password": REDIS_PASSWD, "socket_timeout": 10}

# TRANSFER
TRANSFER_HOST = os.environ.get("BK_TRANSFER_HOST", "transfer.bkmonitorv3.service.consul")
TRANSFER_PORT = os.environ.get("BK_TRANSFER_HTTP_PORT", 10202)

# INFLUXDB
INFLUXDB_HOST = os.environ.get("BK_INFLUXDB_PROXY_HOST", "influxdb-proxy.bkmonitorv3.service.consul")
INFLUXDB_PORT = int(os.environ.get("BK_INFLUXDB_PROXY_PORT", 10203))

CERT_PATH = os.environ.get("BK_CERT_PATH", "")
LICENSE_HOST = os.environ.get("BK_LICENSE_HOST", "license.service.consul")
LICENSE_PORT = os.environ.get("BK_LICENSE_PORT", "8443")
LICENSE_REQ_INTERVAL = [20, 60, 120]  # 连续请求n次，每次请求间隔(单位：秒)

RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_VHOST, RABBITMQ_USER, RABBITMQ_PASS, _ = get_rabbitmq_settings(
    app_code=APP_CODE, backend=True
)

# esb组件地址
COMMON_USERNAME = os.environ.get("BK_ESB_SUPER_USER", "admin")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "OPTIONS": {"MAX_ENTRIES": 100000, "CULL_FREQUENCY": 10},
    },
    "db": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "OPTIONS": {"MAX_ENTRIES": 100000, "CULL_FREQUENCY": 10},
    },
    "login_db": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "account_cache"},
    "locmem": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

# django cache backend using redis
DJANGO_REDIS_PASSWORD = os.environ.get("DJANGO_REDIS_PASSWORD")
DJANGO_REDIS_HOST = os.environ.get("DJANGO_REDIS_HOST")
DJANGO_REDIS_PORT = os.environ.get("DJANGO_REDIS_PORT")
DJANGO_REDIS_DB = os.environ.get("DJANGO_REDIS_DB")
USE_DJANGO_CACHE_REDIS = "DJANGO_REDIS_HOST" in os.environ and "DJANGO_REDIS_PORT" in os.environ
if USE_DJANGO_CACHE_REDIS:
    CACHES["redis"] = {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://:{}@{}:{}/{}".format(
            DJANGO_REDIS_PASSWORD or "", DJANGO_REDIS_HOST, DJANGO_REDIS_PORT, DJANGO_REDIS_DB or "0"
        ),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        },
    }
    CACHES["default"] = CACHES["redis"]
    CACHES["login_db"] = CACHES["redis"]

# 全局告警屏蔽开关
GLOBAL_SHIELD_ENABLED = False

# 处理动作丢弃阈值
QOS_DROP_ACTION_THRESHOLD = 100
# 处理动作流控窗口大小
QOS_DROP_ACTION_WINDOW = 60

# 处理动作丢弃阈值
QOS_ALERT_THRESHOLD = 200
# 处理动作流控窗口大小
QOS_ALERT_WINDOW = 60

# 第三方事件接入白名单
BIZ_WHITE_LIST_FOR_3RD_EVENT = []

# 自定义指标拉取最大步长
MAX_METRICS_FETCH_STEP = os.environ.get("MAX_METRICS_FETCH_STEP", 500)
METRICS_KEY_PREFIX = "bkmonitor:metrics_"
METRIC_DIMENSIONS_KEY_PREFIX = "bkmonitor:metric_dimensions_"

# 默认 Kafka 存储集群 ID
DEFAULT_KAFKA_STORAGE_CLUSTER_ID = None
# BCS Kafka 存储集群 ID
BCS_KAFKA_STORAGE_CLUSTER_ID = None
# 自定义上报时间存储集群
BCS_CUSTOM_EVENT_STORAGE_CLUSTER_ID = None

# 无数据告警过期时间
NO_DATA_ALERT_EXPIRED_TIMEDELTA = 24 * 60 * 60

# 计算平台计算 FLOW 存储数据的 HDFS 的集群
BKDATA_FLOW_HDFS_CLUSTER = os.environ.get("BKDATA_FLOW_HDFS_CLUSTER", "hdfsOnline4")

# 单次build告警的event数量设置
MAX_BUILD_EVENT_NUMBER = 0
