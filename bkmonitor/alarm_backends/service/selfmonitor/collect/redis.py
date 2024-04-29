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

import os

from typing_extensions import Literal

from core.prometheus import metrics
from utils.redis_client import redis_cli


class RedisMetricCollectReport(object):
    @staticmethod
    def get_redis_info():
        info = redis_cli.info()
        return info

    def get_node_type_and_mastername(
        self, prefix: str = "BK_MONITOR", prefer_type: Literal["sentinel", "standalone"] = "sentinel"
    ):
        node_type = os.environ.get(f"{prefix}_REDIS_MODE", prefer_type)
        if node_type == "sentinel":
            mastername = os.environ[f"{prefix}_REDIS_SENTINEL_MASTER_NAME"]
        else:
            mastername = ""
        return node_type, mastername

    def collect_report_redis_metric_data(
        self, prefix: str = "BK_MONITOR", prefer_type: Literal["sentinel", "standalone"] = "sentinel"
    ):
        info = self.get_redis_info()
        node_type, mastername = self.get_node_type_and_mastername(prefix, prefer_type)

        metrics.ACTIVE_DEFRAG_RUNNING.labels(node_type=node_type, mastername=mastername, role=info["role"]).set(
            info["active_defrag_running"]
        )

        metrics.AOF_ENABLED.labels(node_type=node_type, mastername=mastername, role=info["role"]).set(
            info["aof_enabled"]
        )

        # metrics.xxx   ...

        metrics.report_all()
