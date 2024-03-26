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

import six
from blueapps.conf.log import get_logging_config_dict
from blueapps.patch.log import get_paas_v2_logging_config_dict
from celery.schedules import crontab

from config.tools.rabbitmq import get_rabbitmq_settings

from ..tools.environment import (
    DJANGO_CONF_MODULE,
    ENVIRONMENT,
    IS_CONTAINER_MODE,
    NEW_ENV,
    PAAS_VERSION,
)

# fmt: off
for k, v in six.iteritems(os.environ):
    for prefix in ("BK_", "BKAPP_"):
        k = k.upper()
        if k.startswith(prefix) and k[len(prefix):]:
            locals()[k[len(prefix):]] = v
# fmt: on

# 按照环境变量中的配置，加载对应的配置文件
try:
    _module = __import__(f"config.{NEW_ENV}", globals(), locals(), ["*"])
except ImportError as e:
    logging.exception(e)
    raise ImportError("Could not import config '{}' (Is it on sys.path?): {}".format(DJANGO_CONF_MODULE, e))

for _setting in dir(_module):
    if _setting == _setting.upper():
        locals()[_setting] = getattr(_module, _setting)

ROOT_URLCONF = "urls"


INSTALLED_APPS = locals().get("INSTALLED_APPS", tuple())
INSTALLED_APPS += (
    "django_elasticsearch_dsl",
    "rest_framework",
    "django_filters",
    "drf_yasg",
    "bkmonitor",
    "healthz",
    "metadata",
    "bkm_space",
    "calendars",
    "monitor",
    "monitor_api",
    "monitor_web",
    "apm_web",
    "apm_ebpf",
    "apm",
    "weixin.core",
    "weixin",
    "core.drf_resource",
    "bkm_ipchooser",
    "version_log",
    "iam.contrib.iam_migration",
    "fta_web",
    "audit",
    "apigw_manager",
    'bk_notice_sdk',
)

MIDDLEWARE = (
    "bkmonitor.middlewares.pyinstrument.ProfilerMiddleware",
    "bkmonitor.middlewares.prometheus.MetricsBeforeMiddleware",  # 必须放到最前面
    "django.contrib.sessions.middleware.SessionMiddleware",
    "blueapps.middleware.request_provider.RequestProvider",
    "bkmonitor.middlewares.request_middlewares.RequestProvider",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "weixin.core.middlewares.WeixinProxyPatchMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # 静态资源
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # Auth middleware
    "weixin.core.middlewares.WeixinAuthenticationMiddleware",
    "weixin.core.middlewares.WeixinLoginMiddleware",
    "blueapps.account.components.rio.middlewares.RioLoginRequiredMiddleware",
    # 用户登录验证middleware
    "bkmonitor.middlewares.authentication.ApiTokenAuthenticationMiddleware",
    # 应用流控保护，放在用户登录验证之后
    "bkmonitor.middlewares.application_protection.ProtectionMiddleware",
    "blueapps.middleware.xss.middlewares.CheckXssMiddleware",
    # APIGW JWT验证中间件
    "bkmonitor.middlewares.authentication.ApiGatewayJWTExternalMiddleware",
    "apigw_manager.apigw.authentication.ApiGatewayJWTAppMiddleware",
    "common.middlewares.TimeZoneMiddleware",
    "common.middlewares.TrackSiteVisitMiddleware",
    "version_log.middleware.VersionLogMiddleware",
    "monitor_api.middlewares.MonitorAPIMiddleware",
    "bkm_space.middleware.ParamInjectMiddleware",
    "bkmonitor.middlewares.prometheus.MetricsAfterMiddleware",  # 必须放到最后面
)


DATABASES = locals()["DATABASES"]
# 未配置节点管理，默认和监控 SaaS 共用 DB
DATABASES["nodeman"] = {}
DATABASES["nodeman"].update(DATABASES["default"])
DATABASES["nodeman"]["NAME"] = "bk_nodeman"
# 设置节点管理数据库配置
for db_key in [
    "BKAPP_NODEMAN_DB_NAME",
    "BKAPP_NODEMAN_DB_USERNAME",
    "BKAPP_NODEMAN_DB_PASSWORD",
    "BKAPP_NODEMAN_DB_HOST",
    "BKAPP_NODEMAN_DB_PORT",
]:
    if db_key not in os.environ:
        break
else:
    DATABASES.update(
        {
            "nodeman": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": os.environ["BKAPP_NODEMAN_DB_NAME"],
                "USER": os.environ["BKAPP_NODEMAN_DB_USERNAME"],
                "PASSWORD": os.environ["BKAPP_NODEMAN_DB_PASSWORD"],
                "HOST": os.environ["BKAPP_NODEMAN_DB_HOST"],
                "PORT": os.environ["BKAPP_NODEMAN_DB_PORT"],
            },
        }
    )

SILENCED_SYSTEM_CHECKS = ["urls.W005"]

#
# Templates
#
# mako template dir(render_mako settings)
MAKO_TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")
MAKO_TEMPLATE_MODULE_DIR = os.path.join(PROJECT_ROOT, "templates_module", APP_CODE)

# django template dir(support mako)
TEMPLATE_DIRS = (
    os.path.join(PROJECT_ROOT, "static"),
    os.path.join(PROJECT_ROOT, "templates"),
    os.path.join(PROJECT_ROOT, "webpack"),
)

TEMPLATES = [
    {
        "BACKEND": "blueapps.template.backends.mako.MakoTemplates",
        "DIRS": TEMPLATE_DIRS,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
                "django.contrib.messages.context_processors.messages",
                "common.context_processors.get_context",
                "django.template.context_processors.i18n",
            ],
            "default_filters": ["h"],
        },
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(PROJECT_ROOT, "django_templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
                "django.contrib.messages.context_processors.messages",
                "common.context_processors.get_context",
                "django.template.context_processors.i18n",
            ]
        },
    },
]

CACHES = {
    "db": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "OPTIONS": {"MAX_ENTRIES": 100000, "CULL_FREQUENCY": 10},
    },
    "login_db": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "account_cache"},
    "dummy": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
    "locmem": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}
CACHES["default"] = CACHES["db"]


def django_redis_cache_config():
    variable_list = ["REDIS_PASSWORD", "REDIS_HOST", "REDIS_PORT", "REDIS_DB"]
    for variable in variable_list:
        key = f"DJANGO_{variable}"
        if variable not in os.environ and key not in os.environ:
            yield None
        else:
            yield os.getenv(key) or os.getenv(variable)


# Django Redis Cache 相关配置
DJANGO_REDIS_PASSWORD, DJANGO_REDIS_HOST, DJANGO_REDIS_PORT, DJANGO_REDIS_DB = list(django_redis_cache_config())

USE_DJANGO_CACHE_REDIS = DJANGO_REDIS_HOST and DJANGO_REDIS_PORT
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

#
# Cookies & Sessions
#

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_PATH = SITE_URL
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = APP_CODE + "_sessionid"

#
# Authentication & Authorization
#
AUTH_USER_MODEL = "account.User"


LOG_LEVEL = os.environ.get("BKAPP_LOG_LEVEL", "INFO")

if PAAS_VERSION == "V2":
    LOGGING = get_paas_v2_logging_config_dict(is_local=ENVIRONMENT == "dev", bk_log_dir=LOG_PATH, log_level=LOG_LEVEL)
else:
    LOGGING = get_logging_config_dict(locals())

LOGGING["loggers"].update(
    {
        "monitor_web": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "monitor_api": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "apm": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "apm_ebpf": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "utils": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "core": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "common": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "monitor_adapter": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "root": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "account": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "bkmonitor": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "metadata": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "kubernetes": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "calendars": {"handlers": ["root"], "level": LOG_LEVEL, "propagate": True},
        "iam": {"handlers": ["root"], "level": "ERROR", "propagate": True},
    }
)

if IS_CONTAINER_MODE:
    for logger in LOGGING["loggers"]:
        if "null" not in LOGGING["loggers"][logger]["handlers"]:
            LOGGING["loggers"][logger]["handlers"] = ["console"]

#
# CELERY 配置
#
IS_USE_CELERY = True
INSTALLED_APPS += ("django_celery_beat", "django_celery_results")
CELERYBEAT_SCHEDULER = "monitor.schedulers.MonitorDatabaseScheduler"
CELERY_ENABLE_UTC = False

CELERYBEAT_SCHEDULE = {
    "monitor_web.tasks.update_config_status": {
        "task": "monitor_web.tasks.update_config_status",
        "schedule": crontab(),
        "enabled": False,
    },
    "monitor_web.tasks.update_config_instance_count": {
        "task": "monitor_web.tasks.update_config_instance_count",
        "schedule": crontab(minute=0),  # todo 该任务的周期需建议和节点管理的自动执行的周期保持一致
        "enabled": False,
    },
    "monitor_web.tasks.update_external_approval_status": {
        "task": "monitor_web.tasks.update_external_approval_status",
        "schedule": crontab(minute="*/10"),
        "enabled": True,
    },
    "monitor_web.tasks.update_metric_list": {
        "task": "monitor_web.tasks.update_metric_list",
        "schedule": crontab(),
        "enabled": True,
        "options": {"queue": "celery_resource"},
    },
    "monitor_web.tasks.access_pending_aiops_strategy": {
        "task": "monitor_web.tasks.access_pending_aiops_strategy",
        "schedule": crontab(minute="*/5"),
        "enabled": True,
    },
    "monitor_web.tasks.update_aiops_dataflow_status": {
        "task": "monitor_web.tasks.update_aiops_dataflow_status",
        "schedule": crontab(minute="*/10"),
        "enabled": False,
    },
    "fta_web.tasks.update_home_statistics": {
        "task": "fta_web.tasks.update_home_statistics",
        "schedule": crontab(minute="*/5"),
        "enabled": True,
    },
    "monitor_web.tasks.update_report_receivers": {
        "task": "monitor_web.tasks.update_report_receivers",
        "schedule": crontab(minute=27, hour=2),
        "enabled": True,
    },
    "apm_web.tasks.refresh_application": {
        "task": "apm_web.tasks.refresh_application",
        "schedule": crontab(minute="*/10"),
        "enabled": True,
    },
    "apm_web.tasks.refresh_apm_application_metric": {
        "task": "apm_web.tasks.refresh_apm_application_metric",
        "schedule": crontab(minute="*/10"),
        "enabled": True,
    },
    "monitor_web.tasks.keep_alive": {
        "task": "monitor_web.tasks.keep_alive",
        "schedule": crontab(),
        "enabled": True,
        "options": {"queue": "celery_resource"},
    },
    "monitor_web.tasks.update_statistics_data": {
        "task": "monitor_web.tasks.update_statistics_data",
        "schedule": crontab(),
        "enabled": True,
    },
}

*_, BROKER_URL = get_rabbitmq_settings(APP_CODE)

CELERY_RESULT_BACKEND = "django_celery_results.backends.database:DatabaseBackend"

CELERY_TASK_SERIALIZER = "pickle"
CELERY_ACCEPT_CONTENT = ["pickle"]
CELERY_RESULT_SERIALIZER = "pickle"

#
# Django Rest Framework Settings
#

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_RENDERER_CLASSES": ("bkmonitor.views.renderers.MonitorJSONRenderer",),
    # 'DATETIME_FORMAT': "%Y-%m-%d %H:%M:%S",
    "EXCEPTION_HANDLER": "core.drf_resource.exceptions.custom_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "monitor_api.pagination.MonitorAPIPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_PERMISSION_CLASSES": ("monitor_web.permissions.BusinessViewPermission",),
}

#
# MonitorAPI Settings
#

MONITOR_API_MODELS = (
    ("bkmonitor.BaseAlarm", True),
    ("bkmonitor.SnapshotHostIndex", True),
    # 配置相关
    ("monitor.UserConfig", False),
    ("monitor.ApplicationConfig", False),
    ("monitor.GlobalConfig", True),
)

###############################################################################

# 水印字体素材路径
SIGNATURE_FONT_PATH = os.path.join(PROJECT_ROOT, "static", "font", "arial.ttf")

# 重启服务器时清除缓存
CLEAR_CACHE_ON_RESTART = False

# csrf token name
CSRF_COOKIE_NAME = "%s_monitor_csrftoken" % BKAPP_DEPLOY_PLATFORM

# 主机任务状态码: 1.Agent异常; 3.上次已成功; 5.等待执行; 7.正在执行;
# 9.执行成功; 11.任务失败; 12.任务下发失败; 13.任务超时; 15.任务日志错误;
# 101.脚本执行失败; 102.脚本执行超时; 103.脚本执行被终止; 104.脚本返回码非零;
# 202.文件传输失败; 203.源文件不存在; 310.Agent异常; 311.用户名不存在;
# 320.文件获取失败; 321.文件超出限制; 329.文件传输错误; 399.任务执行出错
IP_STATUS_SUCCESS = 9
IP_STATUS_WAITING = 5
IP_STATUS_RUNNING = 7

# 脚本类型：1(shell脚本)、2(bat脚本)、3(perl脚本)、4(python脚本)、5(Powershell脚本)
SCRIPT_TYPE_SHELL = 1
SCRIPT_TYPE_BAT = 2

# 不同OS对应的exporter文件名
EXPORTER_FILENAME_OS_MAPPING = {
    "linux": "exporter-linux",
    "windows": "exporter-windows.exe",
    "aix": "exporter-aix",
}

OS_TYPE_NAME_DICT = {1: "linux", 2: "windows", 3: "aix"}


def get_saas_version():
    version = ""
    if "VERSION" in os.listdir(BASE_DIR):
        with open(os.path.join(BASE_DIR, "VERSION")) as fd:
            version = fd.read().strip()
    return version


# 实际版本号，基于包解析的
REAL_SAAS_VERSION = get_saas_version()

# 高级配置，放在db的
SAAS_VERSION = REAL_SAAS_VERSION or "3.2.x"

# 版本日志配置
VERSION_LOG = {
    "LATEST_VERSION_INFORM": True,
    "LATEST_VERSION_INFORM_TYPE": "popup",
    "LANGUAGE_MAPPINGS": {"zh-hans": "zh-cn", "en": "en"},
    "LANGUAGE_POSTFIX_SEPARATION": "/",
}

# blueapps配置，ajax请求401返回plain信息
IS_AJAX_PLAIN_MODE = True

# 显示图表水印
GRAPH_WATERMARK = True

# Grafana配置
GRAFANA = {
    "HOST": GRAFANA_URL,
    "PROVISIONING_PATH": BASE_DIR + "/packages/monitor_web/grafana/provisioning",  # noqa
    "PROVISIONING_CLASSES": [
        "monitor_web.grafana.provisioning.BkMonitorProvisioning",
    ],
    "PERMISSION_CLASSES": ["monitor_web.grafana.permissions.DashboardPermission"],
    "CODE_INJECTIONS": {
        "<head>": """<head>
<style>
      .sidemenu {
        display: none !important;
      }
      .navbar-page-btn .gicon-dashboard {
        display: none !important;
      }
      .navbar .navbar-buttons--tv {
        display: none !important;
      }
    .css-1jrggg2 {
          left: 0 !important;
      }
      .css-9nwlx8 {
        display: none;
      }
</style>
<script>
var is_external = false;
var _wr = function(type) {
    var orig = history[type];
    return function() {
        var rv = orig.apply(this, arguments);
        var e = new Event(type);
        e.arguments = arguments;
        window.dispatchEvent(e);
        return rv;
    };
};
   history.pushState = _wr('pushState');
   history.replaceState = _wr('replaceState');
  ["popstate", "replaceState", "pushState"].forEach(function(eventName) {
    window.addEventListener(eventName, function() {
      window.parent.postMessage({ pathname: this.location.pathname }, "*");
    });
  });
</script>
""",
    },
}

# 拨测任务最大超时限制(ms)
MAX_AVAILABLE_DURATION_LIMIT = 60000

# job平台在登录目标机器时，有时会遇到目标机器配置了登录时打印一些信息的情况
# 该变量用于分割额外信息与真正的脚本执行结果
DIVIDE_SYMBOL = "=======bkmonitor======="

# 开发商ID
BK_SUPPLIER_ID = 0

# 登录缓存时间配置, 单位秒（与django cache单位一致）
LOGIN_CACHE_EXPIRED = 60

# 蓝鲸微信请求URL前缀
WEIXIN_SITE_URL = os.environ.get("BKAPP_WEIXIN_SITE_URL", SITE_URL + "weixin/")
# 蓝鲸微信本地静态文件请求URL前缀
WEIXIN_STATIC_URL = os.environ.get("BKAPP_WEIXIN_STATIC_URL", STATIC_URL + "weixin/")
# 微信调试开关
WX_USER = os.environ.get("BKAPP_WX_USER", None) == 1
# 微信Console开关
ENABLE_CONSOLE = os.environ.get("BKAPP_ENABLE_CONSOLE", None) == 1

# 移动网关鉴权
RIO_TOKEN = os.environ.get("BKAPP_RIO_TOKEN", "")
RIO_TOKEN_LIMIT = os.environ.get("BKAPP_RIO_TOKEN_LIMIT", "")
RIO_URL_LIMIT = os.environ.get("BKAPP_RIO_URL_LIMIT", "")

# 代理转发的请求需要配置
if os.environ.get("BKAPP_CSRF_TRUSTED_ORIGINS", ""):
    CSRF_TRUSTED_ORIGINS = os.environ.get("BKAPP_CSRF_TRUSTED_ORIGINS").split("|")

# COMMON_USERNAME 平台账号
COMMON_USERNAME = os.environ.get("BKAPP_COMMON_USERNAME", "admin")

# 自定义字符型data id
GSE_CUSTOM_EVENT_DATAID = 1100000

# influxdb host
INFLUXDB_METRIC_HOST = os.getenv("BKAPP_INFLUXDB_METRIC_HOST", "influxdb.service.consul")
INFLUXDB_METRIC_PORT = os.getenv("BKAPP_INFLUXDB_METRIC_PORT", "9273")
INFLUXDB_METRIC_URI = os.getenv("BKAPP_INFLUXDB_METRIC_URI", "/metrics")

TAM_ID = os.getenv("BKAPP_TAM_ID", "")

AUTHENTICATION_BACKENDS = (
    "bkmonitor.middlewares.authentication.ApiTokenAuthBackend",
    "blueapps.account.components.rio.backends.RioBackend",
    "blueapps.account.backends.WeixinBackend",
    "blueapps.account.backends.UserBackend",
)

INGESTER_HOST = os.getenv("BKAPP_INGESTER_HOST", "http://ingester.bkfta.service.consul")

# CORS配置
CORS_ALLOW_ALL_ORIGINS = True

# BK-Repo
if os.getenv("USE_BKREPO", os.getenv("BKAPP_USE_BKREPO", "")).lower() == "true":
    USE_CEPH = True
    BKREPO_ENDPOINT_URL = os.getenv("BKAPP_BKREPO_ENDPOINT_URL") or os.environ["BKREPO_ENDPOINT_URL"]
    BKREPO_USERNAME = os.getenv("BKAPP_BKREPO_USERNAME") or os.environ["BKREPO_USERNAME"]
    BKREPO_PASSWORD = os.getenv("BKAPP_BKREPO_PASSWORD") or os.environ["BKREPO_PASSWORD"]
    BKREPO_PROJECT = os.getenv("BKAPP_BKREPO_PROJECT") or os.environ["BKREPO_PROJECT"]
    BKREPO_BUCKET = os.getenv("BKAPP_BKREPO_BUCKET") or os.environ["BKREPO_BUCKET"]

    DEFAULT_FILE_STORAGE = "bkstorages.backends.bkrepo.BKRepoStorage"

CSRF_USE_SESSIONS = True

# 设置最大请求大小
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# 设置pyinstrument的profiler开关
PYINSTRUMENT_URL_ARGUMENT = "bk-monitor-profile"

# 指标缓存任务执行周期数
METRIC_CACHE_TASK_PERIOD = 10

# 外部监控域名前缀
EXTERNAL_PREFIX = ""
# ITSM外部授权审批服务ID
EXTERNAL_APPROVAL_SERVICE_ID = int(os.getenv("BKAPP_EXTERNAL_APPROVAL_SERVICE_ID", 0))
# 外部版APIGW公钥
EXTERNAL_APIGW_PUBLIC_KEY = ""

# https相关配置
SECURE_SSL_REDIRECT = os.getenv("BKAPP_SECURE_SSL_REDIRECT", "").lower() == "true"
SECURE_SSL_HOST = os.getenv("BKAPP_SECURE_SSL_HOST", "")
SECURE_REDIRECT_EXEMPT = os.getenv("BKAPP_SECURE_REDIRECT_EXEMPT", "")
if SECURE_REDIRECT_EXEMPT:
    SECURE_REDIRECT_EXEMPT = SECURE_REDIRECT_EXEMPT.split(",")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# 屏蔽空间信息的用户规则（正则）
BLOCK_SPACE_RULE = ""
