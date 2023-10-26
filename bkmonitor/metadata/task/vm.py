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

import json
import logging
import time

from django.conf import settings

from alarm_backends.core.lock.service_lock import share_lock
from metadata.models.vm.constants import (
    QUERY_VM_SPACE_UID_CHANNEL_KEY,
    QUERY_VM_SPACE_UID_LIST_KEY,
)
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


@share_lock(identify="metadata__refresh_query_vm_space_list")
def refresh_query_vm_space_list():
    """刷新查询 vm 的空间列表

    因为是白名单控制，添加完白名单，然后再刷入到 redis
    """
    logger.info("start refresh query vm space list")
    # 获取空间列表
    space_uid_list = getattr(settings, "QUERY_VM_SPACE_UID_LIST", [])
    if not space_uid_list:
        logger.warning("no space_uid from QUERY_VM_SPACE_UID_LIST")
        return
    # 推送到 redis
    if not isinstance(space_uid_list, list):
        logger.error("space_uid type is not list")
        return
    # 推送到 redis
    RedisTools.push_space_to_redis(QUERY_VM_SPACE_UID_LIST_KEY, space_uid_list)
    # 进行 publish
    curr_time = {"time": time.time()}
    RedisTools.publish(QUERY_VM_SPACE_UID_CHANNEL_KEY, [json.dumps(curr_time)])

    logger.info("refresh query vm space list successfully")
