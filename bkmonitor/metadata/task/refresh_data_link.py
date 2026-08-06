"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from alarm_backends.core.lock.service_lock import share_lock
from metadata.task.tasks import bulk_refresh_data_link_status

logger = logging.getLogger("metadata")


@share_lock(identify="metadata_refreshDataLink", ttl=1800)
def refresh_data_link_status():
    """
    批量刷新链路组件状态及链路整体状态。
    """
    logger.info("refresh_data_link_status: cron task started, dispatch bulk refresh task")
    bulk_refresh_data_link_status.delay()
