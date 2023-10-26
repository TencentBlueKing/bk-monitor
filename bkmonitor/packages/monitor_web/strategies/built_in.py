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

from django.conf import settings
from monitor_web.strategies.loader import (
    GseDefaultAlarmStrategyLoader,
    K8sDefaultAlarmStrategyLoader,
    OsDefaultAlarmStrategyLoader,
)

__all__ = [
    "run_build_in",
]

logger = logging.getLogger(__name__)


def run_build_in(bk_biz_id: int, mode: str = "host") -> None:
    """
    执行内置操作[entry]
    :param bk_biz_id: 业务ID
    :param mode: 内置模式，host or k8s
    """
    if not settings.ENABLE_DEFAULT_STRATEGY:
        return

    if bk_biz_id <= 0:
        return

    if mode == "host":
        try:
            os_loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
            os_loader.run()
        except Exception as e:
            logger.error("create default host strategy failed")
            logger.exception(e)
        try:
            gse_loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
            gse_loader.run()
        except Exception as e:
            logger.error("create default gse strategy failed")
            logger.exception(e)
    elif mode == "k8s" and settings.BCS_API_GATEWAY_HOST:
        # 加载k8s默认告警策略
        try:
            k8s_loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
            k8s_loader.run()
        except Exception as e:
            logger.error("create default k8s strategy failed")
            logger.exception(e)
