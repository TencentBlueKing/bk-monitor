"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re

RE_IPV4 = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")


def is_ipv4(ip: str) -> bool:
    """
    判断是否为IPv4地址
    """
    return RE_IPV4.match(ip) is not None


def transform_to_ip4(inner_ip: str) -> str:
    """
    将node-1-2-3-4转换为1.2.3.4
    """
    if not inner_ip:
        return ""
    if is_ipv4(inner_ip):
        return inner_ip
    parts = inner_ip.split("-")
    if not all(part.isdigit() and 0 <= int(part) <= 255 for part in parts[1:]):
        return ""
    return ".".join(parts[1:])
