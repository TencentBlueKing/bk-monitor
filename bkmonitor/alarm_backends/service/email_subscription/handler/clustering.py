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
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

from django.conf import settings
from django.templatetags.i18n import language

from alarm_backends.core.context import logger
from alarm_backends.service.email_subscription.handler.base import (
    BaseSubscriptionHandler,
)
from bkmonitor.email_subscription.utils import get_data_range
from bkmonitor.models import EmailSubscription
from constants.email_subscription import (
    LogColShowTypeEnum,
    YearOnYearChangeEnum,
    YearOnYearEnum,
)
from core.drf_resource import api


class ClusteringSubscriptionHandler(BaseSubscriptionHandler):
    """
    日志聚类订阅管理器
    """

    content_template_path = "clustering_mail_en.html"
    serializer_class = None
    AGGS_FIELD_PREFIX = "__dist"

    def __init__(self, subscription: EmailSubscription):
        super(ClusteringSubscriptionHandler, self).__init__(subscription)
        self.log_prefix = (
            f"[clustering_subscription] space_uid: {self.subscription.bk_biz_id}"
            f" index_set_id: {self.subscription.scenario_config['index_set_id']}"
        )

    def query_patterns(self, time_config: dict) -> list:
        config = self.subscription.scenario_config
        query_params = {
            "start_time": time_config["start_time"],
            "end_time": time_config["end_time"],
            "keyword": config.get("query_string", "*"),
            "addition": config.get("addition", []),
            "host_scopes": config.get("host_scopes", {}),
            "size": 10000,
            "pattern_level": config["pattern_level"],
            "show_new_pattern": config["is_show_new_pattern"],
            "year_on_year_hour": config["year_on_year_hour"],
            "group_by": config.get("group_by", []),
        }
        logger.info(f"{self.log_prefix} search pattern params: {query_params}")
        # result = api.log_search.search_pattern(query_params)
        result = []
        logger.info(f"{self.log_prefix} search pattern result: {result}")
        return result

    def clean_pattern(self, config: dict, time_config: dict, data: list, clustering_config: dict) -> dict:
        patterns = []
        new_patterns = []
        for _data in data:
            # 过滤掉空pattern
            if not _data["pattern"]:
                continue

            _data["signature_url"] = self.generate_log_search_url(config, time_config, signature=_data["signature"])

            # 按同比进行过滤
            if (
                config["year_on_year_change"] == YearOnYearChangeEnum.RISE.value
                and _data["year_on_year_percentage"] < 0
                or config["year_on_year_change"] == YearOnYearChangeEnum.DECLINE.value
                and _data["year_on_year_percentage"] > 0
            ):
                continue

            # 区分是否为新增
            if _data["is_new_class"]:
                new_patterns.append(_data)
            else:
                patterns.append(_data)

        # 截取显示长度
        pattern_count = [p["count"] for p in patterns]
        new_pattern_count = [p["count"] for p in new_patterns]
        result = {
            "patterns": {
                "pattern_count": len(patterns),
                "log_count": sum(pattern_count) if pattern_count else 0,
                "data": patterns[: config["log_display_count"]],
                "max_num": max(pattern_count) if pattern_count else 0,
                "percentage": round(max([p["percentage"] for p in patterns] or [0]), 2),
            },
            "new_patterns": {
                "pattern_count": len(new_patterns),
                "log_count": sum(new_pattern_count) if new_pattern_count else 0,
                "data": new_patterns[: config["log_display_count"]],
                "max_num": max(new_pattern_count) if new_pattern_count else 0,
                "percentage": round(max([p["percentage"] for p in new_patterns] or [0]), 2),
            },
        }

        if config["log_col_show_type"] == LogColShowTypeEnum.LOG.value and (patterns or new_patterns):
            # 查询pattern对应的log, 将pattern替换为log
            log_map = {}
            with ThreadPoolExecutor() as ex:
                tasks = [
                    ex.submit(
                        self.query_logs,
                        config,
                        time_config,
                        pattern,
                        clustering_config.clustering_fields,
                        self.log_prefix,
                    )
                    for pattern in result["new_patterns"]["data"] + result["patterns"]["data"]
                ]
                for feature in as_completed(tasks):
                    log_map.update(feature.result())

            # 将pattern替换为log
            for _data in result["patterns"]["data"]:
                _data["pattern"] = log_map.get(_data["signature"]) or _data["pattern"]

            for _data in result["new_patterns"]["data"]:
                _data["pattern"] = log_map.get(_data["signature"]) or _data["pattern"]

        return result

    def query_logs(
        self,
        config: dict,
        time_config: dict,
        pattern: dict,
        clustering_field: list,
        log_prefix: str,
    ) -> dict:
        addition = config.get("addition", [])
        addition.append(
            {
                "field": f"{self.AGGS_FIELD_PREFIX}_{config['pattern_level']}",
                "operator": "is",
                "value": pattern["signature"],
            }
        )
        params = {
            "start_time": time_config["start_time"],
            "end_time": time_config["end_time"],
            "keyword": config.get("query_string", "*"),
            "addition": addition,
            "host_scopes": config.get("host_scopes", {}),
            "size": 1,
        }
        logger.info(f"{log_prefix} Query signature log params: {params}")
        result = api.log_search.es_query_search(params)
        logger.info(f"{log_prefix} Query signature log result: {result}")
        if not result.get("list", []):
            return {}

        return {pattern["signature"]: result["list"][0][clustering_field]}

    def generate_log_search_url(self, config: dict, time_config: dict, signature: str = "") -> str:
        params = {
            "spaceUid": self.subscription.bk_biz_id,
            "keyword": config.get("query_string", "*"),
            "addition": config.get("addition", []),
            "host_scopes": config.get("host_scopes", {}),
            "start_time": time_config["start_time"],
            "end_time": time_config["end_time"],
        }

        if signature:
            params["addition"].append(
                {"field": f"{self.AGGS_FIELD_PREFIX}_{config['pattern_level']}", "operator": "=", "value": signature}
            )

        params["addition"] = json.dumps(params["addition"])
        params["host_scopes"] = json.dumps(params["host_scopes"])

        url = f"{'test' or settings.BK_BKLOG_HOST}#/retrieve/{config['index_set_id']}?{urlencode(params)}"
        return url

    def get_render_params(self) -> dict:
        """
        获取渲染参数
        """
        # TODO: 激活时区

        time_config = get_data_range(self.subscription.frequency)
        result = self.query_patterns(time_config)
        content_config = self.subscription.content_config
        scenario_config = self.subscription.scenario_config

        # TODO: 获取索引集信息
        log_index_set = {"index_set_name": ""}
        # TODO: 获取cluster信息
        clustering_config = {"clustering_fields": []}
        all_patterns = result
        log_col_show_type = None

        render_params = {
            "language": language,
            "title": content_config["title"],
            "time_config": time_config,
            "show_year_on_year": False if scenario_config["year_on_year_hour"] == YearOnYearEnum.NOT.value else True,
            "space_name": "",
            "index_set_name": log_index_set["index_set_name"],
            "log_search_url": self.generate_log_search_url(scenario_config, time_config),
            "all_patterns": all_patterns,
            "log_col_show_type": log_col_show_type,
            "group_by": scenario_config.get("group_by", []),
            "percentage": 1 or round(max([i["percentage"] for i in result]), 2),
            "clustering_fields": clustering_config["clustering_fields"],
        }

        logger.info(f"{self.log_prefix} Before sending notification params: {render_params}")
        return render_params

    def render(self, render_params: dict) -> dict:
        """
        渲染订阅
        """
        return {
            "title_template_path": self.title_template_path,
            "content_template_path": self.content_template_path,
            "title": self.subscription.content_config["title"],
            "content": "test",
        }
