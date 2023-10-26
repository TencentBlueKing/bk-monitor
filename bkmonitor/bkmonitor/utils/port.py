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


def merge_port(ports):
    """
    合并多个端口，组成端口段
    :param ports: 端口列表 [1080, 1081, 1082]
    :type ports: list
    :return: 端口段列表 ["1080-1090", "1099"]
    :rtype: list
    """
    ports = [int(port) for port in ports if str(port).isdigit()]
    ports.sort()

    port_ranges = []
    start_port = None
    end_port = None
    for index, port in enumerate(ports):
        # 开始记录新的端口段
        if not start_port:
            start_port = port
            end_port = port
        # 连续端口直接记录
        elif port - 1 == end_port:
            end_port = port
        else:
            if start_port == end_port:
                port_ranges.append(str(start_port))
            else:
                port_ranges.append("{}-{}".format(start_port, end_port))
            start_port = port
            end_port = port

    if start_port:
        if start_port == end_port:
            port_ranges.append(str(start_port))
        else:
            port_ranges.append("{}-{}".format(start_port, end_port))

    return port_ranges
