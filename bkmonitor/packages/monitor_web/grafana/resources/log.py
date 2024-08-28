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
import logging
from datetime import datetime, timedelta
from typing import Dict, List

import arrow
from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.data_source import load_data_source
from bkmonitor.share.api_auth_resource import ApiAuthResource
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import resource

logger = logging.getLogger(__name__)


class LogQueryResource(ApiAuthResource):
    """
    日志数据查询
    """

    class RequestSerializer(serializers.Serializer):
        data_format = serializers.CharField(label="数据格式", default="strategy")

        bk_biz_id = serializers.IntegerField(label="业务ID")
        data_source_label = serializers.CharField(label="数据来源")
        data_type_label = serializers.CharField(label="数据类型")

        query_string = serializers.CharField(default="", allow_blank=True)
        index_set_id = serializers.CharField(label="索引集ID", default="", allow_blank=True)
        alert_name = serializers.CharField(label="告警名称", required=False)
        bkmonitor_strategy_id = serializers.CharField(label="策略ID", required=False)

        result_table_id = serializers.CharField(label="结果表ID", default="", allow_blank=True)
        where = serializers.ListField(label="过滤条件", default=lambda: [])
        filter_dict = serializers.DictField(default=lambda: {})

        start_time = serializers.IntegerField(required=False, label="开始时间")
        end_time = serializers.IntegerField(required=False, label="结束时间")
        limit = serializers.IntegerField(label="查询条数", default=10)
        offset = serializers.IntegerField(label="查询偏移", default=0)

        @classmethod
        def to_str(cls, value):
            if isinstance(value, list):
                return [cls.to_str(v) for v in value if v or not isinstance(v, (dict, list))]
            elif isinstance(value, dict):
                return {k: cls.to_str(v) for k, v in value.items() if v or not isinstance(v, (dict, list))}
            else:
                return str(value)

        def validate(self, attrs):
            attrs["filter_dict"] = self.to_str(attrs["filter_dict"])
            return attrs

    @staticmethod
    def table_format(data: List[Dict], total: int, data_format: str = ""):
        """
        生成grafana table格式
        """
        dimensions = set()
        for row in data:
            for key in row:
                dimensions.add(key)

        if dimensions:
            dimensions.add("time")

        dimensions = ["time"] + sorted([d for d in dimensions if d != "time"])

        if data_format == "scene_view":
            return {
                "columns": [
                    {"name": _("时间"), "id": "time", "type": "time"},
                    {"name": _("事件名"), "id": "event_name", "type": "string"},
                    {"name": _("事件内容"), "id": "event.content", "type": "string"},
                    {"name": _("目标"), "id": "target", "type": "string"},
                ],
                "checkable": False,
                "data": data,
                "total": total,
            }
        else:
            return [
                {
                    "columns": [{"text": d, "type": "time" if d == "time" else "string"} for d in dimensions],
                    "rows": [[row.get(d, "") for d in dimensions] for row in data],
                }
            ]

    @staticmethod
    def get_time(record: Dict, time_field: str) -> int:
        time_value = record.pop(time_field)

        # 带毫秒的时间戳处理
        try:
            time_value = int(time_value)
            if len(str(time_value)) > 10:
                time_value = time_value // 1000
        except (TypeError, ValueError):
            pass

        # 将时间字段序列化
        try:
            _time = arrow.get(time_value)
        except Exception as e:
            logger.error(f"parse time error: {time_value}")
            logger.exception(e)
            _time = arrow.now()

        return int(_time.timestamp)

    def perform_request(self, params):
        if "start_time" not in params or "end_time" not in params:
            params["end_time"] = int(datetime.now().timestamp())
            params["start_time"] = int((datetime.now() - timedelta(hours=1)).timestamp())

        params["start_time"] *= 1000
        params["end_time"] *= 1000

        time_field = None
        # 查询日志平台关键字时间字段
        if (params["data_source_label"], params["data_type_label"]) == (
            DataSourceLabel.BK_LOG_SEARCH,
            DataTypeLabel.LOG,
        ):
            try:
                result = resource.strategies.get_index_set_list(
                    bk_biz_id=params["bk_biz_id"], index_set_id=params["index_set_id"]
                )
                if result["metric_list"]:
                    time_field = result["metric_list"][0]["extend_fields"].get("time_field") or None
            except Exception as e:
                logger.exception(e)

        data_source_class = load_data_source(params["data_source_label"], params["data_type_label"])

        kwargs = dict(
            table=params["result_table_id"],
            index_set_id=params["index_set_id"],
            where=params["where"],
            query_string=params["query_string"],
            filter_dict=params["filter_dict"],
            time_field=time_field,
            bk_biz_id=params["bk_biz_id"],
        )
        if params["data_source_label"] == DataSourceLabel.BK_FTA:
            if not params.get("alert_name"):
                raise ValidationError(_("告警名称不能为空"))
            kwargs["alert_name"] = params["alert_name"]
        elif (params["data_source_label"], params["data_type_label"]) == (
            DataSourceLabel.BK_MONITOR_COLLECTOR,
            DataTypeLabel.ALERT,
        ):
            if not params.get("bkmonitor_strategy_id"):
                raise ValidationError(_("策略ID不能为空"))
            kwargs["bkmonitor_strategy_id"] = params["bkmonitor_strategy_id"]

        data_source = data_source_class(**kwargs)
        limit = None if params["limit"] <= 0 else params["limit"]
        records, total = data_source.query_log(
            start_time=params["start_time"], end_time=params["end_time"], limit=limit, offset=params["offset"]
        )

        result = []
        for record in records:
            _record = {"time": self.get_time(record, data_source.time_field)}

            if params["data_source_label"] in (DataSourceLabel.BK_MONITOR_COLLECTOR, DataSourceLabel.CUSTOM) and params[
                "data_type_label"
            ] not in [DataTypeLabel.ALERT]:
                dimensions = record.pop("dimensions", {})

                if params["data_source_label"] == DataSourceLabel.BK_MONITOR_COLLECTOR and params.get(
                    "data_format"
                ) in ["table", "scene_view"]:
                    for dimension in [
                        "bk_biz_id",
                        "bk_collect_config_id",
                        "bk_module_id",
                        "bk_set_id",
                        "bk_target_service_category_id",
                        "dimensions.bk_target_service_instance_id",
                        "bk_target_topo_id",
                        "bk_target_topo_level",
                    ]:
                        dimensions.pop(dimension, None)

                event = record.pop("event", {})
                content = event.get("content", "")
                count = event.get("count", 1)
                _record.update({f"dimensions.{key}": value for key, value in dimensions.items()})
                _record["event.content"] = content
                _record["event.count"] = count
                _record.update(record)
            elif params["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH and "log" in record:
                _record["event.content"] = record["log"]
            else:
                _record["event.content"] = json.dumps(record, ensure_ascii=False)

            result.append(_record)

        if params.get("data_format") in ["table", "scene_view"]:
            return self.table_format(result, total, params.get("data_format"))

        return {
            "result": True,
            "data": result,
            "meta": {
                "total": total,
            },
            "code": 200,
            "message": "OK",
        }
