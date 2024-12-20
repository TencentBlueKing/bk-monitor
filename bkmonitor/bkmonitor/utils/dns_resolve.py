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

import dns.resolver

logger = logging.getLogger(__name__)


def resolve_domain(domain):
    """解析域名得到IP列表"""
    try:
        resolve_items = dns.resolver.resolve(domain)
    except Exception as e:
        logger.warning("domain({}) dns resolve error: {}".format(domain, e))
        resolve_items = []
    return [item.address for item in resolve_items]
