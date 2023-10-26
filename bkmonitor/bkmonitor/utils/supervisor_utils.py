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


import re

import six.moves.xmlrpc_client
from django.conf import settings
from supervisor.xmlrpc import SupervisorTransport


def get_supervisor_client():
    match = re.match(
        r"(?:(?P<protocol>\w+)://)?(?P<host>[^:/]+)?(?::(?P<port>\d+))?$",
        settings.SUPERVISOR_SERVER,
    )
    if match:
        group_dict = match.groupdict()
        url = "{protocol}://{host}:{port}".format(
            protocol=group_dict.get("protocol") or "http",
            host=group_dict.get("host") or "127.0.0.1",
            port=group_dict.get("port") or "9001",
        )
    else:
        url = settings.SUPERVISOR_SERVER

    return six.moves.xmlrpc_client.ServerProxy(
        "http://127.0.0.1",
        transport=SupervisorTransport(
            settings.SUPERVISOR_USERNAME,
            settings.SUPERVISOR_PASSWORD,
            serverurl=url,
        ),
    )
