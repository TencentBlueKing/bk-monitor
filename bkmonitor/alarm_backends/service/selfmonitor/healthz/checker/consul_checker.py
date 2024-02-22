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


import logging

from bkmonitor.utils import consul

from .checker import CheckerRegister

register = CheckerRegister.consul
logger = logging.getLogger("self_monitor")


@register.status()
def consul_status(manager, result, ttl=60):
    """Consul 状态"""
    client_ready = False
    try:
        client = consul.BKConsul()
        client_ready = True
        result.ok(client.session.create(ttl=ttl))
    except Exception as err:
        logger.exception(err)
        result.fail(str(err))
    finally:
        if client_ready:
            client.http.session.close()
