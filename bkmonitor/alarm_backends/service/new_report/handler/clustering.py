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
from datetime import datetime
from urllib.parse import urlencode

from django.conf import settings
from django.templatetags.i18n import language

from alarm_backends.core.context import logger
from alarm_backends.service.new_report.handler.base import BaseReportHandler
from bkm_space.api import SpaceApi
from bkmonitor.models import Report
from bkmonitor.report.utils import get_data_range
from constants.new_report import (
    LogColShowTypeEnum,
    YearOnYearChangeEnum,
    YearOnYearEnum,
)
from core.drf_resource import api


class ClusteringReportHandler(BaseReportHandler):
    """
    日志聚类订阅管理器
    """

    mail_template_path = "new_report/clustering/clustering_mail.jinja"
    wechat_template_path = "new_report/clustering/clustering_wechat.jinja"
    AGGS_FIELD_PREFIX = "__dist"

    def __init__(self, report: Report):
        super(ClusteringReportHandler, self).__init__(report)
        self.log_prefix = (
            f"[clustering_report] bk_biz_id: {self.report.bk_biz_id}"
            f" index_set_id: {self.report.scenario_config['index_set_id']}"
        )

    def query_patterns(self, time_config: dict) -> list:
        config = self.report.scenario_config
        query_params = {
            "index_set_id": config["index_set_id"],
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
        result = api.log_search.search_pattern(query_params)
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

        if config.get("log_col_show_type", LogColShowTypeEnum.PATTERN.value) == LogColShowTypeEnum.LOG.value and (
            patterns or new_patterns
        ):
            # 查询pattern对应的log, 将pattern替换为log
            log_map = {}
            with ThreadPoolExecutor() as ex:
                tasks = [
                    ex.submit(self.query_logs, config, time_config, pattern, clustering_config["clustering_fields"])
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

    def query_logs(self, config: dict, time_config: dict, pattern: dict, clustering_field: list) -> dict:
        addition = config.get("addition", [])
        addition.append(
            {
                "field": f"{self.AGGS_FIELD_PREFIX}_{config['pattern_level']}",
                "operator": "is",
                "value": pattern["signature"],
            }
        )
        params = {
            "index_set_id": config["index_set_id"],
            "start_time": time_config["start_time"],
            "end_time": time_config["end_time"],
            "keyword": config.get("query_string", "*"),
            "addition": addition,
            "host_scopes": config.get("host_scopes", {}),
            "size": 1,
        }
        logger.info(f"{self.log_prefix} Query signature log params: {params}")
        result = api.log_search.search_index_set_log(params)
        logger.info(f"{self.log_prefix} Query signature log result: {result}")
        if not result.get("list", []):
            return {}

        return {pattern["signature"]: result["list"][0][clustering_field]}

    def generate_log_search_url(self, config: dict, time_config: dict, signature: str = "") -> str:
        params = {
            "spaceUid": self.report.bk_biz_id,
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

        url = f"{settings.BKLOGSEARCH_HOST}#/retrieve/{config['index_set_id']}?{urlencode(params)}"
        return url

    def get_render_params(self) -> dict:
        """
        获取渲染参数
        """
        time_config = get_data_range(self.report.frequency)
        try:
            result = self.query_patterns(time_config)
        except Exception as e:
            logger.exception(f"{self.log_prefix} query pattern error: {e}")
            return {}
        if not result:
            logger.info("[{}] Query pattern is empty.".format(self.log_prefix))
        content_config = self.report.content_config
        scenario_config = self.report.scenario_config

        # 获取索引集信息
        index_set_name = ""
        log_index_sets = api.log_search.search_index_set(bk_biz_id=self.report.bk_biz_id)
        for index_set in log_index_sets:
            if index_set["index_set_id"] == scenario_config["index_set_id"]:
                index_set_name = index_set["index_set_name"]
        # 获取cluster信息
        clustering_config = api.log_search.get_clustering_config(index_set_id=scenario_config["index_set_id"])
        try:
            all_patterns = self.clean_pattern(scenario_config, time_config, result, clustering_config)
        except Exception as e:
            logger.exception(f"{self.log_prefix} clean pattern error: {e}")
            return {}
        logger.info(f"{self.log_prefix} clean pattern result: {all_patterns}")
        log_col_show_type = scenario_config.get("log_col_show_type", LogColShowTypeEnum.PATTERN.value).capitalize()

        space_name = ""
        try:
            space = SpaceApi.get_space_detail(bk_biz_id=self.report.bk_biz_id)
            space_name = space.space_name
        except Exception as e:  # pylint:disable=broad-except
            logger.exception("get space info error: {}".format(e))

        render_params = {
            "language": language,
            "title": content_config["title"],
            "time_config": time_config,
            "show_year_on_year": False if scenario_config["year_on_year_hour"] == YearOnYearEnum.NOT.value else True,
            "space_name": space_name,
            "index_set_name": index_set_name,
            "log_search_url": self.generate_log_search_url(scenario_config, time_config),
            "all_patterns": all_patterns,
            "log_col_show_type": log_col_show_type,
            "group_by": scenario_config.get("group_by", []),
            "percentage": 1 or round(max([i["percentage"] for i in result]), 2),
            "clustering_fields": clustering_config["clustering_fields"],
            "time": datetime.now().strftime("%Y%m%d"),
            "is_link_enabled": content_config.get("is_link_enabled", True),
            "generate_attachment": scenario_config.get("generate_attachment", False),
        }

        logger.info(f"{self.log_prefix} Before sending notification params: {render_params}")
        return render_params

    def render(self, render_params: dict) -> dict:
        """
        渲染订阅
        """
        render_params["title"] = render_params["title"].format(**render_params)
        render_params["mail_template_path"] = self.mail_template_path
        render_params["wechat_template_path"] = self.wechat_template_path
        return render_params
