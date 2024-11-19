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

from alarm_backends.core.lock.service_lock import share_lock
from metadata import models
from metadata.task.tasks import bulk_refresh_data_link_status

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
    bulk_refresh_data_link_status.delay(bkbase_rt_records)  # task_id
