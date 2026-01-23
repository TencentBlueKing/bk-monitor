"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from blueapps.conf.validators import EnvValidator

from config import RUN_VER

from .default import *  # noqa

EnvValidator(RUN_VER).validate()

# 本地开发环境
RUN_MODE = "DEVELOP"

# 自定义本地环境日志级别
# from blueapps.conf.log import set_log_level # noqa
# LOG_LEVEL = "DEBUG"
# LOGGING = set_log_level(locals())

# APP本地静态资源目录
STATIC_URL = "/static/"

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "webpack"),
]

# APP静态资源目录url
# REMOTE_STATIC_URL = '%sremote/' % STATIC_URL

# Celery 消息队列设置 RabbitMQ
# BROKER_URL = 'amqp://guest:guest@localhost:5672//'
# Celery 消息队列设置 Redis
BROKER_URL = "redis://localhost:6379/0"

DEBUG = True

# 本地开发数据库设置
# USE FOLLOWING SQL TO CREATE THE DATABASE NAMED APP_CODE
# SQL: CREATE DATABASE `framework_py` DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci; # noqa: E501
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": APP_CODE,  # noqa
        "USER": "root",
        "PASSWORD": "",
        "HOST": "localhost",
        "PORT": "3306",
    },
    "monitor_api": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": APP_CODE,  # noqa
        "USER": "root",
        "PASSWORD": "",
        "HOST": "localhost",
        "PORT": "3306",
    },
}
