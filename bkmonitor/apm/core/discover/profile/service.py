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
import logging

from django.utils import timezone

from apm.constants import ProfileApiType, ProfileQueryType
from apm.core.discover.profile.base import Discover
from apm.core.handlers.profile.query import ProfileQueryBuilder
from apm.models.profile import ProfileService

logger = logging.getLogger("apm")


class ServiceDiscover(Discover):
    # 获取service的前10条数据进行计算信息
    # TODO 目前实现可能是临时方案 后续支持SQL查询时使用distinct+group_by实现
    SERVICE_LIMIT_OFFSET = 10

    @classmethod
    def get_name(cls):
        return "service_discover"

    def discover(self, start_time, end_time):
        """发现profile服务"""
        check_time = timezone.now()
        logger.info(f"[ProfileServiceDiscover] start at {check_time}")

        # Step1: 查询出现过的服务
        builder = ProfileQueryBuilder.from_table(self.result_table_id, self.bk_biz_id, self.app_name).with_time(
            start_time, end_time
        )
        response = builder.copy().with_api_type(ProfileApiType.SERVICE_NAME).with_type(ProfileQueryType.CPU).execute()
        service_names = list({i["service_name"] for i in response if i.get("service_name")})
        logger.info(f"[ProfileServiceDiscover] found {len(service_names)} services: {service_names}")

        instances = []
        exist_keys = []
        # Step2: 按照服务获取前n条sampler
        for svr in service_names:
            samplers = (
                builder.copy()
                .with_api_type(ProfileApiType.SAMPLE)
                .with_service_filter(svr)
                .with_offset_limit(0, self.SERVICE_LIMIT_OFFSET)
                .execute()
            )

            for sample in samplers:
                key = (sample.get("period"), sample.get("period_type"))
                if key in exist_keys:
                    continue

                period = sample.get("period")
                period_type = sample.get("period_type")
                instances.append(
                    ProfileService(
                        bk_biz_id=self.bk_biz_id,
                        app_name=self.app_name,
                        name=svr,
                        period=period,
                        period_type=period_type,
                        frequency=self._calculate_frequency(period, period_type),
                        data_type=self._parse_data_type(period_type),
                        last_check_time=check_time,
                    )
                )

        # Final: 保存到数据库
        self._upsert(instances, check_time)

    def _upsert(self, instances, check_time):
        """创建/更新到数据库"""
        update_instances = []
        create_instances = []

        exist_mapping = {
            (i.name, i.period, i.period_type, i.frequency, i.data_type): i.id
            for i in ProfileService.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        }

        for instance in instances:
            key = (instance.name, instance.period, instance.period_type, instance.frequency, instance.data_type)
            if key in exist_mapping:
                logger.info(f"[ProfileDiscover] update service key -> {key}")
                update_instances.append(exist_mapping[key])
            else:
                logger.info(f"[ProfileDiscover] create service key -> {key}")
                create_instances.append(instance)

        # 同一个service_name可能会有多个记录
        ProfileService.objects.bulk_create(create_instances)
        ProfileService.objects.filter(id__in=update_instances).update(last_check_time=check_time)
        logger.info(f"[ProfileDiscover] service update {len(update_instances)} create: {len(create_instances)}")

        self.clear_if_overflow(ProfileService)
        self.clear_expired(ProfileService)

    @classmethod
    def _calculate_frequency(cls, period, period_type):
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
            raise ValueError("Invalid period_type")

        # 计算采样频率 单位: Hz
        sampling_frequency = 1e9 / period_in_ns

        return sampling_frequency

    @classmethod
    def _parse_data_type(cls, period_type):
        # cpu/nanoseconds -> cpu
        if not period_type:
            return None

        return period_type.split("/")[0]
