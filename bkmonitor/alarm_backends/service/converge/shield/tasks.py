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

from alarm_backends.core.cluster import get_cluster_bk_biz_ids
from alarm_backends.service.converge.shield.shield_obj import AlertShieldObj
from alarm_backends.service.scheduler.app import app
from alarm_backends.service.scheduler.tasks import perform_sharding_task
from bkmonitor.models import Shield
from bkmonitor.utils import time_tools

logger = logging.getLogger("fta_action.converge")


def check_and_send_shield_notice():
    """
    检查当前屏蔽配置，发送屏蔽开始/结束通知
    """

    # 获取目标任务列表
    shield_configs = Shield.objects.filter(
        is_enabled=True, is_deleted=False, failure_time__gte=time_tools.now(), bk_biz_id__in=get_cluster_bk_biz_ids()
    ).only("id", "bk_biz_id")

    # 根据集群配置过滤出需要处理的屏蔽配置
    bk_biz_ids = set(get_cluster_bk_biz_ids())
    target_ids = []
    for shield_config in shield_configs:
        if shield_config.bk_biz_id in bk_biz_ids:
            target_ids.append(shield_config.id)

    perform_sharding_task(target_ids, do_check_and_send_shield_notice, num_per_task=10)


# sharded task
@app.task(ignore_result=True, queue="celery_cron")
def do_check_and_send_shield_notice(ids):
    shield_configs = list(
        Shield.objects.filter(
            id__in=ids, is_enabled=True, is_deleted=False, failure_time__gte=time_tools.now()
        ).values()
    )

    logger.info("[屏蔽通知] 开始处理。拉取到 {} 条屏蔽配置等待检测".format(len(shield_configs)))
    # TODO: 确定是否需要加锁，防止重复通知
    notice_config_ids = set()
    for shield_config in shield_configs:
        shield_obj = AlertShieldObj(shield_config)
        config_id = shield_obj.config["id"]
        try:
            start_notice_result, end_notice_result = shield_obj.check_and_send_notice()
        except Exception as e:
            logger.info("[屏蔽通知] shield({}) 处理异常，原因: {}".format(config_id, e))
            continue
        if start_notice_result:
            notice_config_ids.add(config_id)
            logger.info("[屏蔽通知] shield({}) 发送屏蔽开始通知，发送结果: {}".format(config_id, start_notice_result))
        if end_notice_result:
            notice_config_ids.add(config_id)
            logger.info("[屏蔽通知] shield({}) 发送屏蔽结束通知，发送结果: {}".format(config_id, end_notice_result))

    logger.info("[屏蔽通知] 结束处理。有 {} 条屏蔽告警发送了通知".format(len(notice_config_ids)))
    return notice_config_ids
