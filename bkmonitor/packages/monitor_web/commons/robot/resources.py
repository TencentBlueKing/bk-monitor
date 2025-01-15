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
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework import serializers

from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.time_tools import hms_string
from monitor_web.commons.robot.constant import (
    LATEST_FETCH_TIME_KEY,
    MAX_FETCH_TIME_RANGE,
    ROBOT_AI_SETTING_KEY,
)
from monitor_web.commons.robot.utils import (
    AlertRobotModule,
    robot_module_result_build,
    time_range_regular,
)


class AlertSerializer(serializers.Serializer):
    abnormal_count = serializers.IntegerField()
    recent_count = serializers.IntegerField()
    emergency_count = serializers.IntegerField()


class HostSceneIntelligentDetectSerializer(serializers.Serializer):
    class PreviewSerializer(serializers.Serializer):
        ip = serializers.IPAddressField()
        bk_cloud_id = serializers.IntegerField()
        exception_metric_count = serializers.IntegerField()
        other_metric_count = serializers.IntegerField()

    abnormal_count = serializers.IntegerField()
    preview = serializers.ListSerializer(child=PreviewSerializer(), allow_null=True, default=list)


class IntelligentDetectSerializer(serializers.Serializer):
    host = HostSceneIntelligentDetectSerializer(required=False)


class LinkItemSerializer(serializers.Serializer):
    link = serializers.URLField()
    name = serializers.CharField()
    icon_name = serializers.CharField(allow_blank=True)


class FetchRobotInfoResource(ApiAuthResource):
    ROBOT_MODULES = [AlertRobotModule]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]

        # 获取用户名以及上次的拉取时间
        username = get_request_username()

        latest_fetch_time_cache_key = f"{ROBOT_AI_SETTING_KEY}_{username}_{bk_biz_id}_{LATEST_FETCH_TIME_KEY}"

        last_fetch_time = cache.get(latest_fetch_time_cache_key, 0)

        end_time = int(time.time())

        # 计算start_time
        if not last_fetch_time:
            start_time = end_time - MAX_FETCH_TIME_RANGE
        else:
            # 计算上次拉取时间与本次的差值
            time_range = end_time - last_fetch_time

            time_range = time_range_regular(time_range)

            start_time = end_time - time_range

        robot_module_params = {
            "bk_biz_id": bk_biz_id,
            "start_time": start_time,
            "end_time": end_time,
            "username": username,
        }

        # 机器人模块统一处理
        module_result = robot_module_result_build(
            [robot_module(**robot_module_params) for robot_module in self.ROBOT_MODULES]
        )

        # 将用户拉取时间保存
        cache.set(latest_fetch_time_cache_key, end_time, MAX_FETCH_TIME_RANGE)

        # 最后的结果构造开始 ---
        result = {
            "fetch_range": hms_string(end_time - start_time),
            "link": settings.BK_DATA_ROBOT_LINK_LIST,
            **module_result,
        }
        # 最后的结果构造结束 ---

        return result
