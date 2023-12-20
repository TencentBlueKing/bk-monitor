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
import urllib.parse
from typing import Optional

import requests
from django.conf import settings

from alarm_backends.core.cluster import get_cluster
from bkmonitor.utils.cipher import transform_data_id_to_token
from core.prometheus.tools import get_metric_agg_gateway_url

logger = logging.getLogger("bkmonitor")


def get_agg_gateway_url() -> Optional[str]:
    """获取聚合网关 URL"""
    # TODO: agg_gateway_url should include scheme part
    agg_gateway_url = get_metric_agg_gateway_url()
    if not agg_gateway_url:
        logger.warning("agg gateway url is missing in settings, skipping report to bk-data")
        return
    return f"http://{agg_gateway_url}/metrics"


def register_report_task():
    """注册聚合网关上报任务"""
    agg_gateway_url = get_metric_agg_gateway_url()
    if not agg_gateway_url:
        return
    url = urllib.parse.urljoin(f"http://{agg_gateway_url}", "report")
    report_url = f"http://{settings.CUSTOM_REPORT_DEFAULT_PROXY_IP[0]}:4318"

    job_infos = [
        {
            "job": settings.DEFAULT_METRIC_PUSH_JOB,
            "data_id": settings.CUSTOM_REPORT_DEFAULT_DATAID,
            "filter": {
                "exclude_labels": {"job": [settings.OPERATION_STATISTICS_METRIC_PUSH_JOB]},
            },
        },
        {
            "job": settings.OPERATION_STATISTICS_METRIC_PUSH_JOB,
            "data_id": settings.STATISTICS_REPORT_DATA_ID,
            "filter": {
                "include_labels": {"job": [settings.OPERATION_STATISTICS_METRIC_PUSH_JOB]},
            },
        },
    ]

    for job_info in job_infos:
        token = transform_data_id_to_token(metric_data_id=job_info["data_id"])
        params = {
            "name": f"bkmonitor {job_info['job']}",
            "type": "prometheus",
            "job": get_cluster().name,
            "interval": 60,
            "timeout": 10,
            "concurrent": 5,
            "size_limit": 10485760,
            "address": report_url,
            "auth": {"header": {"X-BK-Token": token}},
            **job_info["filter"],
        }
        requests.post(url=url, json=params)
