"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import asyncio
import logging
import selectors
from collections import defaultdict
from dataclasses import dataclass, field
from typing import ClassVar, List, Tuple, Type

import arrow
import requests
from django.apps import apps
from django.conf import settings
from django.utils.encoding import force_str
from prometheus_client.parser import text_string_to_metric_families
from prometheus_client.samples import Sample

from bkmonitor.utils.consul import BKConsul
from bkmonitor.utils.custom_report_tools import custom_report_tool
from metadata.models import DataSource

logger = logging.getLogger(__name__)

GlobalConfig = apps.get_model("bkmonitor.GlobalConfig")


@dataclass
class Deformer:
    """Transfer 原生指标转换器"""

    KEY: ClassVar[str]

    sample: Sample

    def get_dimensions(self) -> dict:
        raise NotImplementedError


@dataclass
class PipelineBackendHandledTotal(Deformer):
    """transfer_pipeline_backend_handled_total"""

    KEY = "transfer_pipeline_backend_handled_total"

    def get_dimensions(self) -> dict:
        """ """
        return {"data_id": self.sample.labels.get("id"), "pipeline": self.sample.labels.get("pipeline")}


@dataclass
class PipelineFrontendHandledTotal(Deformer):
    """transfer_pipeline_frontend_handled_total"""

    KEY = "transfer_pipeline_frontend_handled_total"

    def get_dimensions(self) -> dict:
        """ """
        return {"data_id": self.sample.labels.get("id"), "pipeline": self.sample.labels.get("pipeline")}


DEFAULT_DEFORMERS = [PipelineBackendHandledTotal, PipelineFrontendHandledTotal]


@dataclass
class TransferMetricHelper:
    """Transfer 指标小助手"""

    consul_client: BKConsul = field(default_factory=BKConsul)
    # transfer 运营指标变形器列表，由运营侧指定其关注内容
    deformers: List[Type["Deformer"]] = field(default_factory=lambda: DEFAULT_DEFORMERS)
    metrics: list = field(default_factory=list)

    TARGET_HOST_TERM: ClassVar[str] = "service_host"
    TARGET_PORT_TERM: ClassVar[str] = "service_port"
    KEY_PREFIX: ClassVar[str] = f"{settings.APP_CODE}_{settings.PLATFORM}_{settings.ENVIRONMENT}/service/v1/"
    TARGET_LABEL: ClassVar[str] = "transfer_cluster"

    def __post_init__(self):
        self.deformers_map = {x.KEY: x for x in self.deformers}

    def ingest_keys(self, _prefix: str, keys: List[str]) -> List[Tuple[str, str]]:
        """消化原始 keys 提供 session 级的 transfer 实例数据"""
        targets = defaultdict(dict)
        for key in keys:
            parts = key[len(_prefix) :].split("/")
            parts = [x for x in parts if x]

            # 存在 data_id\influx_db 等其他 key 内容，忽略
            if not parts or not parts[1] == "session":
                continue

            transfer_cluster_name = parts[0]
            session = parts[2]
            _field = parts[3]
            if _field not in [self.TARGET_HOST_TERM, self.TARGET_PORT_TERM]:
                continue

            targets[f"{transfer_cluster_name}:{session}"][_field] = key

        """
        返回值示例
            [
               (
                   "bkmonitorv3_ieod_production/service/v1/foo/session/bar/service_host",
                   "bkmonitorv3_ieod_production/service/v1/foo/session/bar/service_port"
               ),
               (
                   "bkmonitorv3_ieod_production/service/v1/foo/session/baz/service_host",
                   "bkmonitorv3_ieod_production/service/v1/foo/session/baz/service_port"
               ),
            ]
        """
        return [(x[self.TARGET_HOST_TERM], x[self.TARGET_PORT_TERM]) for x in targets.values()]

    def fetch_target_url(self, key_pair: Tuple[str, str]) -> str:
        """通过 consul key 组装成采集目标 URL"""
        value_pair = []
        # key_pair: (xxx/service_host, xxxx/service_port)
        for key in key_pair:
            _, result = self.consul_client.kv.get(key)
            value_pair.append(force_str(result["Value"]))

        target_url = f"http://{':'.join(value_pair)}/metrics"
        return target_url

    def get_coarse_keys(self):
        """拉取所需的粗粒度 key"""

        # Q: 为什么不逐级拉取 transfer cluster 的数据？
        # A: 首先，Consul.kv.get() 中 recurse 参数无法在此处生效(原因未知)
        #    其次，一口气拉取所有可能的 key，统一在内存中处理可以减少和 consul 的交互次数(有 cluster 和 session 两级)
        _, coarse_keys = self.consul_client.kv.get(self.KEY_PREFIX, keys=True)
        coarse_keys = coarse_keys or []

        logger.debug("Got %s keys", len(coarse_keys))
        return coarse_keys

    async def fetch_metrics(self, _target_url: str):
        """拉取各个节点的 metrics 数据"""

        _metrics = defaultdict(list)
        logger.debug(_target_url)
        with requests.get(_target_url) as resp:
            for family in text_string_to_metric_families(resp.text):
                for sample in family.samples:
                    # 仅保留我们关心的运营指标，其余内容忽略
                    if sample.name not in self.deformers_map.keys():
                        continue

                    _metrics[sample.name].append(sample)

        return _metrics

    async def _fetch(self, loop, target_keys: list):
        tasks = []

        for _target in target_keys:
            target_url = self.fetch_target_url(_target)

            task = loop.create_task(self.fetch_metrics(target_url))
            tasks.append(task)

        if not tasks:
            logger.warning("Failed to get target key from consul[%s]", self.KEY_PREFIX)
            return

        finished, _ = await asyncio.wait(tasks)
        timestamp = arrow.now().timestamp * 1000
        for metrics in finished:
            result = metrics.result()
            if result:
                self.metrics.extend(self._transfer(timestamp, result.values()))

    def _transfer(self, timestamp: int, samples_list: List[Sample]) -> List[dict]:
        """将 Prometheus Sample 转换成目标数据格式"""
        data = []
        for samples in samples_list:
            for sample in samples:
                deformer = self.deformers_map[sample.name](sample)
                data.append(
                    {
                        # 指标，必需项
                        "metrics": {sample.name: sample.value},
                        # 来源标识
                        "target": self.TARGET_LABEL,
                        "timestamp": timestamp,
                        "dimension": deformer.get_dimensions(),
                    }
                )

        return data

    def fetch(self):
        """从 transfer 节点获取运营指标"""
        target_keys = self.ingest_keys(self.KEY_PREFIX, self.get_coarse_keys())
        logger.debug("Got %s target keys", len(target_keys))

        selector = selectors.SelectSelector()
        loop = asyncio.SelectorEventLoop(selector)

        try:
            loop.run_until_complete(self._fetch(loop, target_keys))
        finally:
            loop.close()

        logger.debug("Got metrics: %s", len(self.metrics))

    def report(self):
        """将已加工过的数据上报到链路"""
        try:
            bk_data_id = int(GlobalConfig.objects.get(key="STATISTICS_REPORT_DATA_ID").value)
        except GlobalConfig.DoesNotExist:
            bk_data_id = settings.STATISTICS_REPORT_DATA_ID

        report_tool = custom_report_tool(bk_data_id)
        report_tool.send_data_by_http(self.metrics, access_token=DataSource.objects.get(bk_data_id=bk_data_id).token)
        logger.info("已经发送了 %s 条 Transfer 运营数据到 data_id: %s 中", len(self.metrics), bk_data_id)
