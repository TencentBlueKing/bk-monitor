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
from typing import List, Optional

from django.conf import settings

from alarm_backends.cluster import Cluster, TargetType

logger = logging.getLogger("alarm_backends")

_cluster: Optional[Cluster] = None
_cluster_cache_timestamp = 0
CACHE_UPDATE_INTERVAL = 120


def get_cluster() -> Cluster:
    """
    获取集群配置
    """
    global _cluster, _cluster_cache_timestamp
    if _cluster is None:
        _cluster = Cluster(
            name=settings.ALARM_BACKEND_CLUSTER_NAME,
            code=settings.ALARM_BACKEND_CLUSTER_CODE,
            tags={},
        )
    elif _cluster_cache_timestamp < time.time() - CACHE_UPDATE_INTERVAL:
        try:
            _cluster.get_match_config()
        except (TypeError, ValueError, KeyError) as e:
            logger.exception("get cluster config error: %s", e)
    _cluster_cache_timestamp = time.time() // CACHE_UPDATE_INTERVAL * CACHE_UPDATE_INTERVAL
    return _cluster


def filter_bk_biz_ids(bk_biz_ids: List[int]) -> List[int]:
    """
    过滤出集群需要处理的业务ID
    """
    return get_cluster().filter(TargetType.biz, bk_biz_ids)


def get_cluster_bk_biz_ids() -> List[int]:
    """
    获取集群需要处理的业务ID
    """
    from alarm_backends.core.cache.cmdb import BusinessManager

    return filter_bk_biz_ids(BusinessManager.keys())
