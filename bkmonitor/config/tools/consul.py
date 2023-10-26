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

from bkmonitor.utils.ip import is_v6


def get_consul_settings():
    host = os.getenv("CONSUL_HOST") or os.environ.get("BK_MONITOR_CONSUL_HOST", "localhost")
    port = int(os.getenv("CONSUL_PORT") or os.environ.get("BK_MONITOR_CONSUL_PORT", 8500))
    https_port = int(os.environ.get("BK_CONSUL_HTTPS_PORT") or 0)

    if is_v6(host):
        host = f"[{host}]"

    if "BK_HOME" in os.environ:
        bk_home = os.environ["BK_HOME"]
        cert_file = f"{bk_home}/cert/{os.environ.get('BK_CONSUL_CLIENT_CERT_FILE', '')}"
        key_file = f"{bk_home}/cert/{os.environ.get('BK_CONSUL_CLIENT_KEY_FILE', '')}"
        cat_cert = f"{bk_home}/cert/{os.environ.get('BK_CONSUL_CA_FILE', '')}"
    else:
        cert_file = ""
        key_file = ""
        cat_cert = ""

    return host, port, https_port, cert_file, key_file, cat_cert
