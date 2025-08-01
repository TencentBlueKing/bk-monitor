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
import os
import sys

from bkcrypto import constants as bkcrypto_constants
from blueapps.conf.default_settings import *  # noqa
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from config.log import get_logging_config_dict

# 使用k8s部署模式
IS_K8S_DEPLOY_MODE = os.getenv("DEPLOY_MODE") == "kubernetes"

# 这里是默认的 INSTALLED_APPS，大部分情况下，不需要改动
# 如果你已经了解每个默认 APP 的作用，确实需要去掉某些 APP，请去掉下面的注释，然后修改
# INSTALLED_APPS = (
#     'bkoauth',
#     # 框架自定义命令
#     'blueapps.contrib.bk_commands',
#     'django.contrib.admin',
#     'django.contrib.auth',
#     'django.contrib.contenttypes',
#     'django.contrib.sessions',
#     'django.contrib.sites',
#     'django.contrib.messages',
#     'django.contrib.staticfiles',
#     # account app
#     'blueapps.account',
# )

# 请在这里加入你的自定义 APP
INSTALLED_APPS += (
    # must first django_jsonfield_backport
    "django_jsonfield_backport",
    "django_prometheus",
    "rest_framework",
    "iam.contrib.iam_migration",
    "django_dbconn_retry",
    "apps.iam",
    "apps.api",
    "apps.log_commons",
    "apps.log_search",
    "apps.log_audit",
    "apps.log_databus",
    "apps.log_esquery",
    "apps.log_measure",
    "apps.log_trace",
    "apps.log_bcs",
    "apps.esb",
    "apps.bk_log_admin",
    "apps.grafana",
    "apps.ai_assistant",
    "bk_monitor",
    "home_application",
    "console",
    "pipeline",
    "pipeline.log",
    "pipeline.engine",
    "pipeline.component_framework",
    "pipeline.django_signal_valve",
    "django_celery_beat",
    "django_celery_results",
    "apps.log_extract",
    "apps.feature_toggle",
    "apps.log_clustering",
    "bkm_space",
    "bkm_ipchooser",
    "apps.log_desensitize",
    "log_adapter",
    "bkm_search_module",
    "bk_notice_sdk",
    "apigw_manager.apigw",
)

# BKLOG后台接口：默认否，后台接口session不写入本地数据库
BKAPP_IS_BKLOG_API = os.environ.get("BKAPP_IS_BKLOG_API", 0)
if BKAPP_IS_BKLOG_API:
    SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
else:
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    INSTALLED_APPS += ("version_log",)

# 设置pyinstrument的profiler开关
PYINSTRUMENT_URL_ARGUMENT = "bk-log-profile"

# 这里是默认的中间件，大部分情况下，不需要改动
# 如果你已经了解每个默认 MIDDLEWARE 的作用，确实需要去掉某些 MIDDLEWARE，或者改动先后顺序，请去掉下面的注释，然后修改
MIDDLEWARE = (
    # 性能分析
    "apps.middleware.pyinstrument.ProfilerMiddleware",
    # http -> https 转换中间件
    "apps.middlewares.HttpsMiddleware",
    # "django.middleware.gzip.GZipMiddleware",
    "apps.middleware.user_middleware.BkLogMetricsBeforeMiddleware",
    # request instance provider
    "blueapps.middleware.request_provider.RequestProvider",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "blueapps.middleware.xss.middlewares.CheckXssMiddleware",
    # 跨域检测中间件， 默认关闭
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "django.middleware.security.SecurityMiddleware",
    # 蓝鲸静态资源服务
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Auth middleware
    # "blueapps.account.middlewares.BkJwtLoginRequiredMiddleware",   # 与下面的 apigw_manager 中间件冲突，需要去掉
    "blueapps.account.middlewares.WeixinLoginRequiredMiddleware",
    "apps.middleware.apigw.ApiGatewayJWTMiddleware",  # JWT 认证，解析请求头中的 X-Bkapi-JWT，获取 request.jwt 对象
    "apigw_manager.apigw.authentication.ApiGatewayJWTAppMiddleware",  # 根据 request.jwt，获取 request.app 对象
    "apigw_manager.apigw.authentication.ApiGatewayJWTUserMiddleware",  # 根据 request.jwt，获取 request.user 对象
    # "blueapps.account.middlewares.LoginRequiredMiddleware",
    # 注释掉是因为ApiTokenAuthenticationMiddleware中针对非TOKEN校验的会继承父类
    "apps.middleware.api_token_middleware.ApiTokenAuthenticationMiddleware",
    # exception middleware
    "blueapps.core.exceptions.middleware.AppExceptionMiddleware",
    # 自定义中间件
    # "django.middleware.locale.LocaleMiddleware",
    # 自定义国际化中间件, 替换django.middleware.locale.LocaleMiddleware
    "apps.middleware.custom_locale.CustomLocaleMiddleware",
    "apps.middlewares.CommonMid",
    "apps.middleware.user_middleware.UserLocalMiddleware",
    "apps.middleware.user_middleware.BkLogMetricsAfterMiddleware",
    # 项目空间参数注入
    "bkm_space.middleware.ParamInjectMiddleware",
    "apps.log_audit.middleware.RequestProvider",
)

# 所有环境的日志级别可以在这里配置
# LOG_LEVEL = 'INFO'

# ===============================================================================
# 静态资源配置
# ===============================================================================

# 静态资源文件(js,css等）在APP上线更新后, 由于浏览器有缓存,
# 可能会造成没更新的情况. 所以在引用静态资源的地方，都把这个加上
# Django 模板中：<script src="/a.js?v={{ STATIC_VERSION }}"></script>
# mako 模板中：<script src="/a.js?v=${ STATIC_VERSION }"></script>
# 如果静态资源修改了以后，上线前改这个版本号即可
#
STATIC_VERSION = "1.0"

DEFAULT_HTTPS_HOST = ""

if IS_K8S_DEPLOY_MODE:
    STATIC_ROOT = "static"
else:
    STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

# ==============================================================================
# SENTRY相关配置
# ==============================================================================

SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN:
    RAVEN_CONFIG = {
        "dsn": SENTRY_DSN,
    }

# ==============================================================================
# CELERY相关配置
# ==============================================================================

# CELERY 开关，使用时请改为 True，修改项目目录下的 Procfile 文件，添加以下两行命令：
# worker: python manage.py celery worker -l info
# beat: python manage.py celery beat -l info
# 不使用时，请修改为 False，并删除项目目录下的 Procfile 文件中 celery 配置
IS_USE_CELERY = True

IS_CELERY = False
IS_CELERY_BEAT = False
if "celery" in sys.argv:
    IS_CELERY = True
    if "beat" in sys.argv:
        IS_CELERY_BEAT = True

# CELERY 并发数，默认为 2，可以通过环境变量或者 Procfile 设置
CELERYD_CONCURRENCY = os.getenv("BK_CELERYD_CONCURRENCY", 2)

CELERY_TASK_SERIALIZER = "pickle"
CELERY_ACCEPT_CONTENT = ["pickle"]

# CELERY 配置，申明任务的文件路径，即包含有 @task 装饰器的函数文件

CELERY_IMPORTS = (
    "apps.log_search.tasks.bkdata",
    "apps.log_search.tasks.async_export",
    "apps.log_search.tasks.project",
    "apps.log_search.tasks.space",
    "apps.log_search.tasks.cmdb",
    "apps.log_search.handlers.index_set",
    "apps.log_search.tasks.mapping",
    "apps.log_search.tasks.no_data",
    "apps.log_databus.tasks.collector",
    "apps.log_databus.tasks.itsm",
    "apps.log_databus.tasks.bkdata",
    "apps.log_databus.tasks.archive",
    "apps.log_measure.tasks.report",
    "apps.log_extract.tasks",
    "apps.log_clustering.tasks.msg",
    "apps.log_clustering.tasks.sync_pattern",
    "apps.log_clustering.tasks.subscription",
    "apps.log_extract.tasks.extract",
)

# bk crypto sdk配置
BKPAAS_BK_CRYPTO_KEY = os.getenv("BKPAAS_BK_CRYPTO_KEY")
BKCRYPTO = {
    "SYMMETRIC_CIPHERS": {
        "default": {
            "get_key_config": "apps.utils.aes.get_default_symmetric_key_config",
        },
    },
}

# 对称加密类型
if os.getenv("BKPAAS_BK_CRYPTO_TYPE", "CLASSIC") == "SHANGMI":
    BKCRYPTO.update(
        {
            "SYMMETRIC_CIPHER_TYPE": bkcrypto_constants.SymmetricCipherType.SM4.value,
        }
    )
else:
    BKCRYPTO.update(
        {
            "SYMMETRIC_CIPHER_TYPE": bkcrypto_constants.SymmetricCipherType.AES.value,
        }
    )

# celery web worker高优先级队列配置
BK_LOG_HIGH_PRIORITY_QUEUE = os.getenv("BKAPP_HIGH_PRIORITY_QUEUE", "celery")

# OTLP Service Name
SERVICE_NAME = APP_CODE
if BKAPP_IS_BKLOG_API:
    SERVICE_NAME = APP_CODE + "_api"
if IS_CELERY:
    SERVICE_NAME = APP_CODE + "_worker"
if IS_CELERY_BEAT:
    SERVICE_NAME = APP_CODE + "_beat"

# load logging settings
if RUN_VER != "open":
    LOGGING = get_logging_config_dict(locals())
    LOGGING["handlers"]["root"]["encoding"] = "utf-8"
    LOGGING["handlers"]["component"]["encoding"] = "utf-8"
    LOGGING["handlers"]["mysql"]["encoding"] = "utf-8"
    if not IS_LOCAL:
        logging_format = {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": (
                "%(levelname)s %(asctime)s %(pathname)s %(lineno)d "
                "%(funcName)s %(process)d %(thread)d %(message)s"
                "$(otelTraceID)s $(otelSpanID)s %(otelServiceName)s"
            ),
        }
        LOGGING["formatters"]["verbose"] = logging_format

if IS_K8S_DEPLOY_MODE:
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOGGING = {
        "version": 1,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "fmt": (
                    "%(levelname)s %(asctime)s %(pathname)s %(lineno)d "
                    "%(funcName)s %(process)d %(thread)d %(message)s "
                    "$(otelTraceID)s $(otelSpanID)s %(otelServiceName)s"
                ),
            },
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "django": {"handlers": ["stdout"], "level": "INFO", "propagate": True},
            "django.server": {
                "handlers": ["stdout"],
                "level": LOG_LEVEL,
                "propagate": True,
            },
            "django.request": {
                "handlers": ["stdout"],
                "level": "ERROR",
                "propagate": True,
            },
            "django.db.backends": {
                "handlers": ["stdout"],
                "level": LOG_LEVEL,
                "propagate": True,
            },
            # the root logger ,用于整个project的logger
            "root": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": True},
            # 组件调用日志
            "component": {
                "handlers": ["stdout"],
                "level": LOG_LEVEL,
                "propagate": True,
            },
            "celery": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": True},
            # other loggers...
            # blueapps
            "blueapps": {
                "handlers": ["stdout"],
                "level": LOG_LEVEL,
                "propagate": True,
            },
            # 普通app日志
            "app": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": True},
            "bk_dataview": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": True},
            "iam": {
                "handlers": ["stdout"],
                "level": LOG_LEVEL,
                "propagate": True,
            },
            "bk_monitor": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": True},
        },
    }
    #
    # 可选，开启OT日志上报
    if os.getenv("BKAPP_OTLP_LOG", "off") == "on":
        LOGGING["handlers"]["otlp"] = {
            "class": "apps.utils.log.OTLPLogHandler",
        }
        for v in LOGGING["loggers"].values():
            v["handlers"].append("otlp")

OTLP_TRACE = os.getenv("BKAPP_OTLP_TRACE", "off") == "on"
OTLP_GRPC_HOST = os.getenv("BKAPP_OTLP_GRPC_HOST", "http://localhost:4317")
OTLP_BK_DATA_ID = int(os.getenv("BKAPP_OTLP_BK_DATA_ID", -1))
OTLP_BK_DATA_TOKEN = os.getenv("BKAPP_OTLP_BK_DATA_TOKEN", "")
OTLP_BK_LOG_TOKEN = os.getenv("BKAPP_OTLP_BK_LOG_TOKEN", "")

# ===============================================================================
# 项目配置
# ===============================================================================
BK_PAAS_HOST = os.environ.get("BK_PAAS_HOST", "")
# ESB API调用前辍
BK_PAAS_INNER_HOST = os.environ.get("BK_PAAS_INNER_HOST", BK_PAAS_HOST)
PAAS_API_HOST = os.environ.get("BK_COMPONENT_API_URL") or BK_PAAS_INNER_HOST
if "paas" in BK_PAAS_HOST:
    BK_CC_HOST = BK_PAAS_HOST.replace("paas", "cmdb")
else:
    BK_CC_HOST = "://cmdb.".join(BK_PAAS_HOST.split("://"))
BKDATA_URL = BK_PAAS_HOST
MONITOR_URL = ""
BK_DOC_URL = "https://bk.tencent.com/docs/"
BK_DOC_STATIC_URL = ""
BK_DOC_QUERY_URL = "https://bk.tencent.com/docs/document/5.1/90/3822/"
BK_FAQ_URL = "https://bk.tencent.com/s-mart/community"

# SaaS访问域名
BK_BKLOG_HOST = os.environ.get("BK_BKLOG_HOST", f"{BK_PAAS_HOST}/o/bk_log_search/")

# API访问地址，APIGW 需要用到
BK_BKLOG_API_HOST = os.getenv("BKAPP_BKLOG_API_HOST", "http://bk-log-search-api")

# 网关管理员
APIGW_MANAGERS = f'[{",".join(os.getenv("BKAPP_APIGW_MANAGERS", "admin").split(","))}]'
# 网关名称
BK_APIGW_NAME = os.getenv("BKAPP_APIGW_NAME", "bk-log-search")
# APIGW 接口地址模板
BK_API_URL_TMPL = os.getenv("BKAPP_API_URL_TMPL", f"{PAAS_API_HOST}/api/{{api_name}}/")
BK_APIGW_JWT_PROVIDER_CLS = "apps.middleware.apigw.ApiGatewayJWTProvider"
# APIGW 同步配置
SYNC_APIGATEWAY_ENABLED = os.getenv("BKAPP_SYNC_APIGATEWAY_ENABLED", "on")

# 日志归档文档
BK_ARCHIVE_DOC_URL = os.getenv("BKAPP_ARCHIVE_DOC_URL", "")

BK_ASSESSMEN_HOST_COUNT = int(os.getenv("BKAPP_ASSESSMEN_HOST_COUNT", 30))

# 日志清洗文档
BK_ETL_DOC_URL = os.getenv("BKAPP_ETL_DOC_URL", "")

# 计算平台文档地址
BK_DOC_DATA_URL = ""
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
BK_HOT_WARM_CONFIG_URL = (
    "https://www.elastic.co/guide/en/elasticsearch/reference/master/modules-cluster.html#shard-allocation-awareness"
)
BK_COMPONENT_API_URL = os.environ.get("BK_COMPONENT_API_URL")
DEPLOY_MODE = os.environ.get("DEPLOY_MODE", "")

BK_IAM_APIGATEWAY_URL = os.getenv("BKAPP_IAM_API_BASE_URL") or f"{BK_COMPONENT_API_URL}/api/bk-iam/prod/"

# ===============================================================================
# 企业版登录重定向
# ===============================================================================


def redirect_func(request):
    login_page_url = reverse("account:login_page")
    next_url = f"{login_page_url}?refer_url={request.path}"
    return HttpResponseRedirect(next_url)


# BLUEAPPS_PAGE_401_RESPONSE_FUNC = redirect_func

# bulk_request limit
BULK_REQUEST_LIMIT = int(os.environ.get("BKAPP_BULK_REQUEST_LIMIT", 500))

# redis_version
REDIS_VERSION = int(os.environ.get("BKAPP_REDIS_VERSION", 2))

# 该配置需要等待SITE_URL被patch掉才能正确配置，因此放在patch逻辑后面
GRAFANA = {
    "HOST": os.getenv("BKAPP_GRAFANA_URL", ""),
    "PREFIX": "{}grafana/".format(os.getenv("BKAPP_GRAFANA_PREFIX", SITE_URL)),
    "ADMIN": (os.getenv("BKAPP_GRAFANA_ADMIN_USERNAME", "admin"), os.getenv("BKAPP_GRAFANA_ADMIN_PASSWORD", "admin")),
    "PROVISIONING_CLASSES": [
        "apps.grafana.provisioning.Provisioning",
        "apps.grafana.provisioning.TraceProvisioning",
        "apps.grafana.provisioning.CustomESDataSourceProvisioning",
    ],
    "PERMISSION_CLASSES": ["apps.grafana.permissions.BizPermission"],
}
SKIP_FLOW_MIXIN_MIDDLEWARE_VIEW = ["CustomESDatasourceViewSet"]

# 是否可以跨业务创建索引集
Index_Set_Cross_Biz = False

CONF_PATH = os.path.abspath(__file__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(CONF_PATH))
# BASE_DIR = os.path.dirname(PROJECT_ROOT)
PYTHON_BIN = os.path.dirname(sys.executable)

INIT_SUPERUSER = []
DEBUG = False
SHOW_EXCEPTION_DETAIL = False

# 敏感参数
SENSITIVE_PARAMS = ["app_code", "app_secret", "bk_app_code", "bk_app_secret", "auth_info"]

# esb模块中esb允许转发的接口
ALLOWED_MODULES_FUNCS = {
    "apps.log_databus.views.collector_views": {"tail": "tail"},
    "apps.log_databus.views.storage_views": {"connectivity_detect": "connectivity_detect"},
}
# esb模块中转发meta接口的传发设置
META_ESB_FORWARD_CONFIG = {
    "create_es_snapshot_repository": {
        "iam_key": "cluster_id",
        "target_call": "create_es_snapshot_repository",
        "iam_actions": ["manage_es_source_v2"],
        "iam_resource": "es_source",
    },
    "modify_es_snapshot_repository": {
        "iam_key": "cluster_id",
        "target_call": "modify_es_snapshot_repository",
        "iam_actions": ["manage_es_source_v2"],
        "iam_resource": "es_source",
    },
    "delete_es_snapshot_repository": {
        "iam_key": "cluster_id",
        "target_call": "delete_es_snapshot_repository",
        "iam_actions": ["manage_es_source_v2"],
        "iam_resource": "es_source",
    },
    "verify_es_snapshot_repository": {"is_view_permission": True, "target_call": "verify_es_snapshot_repository"},
}

# resf_framework
REST_FRAMEWORK = {
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    "EXCEPTION_HANDLER": "apps.generic.custom_exception_handler",
    "SEARCH_PARAM": "keyword",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

# 是否同步业务
USING_SYNC_BUSINESS = True

# ==============================================================================
# 国际化相关配置
# ==============================================================================

# 时区
USE_TZ = True
TIME_ZONE = "Asia/Shanghai"
# 数据平台后台时区
TRANSFER_TIME_ZONE = "GMT"
DATAAPI_TIME_ZONE = "Etc/GMT-8"
BKDATA_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S%z"

# admin时间显示
DATETIME_FORMAT = "Y-m-d H:i:s"

# 翻译
USE_I18N = True
USE_L10N = True
LANGUAGE_CODE = "zh-cn"
LOCALEURL_USE_ACCEPT_LANGUAGE = True

LANGUAGES = (("en", "English"), ("zh-cn", _("简体中文")))
LANGUAGE_SESSION_KEY = "blueking_language"
LANGUAGE_COOKIE_NAME = "blueking_language"

# 设定使用根目录的locale
LOCALE_PATHS = (os.path.join(PROJECT_ROOT, "locale"),)

# ===============================================================================
# Authentication
# ===============================================================================
AUTH_USER_MODEL = "account.User"
AUTHENTICATION_BACKENDS = (
    "apps.middleware.api_token_middleware.ApiTokenAuthBackend",
    "apps.middleware.apigw.UserModelBackend",
    "blueapps.account.backends.BkJwtBackend",
    "blueapps.account.backends.UserBackend",
    "django.contrib.auth.backends.ModelBackend",
)
REDIRECT_FIELD_NAME = "c_url"
# 验证登录的cookie名
BK_COOKIE_NAME = "bk_token"

BK_SUPPLIER_ACCOUNT = os.getenv("BKAPP_BK_SUPPLIER_ACCOUNT", "")

# 数据库初始化 管理员列表
ADMIN_USERNAME_LIST = ["admin"]
SYSTEM_USE_API_ACCOUNT = "admin"

# 权限
AUTH_TYPE = "RBAC"
ACTION_PROJECT_MANAGE = "project.manage"
ACTION_PROJECT_RETRIEVE = "project.retrieve"
ACTION_INDEX_SET_RETRIEVE = "index_set.retrieve"
ACTION_INDEX_SET_MANAGE = "project.manage"
ACTION_DATABUS_MANAGE = "project.manage"
ACTION_EXTRACT_MANAGE = "project.manage"
ACTION_MEASURE = "project.manage"

# 数据平台鉴权方式
BKDATA_DATA_APP_CODE = os.getenv("BKAPP_BKDATA_DATA_APP_CODE", APP_CODE)
BKDATA_DATA_TOKEN_ID = os.getenv("BKAPP_BKDATA_DATA_TOKEN_ID", 0)
BKDATA_DATA_TOKEN = os.getenv("BKAPP_BKDATA_DATA_TOKEN", "")

# 登录窗口大小
IFRAME_HEIGHT = int(os.getenv("BKAPP_IFRAME_HEIGHT", 400))
IFRAME_WIDTH = int(os.getenv("BKAPP_IFRAME_WIDTH", 400))

# ===============================================================================
# FeatureToggle 特性开关：以内部版为准，其它版本根据需求调整
# 此配置以V4.2.X企业版做为默认配置，其它版本按需进行调整
# ===============================================================================
FEATURE_TOGGLE = {
    # 菜单：apps.log_search.handlers.meta.MetaHandler.get_menus
    # 索引集管理-数据源
    "scenario_log": os.environ.get("BKAPP_FEATURE_SCENARIO_LOG", "on"),  # 采集
    "scenario_bkdata": "on",  # 数据平台
    "scenario_es": os.environ.get("BKAPP_FEATURE_SCENARIO_ES", "on"),  # 第三方ES：依赖采集接入
    # 日志采集-字段类型
    "es_type_object": os.environ.get("BKAPP_ES_TYPE_OBJECT", "on"),
    "es_type_nested": os.environ.get("BKAPP_ES_TYPE_NESTED", "off"),
    # 是否使用数据平台token鉴权
    "bkdata_token_auth": os.environ.get("BKAPP_BKDATA_TOKEN_AUTH", "off"),
    # 提取cos链路开关
    "extract_cos": os.environ.get("BKAPP_EXTRACT_COS", "off"),
    # 采集接入ITSM
    "collect_itsm": os.environ.get("BKAPP_COLLECT_ITSM", "off"),
    # 自定义指标上报
    "monitor_report": os.environ.get("BKAPP_MONITOR_REPORT", "on"),
    "bklog_es_config": "on",
    # 一键检测工具自定义配置
    "check_collector_custom_config": "",
    # trace
    "trace": os.environ.get("BKAPP_FEATURE_TRACE", "off"),
    # 日志脱敏
    "log_desensitize": os.environ.get("BKAPP_FEATURE_DESENSITIZE", "on"),
}

SAAS_MONITOR = "bk_monitorv3"
SAAS_BKDATA = "bk_dataweb"

# 前端菜单配置
MENUS = [
    {"id": "retrieve", "name": _("检索"), "feature": "on", "icon": ""},
    {
        "id": "trace",
        "name": _("调用链"),
        "feature": FEATURE_TOGGLE["trace"],
        "icon": "",
        "children": [
            {
                "id": "trace_search",
                "name": _("调用链"),
                "feature": "on",
                "icon": "",
                "keyword": _("trace"),
                "children": [
                    {"id": "trace_list", "name": _("调用链列表"), "feature": "on", "icon": "liebiao"},
                    {"id": "trace_detail", "name": _("调用链详情"), "feature": "on", "icon": "document"},
                ],
            }
        ],
    },
    {"id": "monitor", "name": _("监控策略"), "feature": "on", "icon": ""},
    {
        "id": "dashboard",
        "name": _("仪表盘"),
        "feature": "on" if GRAFANA["HOST"] else "off",
        "icon": "",
        "children": [
            {
                "id": "dashboard_manage",
                "name": _("仪表盘"),
                "feature": "on",
                "icon": "",
                "keyword": _("仪表盘"),
                "children": [
                    {"id": "default_dashboard", "name": _("默认仪表盘"), "feature": "on", "icon": "block-shape"},
                    {"id": "create_dashboard", "name": _("新建仪表盘"), "feature": "on", "icon": "log-plus-circle-shape"},
                    {"id": "create_folder", "name": _("新建目录"), "feature": "on", "icon": "folder-fill"},
                    {"id": "import_dashboard", "name": _("导入仪表盘"), "feature": "on", "icon": "topping-fill"},
                ],
            }
        ],
    },
    {
        "id": "manage",
        "name": _("管理"),
        "feature": "on",
        "icon": "",
        "children": [
            {
                "id": "manage_access",
                "name": _("日志接入"),
                "feature": "on",
                "icon": "",
                "keyword": _("接入"),
                "children": [
                    {
                        "id": "log_collection",
                        "name": _("日志采集"),
                        "feature": "on",
                        "scenes": "scenario_log",
                        "icon": "document",
                    },
                    {
                        "id": "bk_data_collection",
                        "name": _("计算平台"),
                        "feature": FEATURE_TOGGLE["scenario_bkdata"],
                        "scenes": "scenario_bkdata",
                        "icon": "calculation-fill",
                    },
                    {
                        "id": "es_collection",
                        "name": _("第三方ES"),
                        "feature": "on",
                        "scenes": "scenario_es",
                        "icon": "elasticsearch",
                    },
                    {"id": "custom_report", "name": _("自定义上报"), "feature": "on", "icon": "menu-custom"},
                ],
            },
            {
                "id": "log_clean",
                "name": _("日志清洗"),
                "feature": "on",
                "icon": "",
                "keyword": _("清洗"),
                "children": [
                    {
                        "id": "clean_list",
                        "name": _("清洗列表"),
                        "feature": "on",
                        "scenes": "scenario_log",
                        "icon": "info-fill--2",
                    },
                    {
                        "id": "clean_templates",
                        "name": _("清洗模板"),
                        "feature": "on",
                        "icon": "moban",
                    },
                    {
                        "id": "log_desensitize",
                        "name": _("日志脱敏"),
                        "feature": FEATURE_TOGGLE["log_desensitize"],
                        "icon": "moban",
                    },
                ],
            },
            {
                "id": "log_archive",
                "name": _("日志归档"),
                "feature": "on",
                "icon": "",
                "keyword": _("归档"),
                "children": [
                    {
                        "id": "archive_repository",
                        "name": _("归档仓库"),
                        "feature": "on",
                        "icon": "new-_empty-fill",
                    },
                    {
                        "id": "archive_list",
                        "name": _("归档列表"),
                        "feature": "on",
                        "icon": "audit-fill",
                    },
                    {
                        "id": "archive_restore",
                        "name": _("归档回溯"),
                        "feature": "on",
                        "icon": "withdraw-fill",
                    },
                ],
            },
            {
                "id": "manage_extract_strategy",
                "name": _("日志提取"),
                "icon": "",
                "keyword": _("提取"),
                "feature": os.environ.get("BKAPP_FEATURE_EXTRACT", "on"),
                "children": [
                    {"id": "manage_log_extract", "name": _("日志提取配置"), "feature": "on", "icon": "cc-log"},
                    {"id": "log_extract_task", "name": _("日志提取任务"), "feature": "on", "icon": "audit-fill"},
                    {"id": "extract_link_manage", "name": _("提取链路管理"), "feature": "on", "icon": "assembly-line-fill"},
                ],
            },
            {
                "id": "log_archive",
                "name": _("日志归档"),
                "feature": "off",
                "icon": "",
                "children": [{"id": "log_archive_conf", "name": _("日志归档"), "feature": "off", "icon": ""}],
            },
            {
                "id": "trace_track",
                "name": _("全链路追踪"),
                "feature": FEATURE_TOGGLE["trace"],
                "icon": "",
                "keyword": "trace",
                "children": [
                    {
                        "id": "collection_track",
                        "name": _("采集接入"),
                        "feature": "off",
                        "scenes": "scenario_log",
                        "icon": "",
                    },
                    {
                        "id": "bk_data_track",
                        "name": _("计算平台"),
                        "feature": FEATURE_TOGGLE["scenario_bkdata"],
                        "scenes": "scenario_bkdata",
                        "icon": "cc-cabinet",
                    },
                    {
                        "id": "third_party_es_trace",
                        "name": _("第三方ES"),
                        "feature": "off",
                        "scenes": "scenario_es",
                        "icon": "",
                    },
                    {"id": "sdk_track", "name": _("SDK接入"), "feature": "off", "icon": ""},
                ],
            },
            {
                "id": "es_cluster_status",
                "name": _("ES集群"),
                "feature": "on",
                "icon": "",
                "keyword": _("集群"),
                "children": [{"id": "es_cluster_manage", "name": _("集群管理"), "feature": "on", "icon": "cc-influxdb"}],
            },
            {
                "id": "report",
                "name": _("订阅"),
                "feature": "on",
                "icon": "",
                "keyword": _("订阅"),
                "children": [{"id": "report_manage", "name": _("订阅管理"), "feature": "on", "icon": "email-shape"}],
            },
            {
                "id": "manage_data_link",
                "name": _("设置"),
                "feature": os.environ.get("BKAPP_FEATURE_DATA_LINK", "on"),
                "icon": "",
                "keyword": _("设置"),
                "children": [
                    {"id": "manage_data_link_conf", "name": _("采集链路管理"), "feature": "on", "icon": "log-setting"}
                ],
            },
        ],
    },
]

# TAM
TAM_AEGIS_KEY = os.environ.get("BKAPP_TAM_AEGIS_KEY", "")

# 任务过期天数
EXTRACT_EXPIRED_DAYS = int(os.getenv("BKAPP_EXTRACT_EXPIRED_DAYS", 1))
# windows系统名称列表
WINDOWS_OS_NAME_LIST = [
    os_name.lower() for os_name in os.getenv("BKAPP_WINDOWS_OS_NAME", "xserver,windows").split(",") if os_name
]

# 中转服务器配置
EXTRACT_FILE_PATTERN_CHARACTERS = os.getenv("BKAPP_EXTRACT_FILE_PATTERN_CHARACTERS", r"():@\[\]a-zA-Z0-9._/*-~")

EXTRACT_SAAS_STORE_DIR = os.getenv("BKAPP_EXTRACT_SAAS_STORY_DIR", "/data/app/code/USERRES")
EXTRACT_TRANSIT_EXPIRED = int(os.getenv("BKAPP_EXTRACT_TRANSIT_EXPIRED", 60 * 5))
EXTRACT_DISTRIBUTION_DIR = os.getenv("BKAPP_EXTRACT_DISTRIBUTION_DIR", "/data/bk_log_extract/distribution/")
EXTRACT_COS_DOMAIN = os.getenv("BKAPP_EXTRACT_COS_DOMAIN")
# 最大打包文件大小限制 单位为Mb 默认2048Mb
EXTRACT_PACK_MAX_FILE_SZIE_LIMIT = int(os.getenv("BKAPP_EXTRACT_PACK_MAX_FILE_SZIE_LIMIT", 2048))
# 同时下载的文件数量限制
CSTONE_DOWNLOAD_FILES_LIMIT = int(os.getenv("BKAPP_CSTONE_DOWNLOAD_FILES_LIMIT", 10))

# 过期pipeline任务超时时间设定
PIPELINE_TASKS_EXPIRED_TIME = os.getenv("BKAPP_PIPELINE_TASKS_EXPIRED_TIME", 24)
# Windows 机器JOB执行账户
WINDOWS_ACCOUNT = os.getenv("BKAPP_WINDOWS_ACCOUNT", "system")

# pipeline 配置
from pipeline.celery.settings import CELERY_QUEUES as PIPELINE_CELERY_QUEUES
from pipeline.celery.settings import CELERY_ROUTES as PIPELINE_CELERY_ROUTES

CELERY_ROUTES = PIPELINE_CELERY_ROUTES
CELERY_QUEUES = PIPELINE_CELERY_QUEUES

# ===============================================================================
# databus
# ===============================================================================
TABLE_ID_PREFIX = "bklog"
TABLE_SPACE_PREFIX = "space"

DEFAULT_OPERATOR = os.environ.get("BKAPP_ES_OPERATOR", "admin")
ES_DATE_FORMAT = os.environ.get("BKAPP_ES_DATE_FORMAT", "%Y%m%d")
ES_SHARDS_SIZE = int(os.environ.get("BKAPP_ES_SHARDS_SIZE", 30))
ES_SLICE_GAP = int(os.environ.get("BKAPP_ES_SLICE_GAP", 1440))
ES_SHARDS = int(os.environ.get("BKAPP_ES_SHARDS", 3))
ES_SHARDS_MAX = int(os.environ.get("BKAPP_ES_SHARDS_MAX", 512))
ES_REPLICAS = int(os.environ.get("BKAPP_ES_REPLICAS", 1))
ES_STORAGE_DEFAULT_DURATION = int(os.environ.get("BKAPP_ES_STORAGE_DURATION", 7))
ES_PRIVATE_STORAGE_DURATION = int(os.environ.get("BKAPP_ES_PRIVATE_STORAGE_DURATION", 365))
ES_PUBLIC_STORAGE_DURATION = int(os.environ.get("BKAPP_ES_PUBLIC_STORAGE_DURATION", 7))

# 公共集群存储容量限制
ES_STORAGE_CAPACITY = os.environ.get("BKAPP_ES_STORAGE_CAPACITY", 0)

# ES兼容：默认关闭，可以通过环境变量调整
ES_COMPATIBILITY = int(os.environ.get("BKAPP_ES_COMPATIBILITY", 0))

# scroll滚动查询：默认关闭，通过环境变量控制
FEATURE_EXPORT_SCROLL = os.environ.get("BKAPP_FEATURE_EXPORT_SCROLL", False)

# BCS
BCS_API_GATEWAY_TOKEN = os.getenv("BKAPP_BCS_API_GATEWAY_TOKEN", "")
BCS_CC_SSM_SWITCH = os.getenv("BKAPP_BCS_CC_SSM_SWITCH", "on")
BCS_APIGATEWAY_HOST = os.getenv("BKAPP_BCS_APIGATEWAY_HOST", "")
BCS_CC_APIGATEWAY_HOST = os.getenv("BKAPP_BCS_CC_APIGATEWAY_HOST", "")
BK_SSM_HOST = os.getenv("BKAPP_SSM_HOST", "http://bkssm.service.consul:5000/api/v1/auth/access-tokens")
BCS_WEB_CONSOLE_DOMAIN = os.getenv("BKAPP_BCS_WEB_CONSOLE_DOMAIN", BK_BKLOG_HOST.replace("bklog", "bcs"))
BKLOG_CONFIG_KIND = os.getenv("BKAPP_BKLOG_CONFIG_KIND", "BkLogConfig")
BKLOG_CONFIG_API_VERSION = os.getenv("BKAPP_BKLOG_CONFIG_API_VERSION", "bk.tencent.com/v1alpha1")
BKLOG_CONFIG_VERSION = os.getenv("BKAPP_BKLOG_CONFIG_VERSION", "v1alpha1")

# 是否关闭权限中心校验
IGNORE_IAM_PERMISSION = os.environ.get("BKAPP_IGNORE_IAM_PERMISSION", False)

# 是否开启过期时间处理
DEAL_RETENTION_TIME = os.getenv("BKAPP_DEAL_RETENTION_TIME", "on") == "on"

# 日志采集器配置
# 日志文件多久没更新则不再读取
COLLECTOR_CLOSE_INACTIVE = 86400
# 行日志一次上报条数
COLLECTOR_ROW_PACKAGE_COUNT = 100
# 段日志一次上报条数
COLLECTOR_SECTION_PACKAGE_COUNT = 10
# 系统支持的清洗类型
COLLECTOR_SCENARIOS = os.environ.get("BKAPP_COLLECTOR_SCENARIOS", "row,section,wineventlog").split(",")
# 接入指引
COLLECTOR_GUIDE_URL = os.environ.get("BKAPP_COLLECTOR_GUIDE_URL", "")
# ITSM接入服务ID
COLLECTOR_ITSM_SERVICE_ID = int(os.environ.get("BKAPP_COLLECTOR_ITSM_SERVICE_ID", 0))
ITSM_LOG_DISPLAY_ROLE = "LOG_SEARCH"
BLUEKING_BK_BIZ_ID = int(os.environ.get("BKAPP_BLUEKING_BK_BIZ_ID", 2))
BKMONITOR_CUSTOM_PROXY_IP = os.environ.get("BKAPP_BKMONITOR_CUSTOM_PROXY_IP", "")
# 蓝鲸监控平台的业务ID
BKMONITOR_BK_BIZ_ID = os.environ.get("BKAPP_BKMONITOR_BK_BIZ_ID", BLUEKING_BK_BIZ_ID)
TABLE_TRANSFER = os.environ.get("BKAPP_TABLE_TRANSFER", "pushgateway_transfer_metircs.base")

# ===============================================================================
# 前端上报
# ===============================================================================
# 环境代号
ENVIRONMENT_CODE = os.getenv("BKAPP_ENVIRONMENT_CODE") or APP_CODE
FRONTEND_REPORT_DATA_ID = os.environ.get("BKAPP_FRONTEND_REPORT_DATA_ID")
FRONTEND_REPORT_DATA_TOKEN = os.environ.get("BKAPP_FRONTEND_REPORT_DATA_TOKEN")
FRONTEND_REPORT_DATA_URL = os.environ.get("BKAPP_FRONTEND_REPORT_DATA_URL")

# ===============================================================================
# EsQuery
# ===============================================================================
ES_QUERY_ACCESS_LIST: list = ["bkdata", "es", "log"]
ES_QUERY_TIMEOUT = int(os.environ.get("BKAPP_ES_QUERY_TIMEOUT", 55))

# ESQUERY 查询白名单，直接透传
ESQUERY_EXTRA_WHITE_LIST = [app for app in os.getenv("BKAPP_ESQUERY_WHITE_LIST", "").split(",") if app]

ESQUERY_WHITE_LIST = [
    "bk_log_search",
    "hippogriff-4",
    "bk_bklog",
    "bk_monitor",
    "bk_bkmonitor",
    "bk_monitorv3",
    "bk_bkmonitorv3",
    "log-trace",
    "log-search-4",
    "bkmonitorv3",
    "bk-log-search",
    "gem3",
    "data",
    "dataweb",
    "bk_bcs",
    "bk_bcs_app",
    "bk-dbm",
    "bk_dbm",
    "bk-audit",
    "klc_saas",
    "paasv3cli",
    "bk_paas3",
    "kingeye-web_saas",
    "apigw-dashboard",
    "bk_apigateway",
] + ESQUERY_EXTRA_WHITE_LIST

# BK repo conf
BKREPO_ENDPOINT_URL = os.getenv("BKREPO_ENDPOINT_URL") or os.getenv("BKAPP_BKREPO_ENDPOINT_URL")
BKREPO_USERNAME = os.getenv("BKREPO_USERNAME") or os.getenv("BKAPP_BKREPO_USERNAME")
BKREPO_PASSWORD = os.getenv("BKREPO_PASSWORD") or os.getenv("BKAPP_BKREPO_PASSWORD")
BKREPO_PROJECT = os.getenv("BKREPO_PROJECT") or os.getenv("BKAPP_BKREPO_PROJECT")
BKREPO_BUCKET = os.getenv("BKREPO_BUCKET") or os.getenv("BKAPP_BKREPO_BUCKET")

BKLOG_NODE_IP = os.getenv("BK_BKLOG_NODE_IP")
BKLOG_STORAGE_ROOT_PATH = os.getenv("BK_BKLOG_STORAGE_ROOT_PATH")
BKLOG_CLOUD_ID = os.getenv("BK_BKLOG_CLOUD_ID", 0)
# custom report
CUSTOM_REPORT_TYPE = os.getenv("BKAPP_CUSTOM_REPORT_TYPE", "log")

# ===============================================================================
# Demo业务配置
# ===============================================================================
BIZ_ACCESS_URL = os.getenv("BKAPP_BIZ_ACCESS_URL", "")
DEMO_BIZ_ID = int(os.getenv("BKAPP_DEMO_BIZ_ID") or 0)
DEMO_BIZ_EDIT_ENABLED = bool(os.getenv("BKAPP_DEMO_BIZ_EDIT_ENABLED", ""))

# ==============================================================================
# 仅用于调试：可根据需要设置此环境变量关闭CORS限制
# ==============================================================================
if os.getenv("BKAPP_CORS_ENABLED", "on") == "off":
    # allow all hosts
    CORS_ORIGIN_ALLOW_ALL = True
    MIDDLEWARE += ("corsheaders.middleware.CorsMiddleware",)
    # cookies will be allowed to be included in cross-site HTTP requests
    CORS_ALLOW_CREDENTIALS = True

# ==============================================================================
# consul
# ==============================================================================
CONSUL_CLIENT_CERT_FILE_PATH = os.getenv("CONSUL_CLIENT_CERT_FILE_PATH")
CONSUL_CLIENT_KEY_FILE_PATH = os.getenv("CONSUL_CLIENT_KEY_FILE_PATH")
CONSUL_SERVER_CA_CERT_PATH = os.getenv("CONSUL_SERVER_CA_CERT_PATH")
CONSUL_HTTPS_PORT = os.getenv("CONSUL_HTTPS_PORT")

# ==============================================================================
# kafka
# ==============================================================================
# 默认kafka域名，若提供了，则不再使用metadata返回的域名。
# 用于 SaaS 没有 consul 域名解析的情况。需要手动给出
DEFAULT_KAFKA_HOST = os.getenv("BKAPP_DEFAULT_KAFKA_HOST")
DEFAULT_KAFKA_POLL_TIMEOUT = int(os.getenv("BKAPP_DEFAULT_KAFKA_POLL_TIMEOUT", 1000))

# ==============================================================================
# redis
# ==============================================================================
# 默认开启
USE_REDIS = os.getenv("BKAPP_USE_REDIS", "on") == "on"
REDIS_HOST = os.getenv("BKAPP_REDIS_HOST", os.getenv("REDIS_HOST", "127.0.0.1"))
REDIS_PORT = int(os.getenv("BKAPP_REDIS_PORT", os.getenv("REDIS_PORT", 6379)))
REDIS_PASSWD = os.getenv("BKAPP_REDIS_PASSWORD", os.getenv("REDIS_PASSWORD", ""))
REDIS_MODE = os.getenv("BKAPP_REDIS_MODE", os.getenv("BK_BKLOG_REDIS_MODE", "single"))

if REDIS_MODE == "single" and BKAPP_IS_BKLOG_API:
    REDIS_HOST = os.getenv("BK_BKLOG_REDIS_HOST", os.getenv("REDIS_HOST", ""))
    REDIS_PORT = int(os.getenv("BK_BKLOG_REDIS_PORT", os.getenv("REDIS_PORT", 6379)))
    REDIS_PASSWD = os.getenv("BK_BKLOG_REDIS_PASSWORD", os.getenv("REDIS_PASSWORD", ""))

if REDIS_MODE == "sentinel" and BKAPP_IS_BKLOG_API:
    REDIS_PASSWD = os.getenv("BK_BKLOG_REDIS_PASSWORD", os.getenv("REDIS_PASSWORD", ""))
    REDIS_SENTINEL_HOST = os.getenv("BK_BKLOG_REDIS_SENTINEL_HOST", "")
    REDIS_SENTINEL_PORT = int(os.getenv("BK_BKLOG_REDIS_SENTINEL_PORT", 26379))
    REDIS_SENTINEL_MASTER_NAME = os.getenv("BK_BKLOG_REDIS_SENTINEL_MASTER_NAME", "mymaster")
    REDIS_SENTINEL_PASSWORD = os.getenv("BK_BKLOG_REDIS_SENTINEL_MASTER_PASSWORD", "")

if REDIS_MODE == "sentinel" and not BKAPP_IS_BKLOG_API:
    REDIS_PASSWD = os.getenv("BKAPP_REDIS_PASSWORD", os.getenv("REDIS_PASSWORD", ""))
    REDIS_SENTINEL_HOST = os.getenv("BKAPP_REDIS_SENTINEL_HOST", "")
    REDIS_SENTINEL_PORT = int(os.getenv("BKAPP_REDIS_SENTINEL_PORT", 26379))
    REDIS_SENTINEL_MASTER_NAME = os.getenv("BKAPP_REDIS_SENTINEL_MASTER_NAME", "mymaster")
    REDIS_SENTINEL_PASSWORD = os.getenv("BKAPP_REDIS_SENTINEL_MASTER_PASSWORD", "")

# BKLOG 后台QOS配置
BKLOG_QOS_USE = os.getenv("BKAPP_QOS_USE", "on") == "on"
BKLOG_QOS_LIMIT_APP = [
    "bk_monitor",
    "bk_bkmonitor",
    "bk_monitorv3",
    "bk_bkmonitorv3",
    "bkmonitorv3",
]
# 窗口时间 单位分钟
BKLOG_QOS_LIMIT_WINDOW = int(os.getenv("BK_BKLOG_QOS_LIMIT_WINDOW", 5))
# 窗口内超时次数
BKLOG_QOS_LIMIT = int(os.getenv("BK_BKLOG_QOS_LIMIT", 3))
# 达到窗口内限制次数屏蔽时间 单位分钟
BKLOG_QOS_LIMIT_TIME = int(os.getenv("BK_BKLOG_QOS_LIMIT_TIME", 5))

# ajax请求401返回plain信息
IS_AJAX_PLAIN_MODE = True

# ===============
# 项目空间配置
# ===============
BKM_SPACE_API_CLASS = "apps.log_search.models.SpaceApi"

# ===============
# IP选择器配置
# ===============
BKM_IPCHOOSER_BKAPI_CLASS = "apps.utils.ipchooser.BkApi"
# 是否开启动态主机配置协议适配
ENABLE_DHCP = bool(os.getenv("BKAPP_ENABLE_DHCP", False))
# 如果手动设置了GSE版本，则使用手动设置的版本, 否则根据ENABLE_DHCP来判断, True->v2, False->v1
if os.getenv("BKAPP_GSE_VERSION"):
    GSE_VERSION = os.getenv("BKAPP_GSE_VERSION", "v1")
else:
    GSE_VERSION = "v2" if ENABLE_DHCP else "v1"

# 日志检索组件配置
# ===============
BKM_SEARCH_MODULE_BKAPI_CLASS = "apps.utils.search_module.BkApi"

# 国际化切换语言设置
BK_DOMAIN = os.getenv("BK_DOMAIN", "")
# 容器采集配置
CONTAINER_COLLECTOR_CONFIG_DIR = os.getenv("BKAPP_CONTAINER_COLLECTOR_CONFIG_DIR", "/data/etc")
# 容器下发CR全局标签
CONTAINER_COLLECTOR_CR_LABEL_BKENV: str = os.getenv("BKAPP_CONTAINER_COLLECTOR_CR_LABEL_BKENV", "")

# 是否开启RETAIN_EXTRA_JSON
RETAIN_EXTRA_JSON = os.getenv("BKAPP_RETAIN_EXTRA_JSON", "on") == "on"
# 外部版授权ITSM服务ID
ITSM_EXTERNAL_PERMISSION_SERVICE_ID = int(os.getenv("BKAPP_ITSM_EXTERNAL_PERMISSION_SERVICE_ID", 0))
# ITSM回调地址
BK_ITSM_CALLBACK_HOST = os.getenv("BKAPP_ITSM_CALLBACK_HOST", BK_BKLOG_HOST)
# 外部版PAAS地址
EXTERNAL_PAAS_HOST = os.getenv("BKAPP_EXTERNAL_PAAS_HOST", "")

# 是否使用新监控网关地址
USE_NEW_MONITOR_APIGATEWAY = os.getenv("BKAPP_USE_NEW_MONITOR_APIGATEWAY", "off").lower() == "on"

# 外部版网关密钥
EXTERNAL_APIGW_PUBLIC_KEY = os.getenv("BKAPP_EXTERNAL_APIGW_PUBLIC_KEY", "")

# ==============================================================================
# Templates
# ==============================================================================
# mako template dir

MAKO_TEMPLATE_DIR = [os.path.join(PROJECT_ROOT, directory) for directory in ["static/dist", "templates"]]

VUE_INDEX = "index.html"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(PROJECT_ROOT, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                # the context to the templates
                "django.contrib.messages.context_processors.messages",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
                "apps.utils.context_processors.mysetting",  # 自定义模版context，可在页面中使用STATIC_URL等变量
                "django.template.context_processors.i18n",
            ],
            "debug": DEBUG,
        },
    },
    {
        "BACKEND": "blueapps.template.backends.mako.MakoTemplates",
        "DIRS": [os.path.join(PROJECT_ROOT, "static/dist/")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                # the context to the templates
                "django.contrib.messages.context_processors.messages",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
                "apps.utils.context_processors.mysetting",  # 自定义模版context，可在页面中使用STATIC_URL等变量
                "django.template.context_processors.i18n",
            ]
        },
    },
]

# ==============================================================================
# Cache
# ==============================================================================
CACHES = {
    "redis": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", "PASSWORD": REDIS_PASSWD},
        "KEY_PREFIX": APP_CODE,
        "VERSION": REDIS_VERSION,
    },
    "db": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "OPTIONS": {"MAX_ENTRIES": 100000, "CULL_FREQUENCY": 10},
    },
    "dummy": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
    "locmem": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}
CACHES["default"] = CACHES["db"]
CACHES["login_db"] = CACHES["db"]

if USE_REDIS:
    CACHES["default"] = CACHES["redis"]
    CACHES["login_db"] = CACHES["redis"]

if REDIS_MODE == "sentinel" and USE_REDIS:
    DJANGO_REDIS_CONNECTION_FACTORY = "apps.utils.sentinel.SentinelConnectionFactory"
    CACHES["redis_sentinel"] = {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{REDIS_SENTINEL_MASTER_NAME}?is_master=1",
        "OPTIONS": {
            "CLIENT_CLASS": "apps.utils.sentinel.SentinelClient",
            "PASSWORD": REDIS_PASSWD,
            "SENTINELS": [
                (
                    REDIS_SENTINEL_HOST,
                    REDIS_SENTINEL_PORT,
                )
            ],
            "SENTINEL_KWARGS": {"password": REDIS_SENTINEL_PASSWORD},
        },
        "KEY_PREFIX": APP_CODE,
    }
    CACHES["default"] = CACHES["redis_sentinel"]
    CACHES["login_db"] = CACHES["redis_sentinel"]
    CACHES["redis"] = CACHES["redis_sentinel"]

# ==============================================================================
# Prometheus metrics token
PROMETHEUS_METRICS_TOKEN = os.environ.get("PROMETHEUS_METRICS_TOKEN", "")
# ==============================================================================

# ==============================================================================
# Listening Domain, 格式 http(s)://domain_name
SERVICE_LISTENING_DOMAIN = os.environ.get("SERVICE_LISTENING_DOMAIN", "")
# ==============================================================================

# ==============================================================================
# 主机标识优先级, 填入CC的标准字段, 默认 bk_host_innerip,bk_host_name,bk_host_innerip_v6
HOST_IDENTIFIER_PRIORITY = os.environ.get("HOST_IDENTIFIER_PRIORITY", "bk_host_innerip,bk_host_name,bk_host_innerip_v6")
# ==============================================================================

# ==============================================================================
# 一键检测工具开关, 默认为关
CHECK_COLLECTOR_SWITCH: bool = os.getenv("CHECK_COLLECTOR_SWITCH", "off") == "on"
# ==============================================================================

# ==============================================================================
# HTTPS 代理转发
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# ==============================================================================

# ==============================================================================
# 支持监控跨域
allowed_cors_from_settings = os.environ.get("BKAPP_ALLOWED_CORS_ORIGINS", "").split(",")
# 监控默认域名
default_allowed_bkmonitor_origin = BK_BKLOG_HOST.replace("bklog", "bkmonitor")
# 中间件CorsMiddleware中支持跨域的域名配置
CORS_ALLOWED_ORIGINS = [default_allowed_bkmonitor_origin]
for origin in allowed_cors_from_settings:
    if origin:
        CORS_ALLOWED_ORIGINS.append(origin)

#  通知中心配置
BK_NOTICE = {
    # 添加默认值防止本地调试无法启动
    "BK_API_URL_TMPL": os.environ.get("BK_API_URL_TMPL", "")
}

# 平台全局配置
BK_SHARED_RES_URL = os.environ.get("BKPAAS_SHARED_RES_URL", "")

# UNIFYQUERY 日志数据源标签
UNIFY_QUERY_DATA_SOURCE = "bklog"
# UNIFYQUERY APIGW HOST
UNIFYQUERY_APIGATEWAY_ROOT = os.getenv("BKAPP_UNIFYQUERY_APIGATEWAY_ROOT", "")

# AIDEV
# aidev的apigw地址
AIDEV_API_BASE_URL = os.getenv("BKAPP_AIDEV_API_BASE_URL", "")

# 是否启用多租户模式
ENABLE_MULTI_TENANT_MODE = os.getenv("ENABLE_MULTI_TENANT_MODE", "false").lower() == "true"
# 是否启用全局租户（blueapps依赖）
IS_GLOBAL_TENANT = True
# 为了统一多租户和非多租户场景的逻辑，默认使用system租户
DEFAULT_TENANT_ID = "system"
# 已经初始化的租户列表
INITIALIZED_TENANT_LIST = [DEFAULT_TENANT_ID]

# 预查询时间, 默认6h小时, 0代表禁用
try:
    PRE_SEARCH_SECONDS = int(os.getenv("BKAPP_PRE_SEARCH_SECONDS", 6 * 60 * 60))
except ValueError:
    PRE_SEARCH_SECONDS = 6 * 60 * 60

"""
以下为框架代码 请勿修改
"""

# celery settings
if IS_USE_CELERY:
    CELERY_ENABLE_UTC = True
    CELERYBEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

    from celery.signals import setup_logging

    @setup_logging.connect
    def config_loggers(*args, **kwags):
        from logging.config import dictConfig

        dictConfig(LOGGING)


# remove disabled apps
if locals().get("DISABLED_APPS"):
    INSTALLED_APPS = locals().get("INSTALLED_APPS", [])
    DISABLED_APPS = locals().get("DISABLED_APPS", [])

    INSTALLED_APPS = [_app for _app in INSTALLED_APPS if _app not in DISABLED_APPS]

    _keys = (
        "AUTHENTICATION_BACKENDS",
        "DATABASE_ROUTERS",
        "FILE_UPLOAD_HANDLERS",
        "MIDDLEWARE",
        "PASSWORD_HASHERS",
        "TEMPLATE_LOADERS",
        "STATICFILES_FINDERS",
        "TEMPLATE_CONTEXT_PROCESSORS",
    )

    import itertools

    for _app, _key in itertools.product(DISABLED_APPS, _keys):
        if locals().get(_key) is None:
            continue
        locals()[_key] = tuple([_item for _item in locals()[_key] if not _item.startswith(_app + ".")])


import pymysql
from django.db.backends.mysql.features import DatabaseFeatures
from django.utils.functional import cached_property


# Django 4.2+ 不再官方支持 Mysql 5.7，但目前 Django 仅是对 5.7 做了软性的不兼容改动，
# 在没有使用 8.0 特异的功能时，对 5.7 版本的使用无影响，为兼容存量的 Mysql 5.7 DB 做此 Patch
class PatchFeatures:
    """Patched Django Features"""

    @cached_property
    def minimum_database_version(self):
        if self.connection.mysql_is_mariadb:  # type: ignore[attr-defined] # noqa
            return 10, 4
        return 5, 7


DatabaseFeatures.minimum_database_version = PatchFeatures.minimum_database_version  # noqa


# 让 Django 使用 pymysql 作为 MySQLdb 的替代品
pymysql.install_as_MySQLdb()
