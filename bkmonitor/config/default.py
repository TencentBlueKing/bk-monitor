"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import importlib
import ntpath
import os
import sys
import warnings
from urllib.parse import urljoin

from bkcrypto import constants
from bkcrypto.symmetric.options import AESSymmetricOptions, SM4SymmetricOptions
from bkcrypto.utils.convertors import Base64Convertor
from blueapps.conf.default_settings import *  # noqa
from blueapps.conf.log import get_logging_config_dict
from django.utils.translation import gettext_lazy as _

from ai_agent.conf.default import *  # noqa
from bkmonitor.utils.i18n import TranslateDict

from . import get_env_or_raise
from .tools.elasticsearch import get_es7_settings
from .tools.environment import (
    BKAPP_DEPLOY_PLATFORM,
    ENVIRONMENT,
    IS_CONTAINER_MODE,  # noqa
    PAAS_VERSION,
    PLATFORM,
    ROLE,
)
from .tools.mysql import (
    get_backend_mysql_settings,
    get_grafana_mysql_settings,
    get_saas_mysql_settings,
)
from .tools.service import get_service_url

# 这里是默认的 INSTALLED_APPS，大部分情况下，不需要改动
# 如果你已经了解每个默认 APP 的作用，确实需要去掉某些 APP，请去掉下面的注释，然后修改
INSTALLED_APPS = (
    "bkoauth",
    "bk_dataview",
    # 框架自定义命令
    "blueapps.contrib.bk_commands",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # account app
    "blueapps.account",
    "apigw_manager.apigw",
)

# 这里是默认的中间件，大部分情况下，不需要改动
# 如果你已经了解每个默认 MIDDLEWARE 的作用，确实需要去掉某些 MIDDLEWARE，或者改动先后顺序，请去掉下面的注释，然后修改
# MIDDLEWARE = (
#     # request instance provider
#     'blueapps.middleware.request_provider.RequestProvider',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     # 跨域检测中间件， 默认关闭
#     # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
#     'django.middleware.security.SecurityMiddleware',
#     # 蓝鲸静态资源服务
#     'whitenoise.middleware.WhiteNoiseMiddleware',
#     # Auth middleware
#     'blueapps.account.middlewares.RioLoginRequiredMiddleware',
#     'blueapps.account.middlewares.WeixinLoginRequiredMiddleware',
#     'blueapps.account.middlewares.LoginRequiredMiddleware',
#     # exception middleware
#     'blueapps.core.exceptions.middleware.AppExceptionMiddleware',
#     # django国际化中间件
#     'django.middleware.locale.LocaleMiddleware',
# )

# 自定义中间件
MIDDLEWARE += ()  # noqa

# 默认数据库AUTO字段类型
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# 所有环境的日志级别可以在这里配置
# LOG_LEVEL = 'INFO'

# 调试开关，生产环境请关闭
DEBUG = TEMPLATE_DEBUG = bool(os.getenv("DEBUG", "false").lower() == "true") or ENVIRONMENT == "development"

# 允许访问的域名，默认全部放通
ALLOWED_HOSTS = ["*"]

# 前后端分离开发配置开关，设置为True时允许跨域访问
FRONTEND_BACKEND_SEPARATION = True

# CELERY 并发数，默认为 2，可以通过环境变量或者 Procfile 设置
CELERYD_CONCURRENCY = os.getenv("BK_CELERYD_CONCURRENCY", 2)  # noqa

# load logging settings
LOGGING = get_logging_config_dict(locals())

# 初始化管理员列表，列表中的人员将拥有预发布环境和正式环境的管理员权限
# 注意：请在首次提测和上线前修改，之后的修改将不会生效
INIT_SUPERUSER = []

# 使用mako模板时，默认打开的过滤器：h(过滤html)
MAKO_DEFAULT_FILTERS = ["h"]

# BKUI是否使用了history模式
IS_BKUI_HISTORY_MODE = False

# 国际化配置
LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)  # noqa
USE_I18N = True
USE_L10N = True

SAAS_APP_CODE = ""
SAAS_SECRET_KEY = ""

if ROLE == "web":
    # BKPAAS_APP_ID是PaasV3，APP_ID/APP_CODE是PaasV2
    APP_ID = APP_CODE = get_env_or_raise("BKPAAS_APP_ID", "APP_ID", "APP_CODE", default="bk_monitorv3")
    # BKPAAS_APP_TOKEN是PaasV3，APP_TOKEN/SECRET_KEY是PaasV2
    APP_TOKEN = SECRET_KEY = get_env_or_raise("BKPAAS_APP_SECRET", "APP_TOKEN", "SECRET_KEY", default="")
    BACKEND_APP_CODE = os.getenv("BK_MONITOR_APP_CODE") or "bk_bkmonitorv3"
else:
    APP_ID = APP_CODE = get_env_or_raise("BK_MONITOR_APP_CODE", default="bk_bkmonitorv3")
    APP_TOKEN = SECRET_KEY = get_env_or_raise("BK_MONITOR_APP_SECRET", default="")
    BACKEND_APP_CODE = APP_CODE

# 项目配置
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 访问路径配置
DEFAULT_SITE_URL = f"/{'t' if ENVIRONMENT == 'testing' else 'o'}/{APP_CODE}/" if PAAS_VERSION == "V2" else "/"
SITE_URL = os.getenv("BK_SITE_URL") or os.getenv("BKPAAS_SUB_PATH") or DEFAULT_SITE_URL
FORCE_SCRIPT_NAME = SITE_URL

# 静态资源配置
STATICFILES_DIRS = []
STATIC_VERSION = "1.0"
STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATIC_URL = f"{SITE_URL}static/"
REMOTE_STATIC_URL = f"{STATIC_URL}remote/"

# 文件资源配置
MEDIA_ROOT = os.path.join(BASE_DIR, "USERRES")
MEDIA_URL = "/media/"

# 语言相关
LANGUAGE_CODE = "zh-hans"
DEFAULT_LOCALE = "zh_Hans"
LOCALE_PATHS = (os.path.join(PROJECT_ROOT, "locale"),)
LANGUAGES = (("en", "English"), ("zh-hans", "简体中文"))
LANGUAGE_SESSION_KEY = "blueking_language"
LANGUAGE_COOKIE_NAME = "blueking_language"

# 时区相关
USE_TZ = True
TIME_ZONE = "Asia/Shanghai"
TIMEZONE_SESSION_KEY = "blueking_timezone"

# 平台地址配置
BK_PAAS_HOST = BK_URL = os.getenv("BK_PAAS_HOST") or os.getenv("BK_PAAS_PUBLIC_URL") or os.getenv("BK_PAAS2_URL") or ""
BK_PAAS_INNER_HOST = (
    os.getenv("BK_PAAS_PRIVATE_URL") or os.getenv("BK_PAAS2_INNER_URL") or os.getenv("BK_PAAS_INNER_HOST", BK_PAAS_HOST)
)
BK_COMPONENT_API_URL = os.getenv("BK_COMPONENT_API_URL") or BK_PAAS_INNER_HOST
BK_COMPONENT_API_URL_FRONTEND = os.getenv("BK_COMPONENT_API_URL") or BK_PAAS_HOST
BK_LOGIN_URL = os.getenv("BKPAAS_LOGIN_URL", f"{BK_PAAS_HOST}/login").rstrip("/")
BK_LOGIN_INNER_URL = os.getenv("BK_LOGIN_INNER_URL", f"{BK_PAAS_INNER_HOST}/login").rstrip("/")
ESB_SDK_NAME = "blueking.component"

# 内外差异化配置
if locals()["RUN_VER"] == "open":
    # 从 apigw jwt 中获取 app_code 的 键
    APIGW_APP_CODE_KEY = "bk_app_code"

    # 从 apigw jwt 中获取 username 的 键
    APIGW_USER_USERNAME_KEY = "bk_username"

    # PAASV2对外版不需要bkoauth,DISABLED_APPS加入bkoauth
    INSTALLED_APPS = (
        INSTALLED_APPS[0 : INSTALLED_APPS.index("bkoauth")] + INSTALLED_APPS[INSTALLED_APPS.index("bkoauth") + 1 :]
    )

    # 请求官方 API 默认版本号，可选值为："v2" 或 ""；其中，"v2"表示规范化API，
    # ""表示未规范化API.如果外面设置了该值则使用设置值,否则默认使用v2
    DEFAULT_BK_API_VER = locals().get("DEFAULT_BK_API_VER", "v2")
else:
    # 从 apigw jwt 中获取 app_code 的 键
    APIGW_APP_CODE_KEY = "app_code"

    # 从 apigw jwt 中获取 username 的 键
    APIGW_USER_USERNAME_KEY = "username"

# Target: Observation data collection
# api -> api
# worker -> worker / worker_beat
# web -> web / web_worker / web_beat
SERVICE_NAME = f"{APP_CODE}_{ROLE}"
is_celery = any("celery" in arg for arg in sys.argv)
if is_celery and "worker" in sys.argv and ROLE != "worker":
    SERVICE_NAME = SERVICE_NAME + "_worker"
if is_celery and "beat" in sys.argv:
    SERVICE_NAME = SERVICE_NAME + "_beat"

# space 支持
# 请求参数是否需要注入空间属性
BKM_SPACE_INJECT_REQUEST_ENABLED = False
# 返回参数是否需要注入空间属性
BKM_SPACE_INJECT_RESPONSE_ENABLED = False
# 项目空间API类模块路径
BKM_SPACE_API_CLASS = "bkmonitor.space.space_api.InjectSpaceApi"

#
# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases
#

DATABASES = {}

# auto clean DB connection
DATABASE_CONNECTION_AUTO_CLEAN_INTERVAL = 600
CONN_MAX_AGE = int(os.getenv("CONN_MAX_AGE", 0))

# 是否开启网络设备忽略
USE_ETH_FILTER = True

SYSTEM_NET_GROUP_RT_ID = "system.net"
SYSTEM_NET_GROUP_FIELD_NAME = "device_name"

# 网络设备忽略条件列表
ETH_FILTER_CONDITION_LIST = [
    {"method": "!=", "sql_statement": "lo", "condition_regex": "^(?!lo$)"},
]

# 是否开启磁盘设备忽略
USE_DISK_FILTER = True

# 磁盘设备忽略条件列表
# method字段由SaaS在图形展示、策略配置的sql中作为where字段条件使用，
# 无 method 字段则为后台磁盘事件型告警进行过滤使用
DISK_FILTER_CONDITION_LIST_V1 = [
    {"method": "not like", "sql_statement": "%dev\\/loop%", "file_system_regex": r"/?dev/loop.*"},
    {"method": "not like", "sql_statement": "%dev\\/sr%", "file_system_regex": r"/?dev/sr.*"},
    {"method": "not like", "sql_statement": "%.iso", "file_system_regex": r".*?\.iso$"},
]

# SQL最大查询条数
SQL_MAX_LIMIT = 200000

FILE_SYSTEM_TYPE_RT_ID = "system.disk"
FILE_SYSTEM_TYPE_FIELD_NAME = "device_type"
FILE_SYSTEM_TYPE_IGNORE = ["iso9660", "tmpfs", "udf"]

AUTHENTICATION_BACKENDS = ()

RSA_PRIVATE_KEY = ""
TRANSLATE_SNMP_TRAP_DIMENSIONS = False

# 是否开启默认策略
ENABLE_DEFAULT_STRATEGY = True

CLOSE_EVNET_METRIC_IDS = [
    "bk_monitor.gse_process_event",
    "bk_monitor.gse_custom_event",
    "bk_monitor.os_restart",
    "bk_monitor.oom-gse",
    "bk_monitor.corefile-gse",
    "bk_monitor.agent-gse",
    "bk_monitor.disk-readonly-gse",
]

FAKE_EVENT_AGG_INTERVAL = 60

AES_X_KEY_FIELD = "SECRET_KEY"

# 时序数据精度
POINT_PRECISION = 6

# 需要扫描的视图
ACTIVE_VIEWS = {
    "monitor_adapter": {"healthz": "healthz.views"},
    "monitor_api": {"monitor_api": "monitor_api.views"},
    "monitor_web": {
        "uptime_check": "monitor_web.uptime_check.views",
        "plugin": "monitor_web.plugin.views",
        "collecting": "monitor_web.collecting.views",
        "commons": "monitor_web.commons.views",
        "overview": "monitor_web.overview.views",
        "performance": "monitor_web.performance.views",
        "notice_group": "monitor_web.notice_group.views",
        "strategies": "monitor_web.strategies.views",
        "service_classify": "monitor_web.service_classify.views",
        "shield": "monitor_web.shield.views",
        "alert_events": "monitor_web.alert_events.views",
        "export_import": "monitor_web.export_import.views",
        "config": "monitor_web.config.views",
        "custom_report": "monitor_web.custom_report.views",
        "grafana": "monitor_web.grafana.views",
        "iam": "monitor_web.iam.views",
        "data_explorer": "monitor_web.data_explorer.views",
        "report": "monitor_web.report.views",
        "user_groups": "monitor_web.user_group.views",
        "scene_view": "monitor_web.scene_view.views",
        "search": "monitor_web.search.views",
        "aiops": "monitor_web.aiops.views",
        "as_code": "monitor_web.as_code.views",
        "share": "monitor_web.share.views",
        "promql_import": "monitor_web.promql_import.views",
        "datalink": "monitor_web.datalink.views",
        "new_report": "monitor_web.new_report.views",
        "incident": "monitor_web.incident.views",
        "ai_assistant": "monitor_web.ai_assistant.views",
        "k8s": "monitor_web.k8s.views",
    },
    "weixin": {"mobile_event": "weixin.event.views"},
    "fta_web": {
        "action": "fta_web.action.views",
        "event_plugin": "fta_web.event_plugin.views",
        "alert": "fta_web.alert.views",
        "assign": "fta_web.assign.views",
        "home": "fta_web.home.views",
    },
    "calendar": {"calendar": "calendars.views"},
    "apm_web": {
        "apm_meta": "apm_web.meta.views",
        "apm_trace": "apm_web.trace.views",
        "apm_metric": "apm_web.metric.views",
        "apm_topo": "apm_web.topo.views",
        "apm_service": "apm_web.service.views",
        "apm_log": "apm_web.log.views",
        "apm_db": "apm_web.db.views",
        "apm_event": "apm_web.event.views",
        "apm_profile": "apm_web.profile.views",
        "apm_container": "apm_web.container.views",
    },
}

# 是否使用动态配置特性
if os.getenv("USE_DYNAMIC_SETTINGS", "").lower() in ["0", "false"]:
    USE_DYNAMIC_SETTINGS = False
else:
    USE_DYNAMIC_SETTINGS = True

# 告警通知消息队列配置
ENABLE_MESSAGE_QUEUE = True
MESSAGE_QUEUE_DSN = ""
COMPATIBLE_ALARM_FORMAT = True
ENABLE_PUSH_SHIELDED_ALERT = True

# 采集数据存储天数
TS_DATA_SAVED_DAYS = 30

ENABLE_RESOURCE_DATA_COLLECT = False
RESOURCE_DATA_COLLECT_RATIO = 0

# 告警汇总配置
DIMENSION_COLLECT_THRESHOLD = 2
DIMENSION_COLLECT_WINDOW = 120
MULTI_STRATEGY_COLLECT_THRESHOLD = 3
MULTI_STRATEGY_COLLECT_WINDOW = 120

# 主机监控开关配置
HOST_DISABLE_MONITOR_STATES = ["备用机", "测试中", "故障中"]
HOST_DISABLE_NOTICE_STATES = ["运营中[无告警]", "开发中[无告警]"]

RT_TABLE_PREFIX_VALUE = 0

# 文件存储是否使用CEPH
USE_CEPH = False

# 移动端告警带上移动端访问链接
ALARM_MOBILE_NOTICE_WAY = []
ALARM_MOBILE_URL = ""
PLUGIN_AES_KEY = "bk_monitorv3_enterprise"
ENTERPRISE_CODE = ""
SAAS_VERSION = ""
BACKEND_VERSION = ""

# 后台api默认用户
COMMON_USERNAME = "admin"

# 是否允许所有数据源配置CMDB聚合
IS_ALLOW_ALL_CMDB_LEVEL = False

# 是否开启AIOPS功能，业务ID白名单
AIOPS_BIZ_WHITE_LIST = []

# 是否开启AIOPS根因故障定位功能，业务白名单
AIOPS_INCIDENT_BIZ_WHITE_LIST = []

# 是否由GSE分配dataid，默认是False，由监控自身来负责分配
IS_ASSIGN_DATAID_BY_GSE = True

DEMO_BIZ_ID = 0
DEMO_BIZ_WRITE_PERMISSION = False
DEMO_BIZ_APPLY = ""
DEFAULT_COMMUNITY_BIZ_APPLY = "https://bk.tencent.com/docs/markdown/ZH/QuickStart/7.0/quick-start-v7.0-monitor.md"

# 企业微信群通知webhook_url
WXWORK_BOT_WEBHOOK_URL = ""
WXWORK_BOT_NAME = ""
WXWORK_BOT_SEND_IMAGE = True

# 执行流控的 APP 白名单
THROTTLE_APP_WHITE_LIST = []

# 邮件订阅默认业务ID，当ID为0时关闭邮件订阅
MAIL_REPORT_BIZ = 0
MAIL_REPORT_ALL_BIZ_USERNAMES = []

# 订阅报表运营数据内置指标UID
REPORT_DASHBOARD_UID = "CzhKanwtf"

# celery worker进程数量
CELERY_WORKERS = 0

# 当 ES 存在不合法别名时，是否保留该索引
ES_RETAIN_INVALID_ALIAS = True

# gse进程托管DATA ID
GSE_PROCESS_REPORT_DATAID = 1100008

# 日志采集器所属业务
BKUNIFYLOGBEAT_METRIC_BIZ = 0

# 跳过插件的调试
SKIP_PLUGIN_DEBUG = False

# 统一查询模块配置
UNIFY_QUERY_URL = f"http://{os.getenv('BK_MONITOR_UNIFY_QUERY_HOST')}:{os.getenv('BK_MONITOR_UNIFY_QUERY_PORT')}/"
UNIFY_QUERY_ROUTING_RULES = []

# bk-monitor-worker api 地址
BMW_API_URL = os.getenv("BMW_API_URL", "http://bk-monitor-bk-monitor-worker-web-service:10211")

# bkmonitorbeat 升级支持新版节点ID(bk_cloud_id:ip)的版本
BKMONITORBEAT_SUPPORT_NEW_NODE_ID_VERSION = "1.13.95"

# 事件关联信息截断长度
EVENT_RELATED_INFO_LENGTH = 4096
NOTICE_MESSAGE_MAX_LENGTH = {}

CUSTOM_REPORT_DEFAULT_DATAID = 1100011
MAIL_REPORT_DATA_ID = 1100012
STATISTICS_REPORT_DATA_ID = 1100013

# 策略通知限流
STRATEGY_NOTICE_BUCKET_WINDOW = 60
STRATEGY_NOTICE_BUCKET_SIZE = 100

TRANSFER_CONSUMER_GROUP_ID = "bkmonitorv3_transfer"
TRANSFER_ALLOW_MAX_OFFSET_DELTA = 10000

# 通知配置
ENABLED_NOTICE_WAYS = ["weixin", "mail", "sms", "voice"]

# bk_monitor_proxy 自定义上报服务监听的端口
BK_MONITOR_PROXY_LISTEN_PORT = 10205

# 日期格式
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# 自定义上报服务器IP
CUSTOM_REPORT_DEFAULT_PROXY_IP = []
CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN = []
CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = []  # 当接收端为 k8s 集群部署时，需要配置这个，支持部署在多个集群内
IS_AUTO_DEPLOY_CUSTOM_REPORT_SERVER = True

# 监控内置可观测数据上报Redis Key TODO：联调时赋予默认值，后续更改
BUILTIN_DATA_RT_REDIS_KEY = os.getenv(
    "BKAPP_BUILTIN_DATA_RT_REDIS_KEY", "bkmonitorv3:spaces:built_in_result_table_detail"
)

# eco system
ECOSYSTEM_REPOSITORY_URL = ""
ECOSYSTEM_CODE_ROOT_URL = ""

# APM config
APM_ACCESS_URL = ""
APM_BEST_PRACTICE_URL = ""
APM_METRIC_DESCRIPTION_URL = ""

APM_APDEX_T_VALUE = 800
APM_SAMPLING_PERCENTAGE = 100
APM_APP_QPS = 500

APM_CUSTOM_EVENT_REPORT_CONFIG = {}

# 新建应用的刷新频率，每 2 分钟执行一次拓扑发现
APM_APPLICATION_QUICK_REFRESH_INTERVAL = 2

# 新建应用的创建时间到当前时间的时长范围，单位：分钟
APM_APPLICATION_QUICK_REFRESH_DELTA = 30
# 指标数据源数据发现时需要将周期切分为每批查询几分钟的数据 默认 200s
APM_APPLICATION_METRIC_DISCOVER_SPLIT_DELTA = 200

# 是否下发平台级别api_name构成配置
APM_IS_DISTRIBUTE_PLATFORM_API_NAME_CONFIG = (
    os.getenv("BKAPP_APM_IS_DISTRIBUTE_PLATFORM_API_NAME_CONFIG", "false").lower() == "true"
)

APM_IS_ADD_PLATFORM_METRIC_DIMENSION_CONFIG = (
    os.getenv("BKAPP_APM_IS_ADD_PLATFORM_METRIC_DIMENSION_CONFIG", "false").lower() == "true"
)

APM_APP_DEFAULT_ES_STORAGE_CLUSTER = -1
APM_APP_DEFAULT_ES_RETENTION = 7
APM_APP_DEFAULT_ES_SLICE_LIMIT = 100
APM_APP_DEFAULT_ES_REPLICAS = 0
APM_APP_QUERY_TRACE_MAX_COUNT = 1000
APM_APP_DEFAULT_ES_SHARDS = 3
APM_APP_BKDATA_OPERATOR = ""
APM_APP_BKDATA_MAINTAINER = []
APM_APP_BKDATA_FETCH_STATUS_THRESHOLD = 10
APM_APP_BKDATA_REQUIRED_TEMP_CONVERT_NODE = False
# APM计算平台尾部采样Flow配置
APM_APP_BKDATA_TAIL_SAMPLING_PROJECT_ID = 0
APM_APP_BKDATA_STORAGE_REGISTRY_AREA_CODE = "inland"
# APM计算平台虚拟指标Flow配置
APM_APP_BKDATA_VIRTUAL_METRIC_PROJECT_ID = 0
APM_APP_BKDATA_VIRTUAL_METRIC_STORAGE_EXPIRE = 30
APM_APP_BKDATA_VIRTUAL_METRIC_STORAGE = ""
APM_APP_PRE_CALCULATE_STORAGE_SLICE_SIZE = 100
APM_APP_PRE_CALCULATE_STORAGE_RETENTION = 15
APM_APP_PRE_CALCULATE_STORAGE_SHARDS = 3
APM_TRACE_DIAGRAM_CONFIG = {}
APM_DORIS_STORAGE_CONFIG = {}
# {2:["foo", "bar"], 3:["baz"]}
APM_PROFILING_ENABLED_APPS = {}
# dis/enable profiling for all apps
APM_PROFILING_ENABLED = False
APM_EBPF_ENABLED = False
APM_TRPC_ENABLED = False
# {2:["app1", "app2"], 3:["app_name"]}
APM_TRPC_APPS = {}
APM_BMW_DEPLOY_BIZ_ID = 0
# 在列表中业务，才会创建虚拟指标， [2]
APM_CREATE_VIRTUAL_METRIC_ENABLED_BK_BIZ_ID = []
APM_BMW_TASK_QUEUES = []
# APM V4 链路 metric data status 配置
APM_V4_METRIC_DATA_STATUS_CONFIG = {}
# APM 自定义指标 SDK 映射配置
APM_CUSTOM_METRIC_SDK_MAPPING_CONFIG = {}
# UnifyQuery查询表映射配置
UNIFY_QUERY_TABLE_MAPPING_CONFIG = {}
# 拓扑发现允许的最大 Span 数量(预估值)
PER_ROUND_SPAN_MAX_SIZE = 1000
# profiling 汇聚方法映射配置
APM_PROFILING_AGG_METHOD_MAPPING = {
    "HEAP-SPACE": "AVG",
    "WALL-TIME": "SUM",
    "ALLOC-SPACE": "AVG",
    "ALLOC_SPACE": "AVG",
    "CPU-TIME": "SUM",
    "EXCEPTION-SAMPLES": "SUM",
    "CPU": "SUM",
    "INUSE_SPACE": "AVG",
    "DELAY": "AVG",
    "GOROUTINE": "AVG",
}
# bk.data.token 的salt值
BK_DATA_TOKEN_SALT = "bk"
BK_DATA_AES_IV = b"bkbkbkbkbkbkbkbk"

# RUM config
RUM_ENABLED = False
RUM_ACCESS_URL = ""

# ==============================================================================
# elasticsearch for fta
# 自愈的 ES 连接信息
# ==============================================================================
# FTA ES7 config
FTA_ES7_HOST = os.getenv("BKAPP_FTA_ES7_HOST", os.getenv("BK_FTA_ES7_HOST", "es7.service.consul"))
FTA_ES7_REST_PORT = os.getenv("BKAPP_FTA_ES7_REST_PORT", os.getenv("BK_FTA_ES7_REST_PORT", "9200"))
FTA_ES7_TRANSPORT_PORT = os.getenv("BKAPP_FTA_ES7_TRANSPORT_PORT", os.getenv("BK_FTA_ES7_TRANSPORT_PORT", "9301"))
FTA_ES7_USER = os.getenv("BKAPP_FTA_ES7_USER", os.getenv("BK_FTA_ES7_USER", ""))
FTA_ES7_PASSWORD = os.getenv("BKAPP_FTA_ES7_PASSWORD", os.getenv("BK_FTA_ES7_PASSWORD", ""))
ELASTICSEARCH_DSL = {
    "default": {
        "hosts": FTA_ES7_HOST,
        "port": FTA_ES7_REST_PORT,
        "http_auth": (FTA_ES7_USER, FTA_ES7_PASSWORD) if FTA_ES7_USER and FTA_ES7_PASSWORD else None,
    },
}

# BKSSM 配置
BK_SSM_HOST = os.environ.get("BKAPP_BK_SSM_HOST", os.getenv("BK_SSM_HOST", "bkssm.service.consul"))
BK_SSM_PORT = os.environ.get("BKAPP_BK_SSM_PORT", os.getenv("BK_SSM_PORT", "5000"))
# BCS API Gateway 配置
BCS_API_GATEWAY_TOKEN = os.environ.get("BKAPP_BCS_API_GATEWAY_TOKEN", os.getenv("BK_BCS_API_GATEWAY_TOKEN", None))
BCS_API_GATEWAY_HOST = os.environ.get("BKAPP_BCS_API_GATEWAY_HOST", os.getenv("BK_BCS_API_GATEWAY_HOST", None))
BCS_API_GATEWAY_PORT = os.environ.get("BKAPP_BCS_API_GATEWAY_PORT", os.getenv("BK_BCS_API_GATEWAY_PORT", "443"))
BCS_API_GATEWAY_SCHEMA = os.getenv("BKAPP_BCS_API_GATEWAY_SCHEMA", os.getenv("BK_BCS_API_GATEWAY_SCHEMA", "https"))
BCS_DEBUG_STORAGE_ADAPTER = os.getenv(
    "BKAPP_BCS_DEBUG_STORAGE_ADAPTER", os.getenv("BK_BCS_DEBUG_STORAGE_ADAPTER", None)
)

# BCS 集群列表数据获取来源 bcs-cc 或 cluster-manager
BCS_CLUSTER_SOURCE = "cluster-manager"

# 仅用于测试联调环境映射特定集群到业务
DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID = os.getenv(
    "BKAPP_DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID",
    os.getenv("BK_DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID", ""),
)

# UNIFY-QUERY支持bkdata查询灰度业务列表
BKDATA_USE_UNIFY_QUERY_GRAY_BIZ_LIST = []

# BCS CC
BCS_CC_API_URL = os.getenv("BKAPP_BCS_CC_API_URL", None)
# bcs storage接口limit的大小
BCS_STORAGE_PAGE_SIZE = os.getenv("BKAPP_BCS_STORAGE_PAGE_SIZE", 5000)

# BCS资源同步并发数
BCS_SYNC_SYNC_CONCURRENCY = os.getenv("BKAPP_BCS_SYNC_SYNC_CONCURRENCY", 20)

# 所有bcs指标都将基于该信息进行label复制
BCS_METRICS_LABEL_PREFIX = {"*": "kubernetes", "node_": "kubernetes", "container_": "kubernetes", "kube_": "kubernetes"}

# 容器化共存适配，添加API访问子路径
API_SUB_PATH = os.getenv("BKAPP_API_SUB_PATH", os.getenv("API_SUB_PATH", ""))

# 默认transfer集群
DEFAULT_TRANSFER_CLUSTER_ID = "default"
DEFAULT_TRANSFER_CLUSTER_ID_FOR_K8S = "default"

# 内置的transfer集群ID，给到用户选择链路的时候，不需要在页面上展示（多个以逗号分隔）
TRANSFER_BUILTIN_CLUSTER_ID = ""

# 是否开启数据平台指标缓存
ENABLE_BKDATA_METRIC_CACHE = True

# influxdb proxy使用的默认集群名
INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME = "default"
INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME_FOR_K8S = "default"

# 单台机器Ping采集目标数量限制
PING_SERVER_TARGET_NUMBER_LIMIT = 6000

# 业务黑名单
DISABLE_BIZ_ID = []

# 是否开启聚合网关上报
METRIC_AGG_GATEWAY_URL = os.getenv("BKAPP_METRIC_AGG_GATEWAY_URL", "")
METRIC_AGG_GATEWAY_UDP_URL = os.getenv("BKAPP_METRIC_AGG_GATEWAY_UDP_URL", METRIC_AGG_GATEWAY_URL)

# 网关API域名
APIGW_BASE_URL = os.getenv("BKAPP_APIGW_BASE_URL", "")

# 是否允许一键拉群
ENABLE_CREATE_CHAT_GROUP = False

# 蓝鲸插件调用app信息
BK_PLUGIN_APP_INFO = {}

# 重新获取关联信息时间间隔
DELAY_TO_GET_RELATED_INFO_INTERVAL = 500

GRAFANA_URL = os.getenv("BKAPP_GRAFANA_URL", "http://grafana.bkmonitorv3.service.consul:3000")
GRAFANA_ADMIN_USERNAME = os.getenv("BKAPP_GRAFANA_ADMIN_USERNAME", "admin")

# 降噪时间窗口
NOISE_REDUCE_TIMEDELTA = 5

# 故障自愈是否已完成迁移
IS_FTA_MIGRATED = False

# 已经迁移完成的业务
FTA_MIGRATE_BIZS = []

# 指标上报默认任务标志
DEFAULT_METRIC_PUSH_JOB = "SLI"
# 运营指标上报任务标志
OPERATION_STATISTICS_METRIC_PUSH_JOB = "Operation"

# 是否启用计算平台处理influxdb降精度流程
ENABLE_METADATA_DOWNSAMPLE_BY_BKDATA = False
# 是否启用 unify-query 查询计算平台降精度数据
ENABLE_UNIFY_QUERY_DOWNSAMPLE_BY_BKDATA = False

WECOM_ROBOT_BIZ_WHITE_LIST = []
WECOM_ROBOT_ACCOUNT = {}
IS_WECOM_ROBOT_ENABLED = False
MD_SUPPORTED_NOTICE_WAYS = ["wxwork-bot"]

WECOM_APP_ACCOUNT = {}

FTA_ES_SLICE_SIZE = 50
FTA_ES_RETENTION = 365

# 短信通知最大长度设置
SMS_CONTENT_LENGTH = 0
WECOM_ROBOT_CONTENT_LENGTH = 0

# 二次确认
DOUBLE_CHECK_SUM_STRATEGY_IDS = os.environ.get("DOUBLE_CHECK_SUM_STRATEGY_IDS", [])

# BCS 集群配置来源标签
BCS_CLUSTER_BK_ENV_LABEL = os.environ.get("BCS_CLUSTER_BK_ENV_LABEL", "")

ALARM_DISABLE_STRATEGY_RULES = []
OPTZ_FAKE_EVENT_BIZ_IDS = []

# access模块数据拉取延迟时间
ACCESS_DATA_TIME_DELAY = 10

# access模块延迟上报
ACCESS_LATENCY_INTERVAL_FACTOR = 1
ACCESS_LATENCY_THRESHOLD_CONSTANT = 180

# kafka是否自动提交配置
KAFKA_AUTO_COMMIT = True

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

DATABASE_ROUTERS = ["bk_dataview.router.DBRouter"]

# 是否开启表访问次数统计
if os.getenv("ENABLE_TABLE_VISIT_COUNT", "false").lower() == "true":
    DATABASE_ROUTERS.append("bkmonitor.db_routers.TableVisitCountRouter")

# 数据库配置
(
    BACKEND_MYSQL_NAME,
    BACKEND_MYSQL_HOST,
    BACKEND_MYSQL_PORT,
    BACKEND_MYSQL_USER,
    BACKEND_MYSQL_PASSWORD,
) = get_backend_mysql_settings()
SAAS_MYSQL_NAME, SAAS_MYSQL_HOST, SAAS_MYSQL_PORT, SAAS_MYSQL_USER, SAAS_MYSQL_PASSWORD = get_saas_mysql_settings()

# 判断前后台DB配置是否相同，如果不同则需要使用路由
if SAAS_MYSQL_NAME != BACKEND_MYSQL_NAME or SAAS_MYSQL_HOST != BACKEND_MYSQL_HOST:
    DATABASE_ROUTERS.append("bkmonitor.db_routers.BackendRouter")
    BACKEND_DATABASE_NAME = "monitor_api"
    MIGRATE_MONITOR_API = True
else:
    BACKEND_DATABASE_NAME = "default"
    MIGRATE_MONITOR_API = False

(
    GRAFANA_MYSQL_NAME,
    GRAFANA_MYSQL_HOST,
    GRAFANA_MYSQL_PORT,
    GRAFANA_MYSQL_USER,
    GRAFANA_MYSQL_PASSWORD,
) = get_grafana_mysql_settings()

try:
    # 判断 dj_db_conn_pool 是否存在
    importlib.import_module("dj_db_conn_pool")

    assert ROLE == "web"
    default_db_engine = "dj_db_conn_pool.backends.mysql"
except (AssertionError, ModuleNotFoundError):
    default_db_engine = "django.db.backends.mysql"

DATABASES = {
    "default": {
        "ENGINE": default_db_engine,
        "NAME": SAAS_MYSQL_NAME,
        "USER": SAAS_MYSQL_USER,
        "PASSWORD": SAAS_MYSQL_PASSWORD,
        "HOST": SAAS_MYSQL_HOST,
        "PORT": SAAS_MYSQL_PORT,
        "POOL_OPTIONS": {
            "POOL_SIZE": 5,
            "MAX_OVERFLOW": -1,
            "RECYCLE": 600,
        },
        "OPTIONS": {"charset": "utf8mb4"},
    },
    "monitor_api": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": BACKEND_MYSQL_NAME,
        "USER": BACKEND_MYSQL_USER,
        "PASSWORD": BACKEND_MYSQL_PASSWORD,
        "HOST": BACKEND_MYSQL_HOST,
        "PORT": BACKEND_MYSQL_PORT,
        "OPTIONS": {"charset": "utf8mb4"},
    },
    "bk_dataview": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": GRAFANA_MYSQL_NAME,
        "USER": GRAFANA_MYSQL_USER or BACKEND_MYSQL_USER,
        "PASSWORD": GRAFANA_MYSQL_PASSWORD or BACKEND_MYSQL_PASSWORD,
        "HOST": GRAFANA_MYSQL_HOST or BACKEND_MYSQL_HOST,
        "PORT": GRAFANA_MYSQL_PORT or BACKEND_MYSQL_PORT,
        "OPTIONS": {"charset": "utf8mb4"},
    },
}

# ES7 config
ES7_HOST, ES7_REST_PORT, ES7_TRANSPORT_PORT, ES7_USER, ES7_PASSWORD = get_es7_settings(fta=True)
ELASTICSEARCH_DSL = {
    "default": {
        "hosts": ES7_HOST,
        "port": ES7_REST_PORT,
        "http_auth": (ES7_USER, ES7_PASSWORD) if ES7_USER and ES7_PASSWORD else None,
    },
}

# Kafka config
KAFKA_HOST = [os.environ.get("BK_MONITOR_KAFKA_HOST", "kafka.service.consul")]
KAFKA_PORT = int(os.environ.get("BK_MONITOR_KAFKA_PORT", 9092))
# alert 模块告警专属
ALERT_KAFKA_HOST = [os.environ.get("BK_MONITOR_ALERT_KAFKA_HOST", KAFKA_HOST[0])]
ALERT_KAFKA_PORT = int(os.environ.get("BK_MONITOR_ALERT_KAFKA_PORT", KAFKA_PORT))
KAFKA_CONSUMER_GROUP = f"{PLATFORM.lower()}-bkmonitorv3-alert-{ENVIRONMENT.lower()}"
KAFKA_CONSUMER_GROUP = os.environ.get("BK_MONITOR_KAFKA_CONSUMER_GROUP", KAFKA_CONSUMER_GROUP)
COMMON_KAFKA_CLUSTER_INDEX = 0
# for stage
BKAPP_KAFKA_DOMAIN = os.environ.get("BKAPP_KAFKA_DOMAIN", "")

# 日志相关配置
if ENVIRONMENT == "development":
    LOG_PATH = os.path.join(BASE_DIR, "logs")
else:
    LOG_PATH = (
        os.getenv("BKPAAS_APP_LOG_PATH")
        or os.getenv("BK_LOG_DIR")
        or os.getenv("LOGS_PATH")
        or (f"{os.getenv('BK_HOME')}/logs" if os.getenv("BK_HOME") else "" or "/data/app/logs")
    )

    if ROLE in ["worker", "api"]:
        LOG_PATH = os.path.join(LOG_PATH, "bkmonitorv3")
    else:
        LOG_PATH = os.path.join(LOG_PATH, APP_CODE)

    LOG_PATH = os.getenv("BKAPPS_BKMONITOR_LOG_PATH", LOG_PATH)

LOG_FILE_PREFIX = os.getenv("BKPAAS_PROCESS_TYPE", "")
if LOG_FILE_PREFIX:
    LOG_FILE_PREFIX = f"{LOG_FILE_PREFIX}--log--"

if not os.path.exists(LOG_PATH):
    try:
        os.makedirs(LOG_PATH)
    except Exception:
        pass

# 单独配置部分模块日志级别
LOG_LEVEL_MAP = {
    "iam": "ERROR",
    "bk_dataview": "ERROR",
    "elasticsearch": "WARNING",
    "kafka": "WARNING",
}

warnings.filterwarnings(
    "ignore", r"DateTimeField .* received a naive datetime", RuntimeWarning, r"django\.db\.models\.fields"
)

#
# 数据平台接入配置
#
IS_ACCESS_BK_DATA = os.getenv("BKAPP_IS_ACCESS_BK_DATA", "") == "true"  # 是否接入计算平台
IS_ENABLE_VIEW_CMDB_LEVEL = False  # 是否开启前端视图部分的CMDB预聚合
IS_MIGRATE_AIOPS_STRATEGY = False

# 数据接入相关
BK_DATA_PROJECT_ID = 1  # 监控平台数据接入到计算平台 & 异常检测模型所在项目
BK_DATA_BK_BIZ_ID = 2  # 监控平台数据接入到计算平台的指定业务下
BK_DATA_PROJECT_MAINTAINER = "admin"  # 计算平台项目的维护人员
BK_DATA_RT_ID_PREFIX = ""  # 计算平台的表名前缀
BK_DATA_DATA_EXPIRES_DAYS = 30  # 接入到计算平台后，数据保留天数
BK_DATA_DATA_EXPIRES_DAYS_BY_HDFS = 180  # 接入到计算平台后，存储到HDFS时数据保留天数
BK_DATA_MYSQL_STORAGE_CLUSTER_NAME = "jungle_alert"  # 监控专属tspider存储集群名称
BK_DATA_MYSQL_STORAGE_CLUSTER_TYPE = "mysql_storage"  # 监控SQL类存储集群类型
BK_DATA_HDFS_STORAGE_CLUSTER_NAME = "hdfsOnline4"  # 监控专属HDFS存储集群名称
BK_DATA_DRUID_STORAGE_CLUSTER_NAME = "monitor"  # 监控专属druid存储集群名称
BK_DATA_KAFKA_BROKER_URL = "127.0.0.1:9092"
BK_DATA_INTELLIGENT_DETECT_DELAY_WINDOW = 5
BK_DATA_FLOW_CLUSTER_GROUP = "default_inland"
BK_DATA_REALTIME_NODE_WAIT_TIME = 10
# 监控使用计算平台 flow 的项目 ID
BK_DATA_RECORD_RULE_PROJECT_ID = 1

# 场景服务ID
# 单指标异常检测
BK_DATA_SCENE_ID_INTELLIGENT_DETECTION = 5
# 时序预测
BK_DATA_SCENE_ID_TIME_SERIES_FORECASTING = 9
# 离群检测
BK_DATA_SCENE_ID_ABNORMAL_CLUSTER = 33
# 多指标异常检测
BK_DATA_SCENE_ID_MULTIVARIATE_ANOMALY_DETECTION = 15
# 指标推荐
BK_DATA_SCENE_ID_METRIC_RECOMMENDATION = 17
# 主机异常检测
BK_DATA_SCENE_ID_HOST_ANOMALY_DETECTION = 15

# ai设置默认方案
# 单指标异常检测
BK_DATA_PLAN_ID_INTELLIGENT_DETECTION = 87
# 多指标异常检测
BK_DATA_PLAN_ID_MULTIVARIATE_ANOMALY_DETECTION = 155
# 指标推荐
BK_DATA_PLAN_ID_METRIC_RECOMMENDATION = 180
# 主机异常检测
BK_DATA_PLAN_ID_HOST_ANOMALY_DETECTION = 287

BK_DATA_MULTIVARIATE_HOST_RT_ID = os.getenv(
    "BK_DATA_MULTIVARIATE_HOST_RT_ID", f"2_{BKAPP_DEPLOY_PLATFORM}_host_multivariate"
)
BK_DATA_MULTIVARIATE_HOST_MIDDLE_SUFFIX = "multivariate_detection"

# 机器人默认跳转链接列表
BK_DATA_ROBOT_LINK_LIST = os.getenv(
    "BK_DATA_ROBOT_LINK_LIST",
    [
        {
            "link": "https://bk.tencent.com/docs/document/7.0/248/40001",
            "name": "产品白皮书",
            "icon_name": "icon-bangzhuzhongxin",
        }
    ],
)

# 维度下钻API Serving所用结果表ID
BK_DATA_DIMENSION_DRILL_PROCESSING_ID = "multidimension_drill"

# 指标推荐API Serving所用结果表ID前缀
BK_DATA_METRIC_RECOMMEND_PROCESSING_ID_PREFIX = "metric_recommendation"

BK_DATA_METRIC_RECOMMEND_SOURCE_PROCESSING_ID = "ieod_system_multivariate_delay"

# 故障增删事件同步配置
BK_DATA_AIOPS_INCIDENT_BROKER_URL = os.getenv(
    "BK_DATA_AIOPS_INCIDENT_BROKER_URL", "amqp://127.0.0.1:5672/aiops_incident"
)
BK_DATA_AIOPS_INCIDENT_SYNC_QUEUE = os.getenv("BK_DATA_AIOPS_INCIDENT_SYNC_QUEUE", "aiops_incident")

# 表后缀(字母或数字([A-Za-z0-9]), 不能有下划线"_", 且最好不超过10个字符)
BK_DATA_RAW_TABLE_SUFFIX = "raw"  # 数据接入
BK_DATA_CMDB_FULL_TABLE_SUFFIX = "full"  # 补充cmdb节点信息后的表后缀
BK_DATA_CMDB_SPLIT_TABLE_SUFFIX = "cmdb"  # 补充表拆分后的表后缀

#
# Csrf_cookie
#
CSRF_COOKIE_DOMAIN = None
CSRF_COOKIE_PATH = SITE_URL

#
# Session
#
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7

#
# Cache
#
CACHE_CC_TIMEOUT = 60 * 10
CACHE_BIZ_TIMEOUT = 60 * 10
CACHE_HOST_TIMEOUT = 60 * 2
CACHE_DATA_TIMEOUT = 60 * 2
CACHE_OVERVIEW_TIMEOUT = 60 * 2
CACHE_HOME_TIMEOUT = 60 * 10
CACHE_USER_TIMEOUT = 60 * 60

# SaaS访问读写权限
ROLE_WRITE_PERMISSION = "w"
ROLE_READ_PERMISSION = "r"

# GSE SERVER IP 列表，以逗号分隔
GSE_SERVER_LAN_IP = os.getenv("BKAPP_GSE_SERVER_LAN_IP", "$GSE_IP")
GSE_SERVER_PORT = os.getenv("BKAPP_GSE_SERVER_PORT", "58629")

DEFAULT_BK_API_VER = locals().get("DEFAULT_BK_API_VER", "v2")

# 用户反馈地址
CE_URL = os.getenv("BKAPP_CE_URL", "https://bk.tencent.com/s-mart/community")

# 进程端口结果表名称
PROC_PORT_TABLE_NAME = "system_proc_port"
# 进程端口指标字段名称
PROC_PORT_METRIC_NAME = "proc_exists"
# 新版主机默认维度
NEW_DEFAULT_HOST_DIMENSIONS = ["bk_target_ip", "bk_cloud_id"]

# 不同系统类型的信息
# windows系统配置
WINDOWS_SCRIPT_EXT = "bat"
WINDOWS_JOB_EXECUTE_ACCOUNT = "system"
WINDOWS_GSE_AGENT_PATH = "C:\\gse\\"
WINDOWS_FILE_DOWNLOAD_PATH = ntpath.join(WINDOWS_GSE_AGENT_PATH, "download")
WINDOWS_UPTIME_CHECK_COLLECTOR_CONF_NAME = "uptimecheckbeat.conf"
WINDOWS_GSE_AGENT_IPC_PATH = "127.0.0.1:47000"

# linux系统配置
LINUX_SCRIPT_EXT = "sh"
LINUX_JOB_EXECUTE_ACCOUNT = "root"
LINUX_FILE_DOWNLOAD_PATH = "/tmp/bkdata/download/"
LINUX_GSE_AGENT_PATH = "/usr/local/gse/"
LINUX_PLUGIN_DATA_PATH = "/var/lib/gse"
LINUX_PLUGIN_PID_PATH = "/var/run/gse"
LINUX_PLUGIN_LOG_PATH = "/var/log/gse"
LINUX_UPTIME_CHECK_COLLECTOR_CONF_NAME = "uptimecheckbeat.conf"
LINUX_GSE_AGENT_IPC_PATH = "/var/run/ipc.state.report"

# 采集配置升级，使用订阅更新模式的业务列表
COLLECTING_UPGRADE_WITH_UPDATE_BIZ = []

# aix系统配置
AIX_SCRIPT_EXT = "sh"
AIX_JOB_EXECUTE_ACCOUNT = "root"
AIX_FILE_DOWNLOAD_PATH = "/tmp/bkdata/download/"

# cmdb 开发商ID
BK_SUPPLIER_ACCOUNT = os.getenv("BKAPP_BK_SUPPLIER_ACCOUNT", "0")

# 全局系统开关
OS_GLOBAL_SWITCH = ["linux", "windows", "linux_aarch64"]

# --角色管理--

# 告警通知角色
NOTIRY_MAN_DICT = TranslateDict(
    {
        "bk_biz_maintainer": _("运维人员"),
        "bk_biz_productor": _("产品人员"),
        "bk_biz_tester": _("测试人员"),
        "bk_biz_developer": _("开发人员"),
        "operator": _("主负责人"),
        "bk_bak_operator": _("备份负责人"),
    }
)

DEFAULT_ROLE_PERMISSIONS = {
    "bk_biz_maintainer": ROLE_WRITE_PERMISSION,  # noqa
    "bk_biz_productor": ROLE_READ_PERMISSION,  # noqa
    "bk_biz_developer": ROLE_READ_PERMISSION,  # noqa
    "bk_biz_tester": ROLE_READ_PERMISSION,  # noqa
}

# 预设dataid
# 注意：所有的DATAID配置都必须是以【_DATAID】结尾，否则会导致元数据模块无法识别
SNAPSHOT_DATAID = 1001
MYSQL_METRIC_DATAID = 1002
REDIS_METRIC_DATAID = 1003
APACHE_METRIC_DATAID = 1004
NGINX_METRIC_DATAID = 1005
TOMCAT_METRIC_DATAID = 1006
PROCESS_PERF_DATAID = 1007
PROCESS_PORT_DATAID = 1013

# 拨测预设dataid
UPTIMECHECK_HEARTBEAT_DATAID = 1008
UPTIMECHECK_TCP_DATAID = 1009
UPTIMECHECK_UDP_DATAID = 1010
UPTIMECHECK_HTTP_DATAID = 1011
UPTIMECHECK_ICMP_DATAID = 1100003

# ping server dataid
PING_SERVER_DATAID = 1100005

GSE_CUSTOM_EVENT_DATAID = 1100000

# 拨测任务默认最大请求超时设置(ms)
UPTIMECHECK_DEFAULT_MAX_TIMEOUT = 15000

HEADER_FOOTER_CONFIG = {
    "header": [{"zh-cn": "监控平台 | 腾讯蓝鲸智云", "en": "Monitor | Tencent BlueKing"}],
    "footer": [
        {
            "zh-cn": [
                {
                    "text": "技术支持",
                    "link": "https://wpa1.qq.com/KziXGWJs?_type=wpa&qidian=true",
                },
                {"text": "社区论坛", "link": "https://bk.tencent.com/s-mart/community/"},
                {"text": "产品官网", "link": "https://bk.tencent.com/index/"},
            ],
            "en": [
                {
                    "text": "Support",
                    "link": "http://wpa.b.qq.com/cgi/wpa.php?ln=1&key=XzgwMDgwMjAwMV80NDMwOTZfODAwODAyMDAxXzJf",
                },
                {"text": "Forum", "link": "https://bk.tencent.com/s-mart/community"},
                {"text": "Official", "link": "https://bk.tencent.com/"},
            ],
        }
    ],
    "copyright": "Copyright © 2012-{current_year} Tencent BlueKing. All Rights Reserved. ",
}

# 数据平台数据查询TOKEN
BKDATA_DATA_TOKEN = os.getenv("BKAPP_BKDATA_DATA_TOKEN", "")

# 权限中心 SaaS host
BK_IAM_APP_CODE = os.getenv("BK_IAM_V3_APP_CODE", "bk_iam")
BK_IAM_SAAS_HOST = os.getenv("BK_IAM_SITE_URL") or get_service_url(BK_IAM_APP_CODE, bk_paas_host=BK_PAAS_HOST)

# 文档中心地址
BK_DOCS_SITE_URL = os.getenv("BK_DOCS_SITE_URL") or get_service_url("bk_docs_center", bk_paas_host=BK_PAAS_HOST)
if not BK_DOCS_SITE_URL.endswith("/"):
    BK_DOCS_SITE_URL += "/"

# 文档中心地址
DOC_HOST = "https://bk.tencent.com/docs/"

# 版本差异变量
if PLATFORM == "community" and not os.getenv("BK_DOCS_URL_PREFIX"):
    BK_DOCS_SITE_URL = DOC_HOST

CMDB_USE_APIGW = os.getenv("BKAPP_CMDB_USE_APIGW", "false").lower() == "true"
CMDB_API_BASE_URL = os.getenv("BKAPP_CMDB_API_BASE_URL", "")
CMSI_API_BASE_URL = os.getenv("BKAPP_CMSI_API_BASE_URL", "")
JOB_USE_APIGW = os.getenv("BKAPP_JOB_USE_APIGW", "false").lower() == "true"
JOB_API_BASE_URL = os.getenv("BKAPP_JOB_API_BASE_URL", "")
# monitor api base url:
MONITOR_API_BASE_URL = os.getenv("BKAPP_MONITOR_API_BASE_URL", "")
NEW_MONITOR_API_BASE_URL = os.getenv("BKAPP_NEW_MONITOR_API_BASE_URL", "")
# bkdata api base url
BKDATA_API_BASE_URL = os.getenv("BKAPP_BKDATA_API_BASE_URL", "")
# bkdata api only for query data (not required)
BKDATA_QUERY_API_BASE_URL = os.getenv("BKAPP_BKDATA_QUERY_API_BASE_URL", "")
# bkdata api only for query profiling data (not required)
BKDATA_PROFILE_QUERY_API_BASE_URL = os.getenv("BKAPP_BKDATA_PROFILE_QUERY_API_BASE_URL", "")
BKLOGSEARCH_API_BASE_URL = os.getenv("BKAPP_BKLOGSEARCH_API_BASE_URL", "")
# 通过 apigw 访问日志平台 api 的地址
BKLOGSEARCH_API_GW_BASE_URL = os.getenv("BKAPP_BKLOGSEARCH_API_GW_BASE_URL", "")
BKNODEMAN_API_BASE_URL = os.getenv("BKAPP_BKNODEMAN_API_BASE_URL", "")
BKDOCS_API_BASE_URL = os.getenv("BKAPP_BKDOCS_API_BASE_URL", "")
DEVOPS_API_BASE_URL = os.getenv("BKAPP_DEVOPS_API_BASE_URL", "")
# 用户信息
BK_USERINFO_API_BASE_URL = os.getenv("BKAPP_USERINFO_API_BASE_URL", "")
BK_USER_API_BASE_URL = os.getenv("BKAPP_USER_API_BASE_URL", "")
MONITOR_WORKER_API_BASE_URL = os.getenv("BKAPP_MONITOR_WORKER_API_BASE_URL", "")
APIGATEWAY_API_BASE_URL = os.getenv("BKAPP_APIGATEWAY_API_BASE_URL", "")
BK_IAM_APIGATEWAY_URL = os.getenv("BKAPP_IAM_API_BASE_URL") or f"{BK_COMPONENT_API_URL}/api/bk-iam/prod/"

# 以下是bkchat的apigw
BKCHAT_API_BASE_URL = os.getenv("BKAPP_BKCHAT_API_BASE_URL", "")
BKCHAT_MANAGE_URL = os.getenv("BKAPP_BKCHAT_MANAGE_URL", "")

# 以下专门用来测试bkchat
BKCHAT_APP_CODE = os.getenv("BKCHAT_APP_CODE", os.getenv("BKHCAT_APP_CODE", ""))
BKCHAT_APP_SECRET = os.getenv("BKCHAT_APP_SECRET", os.getenv("BKHCAT_APP_SECRET", ""))
BKCHAT_BIZ_ID = os.getenv("BKCHAT_BIZ_ID", "2")

# aidev的apigw地址
AIDEV_API_BASE_URL = os.getenv("BKAPP_AIDEV_API_BASE_URL", "")

BK_NODEMAN_HOST = AGENT_SETUP_URL = os.getenv("BK_NODEMAN_SITE_URL") or os.getenv(
    "BKAPP_NODEMAN_OUTER_HOST", get_service_url("bk_nodeman", bk_paas_host=BK_PAAS_HOST)
)
BK_NODEMAN_INNER_HOST = os.getenv("BKAPP_NODEMAN_HOST") or os.getenv(
    "BKAPP_NODEMAN_INNER_HOST", "http://nodeman.bknodeman.service.consul"
)

BKLOGSEARCH_HOST = os.getenv("BK_LOG_SEARCH_SITE_URL") or get_service_url("bk_log_search", bk_paas_host=BK_PAAS_HOST)
BKLOGSEARCH_INNER_HOST = os.getenv("BK_LOG_SEARCH_INNER_HOST") or BKLOGSEARCH_HOST

# 作业平台url
JOB_URL = BK_PAAS_HOST.replace("paas", "job")
JOB_URL = os.getenv("BK_JOB_SITE_URL") or os.getenv("BK_JOB_HOST", JOB_URL)

# 配置平台URL
BK_CC_URL = BK_PAAS_HOST.replace("paas", "cmdb")
BK_CC_URL = os.getenv("BK_CC_SITE_URL") or os.getenv("BK_CC_HOST", BK_CC_URL)

BK_ITSM_HOST = os.getenv("BK_ITSM_HOST", f"{BK_PAAS_HOST}/o/bk_itsm/")
BK_SOPS_HOST = os.getenv("BK_SOPS_URL", f"{BK_PAAS_HOST}/o/bk_sops/")
# todo  新增BK_CI_URL 需要在bin/environ.sh 模板中定义
BK_BCS_HOST = os.getenv("BK_BCS_URL", f"{BK_PAAS_HOST}/o/bk_bcs_app/")
BK_CI_URL = os.getenv("BK_CI_URL") or os.getenv("BKAPP_BK_CI_URL", "")
# 蓝盾网关接口请求头应用鉴权信息，有此配置，认证请求头优先使用此配置
BKCI_APP_CODE = os.getenv("BKCI_APP_CODE")
BKCI_APP_SECRET = os.getenv("BKCI_APP_SECRET")
BK_MONITOR_HOST = os.getenv("BK_MONITOR_HOST", "{}/o/bk_monitorv3/".format(BK_PAAS_HOST.rstrip("/")))
ACTION_DETAIL_URL = f"{BK_MONITOR_HOST}?bizId={{bk_biz_id}}/#/event-center/action-detail/{{action_id}}"
EVENT_CENTER_URL = urljoin(
    BK_MONITOR_HOST, "?bizId={bk_biz_id}#/event-center?queryString=action_id%20%3A%20{collect_id}"
)
MAIL_REPORT_URL = urljoin(BK_MONITOR_HOST, "#/email-subscriptions")

# IAM
BK_IAM_SYSTEM_ID = "bk_monitorv3"
BK_IAM_SYSTEM_NAME = _("监控平台")

BK_IAM_MIGRATION_APP_NAME = "bkmonitor"
BK_IAM_RESOURCE_API_HOST = os.getenv("BKAPP_IAM_RESOURCE_API_HOST", f"{BK_PAAS_INNER_HOST}{SITE_URL}")

# 是否跳过 iam migrate
BK_IAM_SKIP = os.getenv("BK_IAM_SKIP", "false").lower() == "true"

# 采集配置文件参数最大值(M)
COLLECTING_CONFIG_FILE_MAXSIZE = 2

# 平台管理员
GSE_MANAGERS = []
MONITOR_MANAGERS = []
OFFICIAL_PLUGINS_MANAGERS = []

# 跳过权限中心
SKIP_IAM_PERMISSION_CHECK = False

# 聚合网关默认业务ID
AGGREGATION_BIZ_ID = int(os.getenv("BKAPP_AGGREGATION_BIZ_ID", 2))

# 是否将监控事件推送给自愈去消费
PUSH_MONITOR_EVENT_TO_FTA = True
# 监控推送事件数据给自愈的 kafka topic
MONITOR_EVENT_KAFKA_TOPIC = os.getenv("BK_MONITOR_EVENT_KAFKA_TOPIC", "0bkmonitor_backend_event")
# 监控推送事件数据给自愈的 插件ID
MONITOR_EVENT_PLUGIN_ID = "bkmonitor"
# 主机监控获取单个进程支持最多port数
HOST_GET_PROCESS_MAX_PORT = 12

# 迁移工具使用文档地址
MIGRATE_GUIDE_URL = os.getenv("BKAPP_MIGRATE_GUIDE_URL", "")

# IP选择器接口类
BKM_IPCHOOSER_BKAPI_CLASS = "api.cmdb.ipchooser.IpChooserApi"

# IPv6特性开关
# 当gse新API就绪时可以，此时会切换为新API，在正式出包后可以删除该开关
USE_GSE_AGENT_STATUS_NEW_API = True
# GSE APIGW 的地址
BKGSE_APIGW_BASE_URL = os.getenv("BKAPP_BKGSE_APIGW_BASE_URL", "")
# 全面启用IPv6功能特性
IPV6_SUPPORT_BIZ_LIST = []
# 主机展示字段
HOST_DISPLAY_FIELDS = []
# 主机视图展示字段
HOST_VIEW_DISPLAY_FIELDS = []

# kafka是否自动提交配置
KAFKA_AUTO_COMMIT = True

# 动态字段配置
HOST_DYNAMIC_FIELDS = []

# 拨测默认的输出字段
UPTIMECHECK_OUTPUT_FIELDS = ["bk_host_innerip", "bk_host_innerip_v6"]

CUSTOM_REPORT_PLUGIN_NAME = "bkmonitorproxy"

# 接入计算平台使用的业务，默认 HDFS 集群及 VM 集群
DEFAULT_BKDATA_BIZ_ID = 0
DEFAULT_BKDATA_HDFS_CLUSTER = ""
DEFAULT_BKDATA_VM_CLUSTER = ""
# 开放接入 vm 的空间列表信息，格式: 空间类型__空间ID
ACCESS_VM_SPACE_WLIST = []

# 迁移版本，如果需要下次执行on_migrate，修改MIGRATE_VERSION即可
MIGRATE_VERSION = "v2"
LAST_MIGRATE_VERSION = ""

# ITSM审批回调
BK_ITSM_CALLBACK_HOST = os.getenv("BKAPP_ITSM_CALLBACK_HOST", BK_MONITOR_HOST)

# 蓝鲸业务名
BLUEKING_NAME = os.getenv("BKAPP_BLUEKING_NAME", "蓝鲸")

# 后台任务多进程并行数量，默认设置为1个
MAX_TASK_PROCESS_NUM = os.getenv("BK_MONITOR_MAX_TASK_PROCESS_NUM", 1)
MAX_TS_METRIC_TASK_PROCESS_NUM = os.getenv("BK_MONITOR_MAX_TASK_PROCESS_NUM", 1)

# 是否默认展示策略模块实时功能
SHOW_REALTIME_STRATEGY = False

# 强制使用数据平台查询的cmdb层级表
BKDATA_CMDB_LEVEL_TABLES = []

# 邮件报表整屏渲染等待时间
MAIL_REPORT_FULL_PAGE_WAIT_TIME = 60


# 加密配置
class SymmetricConverter(Base64Convertor):
    bs = 16

    @staticmethod
    def _unpad(s):
        return s[: -ord(s[len(s) - 1 :])]

    @classmethod
    def _pad(cls, s):
        return s + bytes((cls.bs - len(s) % cls.bs) * chr(cls.bs - len(s) % cls.bs), encoding="utf-8")

    @classmethod
    def encode_plaintext(cls, plaintext: str, encoding: str = "utf-8", **kwargs) -> bytes:
        plaintext_bytes = super().encode_plaintext(plaintext, encoding, **kwargs)
        return cls._pad(plaintext_bytes)

    @classmethod
    def decode_plaintext(cls, plaintext_bytes: bytes, encoding: str = "utf-8", **kwargs) -> str:
        plaintext_bytes = cls._unpad(plaintext_bytes)
        return super().decode_plaintext(plaintext_bytes, encoding, **kwargs)


SYMMETRIC_CIPHER_TYPE = get_env_or_raise("BKAPP_SYMMETRIC_CIPHER_TYPE", default=constants.SymmetricCipherType.AES.value)
ASYMMETRIC_CIPHER_TYPE = get_env_or_raise(
    "BKAPP_ASYMMETRIC_CIPHER_TYPE", default=constants.AsymmetricCipherType.RSA.value
)

BKCRYPTO = {
    # 声明项目所使用的非对称加密算法
    "ASYMMETRIC_CIPHER_TYPE": ASYMMETRIC_CIPHER_TYPE,
    # 声明项目所使用的对称加密算法
    "SYMMETRIC_CIPHER_TYPE": SYMMETRIC_CIPHER_TYPE,
    "SYMMETRIC_CIPHERS": {
        # default - 所配置的对称加密实例，根据项目需要可以配置多个
        "default": {
            "get_key_config": "bkmonitor.utils.db.fields.get_key_config",
            "cipher_options": {
                constants.SymmetricCipherType.AES.value: AESSymmetricOptions(
                    enable_iv=True,
                    key_size=32,
                    iv=None,
                    convertor=SymmetricConverter,
                    mode=constants.SymmetricMode.CBC,
                    encryption_metadata_combination_mode=constants.EncryptionMetadataCombinationMode.BYTES,
                ),
                constants.SymmetricCipherType.SM4.value: SM4SymmetricOptions(
                    mode=constants.SymmetricMode.CTR,
                    key_size=16,
                    iv=None,
                    encryption_metadata_combination_mode=constants.EncryptionMetadataCombinationMode.BYTES,
                ),
            },
        },
    },
}

# 特别的AES加密配置信息(全局配置)
SPECIFY_AES_KEY = ""
BK_CRYPTO_KEY = os.getenv("BKAPP_BK_CRYPTO_KEY", "")

# 前端事件上报
FRONTEND_REPORT_DATA_ID = 0
FRONTEND_REPORT_DATA_TOKEN = ""
FRONTEND_REPORT_DATA_HOST = ""

KUBERNETES_CMDB_ENRICH_BIZ_WHITE_LIST = []

# 告警后台集群
ALARM_BACKEND_CLUSTER_NAME = os.getenv("BK_MONITOR_ALARM_BACKEND_CLUSTER_NAME", "default").lower()
ALARM_BACKEND_CLUSTER_CODE = os.getenv("BK_MONITOR_ALARM_BACKEND_CLUSTER_CODE", 0)
ALARM_BACKEND_CLUSTER_ROUTING_RULES = []

# AIDEV配置
AIDEV_AGENT_APP_CODE = os.getenv("BK_AIDEV_AGENT_APP_CODE")
AIDEV_AGENT_APP_SECRET = os.getenv("BK_AIDEV_AGENT_APP_SECRET")
AIDEV_AGENT_API_URL_TMPL = os.getenv("BK_AIDEV_AGENT_API_URL_TMPL")
AIDEV_APIGW_ENDPOINT = os.getenv("BK_AIDEV_APIGW_ENDPOINT")
AIDEV_AGENT_LLM_GW_ENDPOINT = os.getenv("BK_AIDEV_AGENT_LLM_GW_ENDPOINT")
AIDEV_AGENT_LLM_DEFAULT_TEMPERATURE = 0.3  # 默认温度
AIDEV_COMMAND_AGENT_MAPPING = {}  # 快捷指令<->Agent映射
# AIAgent内容生成关键字
AIDEV_AGENT_AI_GENERATING_KEYWORD = "生成中"

# 采集订阅巡检配置，默认开启
IS_SUBSCRIPTION_ENABLED = True

# 允许限制空间功能开关， 默认限制
IS_RESTRICT_DS_BELONG_SPACE = True

# 最大的指标分片查询大小
MAX_FIELD_PAGE_SIZE = 1000

# 访问 PaaS 提供接口地址
PAASV3_APIGW_BASE_URL = os.getenv("BKAPP_PAASV3_APIGW_BASE_URL", "")

# 需要授权给蓝鲸应用的特定的数据源 ID
BKPAAS_AUTHORIZED_DATA_ID_LIST = []

# 环境代号
ENVIRONMENT_CODE = os.getenv("BKAPP_ENVIRONMENT_CODE") or "bk_monitor"

# `dbm_` 开头的结果表，仅特定的业务可以查看，并且不需要添加过滤条件
ACCESS_DBM_RT_SPACE_UID = []

# BCS APIGW 地址
BCS_APIGW_BASE_URL = os.getenv("BKAPP_BCS_APIGW_BASE_URL", "")

# 获取指标的间隔时间，默认为 2 hour
FETCH_TIME_SERIES_METRIC_INTERVAL_SECONDS = 7200

# 自定义指标过期时间
TIME_SERIES_METRIC_EXPIRED_SECONDS = 30 * 24 * 3600

# 是否启用 influxdb 写入，默认 True
ENABLE_INFLUXDB_STORAGE = True

# bk-notice-sdk requirment
if not os.getenv("BK_API_URL_TMPL"):
    os.environ["BK_API_URL_TMPL"] = f"{BK_COMPONENT_API_URL}/api/{{api_name}}"

BK_API_URL_TMPL = os.getenv("BK_API_URL_TMPL")

# 内网collector域名
INNER_COLLOCTOR_HOST = ""

# 外网collector域名
OUTER_COLLOCTOR_HOST = ""

# ES 需要串行的集群的白名单
ES_SERIAL_CLUSTER_LIST = []
ES_CLUSTER_BLACKLIST = []

# BCS 数据合流配置， 默认为 不启用
BCS_DATA_CONVERGENCE_CONFIG = {}

# 独立的vm集群的空间列表
SINGLE_VM_SPACE_ID_LIST = []

# 文档链接配置 格式: {"key1": {"type": "splice/link", "value": ""}}
DOC_LINK_MAPPING = {}

# 插件授权给 bkci 空间使用
BKCI_SPACE_ACCESS_PLUGIN_LIST = []

# 邮件订阅审批服务ID
REPORT_APPROVAL_SERVICE_ID = int(os.getenv("BKAPP_REPORT_APPROVAL_SERVICE_ID", 0))

# 需要base64编码的特殊字符
BASE64_ENCODE_TRIGGER_CHARS = []

# aidev的知识库ID
AIDEV_KNOWLEDGE_BASE_IDS = []

# 邮件订阅审批服务ID
REPORT_APPROVAL_SERVICE_ID = int(os.getenv("BKAPP_REPORT_APPROVAL_SERVICE_ID", 0))

# API地址
BK_MONITOR_API_HOST = os.getenv("BKAPP_BK_MONITOR_API_HOST", "http://monitor.bkmonitorv3.service.consul:10204")

# 网关管理员
APIGW_MANAGERS = f"[{','.join(os.getenv('BKAPP_APIGW_MANAGERS', 'admin').split(','))}]"

# 是否启用新版的数据链路
# 是否启用通过计算平台获取GSE data_id 资源，默认不启用
ENABLE_V2_BKDATA_GSE_RESOURCE = False
# 是否启用新版的 vm 链路，默认不启用
ENABLE_V2_VM_DATA_LINK = False
ENABLE_V2_VM_DATA_LINK_CLUSTER_ID_LIST = []
# 插件数据是否启用接入V4链路
ENABLE_PLUGIN_ACCESS_V4_DATA_LINK = os.getenv("ENABLE_PLUGIN_ACCESS_V4_DATA_LINK", "false").lower() == "true"

# 是否启用计算平台Kafka采样接口
ENABLE_BKDATA_KAFKA_TAIL_API = False
# Kafka采样接口重试次数
KAFKA_TAIL_API_RETRY_TIMES = 3
# Kafka Consumer超时时间(秒)
KAFKA_TAIL_API_TIMEOUT_SECONDS = 1000
# Kafka采样接口重试间隔(秒)
KAFKA_TAIL_API_RETRY_INTERVAL_SECONDS = 2
# 计算平台&监控平台数据一致性Redis相关配置
# 计算平台Redis监听模式
BKBASE_REDIS_PATTERN = "databus_v4_dataid"
# 计算平台Redis单次SCAN数量
BKBASE_REDIS_SCAN_COUNT = 1000
# Redis Watch锁续约间隔(秒)
BKBASE_REDIS_WATCH_LOCK_RENEWAL_INTERVAL_SECONDS = 15
# 计算平台Redis Watch锁过期时间(秒)
BKBASE_REDIS_WATCH_LOCK_EXPIRE_SECONDS = 60
# 单个任务最长执行时间(秒),默认一天
BKBASE_REDIS_TASK_MAX_EXECUTION_TIME_SECONDS = 86400
# 重连等待间隔时间(秒)
BKBASE_REDIS_RECONNECT_INTERVAL_SECONDS = 2
# Redis默认锁名称
BKBASE_REDIS_LOCK_NAME = "watch_bkbase_meta_redis_lock"
# 是否启用同步历史ES集群记录能力
ENABLE_SYNC_HISTORY_ES_CLUSTER_RECORD_FROM_BKBASE = False
# 是否同步数据至DB
ENABLE_SYNC_BKBASE_METADATA_TO_DB = False

# 特殊的可以不被禁用的BCS集群ID
ALWAYS_RUNNING_FAKE_BCS_CLUSTER_ID_LIST = []

# 使用RT中的路由过滤别名的结果表列表
SPECIAL_RT_ROUTE_ALIAS_RESULT_TABLE_LIST = []

# 是否启用新版方式接入计算平台
ENABLE_V2_ACCESS_BKBASE_METHOD = True

# BCS集群自动发现任务周期
BCS_DISCOVER_BCS_CLUSTER_INTERVAL = 5

# 启用新版ES索引轮转的ES集群名单
ENABLE_V2_ROTATION_ES_CLUSTER_IDS = []
# ES索引轮转间隔等待数值
ES_INDEX_ROTATION_SLEEP_INTERVAL_SECONDS = 3
# ES索引轮转步长
ES_INDEX_ROTATION_STEP = 50
# ES采集项整体偏移量（小时）
ES_STORAGE_OFFSET_HOURS = 8
# ES请求默认超时时间（秒）
METADATA_REQUEST_ES_TIMEOUT_SECONDS = 10

# 是否开启计算平台RT元信息同步任务
ENABLE_SYNC_BKBASE_META_TASK = False
# 同步计算平台RT元信息时的黑名单业务ID列表(计算平台自身业务ID）
SYNC_BKBASE_META_BLACK_BIZ_ID_LIST = []
# 同步计算平台RT元信息时的单轮拉取业务ID个数
SYNC_BKBASE_META_BIZ_BATCH_SIZE = 10
# 同步计算平台RT元信息时支持的存储类型
SYNC_BKBASE_META_SUPPORTED_STORAGE_TYPES = ["mysql", "tspider", "hdfs"]

# 创建 vm 链路资源所属的命名空间
DEFAULT_VM_DATA_LINK_NAMESPACE = "bkmonitor"
# grafana和策略导出是否支持data_label转换
ENABLE_DATA_LABEL_EXPORT = True

# 是否启用多租户版本的BKBASE V4链路
ENABLE_BKBASE_V4_MULTI_TENANT = False

# 是否启用access数据批量处理
ENABLED_ACCESS_DATA_BATCH_PROCESS = False
ACCESS_DATA_BATCH_PROCESS_SIZE = 50000
ACCESS_DATA_BATCH_PROCESS_THRESHOLD = 0

# metadata请求es超时配置, 单位为秒，默认10秒
# 格式: {default: 10, 集群域名: 20}
METADATA_REQUEST_ES_TIMEOUT = {}

# 是否启用自定义事件休眠
ENABLE_CUSTOM_EVENT_SLEEP = False

# 平台全局配置
BK_SHARED_RES_URL = os.environ.get("BK_SHARED_RES_URL", os.environ.get("BKPAAS_SHARED_RES_URL", ""))

# 跳过写入influxdb的结果表
SKIP_INFLUXDB_TABLE_ID_LIST = []

# 是否开启拨测联通性测试
ENABLE_UPTIMECHECK_TEST = True

# 检测结果缓存 TTL(小时)
CHECK_RESULT_TTL_HOURS = 1

# LLM 接口地址
BK_MONITOR_AI_API_URL = os.environ.get("BK_MONITOR_AI_API_URL", "")

# 支持来源 APIGW 列表
FROM_APIGW_NAME = os.getenv("FROM_APIGW_NAME", "bk-monitor")
# 网关环境，prod 表示生产环境，stage 表示测试环境
APIGW_STAGE = os.getenv("APIGW_STAGE", "prod")

# 集群内 bkmonitor-operator 特殊部署命名空间信息，针对一个集群部署多套 operator 时需要配置这个
# 格式: {
#     "BCS-K8S-00000": "bkmonitor-operator-bkte",
#     "BCS-K8S-00001": "bkmonitor-operator",
# }
K8S_OPERATOR_DEPLOY_NAMESPACE = {}

# 集群内 collector 接收端特殊配置，针对一个集群部署多套 operator 时需要配置这个
# 格式: {
#     "BCS-K8S-00000": {"cache": {"interval": "10s"}},
#     "BCS-K8S-00001": {"cache": {"interval": "1s"}},
# }
K8S_COLLECTOR_CONFIG = {}

# 默认K8S插件采集集群ID
K8S_PLUGIN_COLLECT_CLUSTER_ID = ""

# 腾讯云指标插件配置
# {
#     "label": "",
#     "plugin_display_name": "",
#     "description_md": "",
#     "logo": "",
#     "collect_json": {
#         "values": {
#             "limits": {
#                 "cpu": "100m",
#                 "memory": "100Mi"
#             },
#             "requests": {
#                 "cpu": "10m",
#                 "memory": "15Mi"
#             }
#         },
#         "template": ""
#     },
#     "config_json": []
# }
TENCENT_CLOUD_METRIC_PLUGIN_CONFIG = {}
TENCENT_CLOUD_METRIC_PLUGIN_ID = "qcloud_exporter"

# 启用监控目标缓存的业务ID列表
ENABLED_TARGET_CACHE_BK_BIZ_IDS = []

# k8s灰度列表，关闭灰度: [0] 或删除该配置
K8S_V2_BIZ_LIST = []

# APM UnifyQuery 查询业务黑名单
APM_UNIFY_QUERY_BLACK_BIZ_LIST = []

# 文档中心对应文档版本
BK_DOC_VERSION = "3.9"

# BK-Repo
if os.getenv("USE_BKREPO", os.getenv("BKAPP_USE_BKREPO", "")).lower() == "true":
    USE_CEPH = True
    BKREPO_ENDPOINT_URL = os.getenv("BKAPP_BKREPO_ENDPOINT_URL") or os.environ["BKREPO_ENDPOINT_URL"]
    BKREPO_USERNAME = os.getenv("BKAPP_BKREPO_USERNAME") or os.environ["BKREPO_USERNAME"]
    BKREPO_PASSWORD = os.getenv("BKAPP_BKREPO_PASSWORD") or os.environ["BKREPO_PASSWORD"]
    BKREPO_PROJECT = os.getenv("BKAPP_BKREPO_PROJECT") or os.environ["BKREPO_PROJECT"]
    BKREPO_BUCKET = os.getenv("BKAPP_BKREPO_BUCKET") or os.environ["BKREPO_BUCKET"]

    DEFAULT_FILE_STORAGE = "bkstorages.backends.bkrepo.BKRepoStorage"

# 告警图表渲染模式
ALARM_GRAPH_RENDER_MODE = os.getenv("BKAPP_ALARM_GRAPH_RENDER_MODE", "image_exporter")

# 首页告警图业务数量限制
HOME_PAGE_ALARM_GRAPH_BIZ_LIMIT = 5
# 首页告警图图表数量限制
HOME_PAGE_ALARM_GRAPH_LIMIT = 10

# 是否启用多租户模式
ENABLE_MULTI_TENANT_MODE = os.getenv("ENABLE_MULTI_TENANT_MODE", "false").lower() == "true"
# 是否启用全局租户（blueapps依赖）
IS_GLOBAL_TENANT = True
# IAM多租户配置
BK_APP_TENANT_ID = "system"
# 已经初始化的租户列表
INITIALIZED_TENANT_LIST = ["system"]

# 事件中心AIOps功能灰度业务列表
ENABLE_AIOPS_EVENT_CENTER_BIZ_LIST = []

# 用户管理web api地址
BK_USER_WEB_API_URL = os.getenv("BK_USER_WEB_API_URL") or f"{BK_COMPONENT_API_URL}/api/bk-user-web/prod/"

# 进程采集独立数据源模式业务ID列表
PROCESS_INDEPENDENT_DATAID_BIZ_IDS = []
