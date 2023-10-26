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
from typing import Tuple


def get_es7_settings(fta=True) -> Tuple[str, int, int, str, str]:
    if fta:
        host = os.getenv("BKAPP_FTA_ES7_HOST") or os.getenv("BK_FTA_ES7_HOST") or "es7.service.consul"
        rest_port = int(os.getenv("BKAPP_FTA_ES7_REST_PORT") or os.getenv("BK_FTA_ES7_REST_PORT") or "9200")
        transport_port = int(
            os.getenv("BKAPP_FTA_ES7_TRANSPORT_PORT") or os.getenv("BK_FTA_ES7_TRANSPORT_PORT") or "9301"
        )
        user = os.getenv("BKAPP_FTA_ES7_USER") or os.getenv("BK_FTA_ES7_USER") or ""
        password = os.getenv("BKAPP_FTA_ES7_PASSWORD") or os.getenv("BK_FTA_ES7_PASSWORD") or ""
    else:
        host = os.getenv("BK_MONITOR_ES7_HOST", "es7.service.consul")
        rest_port = int(os.getenv("BK_MONITOR_ES7_REST_PORT", "9200"))
        transport_port = int(os.getenv("BK_MONITOR_ES7_TRANSPORT_PORT", "9301"))
        user = os.getenv("BK_MONITOR_ES7_USER", "")
        password = os.getenv("BK_MONITOR_ES7_PASSWORD", "")
    return host, rest_port, transport_port, user, password
