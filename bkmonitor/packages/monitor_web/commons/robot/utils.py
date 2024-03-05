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

import json
from abc import ABC, abstractmethod
from bisect import bisect_left

from django.core.cache import cache
from elasticsearch_dsl import Q

from constants.aiops import SceneSet
from core.drf_resource import resource
from core.errors.api import BKAPIError
from fta_web.alert.handlers.alert import AlertQueryHandler
from monitor_web.aiops.host_monitor.constant import NoAccessException
from monitor_web.commons.robot.constant import (
    DISPLAY_TIME_LEVEL,
    MAX_FETCH_TIME_RANGE,
    ROBOT_AI_SETTING_KEY,
    RobotLevel,
)


def time_range_regular(time_range):
    index = bisect_left(DISPLAY_TIME_LEVEL, time_range)
    index = index if index < len(DISPLAY_TIME_LEVEL) else len(DISPLAY_TIME_LEVEL) - 1
    return DISPLAY_TIME_LEVEL[index]


class RobotModule(ABC):
    PATH_KEY = ""
    POSITION_KEY = ""
    TIME_STORAGE_KEY = ""

    LATEST_ITEM_CREATE_TIME = 0
    LATEST_FETCH_ITEM_CREATE_TIME = 0

    def __init__(self, username, bk_biz_id, start_time, end_time):
        self.username = username
        self.bk_biz_id = bk_biz_id
        self.start_time = start_time
        self.end_time = end_time
        self.time_cache_key = f"{ROBOT_AI_SETTING_KEY}_{bk_biz_id}_{username}_{self.TIME_STORAGE_KEY}"
        self.LATEST_ITEM_CREATE_TIME = cache.get(self.time_cache_key, 0)

    def save(self):
        cache.set(self.time_cache_key, self.LATEST_FETCH_ITEM_CREATE_TIME, MAX_FETCH_TIME_RANGE)

    @abstractmethod
    def fetch_info(self, start_time, end_time):
        raise NotImplementedError

    @property
    @abstractmethod
    def level(self):
        raise NotImplementedError

    @property
    def is_notice(self):
        return self.LATEST_FETCH_ITEM_CREATE_TIME > self.LATEST_ITEM_CREATE_TIME

    @property
    def is_empty(self):
        raise NotImplementedError


class AlertRobotModule(RobotModule):
    PATH_KEY = "alert"
    POSITION_KEY = ""
    TIME_STORAGE_KEY = "latest_alert_time"

    def __init__(self, *args, **kwargs):
        super(AlertRobotModule, self).__init__(*args, **kwargs)
        self.alert_count = 0
        self.person_alert_count = 0
        self.latest_person_alert_search_count = 0

    def fetch_info(self):
        query_config = {
            "bk_biz_ids": [self.bk_biz_id],
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

        alert_handler = AlertQueryHandler(status=[AlertQueryHandler.NOT_SHIELD_ABNORMAL_STATUS_NAME], **query_config)

        alert_search_object = alert_handler.get_search_object(self.start_time, self.end_time)
        alert_count = alert_search_object.params(track_total_hits=True).execute().hits.total.value
        self.alert_count = min(alert_count, 1000)

        person_alert_search_object = alert_search_object.filter(
            Q("term", assignee=self.username) | Q("term", appointee=self.username)
        )
        person_alert_count = person_alert_search_object.params(track_total_hits=True).execute().hits.total.value
        self.person_alert_count = min(person_alert_count, 1000)

        latest_person_alert_search_object = person_alert_search_object.filter(
            Q("range", create_time={"gte": self.start_time})
        )
        latest_person_alert_search_count = (
            latest_person_alert_search_object.params(track_total_hits=True).execute().hits.total.value
        )
        self.latest_person_alert_search_count = min(latest_person_alert_search_count, 1000)

        latest_person_alerts = alert_handler.handle_hit_list(latest_person_alert_search_object)
        if latest_person_alerts:
            self.LATEST_FETCH_ITEM_CREATE_TIME = latest_person_alerts[0].get("create_time", 0)

        alert_result = {
            "abnormal_count": self.alert_count,
            "person_abnormal_count": self.person_alert_count,
            "latest_person_abnormal_count": self.latest_person_alert_search_count,
        }

        return alert_result

    @property
    def level(self):
        level = RobotLevel.BLUE
        if self.person_alert_count or self.latest_person_alert_search_count:
            level = RobotLevel.RED
        elif self.alert_count:
            level = RobotLevel.YELLOW
        return level


class HostAnomalyRobotModule(RobotModule):
    PATH_KEY = "intelligent_detect"
    POSITION_KEY = SceneSet.HOST
    TIME_STORAGE_KEY = "latest_host_anomaly_time"

    def __init__(self, *args, **kwargs):
        super(HostAnomalyRobotModule, self).__init__(*args, **kwargs)
        self.abnormal_count = 0

    def fetch_info(self):
        # 获取异常点
        params = {
            "bk_biz_id": self.bk_biz_id,
            "raw_data": {},
            "query_config": {
                "start_time": self.start_time,
                "end_time": self.end_time,
            },
        }

        try:
            points = resource.aiops.host_intelligen_anomaly_base(**params)

            # 构建预览
            preview = []
            for point in points:
                anomaly_sort = point["anomaly_sort"]
                anomaly_sort = anomaly_sort if anomaly_sort else "[]"
                preview_item = {
                    "ip": point["ip"],
                    "bk_cloud_id": point["bk_cloud_id"],
                    "exception_metric_count": len(json.loads(anomaly_sort)),
                }
                preview.append(preview_item)

            self.LATEST_FETCH_ITEM_CREATE_TIME = points[0]["dtEventTimeStamp"] if points else 0
            self.abnormal_count = len(points)

            # 构建智能异常结果
            result = {"abnormal_count": self.abnormal_count, "preview": preview}
            return result
        except (NoAccessException, BKAPIError):
            return {}

    @property
    def level(self):
        level = RobotLevel.BLUE

        if self.abnormal_count:
            level = RobotLevel.RED

        return level

    @property
    def is_empty(self):
        return self.abnormal_count == 0


def robot_module_result_build(robot_modules):
    result = {}
    level_list = []
    notice_list = []
    for robot_module in robot_modules:
        module_path_list = robot_module.PATH_KEY.split(".")
        module_info_path = result
        for module_path in module_path_list:
            module_info_path = module_info_path.setdefault(module_path, {})

        fetch_info = robot_module.fetch_info()
        robot_module.save()

        if not robot_module.POSITION_KEY:
            module_info_path.update(fetch_info)
        elif robot_module.POSITION_KEY and not robot_module.is_empty:
            module_info_path.update({robot_module.POSITION_KEY: fetch_info})

        level_list.append(robot_module.level)
        notice_list.append(robot_module.is_notice)

    robot_level = min(*level_list)
    robot_is_notice = any(notice_list)

    return {"need_notice": robot_is_notice, "robot_level": robot_level, **result}
