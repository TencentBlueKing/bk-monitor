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
import time
from concurrent.futures import ThreadPoolExecutor

from django.db import transaction

from alarm_backends.core.lock.service_lock import share_lock
from alarm_backends.service.scheduler.app import app
from metadata import models
from metadata.models import BkBaseResultTable
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.service import get_data_link_component_status

logger = logging.getLogger("metadata")


@share_lock(identify="metadata_refreshDataLink", ttl=1800)
def refresh_data_link_status():
    """
    刷新链路状态（各组件状态+整体状态）
    """
    logger.info("refresh_data_link_status: cron task started,start to refresh data_link status")
    bkbase_rt_records = models.BkBaseResultTable.objects.all()

    table_id_list = models.ResultTable.objects.filter(
        table_id__in=bkbase_rt_records.values_list("monitor_table_id", flat=True), is_enable=True, is_deleted=False
    ).values_list("table_id", flat=True)

    bkbase_rt_records = models.BkBaseResultTable.objects.filter(monitor_table_id__in=table_id_list)
    logger.info("refresh_data_link_status: now try to bulk_refresh_data_link_status,len->[%s] ", len(bkbase_rt_records))
    bulk_refresh_data_link_status.delay(bkbase_rt_records)


@app.task(ignore_result=True, queue="celery_long_task_cron")
def bulk_refresh_data_link_status(bkbase_rt_records):
    """
    并发刷新链路状态
    """
    logger.info("manage_refresh_data_link_status:start to refresh data_link status")
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(_refresh_data_link_status, bkbase_rt_records)


def _refresh_data_link_status(bkbase_rt_record: BkBaseResultTable):
    """
    刷新链路状态（各组件状态+整体状态）
    """

    # 0. 获取基本信息
    start_time = time.time()  # 记录开始时间
    bkbase_data_id_name = bkbase_rt_record.bkbase_data_name
    data_link_name = bkbase_rt_record.data_link_name
    bkbase_rt_name = bkbase_rt_record.bkbase_rt_name
    logger.info(
        "_refresh_data_link_status: data_link_name->[%s],bkbase_data_id_name->[%s],bkbase_rt_name->[%s]",
        data_link_name,
        bkbase_data_id_name,
        bkbase_rt_name,
    )
    data_link_ins = models.DataLink.objects.get(data_link_name=data_link_name)
    data_link_strategy = data_link_ins.data_link_strategy
    logger.info(
        "_refresh_data_link_status: data_link_name->[%s] data_link_strategy->[%s]", data_link_name, data_link_strategy
    )

    # 1. 刷新数据源状态
    try:
        with transaction.atomic():
            data_id_config = models.DataIdConfig.objects.get(name=bkbase_data_id_name)
            data_id_status = get_data_link_component_status(
                kind=data_id_config.kind, namespace=data_id_config.namespace, component_name=data_id_config.name
            )
            # 当和DB中的数据不一致时，才进行变更
            if data_id_config.status != data_id_status:
                logger.info(
                    "_refresh_data_link_status:data_link_name->[%s],data_id_config status->[%s] is different "
                    "with exist record,will change to->[%s]",
                    data_link_name,
                    data_id_config.status,
                    data_id_status,
                )
                data_id_config.status = data_id_status
                data_id_config.data_link_name = data_link_name
                data_id_config.save()
    except models.DataIdConfig.DoesNotExist:
        logger.error(
            "_refresh_data_link_status: data_link_name->[%s],data_id_config->[%s] does not exist",
            data_link_name,
            bkbase_data_id_name,
        )

    # 2. 根据链路套餐（类型）获取该链路需要的组件资源种类
    components = models.DataLink.STRATEGY_RELATED_COMPONENTS.get(data_link_strategy)
    all_components_ok = True

    # 3. 遍历链路关联的所有类型资源，查询并刷新其状态
    for component in components:
        try:
            with transaction.atomic():
                component_ins = component.objects.get(name=bkbase_rt_name)
                component_status = get_data_link_component_status(
                    kind=component_ins.kind, namespace=component_ins.namespace, component_name=component_ins.name
                )
                logger.info(
                    "_refresh_data_link_status: data_link_name->[%s],component->[%s],kind->[%s],status->[%s]",
                    data_link_name,
                    component_ins.name,
                    component_ins.kind,
                    component_status,
                )
                if component_status != DataLinkResourceStatus.OK.value:
                    all_components_ok = False
                # 和DB中数据不一致时，才进行更新操作
                if component_ins.status != component_status:
                    component_ins.status = component_status
                    component_ins.save()
                    logger.info(
                        "_refresh_data_link_status: data_link_name->[%s],component->[%s],kind->[%s],"
                        "status updated to->[%s]",
                        data_link_name,
                        component.name,
                        component.kind,
                        component_status,
                    )

        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "_refresh_data_link_status: data_link_name->[%s],component->[%s],kind->[%s] refresh failed,error->[%s]",
                data_link_name,
                component.name,
                component.kind,
                e,
            )

    # 如果所有的component_ins状态都为OK，那么BkBaseResultTable也应设置为OK，否则为PENDING
    if all_components_ok:
        bkbase_rt_record.status = DataLinkResourceStatus.OK.value
    else:
        bkbase_rt_record.status = DataLinkResourceStatus.PENDING.value
    with transaction.atomic():
        bkbase_rt_record.save()
    logger.info(
        "_refresh_data_link_status: data_link_name->[%s],all_components_ok->[%s],status updated to->[%s]",
        data_link_name,
        all_components_ok,
        bkbase_rt_record.status,
    )

    logger.info(
        "_refresh_data_link_status: data_link_name->[%s] refresh status finished,cost time->[%s]",
        data_link_name,
        time.time() - start_time,
    )
