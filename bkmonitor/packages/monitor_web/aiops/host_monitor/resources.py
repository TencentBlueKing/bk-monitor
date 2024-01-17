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
import re

from django.db.models import Value
from django.db.models.functions import Concat
from rest_framework.exceptions import ValidationError

from bkmonitor.aiops.utils import AiSetting
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.models import MetricListCache
from bkmonitor.strategy.new_strategy import get_metric_id
from bkmonitor.views import serializers
from constants.data_source import DataSourceLabel
from core.drf_resource import Resource, resource
from monitor_web.aiops.host_monitor.constant import (
    GROUP_BY_METRIC_FIELDS,
    NO_ACCESS_METRIC_ANOMALY_RANGE_COLOR,
    QUERY_METRIC_FIELDS,
    NoAccessException,
)
from monitor_web.aiops.host_monitor.serializers import HostSerializer
from monitor_web.aiops.host_monitor.utils import (
    build_interval,
    build_start_time_and_end_time,
)
from monitor_web.commons.cc.utils.cmdb import CmdbUtil
from monitor_web.scene_view.builtin.host import get_metric_panel

logger = logging.getLogger(__name__)


def query_metric_info(metric_name_set):
    bkmonitor_metric_queryset = MetricListCache.objects.annotate(
        bkmonitor_metric_fullname=Concat("result_table_id", Value("."), "metric_field")
    ).filter(bkmonitor_metric_fullname__in=metric_name_set)

    return bkmonitor_metric_queryset


class HostIntelligenAnomalyResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        host = serializers.ListSerializer(child=HostSerializer())
        start_time = serializers.IntegerField(required=False)
        end_time = serializers.IntegerField(required=False)

        def validate_host(self, attr):
            return [host for host in attr if "bk_target_ip" in host and "bk_target_cloud_id" in host]

    def perform_request(self, validated_request_data):
        if not validated_request_data["host"]:
            return {"anomaly_info": [], "metrics": []}

        bk_biz_id = validated_request_data["bk_biz_id"]

        group_by = GROUP_BY_METRIC_FIELDS.copy()

        group_by.append("minute1")

        query_config = {"group_by": group_by}

        points = HostIntelligenAnomalyBaseResource().request(
            {"bk_biz_id": bk_biz_id, "query_config": query_config, "raw_data": validated_request_data}
        )

        unique_metric_anomaly_info = {}
        metric_name_set = set()

        for point in points:
            anomaly_sort = point.get("anomaly_sort", "[]")
            anomaly_sort = json.loads(anomaly_sort)
            # anomaly_sort本身为list嵌套格式，用下标读取
            # 示例[["metric1", 数值(float), 异常分数(float)], ["metric2", 数值(float), 异常分数(float)]]
            for anomaly_item in anomaly_sort:
                metric_name = anomaly_item[0].replace("__", ".")
                anomaly_info_item = {
                    "metric_id": f'{DataSourceLabel.BK_MONITOR_COLLECTOR}.{metric_name}',
                    "value": anomaly_item[1],
                    "score": anomaly_item[2],
                    "ip": point["ip"],
                    "bk_cloud_id": point["bk_cloud_id"],
                    "dtEventTime": point["dtEventTimeStamp"],
                }
                metric_name_set.add(metric_name)
                if not unique_metric_anomaly_info.get(metric_name):
                    unique_metric_anomaly_info[metric_name] = anomaly_info_item

        anomaly_info = list(unique_metric_anomaly_info.values())

        # 查询出现的指标
        metrics_info = query_metric_info(metric_name_set)

        # 为每一项添加大图需要加上相关panel
        panels = {
            get_metric_id(
                data_source_label=metric.data_source_label,
                data_type_label=metric.data_type_label,
                result_table_id=metric.result_table_id,
                metric_field=metric.metric_field,
            ): get_metric_panel(bk_biz_id=bk_biz_id, metric=metric, type="performance-chart")
            for metric in metrics_info
        }

        for anomaly_info_item in anomaly_info:
            panel = panels[anomaly_info_item["metric_id"]]
            anomaly_info_item["panel"] = panel

        metrics = resource.grafana.unify_query_raw.transfer_metric(bk_biz_id, metrics_info)

        return {"anomaly_info": anomaly_info, "metrics": metrics}


class HostIntelligenAnomalyRangeResource(Resource):
    class RequestSerializer(serializers.Serializer):
        TIME_PATTERNS = {
            'seconds': r'(?P<seconds>\d+(\.\d+)?)\s*(?:s|sec|secs?|second|seconds?)',
            'minutes': r'(?P<minutes>\d+(\.\d+)?)\s*(?:m|min|mins?|minute|minutes?)',
            'hours': r'(?P<hours>\d+(\.\d+)?)\s*(?:h|hr|hrs?|hour|hours?)',
        }

        TIME_UNITS_IN_SECONDS = {
            'seconds': 1,
            'minutes': 60,
            'hours': 60 * 60,
        }

        bk_biz_id = serializers.IntegerField()
        host = serializers.ListSerializer(child=HostSerializer())
        start_time = serializers.IntegerField(required=False)
        end_time = serializers.IntegerField(required=False)
        metric_ids = serializers.ListSerializer(child=serializers.CharField())
        interval = serializers.CharField()

        def validate_host(self, attr):
            return [host for host in attr if "bk_target_ip" in host and "bk_target_cloud_id" in host]

        def validate_interval(self, attr):
            if attr == "auto":
                return attr

            for unit, pattern in self.TIME_PATTERNS.items():
                match = re.match(pattern, attr)
                if match:
                    interval = float(match.group(unit)) * self.TIME_UNITS_IN_SECONDS[unit]
                    return interval
            raise ValidationError(f"Invalid time format: {attr}")

        def validate(self, attrs):
            start_time = attrs.get('start_time')
            end_time = attrs.get('end_time')
            interval = attrs.get('interval')

            start_time, end_time = build_start_time_and_end_time(start_time, end_time)
            interval = build_interval(start_time, end_time, interval)

            # 把验证后的值放回attrs中，这样它们就可以在以后被序列化器的其他部分使用。
            attrs['start_time'] = start_time
            attrs['end_time'] = end_time
            attrs['interval'] = interval
            return attrs

    def perform_request(self, validated_request_data):
        if not validated_request_data["host"]:
            return {}

        bk_biz_id = validated_request_data["bk_biz_id"]
        query_config = {}

        query_config["start_time"] = validated_request_data.get("start_time")
        query_config["end_time"] = validated_request_data.get("end_time")
        query_config["interval"] = validated_request_data.get("interval")

        metric_ids = validated_request_data["metric_ids"]
        query_config["order_by"] = ["dtEventTimeStamp ASC"]

        points = HostIntelligenAnomalyBaseResource().request(
            {"bk_biz_id": bk_biz_id, "query_config": query_config, "raw_data": validated_request_data}
        )

        result = {}

        point_time_range = int(validated_request_data.get("interval")) * 1000

        # 遍历传过来的指标列表
        for metric in metric_ids:
            prefix, metric = metric.split(".", 1)
            anomaly_ranges = []

            last_point_time_stamp = 0

            # 遍历每一个异常
            for point in points:
                anomaly_sort = point.get("anomaly_sort", "[]")
                anomaly_sort = json.loads(anomaly_sort)

                # 拿出时间戳
                point_time_stamp = point["dtEventTimeStamp"]

                # 遍历异常中异常指标每一个指标是否是传入的指标
                for anomaly_item in anomaly_sort:
                    if metric == anomaly_item[0].replace("__", "."):
                        if anomaly_ranges and (point_time_stamp - last_point_time_stamp == point_time_range):
                            anomaly_ranges[-1]["to"] += point_time_range
                        else:
                            anomaly_range = {"from": point_time_stamp, "to": point_time_stamp + point_time_range}
                            color = NO_ACCESS_METRIC_ANOMALY_RANGE_COLOR
                            anomaly_range["color"] = anomaly_range["borderColor"] = anomaly_range["shadowColor"] = color
                            anomaly_ranges.append(anomaly_range)

                        break

                # 退出这一个异常点循环时记录该次时间戳作为下一次异常点的上次时间戳
                last_point_time_stamp = point_time_stamp

            metric_info = result.setdefault(f"{prefix}.{metric}", [])
            metric_info += anomaly_ranges

        return result


class HostIntelligenAnomalyBaseResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        query_config = serializers.DictField()
        raw_data = serializers.DictField()

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]

        biz_ai_setting = AiSetting(bk_biz_id=bk_biz_id)

        if not biz_ai_setting.multivariate_anomaly_detection.host.is_access_aiops():
            err_msg = "bk_biz_id({}) host scene not access aiops".format(bk_biz_id)
            raise NoAccessException(err_msg)

        intelligent_detect = biz_ai_setting.multivariate_anomaly_detection.host.intelligent_detect

        query_config = validated_request_data["query_config"]

        raw_data = validated_request_data["raw_data"]
        host = raw_data.get("host", [])
        exclude_target = biz_ai_setting.multivariate_anomaly_detection.host.exclude_target
        exclude_hosts = []
        if exclude_target:
            exclude_hosts = CmdbUtil.get_target_hosts(bk_biz_id=bk_biz_id, target=exclude_target)
            exclude_hosts = [exclude_host.host_id for exclude_host in exclude_hosts]

        where = query_config.setdefault("where", [])
        if not host:
            where.append({"condition": "and", "key": "is_anomaly", "method": "eq", "value": [1]})
        else:
            for host_item in host:
                ip = host_item["bk_target_ip"]
                bk_cloud_id = host_item["bk_target_cloud_id"]
                # 第一组的ip需要是and，后续的ip为or
                where.append({"condition": "and" if not where else "or", "key": "ip", "method": "eq", "value": [ip]})
                where.append({"condition": "and", "key": "bk_cloud_id", "method": "eq", "value": [bk_cloud_id]})
                where.append({"condition": "and", "key": "is_anomaly", "method": "eq", "value": [1]})

        query_config["start_time"] = (
            query_config["start_time"] if query_config.get("start_time") else raw_data.get("start_time")
        )
        query_config["end_time"] = (
            query_config["end_time"] if query_config.get("end_time") else raw_data.get("end_time")
        )

        metrics = query_config.get("metrics", QUERY_METRIC_FIELDS.copy())
        metrics = [{"field": field} for field in metrics]

        group_by = query_config.get("group_by", GROUP_BY_METRIC_FIELDS)

        start_time, end_time = build_start_time_and_end_time(
            query_config.get("start_time"), query_config.get("end_time")
        )

        query_config["start_time"] = start_time
        query_config["end_time"] = end_time

        query_config.update({"table": intelligent_detect["result_table_id"], "metrics": metrics, "group_by": group_by})

        data_source_class = load_data_source(
            intelligent_detect["data_source_label"], intelligent_detect["data_type_label"]
        )
        data_source = data_source_class(bk_biz_id=bk_biz_id, **query_config)
        data_source.time_field = query_config.get("time_field", "")

        query = UnifyQuery(
            bk_biz_id=bk_biz_id,
            data_sources=[data_source],
            expression="",
        )

        points = query.query_data(
            start_time=query_config["start_time"] * 1000, end_time=query_config["end_time"] * 1000
        )

        points = [point for point in points if f'{point["ip"]}|{point["bk_cloud_id"]}' not in exclude_hosts]

        return points
