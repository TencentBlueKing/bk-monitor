# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
import logging
import re

from django.utils import timezone

from apm.constants import ProfileApiType
from apm.core.discover.profile.base import Discover
from apm.models.profile import ProfileService

logger = logging.getLogger("apm")


class ServiceDiscover(Discover):
    """Profile 服务 + 采样类型发现"""

    LARGE_SERVICE_SIZE = 10000

    def discover(self, start_time: int, end_time: int):
        check_time = timezone.now()
        logger.info(f"[ProfileServiceDiscover] start at {check_time}")

        # Step1: 获取 service_name，type，sample_type
        result_list = (
            self.get_builder()
            .with_api_type(ProfileApiType.AGGREGATE)
            .with_time(start_time, end_time)
            .with_metric_fields("count(1)")
            .with_dimension_fields("service_name,sample_type,type")
            .with_offset_limit(0, 1000)
            .execute()
        )

        instances = []

        # Step2: 遍历 service_name，type，sample_type三个键的字典组成的列表，再从字典内去获取字典内的type，sample_type，service_name去查询数据
        if result_list:
            for result_dict in result_list:
                col_type = result_dict.get("type", "")
                sample_type = result_dict.get("sample_type", "")
                svr = result_dict.get("service_name", "")
                # 如果这三个值都没有，直接 continue，查出来的可能也是重复的数据
                if not col_type and not sample_type and not svr:
                    logger.info(
                        f"[ProfileServiceDiscover] "
                        f"when service_name: {svr} and type: {col_type} and sample_type: {sample_type} has no value, "
                        f"The queried data may be duplicated! ! !！！！"
                    )
                    continue
                sample_type_samplers = (
                    self.get_builder()
                    .with_time(start_time, end_time)
                    .with_api_type(ProfileApiType.SAMPLE)
                    .with_service_filter(svr)
                    .with_offset_limit(0, 1)
                    .with_type(col_type)
                    .with_general_filters({"sample_type": f"op_eq|{sample_type}"})
                    .execute()
                )
                if not sample_type_samplers:
                    logger.info(
                        f"[ProfileServiceDiscover] "
                        f"service_name: {svr} + type: {col_type} + sample_type: {sample_type} cannot find data！！！"
                    )
                    continue
                sampler = sample_type_samplers[0]
                if sampler:
                    period = sampler.get("period", "")
                    period_type = sampler.get("period_type", "")
                    instances.append(
                        ProfileService(
                            bk_biz_id=self.bk_biz_id,
                            app_name=self.app_name,
                            name=svr,
                            period=period,
                            period_type=period_type,
                            frequency=self._calculate_frequency(sampler),
                            data_type=col_type,
                            last_check_time=check_time,
                            sample_type=sample_type,
                            is_large=self.is_large_service(end_time, svr, col_type, sample_type),
                        )
                    )

        # Final: 保存到数据库
        self._upsert(instances, check_time)

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

    def is_large_service(self, end_timestamp, service, _type, sample_type):
        """
        判断此服务是否是大数据量应用
        如果 10 分钟内超过 10000 条数据即认为是大数据量应用
        """

        end_time = datetime.datetime.fromtimestamp(end_timestamp / 1000)
        start_time = end_time - datetime.timedelta(minutes=10)

        response = (
            self.get_builder()
            .with_api_type(ProfileApiType.AGGREGATE)
            .with_time(int(start_time.timestamp() * 1000), int(end_time.timestamp() * 1000))
            .with_metric_fields("count(*) AS count")
            .with_type(_type)
            .with_service_filter(service)
            .with_dimension_fields("service_name")
            .with_general_filters(
                {
                    "sample_type": f"op_eq|{sample_type}",
                }
            )
            .execute()
        )

        if not response:
            return False

        count = next((i.get("count", 0) for i in response if i.get("service_name") == service), None)
        return count and count > self.LARGE_SERVICE_SIZE
