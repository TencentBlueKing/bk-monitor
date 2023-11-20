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
from dataclasses import dataclass
from typing import Generator, Optional
from urllib.parse import quote_plus

import arrow
import requests
from django.conf import settings
from prometheus_client.exposition import CONTENT_TYPE_LATEST, generate_latest
from prometheus_client.metrics_core import Metric
from prometheus_client.parser import text_string_to_metric_families
from prometheus_client.registry import CollectorRegistry

from bkmonitor.utils.cipher import transform_data_id_to_token
from bkmonitor.utils.custom_report_tools import custom_report_tool
from core.prometheus.tools import get_metric_agg_gateway_url
from metadata.models import DataSource

logger = logging.getLogger("bkmonitor")


def get_agg_gateway_url() -> Optional[str]:
    """获取聚合网关 URL"""
    # TODO: agg_gateway_url should include scheme part
    agg_gateway_url = get_metric_agg_gateway_url()
    if not agg_gateway_url:
        logger.warning("agg gateway url is missing in settings, skipping report to bk-data")
        return

    return f"http://{agg_gateway_url}/metrics"


def fetch_aggregated_metrics(target_gateway_url: str) -> Generator[Metric, None, None]:
    """获取聚合网关数据"""

    response = requests.get(target_gateway_url)
    response.raise_for_status()

    return text_string_to_metric_families(response.text)


def is_job_meet(wanted_job: str, labels: dict, allow_job_absent: bool) -> bool:
    """判断当前 Job 是否符合需求"""
    sending = False
    job = labels.pop("job", None)
    # 当前数据存在两种可能：
    # job 缺失，但上层表示可以忽略
    if job is None:
        if allow_job_absent:
            sending = True
    # job 未缺失，那么过滤掉不想要的条目
    elif job == wanted_job:
        sending = True

    return sending


def push_agg_data_via_json(wanted_job: Optional[str] = None, parallel: bool = True, allow_job_absent: bool = False):
    """
    拉取聚合网关数据并以 JSON 格式上报到数据链路
    :param wanted_job: 想要获取的数据的 job 标签
    :param parallel: 是否并行
    :param allow_job_absent: 是否允许 job 标签缺失
    """
    target_gateway_url = get_agg_gateway_url()
    if target_gateway_url is None:
        return

    metrics = fetch_aggregated_metrics(target_gateway_url)
    timestamp = arrow.now().floor("minute").timestamp * 1000
    fetched_data_count = skipped_data_count = 0
    reporting_datas = []
    for metric in metrics:
        for sample in metric.samples:
            fetched_data_count += 1

            sending = is_job_meet(wanted_job, sample.labels, allow_job_absent)
            if not sending:
                skipped_data_count += 1
                continue

            reporting_datas.append(
                {
                    # 指标，必需项
                    "metrics": {sample.name: sample.value},
                    # 来源标识
                    "target": target_gateway_url,
                    # 数据时间，精确到毫秒，非必需项
                    "timestamp": timestamp,
                    "dimension": sample.labels,
                }
            )

    # 根据不同的 job 获取不同的 dataID
    data_id = settings.JOB_DATAID_MAP.get(wanted_job)
    report_tool = custom_report_tool(data_id)
    access_token = DataSource.objects.get(bk_data_id=data_id).token
    try:
        report_tool.send_data_by_http(reporting_datas, access_token=access_token, parallel=parallel)
    except Exception:
        logger.exception("failed to send data from agg_gateway")

    logger.info(
        f"Aggregated data[{wanted_job}] send done. Fetched({fetched_data_count}) -> Sent({len(reporting_datas)}) + "
        f"Skipped({skipped_data_count})"
    )


def get_custom_report_default_hostname() -> str:
    """获取默认的自定义上报主机名"""
    if settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN:
        return settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN[0]

    return settings.CUSTOM_REPORT_DEFAULT_PROXY_IP[0]


@dataclass
class JobFilterCollector:
    """构造的用于过滤 Job 的 Collector"""

    wanted_job: str
    allow_job_absent: bool
    agg_gateway_url: str

    def __hash__(self):
        return hash(self.wanted_job)

    def collect(self):
        """返回 Metrics"""

        for metric in fetch_aggregated_metrics(self.agg_gateway_url):
            # 用于标记当前 metric 是否属于预期的 Job
            own_job_label: bool = False
            for sample in metric.samples:
                sending = is_job_meet(self.wanted_job, sample.labels, self.allow_job_absent)
                if not sending:
                    continue

                # 当前 metric 中任意一个 sample 满足条件则认为 metric 符合条件
                own_job_label = True
                break

            if own_job_label:
                logger.debug("Metric<%s> collected, waiting for pushing...", metric.name)
                yield metric


def push_agg_data_via_prometheus(wanted_job: str, push_job: str, allow_job_absent: bool = False):
    """
    拉取聚合网关数据并以 Prometheus 格式上报到数据链路
    :param wanted_job: 想要获取的数据的 job 标签
    :param push_job: 上报的 job 标签
    :param allow_job_absent: 是否允许 job 标签缺失
    """
    agg_gateway_url = get_agg_gateway_url()
    if agg_gateway_url is None:
        return

    # 根据不同的 job 获取不同的 dataID
    data_id = settings.JOB_DATAID_MAP.get(wanted_job)
    token = transform_data_id_to_token(metric_data_id=data_id)

    # 想要将序列化后的 metrics 转成 text 的通常做法是构造一个 Registry
    # 参考： https://groups.google.com/g/prometheus-users/c/pDeQJ-ph7ng/m/rPDArR3OAwAJ
    _collector = JobFilterCollector(wanted_job, allow_job_absent, agg_gateway_url)
    _registry = CollectorRegistry()
    _registry.register(_collector)

    # TODO: 端口是否应该改从配置中读取？
    target_url = f"http://{get_custom_report_default_hostname()}:4318/metrics/job/{quote_plus(push_job)}"
    data = generate_latest(_registry)
    try:
        response = requests.put(
            url=target_url,
            timeout=60,
            # 由于我们本来就需要注入 headers，与其定义新的 handler，不如直接将 push_to_gateway 拆开写更简单直接
            headers={"Content-Type": CONTENT_TYPE_LATEST, "X-BK-TOKEN": token},
            data=data,
        )
    except Exception:
        logger.exception(f"Failed push aggregated data to {target_url} with data size: {len(data)}")
        return

    if response.status_code != 200:
        logger.error(
            f"Failed push aggregated data to {target_url} with data size: {len(data)}, "
            f"response from bk-collector: {response.status_code}, {response.text}"
        )
        return

    logger.info(f"Aggregated {wanted_job} data<size:{len(data)}> send done via Prometheus format")
