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
import os

from config.tools.environment import PAAS_VERSION


def get_saas_mysql_settings():
    # MYSQL_是PaaSV3, DB_是PaaSV2环境变量
    name = os.getenv("GCS_MYSQL_NAME") or os.getenv("MYSQL_NAME") or os.getenv("DB_NAME", "bk_monitorv3")
    user = os.getenv("GCS_MYSQL_USER") or os.getenv("MYSQL_USER") or os.getenv("DB_USERNAME", "root")
    password = os.getenv("GCS_MYSQL_PASSWORD") or os.getenv("MYSQL_PASSWORD") or os.getenv("DB_PASSWORD", "")
    host = os.getenv("GCS_MYSQL_HOST") or os.getenv("MYSQL_HOST") or os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("GCS_MYSQL_PORT") or os.getenv("MYSQL_PORT") or os.getenv("DB_PORT", "3306"))

    host = os.getenv("BKAPP_SAAS_DB_HOST") or os.getenv("BK_PAAS_MYSQL_HOST") or host
    port = os.getenv("BKAPP_SAAS_DB_PORT") or os.getenv("BK_PAAS_MYSQL_PORT") or port
    user = os.getenv("BKAPP_SAAS_DB_USER") or os.getenv("BK_PAAS_MYSQL_USER") or user
    password = os.getenv("BKAPP_SAAS_DB_PASSWORD") or os.getenv("BK_PAAS_MYSQL_PASSWORD") or password

    return name, host, port, user, password


def get_backend_mysql_settings():
    if PAAS_VERSION == "V3":
        name = os.getenv("MYSQL_NAME") or os.getenv("DB_NAME", "bk_monitorv3")
    else:
        name = "bkmonitorv3_alert"

    user = os.getenv("MYSQL_USER") or os.getenv("DB_USERNAME", "root")
    password = os.getenv("MYSQL_PASSWORD") or os.getenv("DB_PASSWORD", "")
    host = os.getenv("MYSQL_HOST") or os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT") or os.getenv("DB_PORT", "3306"))

    name = os.getenv("BK_MONITOR_MYSQL_NAME") or os.getenv("BKAPP_BACKEND_DB_NAME") or name
    host = (
        os.getenv("BK_MONITOR_MYSQL_HOST")
        or os.getenv("BKAPP_BACKEND_DB_HOST")
        or os.getenv("BK_PAAS_MYSQL_HOST")
        or host
    )
    port = int(
        os.getenv("BK_MONITOR_MYSQL_PORT")
        or os.getenv("BKAPP_BACKEND_DB_PORT")
        or os.getenv("BK_PAAS_MYSQL_PORT")
        or port
    )
    user = (
        os.getenv("BK_MONITOR_MYSQL_USER")
        or os.getenv("BKAPP_BACKEND_DB_USERNAME")
        or os.getenv("BK_PAAS_MYSQL_USER")
        or user
    )
    password = (
        os.getenv("BK_MONITOR_MYSQL_PASSWORD")
        or os.getenv("BKAPP_BACKEND_DB_PASSWORD")
        or os.getenv("BK_PAAS_MYSQL_PASSWORD")
        or password
    )

    return name, host, port, user, password


def get_grafana_mysql_settings():
    name = os.getenv("BKAPP_GRAFANA_DB_NAME") or "bk_monitorv3_grafana"
    user = os.getenv("BKAPP_GRAFANA_DB_USER")
    password = os.getenv("BKAPP_GRAFANA_DB_PASSWORD")
    host = os.getenv("BKAPP_GRAFANA_DB_HOST")
    port = int(os.getenv("BKAPP_GRAFANA_DB_PORT") or 0)
    return name, host, port, user, password
