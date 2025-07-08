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
import base64
import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlencode

from django.conf import settings
from django.utils.translation import gettext as _
from jinja2.sandbox import SandboxedEnvironment as Environment

from alarm_backends.core.context import logger
from alarm_backends.service.new_report.handler.base import BaseReportHandler
from bkm_space.api import SpaceApi
from bkm_space.utils import bk_biz_id_to_space_uid
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
        space_uid = bk_biz_id_to_space_uid(self.report.bk_biz_id)
        params = {
            "spaceUid": space_uid,
            "keyword": config.get("query_string", "*"),
            "addition": config.get("addition", []),
            "host_scopes": config.get("host_scopes", {}),
            "start_time": time_config["start_time"],
            "end_time": time_config["end_time"],
            "activeTableTab": "clustering",
            "clusterRouteParams": {
                "activeNav": "dataFingerprint",
                "requestData": {
                    "pattern_level": config.get("pattern_level", "09"),
                    "year_on_year_hour": config.get("year_on_year_hour", 0),
                    "show_new_pattern": config.get("is_show_new_pattern", False),
                    "group_by": [],
                    "size": 10000,
                },
            },
        }

        if signature:
            params["addition"].append(
                {"field": f"{self.AGGS_FIELD_PREFIX}_{config['pattern_level']}", "operator": "=", "value": signature}
            )

        params["addition"] = json.dumps(params["addition"])
        params["host_scopes"] = json.dumps(params["host_scopes"])
        params["clusterRouteParams"] = json.dumps(params["clusterRouteParams"])

        url = f"{settings.BKLOGSEARCH_HOST}#/retrieve/{config['index_set_id']}?{urlencode(params, safe=',')}"
        return url

    def get_attachments(self, context):
        # 内存中创建虚拟文件对象
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        rows = []
        log_col_show_type = context['log_col_show_type']
        group_by = context['group_by']
        if context["show_year_on_year"]:
            title_headers = [_("序号"), _("是否新增"), _("数据指纹"), _("数量"), _("占比"), _("同比数量"), _("同比变化"), log_col_show_type]
        else:
            title_headers = [_("序号"), _("是否新增"), _("数据指纹"), _("数量"), _("占比"), log_col_show_type]
        title_headers.extend(group_by)
        rows.append(title_headers)

        for pattern_key in context["all_patterns"]:
            for index, pattern in enumerate(context["all_patterns"][pattern_key]["data"]):
                is_new_pattern = "是" if pattern_key == "new_patterns" else "否"
                data_row = [
                    index,
                    is_new_pattern,
                    '=HYPERLINK("{}", "{}")'.format(pattern["signature_url"], pattern["signature"]),
                    pattern["count"],
                    pattern.get("percentage", round(2)),
                ]
                if context["show_year_on_year"]:
                    data_row.extend([pattern["year_on_year_count"], pattern.get("year_on_year_percentage", round(2))])
                data_row.append(pattern["pattern"])
                data_row.extend(pattern["group"])
                rows.append(data_row)

        for row in rows:
            csv_writer.writerow(row)
        clustering_content = csv_buffer.getvalue()
        csv_buffer.close()

        # 读取内存内容并转换为字符串
        attachments = [
            {
                "filename": f"{context['title']}.csv",
                "disposition": "attachment",
                "type": "csv",
                "content": base64.b64encode(clustering_content.encode()).decode(),
            }
        ]
        return attachments

    def get_render_params(self) -> dict:
        """
        获取渲染参数
        """
        time_config = get_data_range(self.report.frequency, self.report.bk_biz_id)
        try:
            result = self.query_patterns(time_config)
            if not result:
                logger.info("[{}] Query pattern is empty.".format(self.log_prefix))
        except Exception as e:
            logger.exception(f"{self.log_prefix} query pattern error: {e}")
            raise e
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
            logger.info(f"{self.log_prefix} clean pattern result: {all_patterns}")
        except Exception as e:
            logger.exception(f"{self.log_prefix} clean pattern error: {e}")
            raise e
        log_col_show_type = scenario_config.get("log_col_show_type", LogColShowTypeEnum.PATTERN.value).capitalize()

        space_name = ""
        try:
            space = SpaceApi.get_space_detail(bk_biz_id=self.report.bk_biz_id)
            space_name = space.space_name
        except Exception as e:  # pylint:disable=broad-except
            logger.exception("get space info error: {}".format(e))

        render_params = {
            "bk_biz_id": self.report.bk_biz_id,
            "title": content_config["title"],
            "time_config": time_config,
            "show_year_on_year": False if scenario_config["year_on_year_hour"] == YearOnYearEnum.NOT.value else True,
            "space_name": space_name,
            "business_name": space_name,
            "index_set_name": index_set_name,
            "log_search_url": self.generate_log_search_url(scenario_config, time_config),
            "all_patterns": all_patterns,
            "log_col_show_type": log_col_show_type,
            "group_by": scenario_config.get("group_by", []),
            "percentage": 1 or round(max([i["percentage"] for i in result]), 2),
            "clustering_fields": clustering_config["clustering_fields"],
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "is_link_enabled": content_config.get("is_link_enabled", True),
            "generate_attachment": scenario_config.get("generate_attachment", False),
            "is_show_new_pattern": scenario_config.get("is_show_new_pattern", False),
        }

        logger.info(f"{self.log_prefix} Before sending notification params: {render_params}")
        return render_params

    def render(self, render_params: dict) -> dict:
        """
        渲染订阅
        """
        if not render_params:
            logger.exception(f"render_params {render_params} is None.")
        title_template = Environment().from_string(render_params["title"])
        render_params["title"] = title_template.render(**render_params)
        render_params["mail_template_path"] = self.mail_template_path
        render_params["wechat_template_path"] = self.wechat_template_path
        if render_params.get("generate_attachment", False):
            render_params["attachments"] = self.get_attachments(render_params)
        return render_params

    def send_check(self, context: dict) -> bool:
        # 如未产生新类，则不发送
        all_patterns = context["all_patterns"]
        pattern_count = all_patterns["patterns"]["pattern_count"]
        new_pattern_count = all_patterns["new_patterns"]["pattern_count"]
        is_show_new_pattern = context["is_show_new_pattern"]
        if is_show_new_pattern and not new_pattern_count:
            logger.info(
                f"{self.log_prefix} send check is false, is_show_new_pattern: {is_show_new_pattern},"
                f" new_pattern_count: {new_pattern_count}"
            )
            return False
        elif not (pattern_count or new_pattern_count):
            logger.info(
                f"{self.log_prefix} send check is false, is_show_new_pattern: {is_show_new_pattern},"
                f"pattern_count: {pattern_count}, new_pattern_count: {new_pattern_count}"
            )
            return False
        return True
