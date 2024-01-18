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
tsdb_proxy连通性
"""


import logging
import os
import re
import subprocess

import requests
from django.conf import settings

from .checker import CheckerRegister

register = CheckerRegister.tsdb_proxy
logger = logging.getLogger("self_monitor")


@register.status()
def tsdb_proxy_status(manager, result):
    """tsdb-proxy状态"""
    try:
        script_dir = os.path.join(
            settings.BASE_DIR, "alarm_backends", "service", "selfmonitor", "healthz", "checker", "shell_script"
        )
        # 运行对应脚本，获取到对应的ip地址列表文件
        ip_script = os.path.join(script_dir, "get_tsdb_proxy_ips.sh")
        # gse的部署端口
        port_script = os.path.join(script_dir, "get_tsdb_proxy_port.sh")
        get_proxy_status(ip_script, port_script)
        result.ok("ok")
    except Exception as e:
        logger.exception(e)
        result.fail(message=str(e))


def get_proxy_status(ip_script, port_script):
    # 运行对应脚本，获取到对应的ip地址列表文件
    ips_output = subprocess.check_output(["/bin/bash", "-c", ip_script])
    port_output = int(subprocess.check_output(["/bin/bash", "-c", port_script]))
    # ip地址的正则模式
    ip_pattern = re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    )
    # 读取对应的文件获得ip列表
    error_ips = []
    for i in ips_output.split():
        line = i.strip()
        # line不能为空，且满足ip地址的正则匹配
        if line != "" and ip_pattern.match(line):
            url = "http://{}:{}/ping".format(line, port_output)
            status_response = requests.get(url)
            if status_response.status_code < 200 or status_response.status_code >= 300:
                error_ips.append(line)
        else:
            failed_message = "{ip} is not a valid ip address".format(ip=line)
            raise Exception(failed_message)

    # 判断是否存在状态不正常的IP
    if len(error_ips) > 0:
        raise Exception("\n".join(error_ips))
