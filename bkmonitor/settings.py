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

import monkey
from config.tools.environment import ENVIRONMENT, ROLE

try:
    import MySQLdb
except ImportError:
    import pymysql
    pymysql.install_as_MySQLdb()


# settings加载顺序 config.default -> blueapps.patch -> config.{env} -> config.role.{role}

patch_module = ['json', 'shutil', 'furl', 're']
patch_target = {_module: None for _module in patch_module}

# patch backend celery beat only
if "redbeat.RedBeatScheduler" in sys.argv:
    patch_target.update({"redbeat.schedulers": None})
monkey.patch_all(patch_target)

# append packages to sys.path
sys.path.append(os.path.join(os.getcwd(), "packages"))

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
        print('[Django Settings] Set config from env: {} = "{}"'.format(settings_key, value))


# 多人开发时，无法共享的本地配置可以放到新建的 local_settings.py 文件中
# 并且把 local_settings.py 加入版本管理忽略文件中
if RUN_MODE == "DEVELOP":
    try:
        from local_settings import *  # noqa
    except ImportError:
        pass
