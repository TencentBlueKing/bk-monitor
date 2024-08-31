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

from ..tools.environment import NEW_ENV

# 按照环境变量中的配置，加载对应的配置文件
try:
    _module = __import__(f"config.{NEW_ENV}", globals(), locals(), ["*"])
except ImportError as e:
    logging.exception(e)
    raise ImportError("Could not import config '{}' (Is it on sys.path?): {}".format(NEW_ENV, e))

from config.role.web import *  # noqa
from config.role.worker import *  # noqa

for _setting in dir(_module):
    if _setting == _setting.upper():
        locals()[_setting] = getattr(_module, _setting)

# 覆盖默认配置
RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_VHOST, RABBITMQ_USER, RABBITMQ_PASS, _ = get_rabbitmq_settings(
    app_code=APP_CODE, backend=True
)

MIGRATE_MONITOR_API = False

INSTALLED_APPS += (
    "django_elasticsearch_dsl",
    "rest_framework",
    "django_filters",
    "bkmonitor",
    "bkm_space",
    "monitor",
    "monitor_api",
    "monitor_web",
    "apm_web",
    "apm_ebpf",
    "apm",
    "fta_web",
    "kernel_api",
    "metadata",
    "calendars",
    "core.drf_resource",
    "django_celery_beat",
    "django_celery_results",
    "audit",
    "apigw_manager",
)

# api not use celery worker
CELERY_ALWAYS_EAGER = True

LOGGER_LEVEL = os.environ.get("BKAPP_LOG_LEVEL", "INFO")
LOGGER_DEFAULT = {
    "level": LOGGER_LEVEL,
    "propagate": False,
    "handlers": ["file", "console"],
}


def get_logger_config(log_path, logger_level, log_file_prefix):
    return {
        "version": 1,
        "loggers": {
            "": {"level": "ERROR", "handlers": ["file", "console"]},
            "django.request": {"handlers": ["file", "console"], "level": "ERROR", "propagate": True},
            "monitor": LOGGER_DEFAULT,
            "monitor_api": LOGGER_DEFAULT,
            "utils": LOGGER_DEFAULT,
            "drf_non_orm": LOGGER_DEFAULT,
            "common": LOGGER_DEFAULT,
            "monitor_adapter": LOGGER_DEFAULT,
            "kernel_api": LOGGER_DEFAULT,
            "project": LOGGER_DEFAULT,
            "bkmonitor": LOGGER_DEFAULT,
            "kernel": LOGGER_DEFAULT,
            "metadata": LOGGER_DEFAULT,
            "kubernetes": LOGGER_DEFAULT,
            "apm": LOGGER_DEFAULT,
            "apm_ebpf": LOGGER_DEFAULT,
            "calendars": LOGGER_DEFAULT,
            "sql_parse": LOGGER_DEFAULT,
            "file-only": {"level": LOGGER_LEVEL, "propagate": False, "handlers": ["file"]},
            "console-only": {"level": LOGGER_LEVEL, "propagate": False, "handlers": ["console"]},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "level": "DEBUG", "formatter": "standard"},
            "file": {
                "class": "logging.handlers.WatchedFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": os.path.join(log_path, f"{log_file_prefix}kernel_api.log"),
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

#
# Templates
#
TEMPLATE_CONTEXT_PROCESSORS = (
    # the context to the templates
    "django.contrib.auth.context_processors.auth",
    "django.template.context_processors.request",
    "django.template.context_processors.csrf",
    "django.contrib.messages.context_processors.messages",
    "common.context_processors.get_context",  # 自定义模版context，可以在页面中使用STATIC_URL等变量
    "django.template.context_processors.i18n",
)
TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, "kernel_api/templates"),  # noqa
    os.path.join(BASE_DIR, "bkmonitor/templates"),  # noqa
)
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
        "DIRS": list(TEMPLATE_DIRS),
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": list(TEMPLATE_CONTEXT_PROCESSORS)},
    },
]

ROOT_URLCONF = "kernel_api.urls"
MIDDLEWARE = (
    "bkmonitor.middlewares.prometheus.MetricsBeforeMiddleware",  # 必须放到最前面
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    # 'django.middleware.csrf.CsrfViewMiddleware',
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "blueapps.middleware.request_provider.RequestProvider",
    "bkmonitor.middlewares.request_middlewares.RequestProvider",
    "kernel_api.middlewares.ApiTimeZoneMiddleware",
    "kernel_api.middlewares.ApiLanguageMiddleware",
    "kernel_api.middlewares.authentication.AuthenticationMiddleware",
    "bkm_space.middleware.ParamInjectMiddleware",
    "bkmonitor.middlewares.prometheus.MetricsAfterMiddleware",  # 必须放到最后面
)

# 后台api服务， 请求的cookie中不会有session id， 因此每次都会创建新的session， 这里只保留1min即可。
SESSION_COOKIE_AGE = 60

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_RENDERER_CLASSES": ("kernel_api.adapters.ApiRenderer",),
    "DEFAULT_AUTHENTICATION_CLASSES": ("kernel_api.middlewares.authentication.KernelSessionAuthentication",),
    # 'DATETIME_FORMAT': "%Y-%m-%d %H:%M:%S",
    "EXCEPTION_HANDLER": "kernel_api.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "bkmonitor.views.pagination.MonitorAPIPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_PERMISSION_CLASSES": (),
}

RESOURCE_PROXY_TEMPLATE = "{module}.project.{path}"

#
# Authentication & Authorization
#
AUTH_USER_MODEL = "account.User"

AUTHENTICATION_BACKENDS = (
    "kernel_api.middlewares.authentication.AppWhiteListModelBackend",
    "blueapps.account.backends.UserBackend",
)

ALLOW_EXTEND_API = True
AES_X_KEY_FIELD = "SAAS_SECRET_KEY"

# 跳过权限中心检查
SKIP_IAM_PERMISSION_CHECK = True

# 重启服务器时清除缓存
CLEAR_CACHE_ON_RESTART = False

# esb组件地址
COMMON_USERNAME = os.environ.get("BK_ESB_SUPER_USER", "admin")

AES_TOKEN_KEY = os.environ.get("AK_AES_TOKEN_KEY", "ALERT_RESULT")

INGESTER_CONSUL = os.environ.get("INGESTER_CONSUL", "")

# 项目空间API类模块路径
BKM_SPACE_API_CLASS = "metadata.resources.space_api.InjectSpaceApi"

# api 进程禁用ssl
SECURE_SSL_REDIRECT = False
