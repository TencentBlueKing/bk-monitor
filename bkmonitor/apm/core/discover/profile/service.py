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
import re

from django.utils import timezone

from apm.constants import ProfileApiType
from apm.core.discover.profile.base import Discover
from apm.models.profile import ProfileService

logger = logging.getLogger("apm")


class ServiceDiscover(Discover):
    # 获取service的前10条数据进行计算信息
    # TODO
    #  1. 目前实现可能是临时方案 后续支持SQL查询时使用distinct+group_by实现
    #  2. Bkbase 暂不支持时间过滤 service 接口所以这里查询了所有出现过的 service

    @classmethod
    def get_name(cls):
        return "service_discover"

    def discover(self, start_time: int, end_time: int):
        """发现profile服务"""
        check_time = timezone.now()
        logger.info(f"[ProfileServiceDiscover] start at {check_time}")

        # Step1: 查询所有出现过的服务
        response = self.get_builder().with_api_type(ProfileApiType.SERVICE_NAME).execute()
        service_names = list({i["service_name"] for i in response if i.get("service_name")})
        logger.info(f"[ProfileServiceDiscover] found {len(service_names)} services: {service_names}")

        instances = []
        for svr in service_names:
            # Step2: 按照此服务下出现过的 type
            types = self.get_builder().with_api_type(ProfileApiType.COL_TYPE).with_service_filter(svr).execute()
            if not types:
                logger.warning(f"[ProfileServiceDiscover] could not found types of service: {svr}")
                continue

            logger.info(f"[ProfileServiceDiscover] found {len(types)} types: {types}")
            for col_type in types:
                col_type = col_type.get("type")
                if not col_type:
                    logger.warning(f"[ProfileServiceDiscover] query {svr} types successfully, but return a none type")
                    continue

                # Step3: 获取此 type 下的一条数据
                type_samplers = (
                    self.get_builder()
                    .with_time(start_time, end_time)
                    .with_api_type(ProfileApiType.SAMPLE)
                    .with_service_filter(svr)
                    .with_offset_limit(0, 1)
                    .with_type(col_type)
                    .execute()
                )
                if not type_samplers:
                    logger.info(f"[ProfileServiceDiscover] receive a empty sample of {svr}")
                    continue
                sampler = type_samplers[0]
                period = sampler.get("period")
                period_type = sampler.get("period_type")
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
                    )
                )

        # Final: 保存到数据库
        self._upsert(instances, check_time)

    def _upsert(self, instances, check_time):
        """创建/更新到数据库"""
        update_instances = []
        create_instances = []

        # 去重依据: service_name + data_type
        exist_mapping = {
            (i.name, i.data_type): i.id
            for i in ProfileService.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        }

        for instance in instances:
            key = (instance.name, instance.data_type)
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
            update_instances, fields=["period", "period_type", "frequency", "last_check_time", "updated_at"]
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
