"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os

from config import kms


def _env_list(prefix: str) -> list[str]:
    result = []
    while (value := os.getenv(f"{prefix}{len(result)}")) is not None:
        result.append(value)
    return result


def get_influxdb_init_settings() -> tuple[list[str], str | None, str, str]:
    """InfluxDB hosts written into metadata on first init; port stays None when the deployment provides none."""
    ip_list = _env_list("BK_INFLUXDB_BKMONITORV3_IP") or _env_list("INFLUXDB_BKMONITORV3_IP")
    port = os.getenv("BK_MONITOR_INFLUXDB_PORT") or os.getenv("INFLUXDB_BKMONITORV3_PORT")
    user = os.getenv("BK_MONITOR_INFLUXDB_USER") or os.getenv("INFLUXDB_BKMONITORV3_USER", "")
    password = os.getenv("BK_MONITOR_INFLUXDB_PASSWORD") or os.getenv("INFLUXDB_BKMONITORV3_PASS", "")
    if kms.enabled():
        user = kms.value("influxdb", "default", "username")
        password = kms.value("influxdb", "default", "password")
    return ip_list, port, user, password
