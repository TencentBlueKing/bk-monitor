# -*- coding: utf-8 -*-

import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("SAAS_MYSQL_NAME", "bk_monitor_saas"),
        "USER": os.getenv("SAAS_MYSQL_USER", "root"),  # 本地数据库账号
        "PASSWORD": os.getenv("SAAS_MYSQL_PASSWORD", ""),  # 本地数据库密码
        "HOST": os.getenv("SAAS_MYSQL_HOST", "localhost"),
        "PORT": os.getenv("SAAS_MYSQL_PORT", 3306),
        "OPTIONS": {
            # Tell MySQLdb to connect with "utf8mb4" character set
            "charset": "utf8mb4",
        },
        # "CONN_MAX_AGE": 30,
        "COLLATION": "utf8mb4_general_ci",
        "TEST": {
            "NAME": os.getenv("SAAS_MYSQL_NAME", "bk_monitor_saas") + "_test",
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_general_ci",
        },
    },
    "monitor_api": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("API_MYSQL_NAME", "bk_monitor_api"),
        "USER": os.getenv("API_MYSQL_USER", "root"),  # 本地数据库账号
        "PASSWORD": os.getenv("API_MYSQL_PASSWORD", ""),  # 本地数据库密码
        "HOST": os.getenv("API_MYSQL_HOST", "localhost"),
        "PORT": os.getenv("API_MYSQL_PORT", 3306),
        "OPTIONS": {
            # Tell MySQLdb to connect with "utf8mb4" character set
            "charset": "utf8mb4",
        },
        # "CONN_MAX_AGE": 30,
        "COLLATION": "utf8mb4_general_ci",
        "TEST": {
            "NAME": os.getenv("API_MYSQL_NAME", "bk_monitor_api") + "_test",
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_general_ci",
        },
    },
}

# 如果只安装了 Redis，没有安装 RabbitMQ，可设置这个变量
# BROKER_URL = CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/0"

BROKER_URL = os.getenv("BROKER_URL")

SKIP_IAM_PERMISSION_CHECK = True

DEBUG = True
