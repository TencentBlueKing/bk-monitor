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
gse data 进程状态
"""


import logging

from .checker import CheckerRegister
from .utils import check_port_list_status, get_ip_and_port

register = CheckerRegister.gse_data
logger = logging.getLogger("self_monitor")


@register.status()
def gse_data_status(manager, result):
    """Gse_data状态"""
    try:
        ip_port_list = get_ip_and_port("gse-data")
        result_list = check_port_list_status("gse_data", ip_port_list)
        result.ok(value=result_list)
    except BaseException as e:
        logger.exception(e)
        result.fail(message=str(e))
