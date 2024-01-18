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
"""
influxdb连通性
"""


import logging

from .checker import CheckerRegister
from .utils import check_port_list_status
from metadata.models import InfluxDBHostInfo, InfluxDBClusterInfo

register = CheckerRegister.influxdb
logger = logging.getLogger("self_monitor")


@register.status()
def influxdb_proxy_status(manager, result):
    """influxdb状态"""
    try:
        influxdb_host_list = InfluxDBClusterInfo.objects.values_list("host_name", flat=True)
        ip_port_list = (
            InfluxDBHostInfo.objects.filter(host_name__in=influxdb_host_list)
            .extra(select={"ip": "domain_name"})
            .values("ip", "port")
        )
        result_list = check_port_list_status("influxdb", ip_port_list)
        result.ok(value=result_list)
    except Exception as e:
        logger.exception(e)
        result.fail(message=str(e))
