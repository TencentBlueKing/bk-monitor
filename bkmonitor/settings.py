"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import os
import sys

import monkey
from config.tools.environment import ENVIRONMENT, ROLE

try:
    import MySQLdb  # noqa
except ImportError:
    import pymysql

    pymysql.install_as_MySQLdb()


# settings加载顺序 config.default -> blueapps.patch -> config.{env} -> config.role.{role}

patch_module = ["json", "shutil", "furl", "re"]
patch_target = {_module: None for _module in patch_module}

# patch backend celery beat only
if "redbeat.RedBeatScheduler" in sys.argv:
    patch_target.update({"redbeat.schedulers": None})
monkey.patch_all(patch_target)

# append packages to sys.path
sys.path.append(os.path.join(os.getcwd(), "packages"))
# append ai agent sdk to sys.path
sys.path.append(os.path.join(os.getcwd(), "ai_agent", "sdk"))

DJANGO_CONF_MODULE = "config.{env}".format(
    env={"development": "dev", "testing": "stag", "production": "prod"}.get(ENVIRONMENT)
)

# 加载角色配置
try:
    _module = __import__(f"config.role.{ROLE}", globals(), locals(), ["*"])
except ImportError as e:
    logging.exception(e)
    raise ImportError("Could not import config '{}' (Is it on sys.path?): {}".format(f"config.role.{ROLE}", e))

for _setting in dir(_module):
    if _setting == _setting.upper():
        locals()[_setting] = getattr(_module, _setting)

# create settings by env
SETTING_ENV_PREFIX = "BKAPP_SETTINGS_"
for key, value in list(os.environ.items()):
    upper_key = key.upper()
    if upper_key.startswith(SETTING_ENV_PREFIX):
        settings_key = upper_key.replace(SETTING_ENV_PREFIX, "")
        locals()[settings_key] = value
        print(f'[Django Settings] Set config from env: {settings_key} = "{value}"')


# 多人开发时，无法共享的本地配置可以放到新建的 local_settings.py 文件中
# 并且把 local_settings.py 加入版本管理忽略文件中
if RUN_MODE == "DEVELOP":  # noqa
    try:
        from local_settings import *  # noqa
    except ImportError:
        pass

# Django 4.2+ 不再官方支持 Mysql 5.7，但目前 Django 仅是对 5.7 做了软性的不兼容改动，
# 在没有使用 8.0 特异的功能时，对 5.7 版本的使用无影响，为兼容存量的 Mysql 5.7 DB 做此 Patch
try:
    from django.db.backends.mysql.features import DatabaseFeatures
    from django.utils.functional import cached_property

    class PatchFeatures:
        """Patched Django Features"""

        @cached_property
        def minimum_database_version(self):
            if self.connection.mysql_is_mariadb:  # type: ignore[attr-defined] # noqa
                return 10, 4
            return 5, 7

    DatabaseFeatures.minimum_database_version = PatchFeatures.minimum_database_version  # noqa
except ImportError:
    # 如果导入失败，可能是 Django 版本不支持或配置未加载，忽略错误
    pass

# 融合 bk-monitor-base Django 配置：主项目优先，仅补齐缺失项
try:
    from bk_monitor_base.config.django import merge_django_settings

    merge_django_settings(globals())

    # 暂时排除metadata app
    globals()["INSTALLED_APPS"] = tuple(app for app in globals()["INSTALLED_APPS"] if app != "bk_monitor_base.metadata")

    from bk_monitor_base.infras.constant import OLD_MONITOR_BACKEND_DB_NAME, OLD_MONITOR_SAAS_DB_NAME

    # 数据库配置初始化
    globals()["DATABASES"][OLD_MONITOR_SAAS_DB_NAME] = globals()["DATABASES"]["default"].copy()
    globals()["DATABASES"][OLD_MONITOR_BACKEND_DB_NAME] = globals()["DATABASES"]["monitor_api"].copy()
except ImportError as e:
    print(f"import bk-monitor-base and load settings failed, error: {e}")
