# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import logging

from alarm_backends.core.storage.redis import Cache
from apm.core.discover.precalculation.consul_handler import ConsulHandler
from core.drf_resource import api

logger = logging.getLogger("apm")


class PrecalculateGrayRelease:
    KEY = "monitor:apm:pre_calculate:gray_release"

    redis_cli = Cache("cache")

    @classmethod
    def add(cls, app_id):
        """将应用添加进预计算灰度名单中"""
        cls.redis_cli.sadd(cls.KEY, app_id)

    @classmethod
    def exist(cls, app_id):
        """判断此应用是否在灰度名单中"""
        return cls.redis_cli.sismember(cls.KEY, app_id)


class DaemonTaskHandler:
    """预计算常驻任务处理类"""

    DAEMON_TASK_NAME = "daemon:apm:pre_calculate"

    @classmethod
    def execute(cls, app_id, queue=None):
        # 0. 添加到灰度名单 待未来去除
        PrecalculateGrayRelease.add(app_id)
        # 1. 刷新配置到consul
        data_id = ConsulHandler.check_update_by_app_id(app_id)
        logger.info(f"push app_id: {app_id} data_id: {data_id} to consul success")
        # 2. 触发任务
        params = {"kind": cls.DAEMON_TASK_NAME, "payload": {"data_id": str(data_id)}, "options": {}}
        if queue:
            params["options"]["queue"] = queue

        api.bmw.create_task(params)
        logger.info(f"trigger worker create param: {params} successfully")
