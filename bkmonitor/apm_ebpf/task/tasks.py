# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
import time

from alarm_backends.core.cache.key import APM_EBPF_DISCOVER_LOCK
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.scheduler.app import app
from apm_ebpf.apps import logger
from apm_ebpf.handlers.deepflow import DeepflowHandler
from bkm_space.api import SpaceApi
from bkm_space.define import SpaceTypeEnum
from core.errors.alarm_backends import LockError


@app.task(ignore_result=True, queue="celery_cron")
def handler(bk_biz_id):
    start = time.time()
    DeepflowHandler(bk_biz_id).check_installed()
    logger.info(f"[ebpf_discover_cron] end. bk_biz_id: {bk_biz_id} cost: {time.time() - start}")


def ebpf_discover_cron():
    """
    定时寻找安装DeepFlow的业务
    """
    interval = 10
    slug = datetime.datetime.now().minute % interval
    spaces = SpaceApi.list_spaces()

    business = [i for i in spaces if i.space_type_id == SpaceTypeEnum.BKCC.value]
    logger.info(f"[ebpf_discover_cron] business length: {len(business)} slug: {slug}")
    # 目前只遍历业务下集群
    for index, biz in enumerate(business):
        try:
            with service_lock(APM_EBPF_DISCOVER_LOCK, bk_biz_id=biz.bk_biz_id):
                if index % interval == slug:
                    logger.info(f"[ebpf_discover_cron] start. bk_biz_id: {biz.bk_biz_id}")
                    handler.delay(biz.bk_biz_id)
        except LockError:
            logger.info(f"skipped: [ebpf_discover_cron] already running. bk_biz_id: {biz.bk_biz_id}")
            continue
