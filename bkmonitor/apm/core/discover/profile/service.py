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
import re
import time

from django.utils import timezone

from apm.constants import ProfileApiType
from apm.core.discover.profile.base import Discover
from apm.models.profile import ProfileService
from apm.models.topo import TopoNode
from apm.utils.report_event import EventReportHelper
from constants.apm import TelemetryDataType

logger = logging.getLogger("apm")


class ServiceDiscover(Discover):
    """Profile 服务 + 采样类型发现"""

    MAX_DIMENSION_COMBINATION_LIMIT = 3000
    LARGE_SERVICE_SIZE = 10000

    def discover(self, start_time: int, end_time: int) -> None:
        started_at = time.monotonic()
        check_time = timezone.now()
        logger.info(f"[ProfileServiceDiscover] start at {check_time}")

        # 按服务、采样类型聚合，同一窗口的计数同时用于大数据量判定。
        result_list = (
            self.get_builder()
            .with_api_type(ProfileApiType.AGGREGATE)
            .with_time(start_time, end_time)
            .with_metric_fields("count(*) AS count")
            .with_dimension_fields("service_name,sample_type,type")
            .with_offset_limit(0, self.MAX_DIMENSION_COMBINATION_LIMIT)
            .execute()
        )

        if len(result_list) >= self.MAX_DIMENSION_COMBINATION_LIMIT:
            EventReportHelper.report(
                f"应用：({self.bk_biz_id}){self.app_name} Profile 服务 sample 发现超过了上限({self.MAX_DIMENSION_COMBINATION_LIMIT}), 需要人工介入"
            )

        instances: list[ProfileService] = []
        sample_queries: int = 0
        try:
            for result in result_list:
                data_type = result.get("type", "")
                sample_type = result.get("sample_type", "")
                service_name = result.get("service_name", "")
                if not (data_type or sample_type or service_name):
                    continue

                sample_queries += 1
                samples = (
                    self.get_builder()
                    .with_time(start_time, end_time)
                    .with_api_type(ProfileApiType.SAMPLE)
                    .with_service_filter(service_name)
                    .with_offset_limit(0, 1)
                    .with_type(data_type)
                    .with_general_filters({"sample_type": f"op_eq|{sample_type}"})
                    .execute()
                )
                # 聚合命中不代表样本查询仍有结果，只有拿到样本才写入服务和心跳。
                if not samples or not samples[0]:
                    logger.info(
                        "[ProfileServiceDiscover] sample missing: bk_biz_id=%s app_name=%s "
                        "service_name=%s type=%s sample_type=%s",
                        self.bk_biz_id,
                        self.app_name,
                        service_name,
                        data_type,
                        sample_type,
                    )
                    continue

                sample = samples[0]
                instances.append(
                    ProfileService(
                        bk_biz_id=self.bk_biz_id,
                        app_name=self.app_name,
                        name=service_name,
                        period=sample.get("period", ""),
                        period_type=sample.get("period_type", ""),
                        frequency=self._calculate_frequency(sample),
                        data_type=data_type,
                        last_check_time=check_time,
                        sample_type=sample_type,
                        is_large=result["count"] > self.LARGE_SERVICE_SIZE,
                    )
                )
        finally:
            # 包括超时与接口异常，记录本轮规模和已执行查询数，便于评估串行查询容量。
            logger.info(
                "[ProfileServiceDiscover] query progress: bk_biz_id=%s app_name=%s combinations=%s "
                "sample_queries=%s samples_loaded=%s elapsed_seconds=%.3f",
                self.bk_biz_id,
                self.app_name,
                len(result_list),
                sample_queries,
                len(instances),
                time.monotonic() - started_at,
            )

        # Final: 保存到数据库
        self._upsert(instances, check_time)
        service_names: set[str] = {instance.name for instance in instances if instance.name}
        TopoNode.upsert_telemetry_nodes(
            self.bk_biz_id,
            self.app_name,
            TelemetryDataType.PROFILING.value,
            service_names,
            {
                "category": TelemetryDataType.PROFILING.value,
                "kind": TelemetryDataType.PROFILING.value,
                "predicate_value": None,
                "service_language": None,
                "instance": {},
            },
        )
        # 截断时只发布已证实有样本的服务，不宣称其余节点已完整检查。
        TopoNode.touch_heartbeat(
            self.bk_biz_id,
            self.app_name,
            TelemetryDataType.PROFILING.value,
            {name: end_time // 1000 for name in service_names},
            int(time.time()),
            check_all_services=len(result_list) < self.MAX_DIMENSION_COMBINATION_LIMIT,
        )

    def _upsert(self, instances, check_time):
        """创建/更新到数据库"""
        update_instances = []
        create_instances = []

        # 去重依据: service_name + data_type + sample_type
        exist_mapping = {
            (i.name, i.data_type, i.sample_type): i.id
            for i in ProfileService.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        }

        for instance in instances:
            key = (instance.name, instance.data_type, instance.sample_type)
            if key in exist_mapping:
                logger.info(f"[ProfileDiscover] update service key -> {key}")
                instance.id = exist_mapping[key]
                instance.last_check_time = check_time
                instance.updated_at = timezone.now()
                update_instances.append(instance)
            else:
                logger.info(f"[ProfileDiscover] create service key -> {key}")
                create_instances.append(instance)

        ProfileService.objects.bulk_create(create_instances)
        ProfileService.objects.bulk_update(
            update_instances, fields=["period", "period_type", "frequency", "last_check_time", "is_large", "updated_at"]
        )
        logger.info(f"[ProfileDiscover] service update {len(update_instances)} create: {len(create_instances)}")

        self.clear_if_overflow(ProfileService)
        self.clear_expired(ProfileService)

    @classmethod
    def _calculate_frequency(cls, sample):
        sample_type = sample.get("type")
        period_type = sample.get("period_type")
        period = sample.get("period")
        if not period or not period_type or not sample_type:
            return None

        period = int(period)
        value = sample.get("value")
        if value is None:
            return None

        if sample_type == "cpu":
            # CPU采样频率计算 -> period

            # 将周期转换为纳秒
            if period_type == "cpu/nanoseconds":
                period_in_ns = period
            elif period_type == "cpu/microseconds":
                period_in_ns = period * 1e3
            elif period_type == "cpu/milliseconds":
                period_in_ns = period * 1e6
            elif period_type == "cpu/seconds":
                period_in_ns = period * 1e9
            else:
                logger.error(f"[ProfileServiceDiscover] Invalid period_type: {period_type}")
                return None

            return 1e9 / period_in_ns
        if sample_type in ["thread", "space", "contentions", "trace"] and re.match(r"\w+\/count", period_type):
            # 其他xxx/count类型 频率计算为 value / (period * duration(s))
            duration_nanos = sample.get("duration_nanos")
            if duration_nanos:
                return int(value) / (period * (duration_nanos / 1e9))

        return None
