# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import json

from django import template
from six import string_types

from bkmonitor.utils.port import merge_port

register = template.Library()


@register.filter(name="port_range")
def port_range(ports):
    """
    合并多个端口为端口段
    :param ports: 端口列表
    :return:
    """
    if isinstance(ports, string_types):
        ports = json.loads(ports)

    port_ranges = merge_port(ports)
    return "[{}]".format(",".join(port_ranges))
