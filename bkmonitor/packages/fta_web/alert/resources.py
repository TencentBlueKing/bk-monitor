"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import bisect
import copy
import csv
import json
import logging
import re
import time
from abc import ABCMeta
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
from functools import reduce
from io import StringIO
from typing import Any
from itertools import chain

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.db.models import Q as DQ
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.translation import gettext as _
from elasticsearch_dsl import Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.cmdb.define import Host, ServiceInstance
from bkmonitor.aiops.alert.utils import (
    AIOPSManager,
    DimensionDrillManager,
    RecommendMetricManager,
    parse_anomaly,
)
from bkmonitor.data_source import load_data_source
from bkmonitor.documents import (
    ActionInstanceDocument,
    AlertDocument,
    AlertLog,
    EventDocument,
)
from bkmonitor.documents.base import BulkActionType
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.models import (
    ActionInstance,
    AlertAssignGroup,
    AlgorithmModel,
    MetricListCache,
    StrategyModel,
)
from bkmonitor.models.bcs_cluster import BCSCluster
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.strategy.new_strategy import Strategy, parse_metric_id
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.event_related_info import get_alert_relation_info
from bkmonitor.utils.range import load_agg_condition_instance
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.time_tools import (
    datetime2timestamp,
    now,
    utc2datetime,
    utc2localtime,
)
from bkmonitor.utils.user import get_global_user, get_request_username
from constants.action import (
    ACTION_DISPLAY_STATUS_DICT,
    ActionPluginType,
    ActionSignal,
    NoticeWay,
)
from constants.alert import (
    EVENT_STATUS_DICT,
    AlertFieldDisplay,
    EventStatus,
    EventTargetType,
)
from constants.data_source import DataSourceLabel, DataTypeLabel, UnifyQueryDataSources
from core.drf_resource import Resource, api, resource
from core.drf_resource.exceptions import CustomException
from core.errors.alert import AIOpsMultiAnomlayDetectError, AlertNotFoundError
from core.unit import load_unit
from fta_web import constants
from fta_web.alert.handlers.action import ActionQueryHandler
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.handlers.alert_log import AlertLogHandler
from fta_web.alert.handlers.base import BaseQueryHandler
from fta_web.alert.handlers.event import EventQueryHandler
from fta_web.alert.handlers.translator import PluginTranslator
from fta_web.alert.serializers import (
    ActionIDField,
    ActionSearchSerializer,
    AlertFeedbackSerializer,
    AlertIDField,
    AlertSearchSerializer,
    AlertSuggestionSerializer,
    EventSearchSerializer,
)
from fta_web.alert.utils import (
    generate_date_ranges,
    get_day_range_unix,
    get_previous_month_range_unix,
    get_previous_week_range_unix,
    slice_time_interval,
)
from fta_web.models.alert import (
    SEARCH_TYPE_CHOICES,
    AlertFeedback,
    AlertSuggestion,
    MetricRecommendationFeedback,
    SearchHistory,
    SearchType,
)
from monitor_web.aiops.metric_recommend.constant import (
    METRIC_RECOMMAND_SCENE_SERVICE_TEMPLATE,
)
from monitor_web.constants import AlgorithmType
from monitor_web.models import CustomEventGroup

logger = logging.getLogger("root")


class GetFourMetricsData(Resource):
    """
    4线策略告警统计
    在线： 在线 或 online
    登录： 登录 或 登陆 或 login
    注册： 注册 或 registation 或 reg
    对局： 对局 或 排队 或 battle 或 bat
    """

    def perform_request(self, validated_request_data):
        results_format = validated_request_data.get("results", "json")
        thedate = validated_request_data.get("thedate", None)
        biz_ids = validated_request_data.get("biz_ids", "")
        biz_list = api.cmdb.get_business()
        target_biz_ids = [int(biz_id) for biz_id in biz_ids.split(",") if biz_id]
        # 如果有预期的业务 id 则取预期的业务内容
        if target_biz_ids:
            biz_info = {biz.bk_biz_id: biz for biz in biz_list if biz.bk_biz_id in target_biz_ids}
        else:
            biz_info = {biz.bk_biz_id: biz for biz in biz_list}

        if not thedate:
            # 获取日期
            # 如果没有传入指定日期 则获取上一周的日期 四线以每周计
            start_time, end_time = get_previous_week_range_unix()
        else:
            start_time, end_time = get_day_range_unix(thedate)

        ret = []
        scenario = constants.SCENARIO
        # 日期为第一层 再分业务获取对应的告警数量
        for day_start, day_end in generate_date_ranges(start_time, end_time):
            # 初始化存储映射 告警名称/业务
            scenario_totals = {scenario_name: {biz: 0 for biz in biz_info} for scenario_name in scenario.keys()}
            for scenario_name, scenario_list in scenario.items():
                page, page_size, fetched, total = 1, 1000, 0, 1
                # 分页处理
                conditions = " OR ".join(f'告警名称 : "{item}"' for item in scenario_list)
                # 将生成的条件括在括号内
                query_string = f"({conditions})"
                # 查询条件
                while fetched < total:
                    request_body = {
                        "bk_biz_ids": list(biz_info.keys()),
                        "status": [],
                        "conditions": [],
                        "query_string": query_string,
                        "start_time": int(day_start.timestamp()),
                        "end_time": int(day_end.timestamp()),
                        "page": page,
                        "page_size": page_size,
                    }
                    handler = AlertQueryHandler(**request_body)
                    result = handler.search()
                    total = result["total"]
                    fetched += len(result["alerts"])
                    page += 1
                    # 更新结果总数 供后面判断
                    for alert in result["alerts"]:
                        scenario_totals[scenario_name][alert["bk_biz_id"]] += 1
                        # 日期 业务 告警指标
            for biz_id, biz in biz_info.items():
                # 最后按业务插入当天的告警数据统计
                ret.append(
                    {
                        "日期": day_start.date(),
                        "业务": biz.display_name,
                        **{
                            scenario_name: scenario_totals[scenario_name].get(biz_id, 0)
                            for scenario_name in scenario.keys()
                        },
                    }
                )
        if results_format == "file":
            timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            filename = f"data_{timestamp}.csv"
            output = StringIO()
            # 在内存读写文件 避免污染 Pod 的 OS 文件
            output.write("\ufeff")
            # 写入 utf-8 bom 避免纯文本乱码
            fieldnames = ["日期", "业务"] + list(scenario.keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in ret:
                writer.writerow(row)
            output.seek(0)
            response = HttpResponse(output.getvalue().encode("utf-8"), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f"attachment; filename={filename}"
            return response
        else:
            return ret


class GetTmpData(Resource):
    """
    tmp来源告警占比统计
    """

    def perform_request(self, validated_request_data):
        results_format = validated_request_data.get("results", "json")
        start_time, end_time = (
            validated_request_data.get("start_time", None),
            validated_request_data.get("end_time", None),
        )
        biz_ids = validated_request_data.get("biz_ids", "")
        thedate = validated_request_data.get("thedate", None)

        # 如果都没未指定时间，则默认为上一个月 tmp 默认按月计
        if not thedate:
            start_time, end_time = get_previous_month_range_unix()
        else:
            start_time, end_time = get_day_range_unix(thedate)
        biz_list = api.cmdb.get_business()
        target_biz_ids = [int(biz_id) for biz_id in biz_ids.split(",") if biz_id]
        # 检查是否有传入目标业务列表 如果没有 则走事件中心先查询有 tmp 告警来源的业务
        if target_biz_ids:
            biz_info = {biz.bk_biz_id: biz for biz in biz_list if biz.bk_biz_id in target_biz_ids}
        else:
            tmp_biz_params = {
                "bk_biz_ids": [-1],
                "status": [],
                "conditions": [],
                "query_string": "",
                "start_time": start_time,
                "end_time": end_time,
                "fields": ["bk_biz_id"],
                "size": 100,
                "bk_biz_id": -4228445,
            }
            biz_ids = [int(i["id"]) for i in resource.alert.alert_top_n(tmp_biz_params)["fields"][0]["buckets"]]
            biz_info = {biz.bk_biz_id: biz for biz in biz_list if biz.bk_biz_id in biz_ids}
            # 只取 top 100 基本上 100 个业务最后几个 出现的 tmp 告警次数为 1 或个位数
            # 考虑到还要根据过滤条件 符合的其实更少

        ret = {}
        results = []
        # 时间范围需要调整
        for biz in biz_info:
            params = {
                "bk_biz_ids": [biz],
                "status": [],
                "conditions": constants.CONDITIONS_REQ,
                "query_string": "",
                "start_time": start_time,
                "end_time": end_time,
                "fields": ["plugin_id"],
                "size": 10,
                "bk_biz_id": biz,
            }
            ret[biz] = {i["id"]: i["count"] for i in resource.alert.alert_top_n(params)["fields"][0]["buckets"]}
        for biz, alert in ret.items():
            if biz not in biz_info or not alert:
                continue
            tmp = alert.get('"tnm"', 0)
            bkmonitor = alert.get('"bkmonitor"', 0)
            row = {
                "biz": biz,
                "biz_name": biz_info[biz].display_name,
                "tmp": tmp,
                "tmp_bk": bkmonitor + tmp,
                "tmp_bk_ratio": tmp / (tmp + bkmonitor) if tmp != 0 else 0,
            }
            results.append(row)
        if results_format == "file":
            timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            filename = f"data_{timestamp}.csv"
            output = StringIO()
            # 在内存读写文件 避免污染 Pod 的 OS 文件
            output.write("\ufeff")
            # 写入 utf-8 bom 避免纯文本乱码
            fieldnames = constants.TMP_HEADERS
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
            output.seek(0)
            response = HttpResponse(output.getvalue().encode("utf-8"), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f"attachment; filename={filename}"
            return response
        else:
            return results


class GetFourMetricsStrategy(Resource):
    """
    游戏业务下四线统计 业务相关策略数据接口
    """

    def perform_request(self, validated_request_data):
        """
        在线： 在线 或 online
        登录： 登录 或 登陆 或 login
        注册： 注册 或 registation 或 reg
        对局： 对局 或 排队 或 battle 或 bat
        """
        # 策略业务统计
        results_format = validated_request_data.get("results", "json")
        biz_list = api.cmdb.get_business()
        scenario = constants.SCENARIO
        to_be_deleted = set()
        Biz = namedtuple("Biz", ["name", "info"])
        biz_map = {biz.bk_biz_id: Biz(biz.display_name, defaultdict(int)) for biz in biz_list if biz.bk_biz_id > 0}

        for sce, key_words in scenario.items():
            query = StrategyModel.objects.filter(
                reduce(lambda x, y: x | y, (DQ(name__icontains=key) for key in key_words))
            )
            query = query.filter(is_enabled=True)
            # 使用 values 和 annotate 来按 bk_biz_id 分组，然后计算每组的数量
            result = query.values("bk_biz_id").annotate(count=Count("id"))
            # 整理结果
            for item in result:
                bk_biz_id = int(item["bk_biz_id"])
                if bk_biz_id < 0:
                    continue
                if bk_biz_id not in biz_map:
                    to_be_deleted.add(bk_biz_id)
                    continue
                biz_map[bk_biz_id].info[sce] = item["count"]
        results = []
        for biz in biz_map.values():
            row = {"业务": biz.name}
            for key in scenario.keys():
                row[key] = biz.info.get(key, 0)
            results.append(row)
        if results_format == "file":
            timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            filename = f"data_{timestamp}.csv"
            output = StringIO()
            # 在内存读写文件 避免污染 Pod 的 OS 文件
            output.write("\ufeff")
            # 写入 utf-8 bom 避免纯文本乱码
            fieldnames = ["业务"] + list(scenario.keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
            output.seek(0)
            response = HttpResponse(output.getvalue().encode("utf-8"), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f"attachment; filename={filename}"
            return response
        else:
            return results


class AlertPermissionResource(Resource):
    @classmethod
    def has_biz_permission(cls):
        """
        业务鉴权
        """
        client = Permission()
        request = get_request(peaceful=True)
        try:
            is_allowed = client.is_allowed_by_biz(request.biz_id, ActionEnum.VIEW_EVENT, raise_exception=False)
        except Exception:
            logger.warning(
                "user(%s) permission validate failed, request path(%s), request.user(%s),"
                " user.type(%s), current request meta %s",
                client.username,
                request.path_info,
                request.user.__dict__,
                type(request.user),
                request.META,
            )
            raise
        return is_allowed

    @classmethod
    def has_alert_permission(cls, alert_id: int):
        """
        事件鉴权
        """
        try:
            alert = AlertDocument.get(alert_id)
            username = get_request().user.username
            bk_biz_id = int(get_request().biz_id)
            if int(alert.event.bk_biz_id) == bk_biz_id and username in alert.assignee:
                # 业务ID能对上
                # 是当前告警的负责人
                return True
        except Exception:
            pass
        return False

    @classmethod
    def filter_alert_ids(cls, alert_ids: list[int]):
        """
        过滤出有权限的事件ID
        """

        search = (
            AlertDocument.search(all_indices=True)
            .filter("terms", id=alert_ids)
            .filter("term", assignee=get_request().user.username)
            .source(fields=["id"])
        )

        return [hit.id for hit in search.scan()]

    @classmethod
    def has_alert_collect_permission(cls, alert_collect_id: int):
        """
        通知汇总鉴权
        """
        try:
            action = ActionInstance.objects.get(id=str(alert_collect_id)[10:])
            for alert in action.alerts:
                if not cls.has_alert_permission(alert):
                    # 只要其中有告警没权限，返回没权限
                    return False
        except Exception:
            pass

        return False

    def request(self, request_data=None, **kwargs):
        """
        执行请求，并对请求数据和返回数据进行数据校验
        """
        request_data = request_data or kwargs
        validated_request_data = self.validate_request_data(request_data)

        if not self.has_biz_permission():
            if "id" in validated_request_data and not self.has_alert_permission(validated_request_data["id"]):
                raise ValidationError(_("无该告警查看权限"))
            if "event_id" in validated_request_data and not self.has_alert_permission(
                validated_request_data["event_id"]
            ):
                raise ValidationError(_("无该告警查看权限"))
            elif "ids" in validated_request_data:
                validated_request_data["ids"] = self.filter_alert_ids(validated_request_data["ids"])
            elif "alert_collect_id" in validated_request_data:
                if not self.has_alert_collect_permission(validated_request_data["alert_collect_id"]):
                    raise ValidationError(_("无该告警查看权限"))
            elif "action_id" in validated_request_data:
                if not self.has_alert_collect_permission(validated_request_data["action_id"]):
                    raise ValidationError(_("无该告警查看权限"))
            else:
                validated_request_data["receiver"] = get_request().user.username

        response_data = self.perform_request(validated_request_data)
        validated_response_data = self.validate_response_data(response_data)
        return validated_response_data


class QuickActionTokenResource(AlertPermissionResource):
    def validate_request_data(self, request_data):
        validated_data = super().validate_request_data(request_data)
        validated_data["alert_ids"] = self.validate_token(str(validated_data["action_id"]), validated_data["token"])
        return validated_data

    def validate_token(self, action_id, token):
        try:
            action = ActionInstance.objects.get(id=action_id[10:])
            create_timestamp = int(action.create_time.timestamp())
            alert_ids = action.alerts
        except ActionInstance.DoesNotExist:
            action_doc = ActionInstanceDocument.get(action_id)
            if not action_doc:
                raise CustomException(
                    _("Resource[{}] 请求参数格式错误, 请求的通知ID不存在").format(self.get_resource_name())
                )
            create_timestamp = action_doc.create_time
            alert_ids = action_doc.alert_id
        if count_md5([action_id, create_timestamp]) != token:
            raise CustomException(
                _("Resource[{}] 请求参数格式错误, 请求的token不正确").format(self.get_resource_name())
            )
        return alert_ids

    @staticmethod
    def redirect(bk_biz_id, action_id):
        request = get_request()
        mobile_url = f"/weixin/?bizId={bk_biz_id}&collectId={action_id}"
        pc_url = f"/?bizId={bk_biz_id}&routeHash=event-center/?collectId={action_id}#/"
        redirect_url = mobile_url if request.is_mobile() else pc_url
        return HttpResponseRedirect(redirect_url)


class ListAllowedBizResource(Resource):
    """
    获取用户有某个操作权限的业务
    """

    class RequestSerializer(serializers.Serializer):
        action_id = serializers.CharField(label="动作ID")

    def perform_request(self, validated_request_data):
        permission = Permission()
        spaces = permission.filter_space_list_by_action(validated_request_data["action_id"])
        return [{"id": s["bk_biz_id"], "name": s["bk_biz_name"]} for s in spaces]


class ListSearchHistoryResource(Resource):
    """
    获取检索历史
    """

    class RequestSerializer(serializers.Serializer):
        search_type = serializers.ChoiceField(label="检索类型", choices=SEARCH_TYPE_CHOICES, default=SearchType.ALERT)
        count = serializers.IntegerField(label="返回条数", default=10, min_value=1)

    def perform_request(self, validated_request_data):
        username = get_request_username()
        histories = SearchHistory.objects.filter(
            create_user=username, search_type=validated_request_data["search_type"]
        ).order_by("-create_time")

        result: list[SearchHistory] = []
        params_set = set()
        for history in histories.iterator():
            query_string = history.params.get("query_string")
            if not query_string or query_string in params_set:
                continue
            result.append(history)
            params_set.add(query_string)
            if len(result) >= validated_request_data["count"]:
                break

        return [
            {
                "create_user": history.create_user,
                "create_time": history.create_time,
                "params": history.params,
                "duration": history.duration,
                "search_type": history.search_type,
            }
            for history in result
        ]


class AlertDateHistogramResource(Resource):
    """
    查询告警分布直方图
    """

    class RequestSerializer(AlertSearchSerializer):
        interval = serializers.CharField(label="聚合周期", default="auto")

    def perform_request(self, validated_request_data):
        start_time = validated_request_data.pop("start_time")
        end_time = validated_request_data.pop("end_time")
        interval = validated_request_data.pop("interval")
        interval = BaseQueryHandler.calculate_agg_interval(start_time, end_time, interval)
        if validated_request_data["bk_biz_ids"] is not None:
            authorized_bizs, unauthorized_bizs = AlertQueryHandler.parse_biz_item(validated_request_data["bk_biz_ids"])
            validated_request_data["authorized_bizs"] = authorized_bizs
            validated_request_data["unauthorized_bizs"] = unauthorized_bizs
        results = resource.alert.alert_date_histogram_result.bulk_request(
            [
                {
                    "start_time": sliced_start_time,
                    "end_time": sliced_end_time,
                    "interval": interval,
                    **validated_request_data,
                }
                for sliced_start_time, sliced_end_time in slice_time_interval(start_time, end_time)
            ]
        )

        data = {status: {} for status in EVENT_STATUS_DICT}
        for result in results:
            for status, series in result.items():
                if status == "default_time_series":
                    interval = series["interval"]
                    start_time = series["start_time"] // interval * interval
                    end_time = series["end_time"] // interval * interval + interval
                    default_time_series = {ts * 1000: 0 for ts in range(start_time, end_time, interval)}
                    for sta in EVENT_STATUS_DICT:
                        data[sta].update(default_time_series)
                    continue

                data[status].update(series)
        return {
            "series": [
                {"data": list(series.items()), "name": status, "display_name": EVENT_STATUS_DICT[status]}
                for status, series in data.items()
            ],
            "unit": "",
        }


class AlertDateHistogramResultResource(Resource):
    def perform_request(self, validated_request_data):
        interval = validated_request_data.pop("interval")
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        handler = AlertQueryHandler(**validated_request_data)
        datas = list(handler.date_histogram(interval=interval).values())
        if not datas:
            data = {"default_time_series": {"start_time": start_time, "end_time": end_time, "interval": interval}}
            return data
        return datas[0]


class AlertDetailResource(Resource):
    """
    根据ID获取告警
    """

    class RequestSerializer(serializers.Serializer):
        id = AlertIDField(required=True, label="告警ID")

    @classmethod
    def get_relation_info(cls, alert: AlertDocument, length_limit=True):
        """
        获取告警最近的日志
        """
        return get_alert_relation_info(alert, length_limit)

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["id"]

        alert = AlertDocument.get(alert_id)

        graph_panel = AIOPSManager.get_graph_panel(alert)
        relation_info = self.get_relation_info(alert, False)

        result = AlertQueryHandler.clean_document(alert)
        result["plugin_display_name"] = PluginTranslator().translate([result["plugin_id"]])[result["plugin_id"]]
        result["extend_info"] = resource.alert.alert_related_info(ids=[alert_id]).get(alert_id, {})
        result["graph_panel"] = graph_panel

        topo_info = result["extend_info"].get("topo_info", "")
        result["relation_info"] = f"{topo_info} {relation_info}"
        self.add_project_name(result)

        return result

    @classmethod
    def add_project_name(cls, data):
        """
        如果维度中存在key=tags.bcs_cluster_id，则在维度中增加project_name字段
        用于前端进行集群跳转

        data["dimensions"]:[
            {
              "display_value": "BCS-K8S-00000(蓝鲸7.0)",
              "display_key": "bcs_cluster_id",
              "value": "BCS-K8S-00000",
              "key": "tags.bcs_cluster_id"
            }
        ]
        """
        for d in data["dimensions"]:
            if d["key"].replace("tags.", "") != "bcs_cluster_id":
                continue

            cluster = BCSCluster.objects.filter(bcs_cluster_id=d["value"]).first()
            if cluster and cluster.space_uid:
                d["project_name"] = cluster.space_uid.split("__")[1]
            else:
                d["project_name"] = ""


class GetExperienceResource(ApiAuthResource):
    """
    获取告警处理经验
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        alert_id = AlertIDField(required=False, label="告警ID")
        metric_id = serializers.CharField(label="指标", required=False)

        def validate(self, attrs):
            if "alert_id" not in attrs and "metric_id" not in attrs:
                raise ValidationError("alert_id and metric_id cannot be empty at the same time")
            return attrs

    def perform_request(self, params):
        if "alert_id" in params:
            alert_id = params["alert_id"]
            alert = AlertDocument.get(alert_id)
            metric = list(alert.event_document.metric)
            bk_biz_id = alert.event_document.bk_biz_id or 0

            if not metric:
                alert_name = alert.alert_name
            else:
                alert_name = ""

            dimensions = {dimension.key: dimension.value for dimension in alert.dimensions}
            if alert.origin_alarm:
                dimensions.update(alert.origin_alarm.get("data", {}).get("dimensions", {}))
        else:
            bk_biz_id = params["bk_biz_id"]
            metric = params["metric_id"].split(",")
            dimensions = {}
            alert_name = ""

        suggestions = []

        for suggestion in AlertSuggestion.objects.filter(bk_biz_id=bk_biz_id).order_by("-update_time"):
            if suggestion.alert_name == alert_name and suggestion.metric == metric:
                data = AlertSuggestionSerializer(instance=suggestion).data
                if suggestion.type == AlertSuggestion.Type.METRIC:
                    data["is_match"] = True
                else:
                    condition_obj = load_agg_condition_instance(suggestion.conditions)
                    data["is_match"] = condition_obj.is_match(dimensions)
                suggestions.append(data)

        # 匹配的排在前头
        suggestions.sort(key=lambda x: x["is_match"], reverse=True)

        # metric 排在前头
        suggestions.sort(key=lambda x: x["type"] == AlertSuggestion.Type.METRIC, reverse=True)
        return suggestions


class SaveExperienceResource(Resource):
    """
    保存告警处理经验
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        alert_id = AlertIDField(required=False, label="告警ID")
        metric_id = serializers.CharField(required=False, label="指标ID")

        description = serializers.CharField(required=True, label="处理描述")
        type = serializers.ChoiceField(label="类型", choices=AlertSuggestion.TYPE_CHOICES)
        conditions = serializers.ListField(
            default=[], label="查询条件", allow_empty=True, child=serializers.DictField()
        )

        def validate(self, attrs):
            if "alert_id" not in attrs and "metric_id" not in attrs:
                raise ValidationError("alert_id and metric_id cannot be empty at the same time")
            return attrs

    def perform_request(self, params):
        if "alert_id" in params:
            alert_id = params["alert_id"]

            alert = AlertDocument.get(alert_id)
            metric = list(alert.event_document.metric)
            bk_biz_id = alert.event_document.bk_biz_id or 0

            if not metric:
                alert_name = alert.alert_name
            else:
                alert_name = ""
        else:
            alert_name = ""
            bk_biz_id = params["bk_biz_id"]
            metric = params["metric_id"].split(",")
        if params["type"] == AlertSuggestion.Type.METRIC:
            params["conditions"] = []

        suggestion_id = AlertSuggestion.generate_id(
            bk_biz_id=bk_biz_id,
            type=params["type"],
            metric=metric,
            alert_name=alert_name,
            conditions=params["conditions"],
        )

        try:
            suggestion = AlertSuggestion.objects.get(id=suggestion_id)
        except AlertSuggestion.DoesNotExist:
            suggestion = AlertSuggestion(
                id=suggestion_id,
                create_user=get_global_user(),
                bk_biz_id=bk_biz_id,
                type=params["type"],
                metric=metric,
                alert_name=alert_name,
                conditions=params["conditions"],
            )

        suggestion.description = params["description"]
        suggestion.save()

        return AlertSuggestionSerializer(instance=suggestion).data


class DeleteExperienceResource(Resource):
    """
    删除处理经验
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.CharField(label="处理建议ID")

    def perform_request(self, validated_request_data):
        try:
            suggestion = AlertSuggestion.objects.get(id=validated_request_data["id"])
        except AlertSuggestion.DoesNotExist:
            pass
        else:
            # 进行硬删除
            suggestion.delete(hard=True)


class AlertEventCountResource(Resource):
    """
    获取告警关联的事件数量
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(label="告警ID", child=AlertIDField())

    @classmethod
    def cal_simple_event_count(cls, simple_alerts):
        # 计算简单告警的事件数量
        if not simple_alerts:
            return {}

        now_time = int(time.time())
        alert_mapping = {}
        for alert in simple_alerts:
            alert_mapping[alert.id] = {
                "dedupe_md5": alert.dedupe_md5,
                "query": (
                    Q("range", time={"gte": alert.begin_time, "lte": alert.latest_time or now_time})
                    & Q("term", dedupe_md5=alert.dedupe_md5)
                ),
            }

        event_count = {}
        # Step 2: 根据时间范围和MD5去查询告警信息
        search = EventDocument.search(all_indices=True)
        search = search.filter("terms", dedupe_md5=[alert["dedupe_md5"] for alert in alert_mapping.values()])

        for alert_id, alert in alert_mapping.items():
            # 为每个告警条件设置一个桶
            search.aggs.bucket(alert_id, "filter", alert["query"])

        search = search.extra(size=0)
        search_result = search.execute()

        for alert_id in alert_mapping:
            if not search_result.aggs:
                continue
            bucket = getattr(search_result.aggs, alert_id, None)
            if not bucket:
                continue
            event_count[alert_id] = bucket.doc_count
        return event_count

    @classmethod
    def cal_composite_event_count(cls, composite_alerts):
        """
        计算关联告警的事件数量
        """
        if not composite_alerts:
            return {}

        event_count = {}
        results = resource.alert.search_event.bulk_request(
            [{"alert_id": alert.id, "page_size": 1} for alert in composite_alerts], ignore_exceptions=True
        )
        for index, result in enumerate(results):
            if result:
                event_count[composite_alerts[index].id] = result["total"]
        return event_count

    def perform_request(self, validated_request_data):
        alert_ids = validated_request_data["ids"]

        # Step 1: 先根据告警ID，查询对应的告警，将开始结束时间和md5字段拿出来
        alerts = AlertDocument.mget(
            alert_ids, fields=["id", "begin_time", "end_time", "latest_time", "dedupe_md5", "extra_info"]
        )

        simple_alerts = []
        composite_alerts = []
        for alert in alerts:
            if alert.is_composite_strategy or alert.is_fta_event_strategy:
                composite_alerts.append(alert)
            else:
                simple_alerts.append(alert)

        event_count = {}
        for alert_id in alert_ids:
            event_count.setdefault(alert_id, 0)
        event_count.update(self.cal_simple_event_count(simple_alerts))
        event_count.update(self.cal_composite_event_count(composite_alerts))
        return event_count


class AlertRelatedInfoResource(Resource):
    """
    事件关联信息查询
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(label="告警ID", child=AlertIDField(), required=False)
        alerts = serializers.ListField(label="告警文档", required=False)

        def validate(self, attrs):
            if "ids" not in attrs and "alerts" not in attrs:
                raise serializers.ValidationError("Either 'ids' or 'alerts' must be provided.")
            return attrs

    @staticmethod
    def get_cmdb_related_info(alerts: list[AlertDocument]) -> dict[str, dict]:
        """
        查询事件拓扑信息

        {
            "type": "host",
            "ip"： "",
            "bk_cloud_id": "",
            "hostname": "",
            "topo_info": ""
        }
        """
        related_infos = defaultdict(dict)

        # 提取事件的主机IP和服务实例ID，按业务分组
        instances_by_biz = defaultdict(lambda: {"ips": {}, "service_instance_ids": {}, "host_ids": {}})
        for alert in alerts:
            event = alert.event
            dimensions_dict = {d["key"]: d["value"] for d in alert.dimensions}
            if not dimensions_dict:
                continue
            try:
                if event.target_type == EventTargetType.HOST:
                    if hasattr(event, "bk_host_id"):
                        instances_by_biz[event.bk_biz_id]["host_ids"][alert.id] = int(event.bk_host_id)
                    else:
                        instances_by_biz[event.bk_biz_id]["ips"][alert.id] = {
                            "ip": event.ip,
                            "bk_cloud_id": int(event.bk_cloud_id),
                        }
                    related_infos[alert.id]["ip"] = event.ip
                    related_infos[alert.id]["bk_cloud_id"] = getattr(event, "bk_cloud_id", "")
                    related_infos[alert.id]["type"] = "host"
                elif dimensions_dict.get("ip"):
                    bk_cloud_id = dimensions_dict.get("bk_cloud_id", 0)
                    if dimensions_dict.get("bk_host_id"):
                        instances_by_biz[event.bk_biz_id]["host_ids"][alert.id] = int(dimensions_dict["bk_host_id"])
                    else:
                        instances_by_biz[event.bk_biz_id]["ips"][alert.id] = {
                            "ip": dimensions_dict["ip"],
                            "bk_cloud_id": bk_cloud_id,
                        }

                    related_infos[alert.id]["ip"] = dimensions_dict["ip"]
                    related_infos[alert.id]["bk_cloud_id"] = bk_cloud_id
                    related_infos[alert.id]["type"] = dimensions_dict.get("target_type", "")
                elif event.target_type == EventTargetType.SERVICE:
                    instances_by_biz[event.bk_biz_id]["service_instance_ids"][alert.id] = event.bk_service_instance_id
            except AttributeError:
                continue

        set_template = _("集群({}) ")
        module_template = _("模块({})")
        environment_template = _(" 环境类型({})")
        environment_mapping = {"1": _("测试"), "2": _("体验"), "3": _("正式")}

        def enrich_related_infos(params_tuple: tuple) -> None:
            bk_biz_id, instances = params_tuple
            ips = instances["ips"]
            service_instance_ids = instances["service_instance_ids"]
            host_ids = instances["host_ids"]
            # 查询主机和服务实例信息
            hosts: list[Host] = api.cmdb.get_host_by_ip(bk_biz_id=bk_biz_id, ips=list(ips.values()))
            hosts.extend(api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=list(host_ids.values())))
            service_instances: list[ServiceInstance] = api.cmdb.get_service_instance_by_id(
                bk_biz_id=bk_biz_id, service_instance_ids=list(service_instance_ids.values())
            )

            # 将主机和服务实例转为模块ID
            host_to_module_id = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_module_ids for host in hosts}
            host_to_hostname = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_host_name for host in hosts}
            host_id_to_module_id = {host.bk_host_id: host.bk_module_ids for host in hosts}
            host_id_to_hostname = {host.bk_host_id: host.bk_host_name for host in hosts}
            service_to_module_id = {service.service_instance_id: service.bk_module_id for service in service_instances}

            all_bk_module_ids = set()
            for host in hosts:
                all_bk_module_ids.update(host.bk_module_ids)
            for service_instance in service_instances:
                all_bk_module_ids.add(service_instance.bk_module_id)

            # 查询模块和集群信息
            modules = api.cmdb.get_module(bk_biz_id=bk_biz_id, bk_module_ids=all_bk_module_ids)
            module_to_set = {module.bk_module_id: module.bk_set_id for module in modules}
            sets = api.cmdb.get_set(bk_biz_id=bk_biz_id, bk_set_ids=list(module_to_set.values()))
            module_names = {module.bk_module_id: module.bk_module_name for module in modules}
            set_names = {s.bk_set_id: s.bk_set_name for s in sets}
            environment_types = {s.bk_set_id: s.bk_set_env for s in sets}

            # 事件对应到模块ID
            alert_to_module_ids = {}
            for alert_id, ip in ips.items():
                alert_to_module_ids[alert_id] = host_to_module_id.get((ip["ip"], ip["bk_cloud_id"]), [])
                related_infos[alert_id]["hostname"] = host_to_hostname.get((ip["ip"], ip["bk_cloud_id"]), "")

            for alert_id, host_id in host_ids.items():
                alert_to_module_ids[alert_id] = host_id_to_module_id.get(host_id, [])
                related_infos[alert_id]["hostname"] = host_id_to_hostname.get(host_id, "")

            for alert_id, service_instance_id in service_instance_ids.items():
                if service_instance_id in service_to_module_id:
                    alert_to_module_ids[alert_id] = [service_to_module_id[service_instance_id]]

            # 记录事件集群模块描述信息
            for alert_id, bk_module_ids in alert_to_module_ids.items():
                topo_info = ""
                if not bk_module_ids:
                    related_infos[alert_id]["topo_info"] = topo_info
                    continue

                bk_set_ids = [
                    module_to_set[bk_module_id] for bk_module_id in bk_module_ids if bk_module_id in module_to_set
                ]

                if bk_set_ids:
                    topo_info += set_template.format(
                        ",".join([set_names[bk_set_id] for bk_set_id in bk_set_ids if bk_set_id in set_names])
                    )

                topo_info += module_template.format(
                    ",".join(
                        [module_names[bk_module_id] for bk_module_id in bk_module_ids if bk_module_id in module_names]
                    )
                )

                if environment_types and bk_set_ids:
                    environments = []
                    for bk_set_id in bk_set_ids:
                        environment_type_id = environment_types.get(bk_set_id)
                        if environment_type_id is not None:
                            environment = environment_mapping.get(environment_type_id, str(environment_type_id))
                            environments.append(environment)

                    if environments:
                        topo_info += environment_template.format(",".join(environments))

                related_infos[alert_id]["topo_info"] = topo_info

        # 多线程处理每个业务的主机和服务实例信息
        with ThreadPool(8) as executor:
            executor.map(enrich_related_infos, list(instances_by_biz.items()))

        return related_infos

    @staticmethod
    def get_log_related_info(alerts: list[AlertDocument]) -> dict[str, dict]:
        """
        日志平台关联信息

        {
            "type": "log_search",
            "index_set_id": "",
            "query_string": "",
            "agg_condition": []
        }
        """

        related_infos = defaultdict(dict)

        for alert in alerts:
            if not alert.strategy:
                continue
            item = alert.strategy["items"][0]
            query_config = item["query_configs"][0]
            if query_config["data_source_label"] != DataSourceLabel.BK_LOG_SEARCH:
                continue

            if not query_config.get("index_set_id"):
                continue

            related_infos[alert.id] = {
                "type": "log_search",
                "index_set_id": query_config["index_set_id"],
                "query_string": query_config.get("query_string", "*"),
                "agg_condition": query_config["agg_condition"],
            }

        return related_infos

    @staticmethod
    def get_custom_event_related_info(alerts: list[AlertDocument]) -> dict[str, dict]:
        """
        自定义事件关联信息

        {
            "type": "custom_event",
            "bk_event_group_id": 1
        }
        """
        related_infos = defaultdict(dict)

        event_groups = CustomEventGroup.objects.filter(
            bk_biz_id__in=[alert.event.bk_biz_id for alert in alerts if alert.event.bk_biz_id]
        )
        table_id_to_group_ids = {event_group.table_id: event_group.bk_event_group_id for event_group in event_groups}

        for alert in alerts:
            if not alert.strategy:
                continue
            item = alert.strategy["items"][0]
            query_config = item["query_configs"][0]

            related_infos[alert.id]["result_table_id"] = query_config.get("result_table_id")
            related_infos[alert.id]["data_label"] = query_config.get("data_label", "")

            if (query_config["data_source_label"], query_config["data_type_label"]) != (
                DataSourceLabel.CUSTOM,
                DataTypeLabel.EVENT,
            ):
                continue

            if query_config["result_table_id"] in table_id_to_group_ids:
                related_infos[alert.id]["type"] = "custom_event"
                related_infos[alert.id]["bk_event_group_id"] = table_id_to_group_ids[query_config["result_table_id"]]

        return related_infos

    @staticmethod
    def get_bkdata_related_info(alerts: list[AlertDocument]) -> dict[str, dict]:
        """
        数据平台关联信息
        {
            "type": "bkdata",
            "metric_field": "",
            "group_by": "",
            "result_table_id": "",
            "method": "",
            "where": "",
            "interval": "",
        }
        """
        related_infos = defaultdict(dict)

        for alert in alerts:
            if not alert.strategy:
                continue
            strategy = alert.strategy

            if not strategy["items"]:
                continue

            item = strategy["items"][0]
            query_config = item["query_configs"][0]

            raw_query_config = query_config.get("raw_query_config", {})
            query_config.update(raw_query_config)

            if query_config["data_source_label"] != DataSourceLabel.BK_DATA:
                continue

            related_infos[alert.id] = {
                "type": "bkdata",
                "query_configs": [
                    {
                        "data_type_label": query_config["data_type_label"],
                        "data_source_label": query_config["data_source_label"],
                        "metric_field": query_config["metric_field"],
                        "group_by": query_config["agg_dimension"],
                        "result_table_id": query_config["result_table_id"],
                        "method": query_config["agg_method"],
                        "where": query_config["agg_condition"],
                        "interval": query_config["agg_interval"],
                    }
                ],
            }

        return related_infos

    def perform_request(self, validated_request_data):
        if "ids" in validated_request_data:
            alerts = AlertDocument.mget(validated_request_data["ids"])
        else:
            alerts = validated_request_data["alerts"]

        related_infos = defaultdict(dict)

        for func in [
            self.get_cmdb_related_info,
            self.get_custom_event_related_info,
            self.get_bkdata_related_info,
            self.get_log_related_info,
        ]:
            infos = func(alerts)
            for alert_id, info in infos.items():
                related_infos[alert_id].update(info)

        return related_infos


class AckAlertResource(Resource):
    """
    告警确认
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(label="告警ID", child=AlertIDField())
        message = serializers.CharField(required=True, allow_blank=True, label="确认信息")

    def perform_request(self, validated_request_data):
        alert_ids = validated_request_data["ids"]

        alerts_should_ack = set()
        alerts_already_ack = set()
        alerts_not_abnormal = set()

        alerts = AlertDocument.mget(alert_ids)

        for alert in alerts:
            if alert.status != EventStatus.ABNORMAL:
                alerts_not_abnormal.add(alert.id)
            elif alert.is_ack:
                alerts_already_ack.add(alert.id)
            else:
                alerts_should_ack.add(alert.id)

        alerts_not_exist = set(alert_ids) - alerts_should_ack - alerts_already_ack - alerts_not_abnormal

        now_time = int(time.time())
        # 保存流水日志
        AlertLog(
            alert_id=list(alerts_should_ack),
            op_type=AlertLog.OpType.ACK,
            create_time=now_time,
            description=validated_request_data["message"],
            operator=get_request_username(),
        ).save()

        # 更新告警确认状态
        alert_documents = [
            AlertDocument(
                id=alert_id,
                is_ack=True,
                is_ack_noticed=False,
                ack_operator=get_request_username(),
                update_time=now_time,
            )
            for alert_id in alerts_should_ack
        ]
        AlertDocument.bulk_create(alert_documents, action=BulkActionType.UPDATE)
        return {
            "alerts_ack_success": list(alerts_should_ack),
            "alerts_not_exist": list(alerts_not_exist),
            "alerts_already_ack": list(alerts_already_ack),
            "alerts_not_abnormal": list(alerts_not_abnormal),
        }


class CloseAlertResource(Resource):
    """
    告警关闭
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        ids = serializers.ListField(label="告警ID列表", child=AlertIDField())
        message = serializers.CharField(allow_blank=True, label="确认信息", default="")

    def perform_request(self, validated_request_data: dict[str, Any]):
        alert_ids = validated_request_data["ids"]

        # 需要关闭的告警
        alerts_should_close = set()
        # 已经结束的告警
        alerts_already_end = set()

        alerts = AlertDocument.mget(alert_ids)

        for alert in alerts:
            # 告警状态为异常且未确认，则需要关闭
            if alert.status == EventStatus.ABNORMAL and not alert.is_ack:
                alerts_should_close.add(alert.id)
            else:
                alerts_already_end.add(alert.id)

        # 不存在的告警
        alerts_not_exist = set(alert_ids) - alerts_should_close - alerts_already_end

        now_time = int(time.time())
        # 保存流水日志
        AlertLog(
            alert_id=list(alerts_should_close),
            op_type=AlertLog.OpType.CLOSE,
            create_time=now_time,
            description=validated_request_data["message"],
            operator=get_request_username(),
        ).save()

        # 更新告警确认状态
        alert_documents = [
            AlertDocument(
                id=alert_id,
                status=EventStatus.CLOSED,
                update_time=now_time,
            )
            for alert_id in alerts_should_close
        ]
        AlertDocument.bulk_create(alert_documents, action=BulkActionType.UPDATE)
        return {
            "alerts_close_success": list(alerts_should_close),
            "alerts_not_exist": list(alerts_not_exist),
            "alerts_already_end": list(alerts_already_end),
        }


class AlertGraphQueryResource(ApiAuthResource):
    """
    告警图表接口
    """

    class RequestSerializer(serializers.Serializer):
        class QueryConfigSerializer(serializers.Serializer):
            class MetricSerializer(serializers.Serializer):
                field = serializers.CharField()
                method = serializers.CharField(allow_blank=True)
                alias = serializers.CharField(required=False)
                display = serializers.BooleanField(default=False)

            data_source_label = serializers.CharField(label="数据来源")
            data_type_label = serializers.CharField(
                label="数据类型", default="time_series", allow_null=True, allow_blank=True
            )
            metrics = serializers.ListField(label="查询指标", allow_empty=True, child=MetricSerializer(), default=[])
            table = serializers.CharField(label="结果表名", allow_blank=True, default="")
            data_label = serializers.CharField(label="db标识", allow_blank=True, default="")
            promql = serializers.CharField(label="PromQL", allow_blank=True, required=False)
            where = serializers.ListField(label="过滤条件", default=[])
            group_by = serializers.ListField(label="聚合字段", default=[])
            interval = serializers.IntegerField(default=60, label="时间间隔")
            filter_dict = serializers.DictField(default={}, label="过滤条件")
            time_field = serializers.CharField(label="时间字段", allow_blank=True, allow_null=True, required=False)

            # 日志平台配置
            query_string = serializers.CharField(default="", allow_blank=True, label="日志查询语句")
            index_set_id = serializers.IntegerField(required=False, label="索引集ID")
            functions = serializers.ListField(label="查询函数", default=[])

            def validate(self, attrs: dict) -> dict:
                if attrs["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH and not attrs.get("index_set_id"):
                    raise ValidationError("index_set_id can not be empty.")
                for condition in attrs["where"]:
                    if isinstance(condition["value"], list):
                        if len(condition["value"]) == 1 and None in condition["value"]:
                            condition["value"].remove(None)
                return attrs

        id = serializers.IntegerField(label="事件ID")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        query_configs = serializers.ListField(label="查询配置列表", default=[], child=QueryConfigSerializer())
        function = serializers.DictField(label="功能函数", default={})
        functions = serializers.ListField(label="计算函数", default=[])
        expression = serializers.CharField(label="查询表达式", allow_blank=True)
        start_time = serializers.IntegerField(required=False, label="开始时间")
        end_time = serializers.IntegerField(required=False, label="结束时间")

    def perform_request(self, params: dict):
        alert = AlertDocument.get(params["id"])
        if not params.get("query_configs"):
            graph_query_config = AIOPSManager.get_graph_panel(alert, compare_function={})
            params.update(graph_query_config["targets"][0]["data"])

        if alert.strategy:
            item = alert.strategy["items"][0]
            query_config = item["query_configs"][0]
            if (
                query_config["data_source_label"],
                query_config["data_type_label"],
            ) not in AIOPSManager.AVAILABLE_DATA_LABEL:
                return []
        else:
            # 第三方告警的情况
            item = None
            query_config = {}

        threshold_band = {"from": alert.first_anomaly_time * 1000, "to": None}

        # 1. 时间的起始时间，当刚发生时是发生时间段往前60个周期的图。
        # 2. 当发生的时间一直往后延，起始时间变成 初次异常+5个周期前数据
        # 3. 结束时间一直到事件结束的后的5个周期 ，或者超过1440个周期 最多到1440个周期数据
        if not params.get("start_time") or not params.get("end_time"):
            start_time = alert.begin_time
            if alert.end_time:
                threshold_band["to"] = alert.end_time * 1000
                end_time = alert.end_time
            else:
                end_time = datetime2timestamp(now())
            interval = params["query_configs"][0]["interval"]
            end_time = min(end_time + interval * 5, start_time + 1440 * interval)
            diff = 1440 * interval - (end_time - start_time)
            if diff < interval * 5:
                diff = interval * 5
            elif diff > interval * 60:
                diff = interval * 60
            start_time -= diff
            params["start_time"] = int(start_time)
            params["end_time"] = int(end_time)
        else:
            start_time = params["start_time"]
            end_time = params["end_time"]
        for q_config in params["query_configs"]:
            q_config["bk_biz_id"] = params["bk_biz_id"]

        logger.info("alert graph query params %s", dict(params))
        result = resource.grafana.graph_unify_query(params)

        # 返回信息加上数据查询的时间范围
        result["date_range"] = [start_time, int(end_time)]

        result["trace_series"] = []
        if (
            query_config
            and (query_config["data_source_label"], query_config["data_type_label"]) in UnifyQueryDataSources
        ):
            # 数据源是蓝鲸监控和自定义上报的时序数据才支持trace信息查找
            try:
                result["trace_series"] = resource.grafana.graph_trace_query(params).get("series", [])
            except BaseException as error:
                logger.warning("alert trace value query failed %s", str(error))
        data = result["series"]
        if not data or not item:
            return result

        unit = load_unit(data[0].get("unit", ""))
        # 暂时只支持静态阈值,以后显示同比环比
        # 用列表是因为同一level下,可以既有静态阈值,又有同比策略
        alert_algorithm_list = [algorithm for algorithm in item["algorithms"] if algorithm["level"] == alert.severity]
        threshold_line = []
        if len(alert_algorithm_list) == 1 and alert_algorithm_list[0]["type"] == AlgorithmType.Threshold:
            threshold_config = alert_algorithm_list[0]["config"]
            if len(threshold_config) == 1 and len(threshold_config[0]) == 1:
                # 算法的值转换为数值单位
                algorithm_unit = alert_algorithm_list[0].get("unit_prefix", "")
                threshold_value = float(threshold_config[0][0]["threshold"])
                threshold_value = unit.convert(threshold_value, unit.unit, algorithm_unit)

                threshold_line.append({"yAxis": threshold_value, "name": _("阈值算法")})

        # 取出首次异常点，保证首次异常点在图表中
        point = None
        try:
            # 针对时序预测进行特殊处理，将未来时间的点标记出来
            for series in data:
                if series["metric_field"] != "predict":
                    continue
                # 尝试取出预测点
                anomaly = alert.event.extra_info.origin_alarm.anomaly.to_dict()
                predict_point = list(anomaly.values())[0]["context"]["predict_point"]
                point = [predict_point[0], predict_point[1] * 1000]
                series["markPoints"] = [point]
                break
        except Exception:
            pass

        if point:
            return result

        point = [alert.origin_alarm["data"]["value"], threshold_band["from"]]
        point_time_list = [point[1] for point in data[0]["datapoints"]]
        first_anomaly_in_time_range = start_time <= threshold_band["from"] <= end_time
        if threshold_band["from"] not in point_time_list and first_anomaly_in_time_range:
            position = bisect.bisect(point_time_list, threshold_band["from"])
            data[0]["datapoints"].insert(position, point)

        mark_points = [point]

        # 离群检测算法特殊处理
        if (
            len(alert_algorithm_list) == 1
            and alert_algorithm_list[0]["type"] == AlgorithmModel.AlgorithmChoices.AbnormalCluster
        ):
            # 离群检测算法不需要异常点
            mark_points = []

            # 离群检测所有维度都需要区域
            for data_item in data:
                data_item["markTimeRange"] = [threshold_band]

        data[0]["markTimeRange"] = [threshold_band]
        data[0]["markPoints"] = mark_points
        data[0]["thresholds"] = threshold_line

        return result


class EventDateHistogramResource(Resource):
    class RequestSerializer(serializers.Serializer):
        alert_id = AlertIDField(required=True, label="告警ID")
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)
        interval = serializers.CharField(label="聚合周期", default="auto")

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["alert_id"]
        alert = AlertDocument.get(alert_id)
        handler = EventQueryHandler(
            dedupe_md5=alert.dedupe_md5,
            start_time=validated_request_data.get("start_time") or alert.begin_time,
            end_time=validated_request_data.get("end_time") or alert.end_time or int(time.time()),
        )
        return handler.date_histogram(interval=validated_request_data["interval"])


class SearchAlertResource(Resource):
    """
    查询告警数据
    """

    class RequestSerializer(AlertSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])
        page = serializers.IntegerField(label="页数", min_value=1, default=1)
        page_size = serializers.IntegerField(label="每页大小", min_value=0, max_value=5000, default=10)
        show_overview = serializers.BooleanField(label="展示总览统计信息", default=True)
        show_aggs = serializers.BooleanField(label="展示聚合统计信息", default=True)
        show_dsl = serializers.BooleanField(label="展示DSL", default=False)
        record_history = serializers.BooleanField(label="是否保存收藏历史", default=False)
        must_exists_fields = serializers.ListField(label="必要字段", child=serializers.CharField(), default=[])
        replace_time_range = serializers.BooleanField(label="是否替换时间范围", default=False)

    def perform_request(self, validated_request_data):
        show_overview = validated_request_data.pop("show_overview")
        show_aggs = validated_request_data.pop("show_aggs")
        show_dsl = validated_request_data.pop("show_dsl")
        record_history = validated_request_data.pop("record_history")
        origin_request_data = copy.deepcopy(validated_request_data)
        # 检测处理记录ID查询并调整时间范围
        has_action_id, detect_result = self.detect_action_id_query(validated_request_data)
        if has_action_id:
            validated_request_data = self.adjust_time_range_for_action_id(validated_request_data, detect_result)

        # 替换时间范围
        if validated_request_data.get("replace_time_range"):
            validated_request_data = self.replace_time_for_alert_id(validated_request_data)

        handler = AlertQueryHandler(**validated_request_data)

        with SearchHistory.record(
            SearchType.ALERT,
            origin_request_data,
            enabled=record_history and origin_request_data.get("query_string"),
        ):
            result = handler.search(show_overview=show_overview, show_aggs=show_aggs, show_dsl=show_dsl)

        return result

    @staticmethod
    def detect_action_id_query(request_data: dict) -> tuple:
        """
        检测查询是否涉及处理记录ID

        Args:
            request_data: 请求数据

        Returns:
            tuple: (是否包含 action_id 查询, 处理记录 ID 列表)
        """
        action_ids_in_query = set()
        action_ids_in_conditions = set()

        has_action_id = False

        # 检查 query_string 中的处理记录ID
        query_string = request_data.get("query_string", "")
        if query_string:
            action_id_matches = re.findall(r"处理记录ID\s*:\s*(\d+)", query_string)
            if action_id_matches:
                action_ids_in_query.update(set(action_id_matches))

        # 检查 conditions 中的 action_id 条件
        conditions = request_data.get("conditions", [])
        for condition in conditions:
            if condition.get("key") == "action_id":
                condition_values = condition.get("value", [])
                if isinstance(condition_values, list):
                    action_ids_in_conditions.update([str(val) for val in condition_values])
                else:
                    action_ids_in_conditions.add(str(condition_values))

        if action_ids_in_query or action_ids_in_conditions:
            has_action_id = True

        result = {
            "action_ids_in_query": list(action_ids_in_query),
            "action_ids_in_conditions": list(action_ids_in_conditions),
        }

        return has_action_id, result

    @staticmethod
    def adjust_time_range_for_action_id(request_data: dict, detect_result: dict) -> dict:
        """
        根据处理记录ID调整查询时间范围并替换查询条件

        该方法不仅调整时间范围，还会将处理记录ID查询转换为直接的告警ID查询，
        避免后续查询中的重复处理，提高查询效率。

        Args:
            request_data: 原始请求数据
            detect_result: 检测结果

        Returns:
            dict: 调整后的请求数据，包含新的时间范围和告警ID查询条件
        """
        from fta_web.alert.handlers.alert import get_alert_ids_by_action_id

        action_ids_in_query = detect_result["action_ids_in_query"]
        action_ids_in_conditions = detect_result["action_ids_in_conditions"]

        alert_ids = set()

        # 通过处理记录ID获取告警ID
        if action_ids_in_query:
            temp_ids_in_query, action_alert_map = get_alert_ids_by_action_id(action_ids_in_query)
            alert_ids.update(temp_ids_in_query)
            # 增加到上下文信息中，便于后续处理query string时，进行精准替换
            request_data["context"] = {"action_alert_map": action_alert_map}

        if action_ids_in_conditions:
            temp_ids_conditions, action_alert_map = get_alert_ids_by_action_id(action_ids_in_conditions)
            alert_ids.update(temp_ids_conditions)
            if temp_ids_conditions:
                # 将对应的action_id条件转换为id条件，值为对应的告警ID
                for condition in request_data.get("conditions", []):
                    if condition["key"] == "action_id":
                        condition["key"] = "id"
                        # 不存在的action_id，告警ID设置为0
                        condition["value"] = chain.from_iterable(
                            [action_alert_map.get(value, ["0"]) for value in condition["value"]]
                        )
                        condition["value"] = list(set(condition["value"]))

        if not alert_ids:
            return request_data

        # 提取告警ID前10位作为时间戳
        timestamps = set()
        for alert_id in alert_ids:
            try:
                timestamp = int(str(alert_id)[:10])
                timestamps.add(timestamp)
            except (ValueError, IndexError):
                logger.warning(f"告警ID {alert_id} 时间戳解析失败")
                continue

        if not timestamps:
            return request_data

        # 计算时间范围（前后扩展1小时）
        one_hour_in_seconds = 3600
        min_timestamp = min(timestamps)
        max_timestamp = max(timestamps)

        # 与原时间范围合并，确保能够覆盖所有情况
        request_data["start_time"] = min(
            min_timestamp - one_hour_in_seconds, request_data.get("start_time", min_timestamp)
        )
        request_data["end_time"] = max(max_timestamp + one_hour_in_seconds, request_data.get("end_time", max_timestamp))

        return request_data

    @staticmethod
    def replace_time_for_alert_id(request_data: dict) -> dict:
        """
        根据查询字符串中的告警ID，动态调整时间范围
        规则：提取所有ID的前10位作为基准时间戳，前后扩展1小时
        """

        one_hour_in_seconds = 3600  # 一小时的秒数
        timestamp_length = 10  # 时间戳位数

        query_string = request_data.get("query_string", "")

        # 匹配所有告警ID/处理记录ID
        id_matches = re.findall(r"告警ID\s*:\s*(\d+)", query_string)
        if not id_matches:
            return request_data

        # 提取出所有的时间戳
        timestamps = [int(match[1][:timestamp_length]) for match in id_matches]

        min_timestamp = min(timestamps)  # 最小时间戳
        max_timestamp = max(timestamps)  # 最大时间戳

        # 计算新的时间范围，确保原本提供的时间范围也被包含，以确保如果存在其他查询条件时，新的范围能够覆盖所有情况
        request_data["start_time"] = min(min_timestamp - one_hour_in_seconds, request_data["start_time"])
        request_data["end_time"] = max(max_timestamp + one_hour_in_seconds, request_data["end_time"])

        return request_data


class ExportAlertResource(Resource):
    """
    导出告警数据
    """

    class RequestSerializer(AlertSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)

    def perform_request(self, validated_request_data):
        handler = AlertQueryHandler(**validated_request_data)
        alert_docs, alerts = handler.export_with_docs()

        related_infos = resource.alert.alert_related_info(alerts=alert_docs)
        id_key = AlertFieldDisplay.ID
        for alert in alerts:
            # 更新关联信息
            alert.update({AlertFieldDisplay.RELATED_INFO: related_infos.get(alert[id_key], {})})

        return resource.export_import.export_package(list_data=alerts, bk_biz_id=validated_request_data["bk_biz_id"])


class SearchEventResource(ApiAuthResource):
    """
    搜索告警关联的事件数据
    """

    class RequestSerializer(EventSearchSerializer):
        page = serializers.IntegerField(label="页数", min_value=1, default=1)
        page_size = serializers.IntegerField(label="每页大小", min_value=0, max_value=1000, default=10)
        show_dsl = serializers.BooleanField(label="展示DSL", default=False)
        record_history = serializers.BooleanField(label="是否保存收藏历史", default=False)
        show_raw = serializers.BooleanField(label="是否展示原始事件", default=False)

    @staticmethod
    def get_dedupe_md5_set(alert: AlertDocument, start_time: int, end_time: int, interval: int):
        dedupe_md5_set = set()
        for query_config in alert.strategy["items"][0]["query_configs"]:
            query_config["agg_dimension"] = ["dedupe_md5"]
            ds_cls = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            ds = ds_cls.init_by_query_config(query_config, bk_biz_id=alert.event.bk_biz_id)
            ds.interval = interval
            records = ds.query_data(start_time=start_time * 1000, end_time=end_time * 1000, limit=10000)
            for record in records:
                dedupe_md5_set.add(record["dedupe_md5"])
        return dedupe_md5_set

    @classmethod
    def search_composite_alerts(cls, alert, validated_request_data, show_dsl=False):
        # 如果是关联告警，需要找出其关联的告警内容，并将其适配为事件
        start_time = alert.begin_time
        end_time = alert.end_time if alert.end_time else int(time.time())
        interval = AlertQueryHandler.calculate_agg_interval(start_time, end_time)
        dedupe_md5_set = cls.get_dedupe_md5_set(alert, start_time, end_time, interval)
        conditions = [
            {
                "key": dim["key"],
                "value": [dim["value"]],
                "method": "eq",
                "condition": "and",
            }
            for dim in alert.dimensions or []
        ]

        handler = AlertQueryHandler(
            start_time=start_time,
            end_time=end_time,
            conditions=[
                {
                    "key": "dedupe_md5",
                    "value": list(dedupe_md5_set),
                    "method": "eq",
                }
            ]
            + conditions,
            **validated_request_data,
        )
        alert_result, _ = handler.search_raw()

        result = {
            "total": min(alert_result.hits.total.value, 10000),
            "events": EventQueryHandler.handle_hit_list(
                [AlertQueryHandler.adapt_to_event(alert.to_dict()) for alert in alert_result]
            ),
        }

        return result

    @classmethod
    def search_fta_alerts(cls, alert, validated_request_data, show_dsl=False):
        # todo 如果是关联告警，需要找出其关联的告警内容，并将其适配为事件
        start_time = alert.begin_time
        end_time = alert.end_time if alert.end_time else int(time.time())
        interval = EventQueryHandler.calculate_agg_interval(start_time, end_time)
        dedupe_md5_set = cls.get_dedupe_md5_set(alert, start_time, end_time, interval)
        conditions = [
            {
                "key": dim["key"],
                "value": [dim["value"]],
                "method": "eq",
                "condition": "and",
            }
            for dim in alert.dimensions or []
        ]

        handler = EventQueryHandler(
            start_time=start_time,
            end_time=end_time,
            conditions=[
                {
                    "key": "dedupe_md5",
                    "value": list(dedupe_md5_set),
                    "method": "eq",
                }
            ]
            + conditions,
            **validated_request_data,
        )
        result = handler.search(show_dsl=show_dsl)
        return result

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["alert_id"]
        record_history = validated_request_data.pop("record_history")
        show_dsl = validated_request_data.pop("show_dsl")

        alert = AlertDocument.get(alert_id)

        with SearchHistory.record(
            SearchType.EVENT,
            validated_request_data,
            enabled=record_history and validated_request_data.get("query_string"),
        ):
            if alert.is_composite_strategy and not validated_request_data["show_raw"]:
                result = self.search_composite_alerts(alert, validated_request_data, show_dsl)
            elif alert.is_fta_event_strategy and not validated_request_data["show_raw"]:
                result = self.search_fta_alerts(alert, validated_request_data, show_dsl)
            else:
                handler = EventQueryHandler(
                    dedupe_md5=alert.dedupe_md5,
                    start_time=alert.begin_time,
                    end_time=alert.latest_time or int(time.time()),
                    **validated_request_data,
                )
                result = handler.search(show_dsl=show_dsl)

        return result


class SearchActionResource(ApiAuthResource):
    """
    查询处理记录数据
    """

    class RequestSerializer(ActionSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])
        page = serializers.IntegerField(label="页数", min_value=1, default=1)
        page_size = serializers.IntegerField(label="每页大小", min_value=0, max_value=1000, default=10)

        show_overview = serializers.BooleanField(label="展示总览统计信息", default=True)
        show_aggs = serializers.BooleanField(label="展示聚合统计信息", default=True)
        show_dsl = serializers.BooleanField(label="展示DSL", default=False)
        record_history = serializers.BooleanField(label="是否保存收藏历史", default=False)

    def perform_request(self, validated_request_data):
        show_overview = validated_request_data.pop("show_overview")
        show_aggs = validated_request_data.pop("show_aggs")
        show_dsl = validated_request_data.pop("show_dsl")
        record_history = validated_request_data.pop("record_history")
        if validated_request_data["bk_biz_ids"] is not None:
            authorized_bizs, unauthorized_bizs = AlertQueryHandler.parse_biz_item(validated_request_data["bk_biz_ids"])
            validated_request_data["authorized_bizs"] = authorized_bizs
            validated_request_data["unauthorized_bizs"] = unauthorized_bizs

        handler = ActionQueryHandler(**validated_request_data)

        with SearchHistory.record(
            SearchType.ACTION,
            validated_request_data,
            enabled=record_history and validated_request_data.get("query_string"),
        ):
            result = handler.search(show_overview=show_overview, show_aggs=show_aggs, show_dsl=show_dsl)

        return result


class SubActionDetailResource(ApiAuthResource):
    """
    查询子任务执行详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        parent_action_id = serializers.CharField(label="父任务ID", required=True)

    def perform_request(self, validated_request_data):
        validated_request_data["page_size"] = 500
        handler = ActionQueryHandler(**validated_request_data)
        resp_data = {}
        if handler.raw_id is None and handler.search_parent_action_id is None:
            # 如果当前告警处理ID记录不存在并且没有主任务直接返回空
            return resp_data
        actions = handler.search()["actions"]
        sub_actions = []
        action_relation = {}
        for action in actions:
            if action["signal"] != ActionSignal.COLLECT or action["id"] == validated_request_data["parent_action_id"]:
                sub_actions.append(action)
                continue
            for action_id in action["outputs"].get("related_actions", []):
                notice_way, notice_receiver = self.get_action_notice_info(action)
                action_relation[f"{str(action_id)}_{notice_way}_{notice_receiver}"] = action

        for action in sub_actions:
            notice_way, notice_receiver = self.get_action_notice_info(action)
            if not (notice_way and notice_receiver):
                continue

            real_action = (
                action_relation.get("{}_{}_{}".format(str(str(action["raw_id"])), notice_way, notice_receiver))
                or action
            )
            action_status = real_action["status"]
            status_display = ACTION_DISPLAY_STATUS_DICT.get(action_status, "--")
            try:
                # 解析notice_way, 保持前端只有一个notice_way的呈现，比如蓝鲸信息流，统一显示为蓝鲸信息流
                notice_way_display, _ = notice_way.split("|")
            except ValueError:
                # 如果解析不出来，表示是内置的通知方式
                notice_way_display = notice_way
            notice_result = {
                notice_way_display: {
                    "status": action_status,
                    "action_id": action["id"],
                    "status_display": status_display,
                    "status_tips": real_action["status_tips"] or status_display,
                }
            }
            if notice_receiver in resp_data:
                resp_data[notice_receiver].update(notice_result)
                continue
            resp_data[notice_receiver] = notice_result
        return resp_data

    @staticmethod
    def get_action_notice_info(action):
        """
        获取通知方式和通知人员
        """
        notice_way = action["inputs"].get("notice_way")
        notice_receiver = action["inputs"].get("notice_receiver")
        notice_way = notice_way[0] if isinstance(notice_way, list) else notice_way
        notice_receiver = ",".join(notice_receiver) if isinstance(notice_receiver, list) else notice_receiver
        return notice_way, notice_receiver


class ExportActionResource(Resource):
    """
    导出处理记录数据
    """

    class RequestSerializer(ActionSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])

    def perform_request(self, validated_request_data):
        handler = ActionQueryHandler(**validated_request_data)
        return resource.export_import.export_package(list_data=handler.export())


class AlertExtendFields(Resource):
    """
    获取告警列表所有的扩展字段
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(label="告警ID", child=AlertIDField())

    def perform_request(self, validated_request_data):
        extend_info = resource.alert.alert_related_info(validated_request_data)
        event_count = resource.alert.alert_event_count(validated_request_data)

        result = defaultdict(lambda: {"extend_info": {}, "event_count": 0})

        for alert_id, item in extend_info.items():
            result[alert_id]["extend_info"] = item

        for alert_id, item in event_count.items():
            result[alert_id]["event_count"] = item

        return result


class ActionDetailResource(Resource):
    """
    根据ID获取处理记录详情
    """

    class RequestSerializer(serializers.Serializer):
        id = ActionIDField(required=True, label="处理记录ID")

    def perform_request(self, validated_request_data):
        action_id = validated_request_data["id"]
        action = ActionInstanceDocument.get(action_id)
        result = ActionQueryHandler.handle_hit_list([action])[0]
        return result


class ActionDateHistogramResource(Resource):
    """
    查询告警分布直方图
    """

    class RequestSerializer(ActionSearchSerializer):
        interval = serializers.CharField(label="聚合周期", default="auto")

    def perform_request(self, validated_request_data):
        interval = validated_request_data.pop("interval")
        handler = ActionQueryHandler(**validated_request_data)
        return handler.date_histogram(interval=interval)


class ListAlertLogResource(ApiAuthResource):
    """
    获取告警流水记录
    """

    class RequestSerializer(serializers.Serializer):
        id = AlertIDField(required=True, label="告警ID")
        offset = serializers.IntegerField(required=False, label="偏移")
        limit = serializers.IntegerField(default=10, label="获取的条数")
        operate = serializers.ListField(default=[], label="记录类型")

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["id"]
        operate_list = validated_request_data["operate"]
        offset = validated_request_data.get("offset")
        limit = validated_request_data["limit"]

        handler = AlertLogHandler(alert_id)
        result_data = handler.search(operate_list=operate_list, offset=offset, limit=limit)
        return result_data


class ValidateQueryString(Resource):
    """
    校验 query_string 是否合法
    """

    class RequestSerializer(serializers.Serializer):
        search_type = serializers.ChoiceField(label="检索类型", choices=SEARCH_TYPE_CHOICES, default=SearchType.ALERT)
        query_string = serializers.CharField(label="查询字符串", allow_blank=True)

    def perform_request(self, validated_request_data):
        if not validated_request_data["query_string"]:
            return ""
        transformer_cls = {
            SearchType.ALERT: AlertQueryHandler.query_transformer,
            SearchType.ACTION: ActionQueryHandler.query_transformer,
            SearchType.EVENT: EventQueryHandler.query_transformer,
        }
        search_type = validated_request_data["search_type"]
        ret = transformer_cls[search_type].transform_query_string(query_string=validated_request_data["query_string"])
        return ret


class BaseTopNResource(Resource):
    """
    统计告警TOP N
    """

    handler_cls = None

    class RequestSerializer(serializers.Serializer):
        fields = serializers.ListField(label="查询字段列表", child=serializers.CharField(), default=[])
        size = serializers.IntegerField(label="获取的桶数量", default=10)

    def perform_request(self, validated_request_data):
        handler = self.handler_cls(**validated_request_data)
        return handler.top_n(fields=validated_request_data["fields"], size=validated_request_data["size"])


class AlertTopNResultResource(BaseTopNResource):
    handler_cls = AlertQueryHandler

    class RequestSerializer(AlertSearchSerializer, BaseTopNResource.RequestSerializer):
        is_time_partitioned = serializers.BooleanField(required=False, default=False, label="是否按时间分片")
        is_finaly_partition = serializers.BooleanField(required=False, default=False, label="是否是最后一个分片")
        authorized_bizs = serializers.ListField(child=serializers.IntegerField(), default=None)
        unauthorized_bizs = serializers.ListField(child=serializers.IntegerField(), default=None)
        need_bucket_count = serializers.BooleanField(required=False, default=True, label="是否需要进行基数聚合")


class AlertTopNResource(Resource):
    handler_cls = AlertQueryHandler

    class RequestSerializer(AlertSearchSerializer, BaseTopNResource.RequestSerializer):
        need_time_partition = serializers.BooleanField(required=False, default=True, label="是否需要按时间分片")

    def perform_request(self, validated_request_data):
        if validated_request_data["bk_biz_ids"] is not None:
            authorized_bizs, unauthorized_bizs = self.handler_cls.parse_biz_item(validated_request_data["bk_biz_ids"])
            validated_request_data["authorized_bizs"] = authorized_bizs
            validated_request_data["unauthorized_bizs"] = unauthorized_bizs

        need_time_partition = validated_request_data.pop("need_time_partition")

        if not need_time_partition:
            return resource.alert.alert_top_n_result(**validated_request_data)

        executor = ThreadPool(processes=1)
        future = executor.apply_async(self.get_bucket_count, [validated_request_data])

        start_time = validated_request_data.pop("start_time")
        end_time = validated_request_data.pop("end_time")
        slice_times = slice_time_interval(start_time, end_time)
        size = validated_request_data.get("size", 10)

        results = resource.alert.alert_top_n_result.bulk_request(
            [
                {
                    "start_time": sliced_start_time,
                    "end_time": sliced_end_time,
                    "is_finaly_partition": True if index == len(slice_times) - 1 else False,
                    "is_time_partitioned": True,
                    "need_bucket_count": False,  # 不在分片查询中进行基数聚合
                    **validated_request_data,
                }
                for index, (sliced_start_time, sliced_end_time) in enumerate(slice_times)
            ]
        )

        result = {
            "doc_count": 0,
            "fields": [],
        }
        field_buckets_map = {}

        for sliced_result in results:
            result["doc_count"] += sliced_result["doc_count"]

            for field_info in sliced_result["fields"]:
                field = field_info["field"]
                if field not in field_buckets_map:
                    field_buckets_map[field] = {
                        "id_buckets_map": {},
                        "field": field,
                        "is_char": field_info["is_char"],
                    }

                id_buckets_map = field_buckets_map[field]["id_buckets_map"]

                for bucket in field_info["buckets"]:
                    _id = bucket["id"]
                    name = bucket["name"]
                    if (_id, name) not in id_buckets_map:
                        id_buckets_map[(_id, name)] = {
                            "id": _id,
                            "name": name,
                            "count": bucket["count"],
                        }
                    else:
                        id_buckets_map[(_id, name)]["count"] += bucket["count"]

        for filed_info in field_buckets_map.values():
            field = {
                "field": filed_info["field"],
                "is_char": filed_info["is_char"],
                "bucket_count": 0,
                "buckets": list(filed_info["id_buckets_map"].values()),
            }
            result["fields"].append(field)

        # 补充bucket_count值，以及限制buckets长度与size一致
        field_bucket_count_map = future.get()
        executor.close()
        # 对每个字段的桶按count降序排序，并截取前size个
        for field_data in result["fields"]:
            field = field_data["field"]
            if field == "bk_biz_id":
                exist_bizs = {int(bucket["id"]) for bucket in field_data["buckets"]}
                authorized_bizs = field_bucket_count_map[field]["authorized_bizs"]
                bucket_count = field_bucket_count_map[field]["bucket_count"]
                for biz in authorized_bizs:
                    if len(exist_bizs) > size:
                        break
                    if int(biz) not in exist_bizs:
                        field_data["buckets"].append({"id": biz, "name": biz, "count": 0})
                        bucket_count += 1
                field_bucket_count_map[field] = bucket_count
            bucket_length = len(field_data["buckets"])
            field_data["buckets"].sort(key=lambda x: x["count"], reverse=True)
            field_data["buckets"] = field_data["buckets"][:size]

            field_data["bucket_count"] = field_bucket_count_map.get(field, 0)
            if field_data["bucket_count"] <= size:
                field_data["bucket_count"] = bucket_length

        return result

    def get_bucket_count(self, validated_request_data):
        fields = validated_request_data.get("fields", [])
        handler = self.handler_cls(**validated_request_data)
        search_object = handler.get_search_object()
        search_object = handler.add_conditions(search_object)
        search_object = handler.add_query_string(search_object)
        search_object = search_object.params(track_total_hits=True).extra(size=0)

        bucket_count_suffix = handler.bucket_count_suffix

        for filed in fields:
            handler.add_cardinality_bucket(search_object.aggs, filed, bucket_count_suffix)

        search_result = search_object.execute()

        result = {}

        # 返回结果的数据处理
        for field in fields:
            if not search_result.aggs:
                continue
            actual_field = field.lstrip("-+")
            if actual_field.startswith("tags."):
                bucket_count = getattr(search_result.aggs, f"{field}{bucket_count_suffix}").key.value.value

            elif actual_field == "duration":
                bucket_count = len(handler.DurationOption.AGG)
            elif actual_field == "bk_biz_id" and hasattr(handler, "authorized_bizs"):
                authorized_bizs = set(handler.authorized_bizs)
                bucket_count = {"bucket_count": len(authorized_bizs), "authorized_bizs": authorized_bizs}
            else:
                bucket_count = getattr(search_result.aggs, f"{field}{bucket_count_suffix}").value

            result[actual_field] = bucket_count
        return result


class ActionTopNResource(BaseTopNResource):
    handler_cls = ActionQueryHandler

    class RequestSerializer(ActionSearchSerializer, BaseTopNResource.RequestSerializer):
        pass


class EventTopNResource(BaseTopNResource, ApiAuthResource):
    handler_cls = EventQueryHandler

    class RequestSerializer(EventSearchSerializer, BaseTopNResource.RequestSerializer):
        pass

    def perform_request(self, validated_request_data):
        alert = AlertDocument.get(validated_request_data["alert_id"])

        handler = EventQueryHandler(
            dedupe_md5=alert.dedupe_md5,
            start_time=alert.begin_time,
            end_time=alert.latest_time or int(time.time()),
            **validated_request_data,
        )
        return handler.top_n(fields=validated_request_data["fields"], size=validated_request_data["size"])


class ListAlertTagsResultResource(Resource):
    """
    获取告警标签
    """

    class RequestSerializer(AlertSearchSerializer):
        is_time_partitioned = serializers.BooleanField(required=False, default=False, label="是否按时间分片")
        is_finaly_partition = serializers.BooleanField(required=False, default=False, label="是否是最后一个分片")
        authorized_bizs = serializers.ListField(child=serializers.IntegerField(), default=None)
        unauthorized_bizs = serializers.ListField(child=serializers.IntegerField(), default=None)

    def perform_request(self, validated_request_data):
        handler = AlertQueryHandler(**validated_request_data)
        return handler.list_tags()


class ListAlertTagsResource(Resource):
    """
    获取告警标签
    """

    class RequestSerializer(AlertSearchSerializer):
        pass

    def perform_request(self, validated_request_data):
        start_time = validated_request_data.pop("start_time")
        end_time = validated_request_data.pop("end_time")
        slice_times = slice_time_interval(start_time, end_time)
        if validated_request_data["bk_biz_ids"] is not None:
            authorized_bizs, unauthorized_bizs = AlertQueryHandler.parse_biz_item(validated_request_data["bk_biz_ids"])
            validated_request_data["authorized_bizs"] = authorized_bizs
            validated_request_data["unauthorized_bizs"] = unauthorized_bizs

        results = resource.alert.list_alert_tags_result.bulk_request(
            [
                {
                    "start_time": sliced_start_time,
                    "end_time": sliced_end_time,
                    "is_finaly_partition": True if index == len(slice_times) - 1 else False,
                    "is_time_partitioned": True,
                    **validated_request_data,
                }
                for index, (sliced_start_time, sliced_end_time) in enumerate(slice_times)
            ]
        )

        result = []
        id_map = {}
        for sliced_result in results:
            for tag in sliced_result:
                if tag["id"] not in id_map:
                    result.append(copy.deepcopy(tag))
                    id_map[tag["id"]] = len(result) - 1
                else:
                    index = id_map[tag["id"]]
                    result[index]["count"] += tag["count"]
        return result


class StrategySnapshotResource(Resource):
    """
    获取策略快照
    """

    class ConfigChangedStatus:
        """
        策略配置变更状态
        """

        UNCHANGED = "UNCHANGED"
        UPDATED = "UPDATED"
        DELETED = "DELETED"

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="事件ID")

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["id"]
        is_enabled = False
        alert = AlertDocument.get(alert_id)
        strategy_config = alert.strategy
        if not strategy_config:
            return None

        # 策略更新状态
        changed_status = self.ConfigChangedStatus.UNCHANGED
        current_strategy = None
        try:
            strategy = StrategyModel.objects.get(id=strategy_config["id"])
            is_enabled = strategy.is_enabled
            current_strategy = Strategy.from_models([strategy])[0]
        except StrategyModel.DoesNotExist:
            changed_status = self.ConfigChangedStatus.DELETED
        else:
            if int(strategy.update_time.timestamp()) != strategy_config["update_time"]:
                changed_status = self.ConfigChangedStatus.UPDATED

        if current_strategy and "intelligent_detect" in strategy_config["items"][0]["query_configs"][0]:
            if not strategy_config["items"][0]["query_configs"][0]["intelligent_detect"].get("use_sdk", False):
                # AIOPS算法在告警检测时会对query_config本身进行修改导致查询配置无法还原，此时直接使用最新的query_config
                strategy_config["items"][0]["query_configs"][0] = current_strategy.items[0].query_configs[0].to_dict()

        strategy_config.update(strategy_status=changed_status)
        strategy_config["create_time"] = utc2datetime(strategy_config["create_time"])
        strategy_config["update_time"] = utc2datetime(strategy_config["update_time"])
        strategy_config["is_enabled"] = is_enabled
        Strategy.fill_user_groups([strategy_config])
        return strategy_config


class SearchAlertByEventResource(Resource):
    """
    TODO: 搜索告警关联的事件数据
    """

    class RequestSerializer(serializers.Serializer):
        """
        请求参数
        """

        event_id = serializers.CharField(label="事件ID", required=True)

    def perform_request(self, validated_request_data):
        # 对应的事件ID
        event_id = validated_request_data.get("event_id")

        # 根据event_id获取对应的event
        event = EventDocument.get_by_event_id(event_id)

        # 根据event 的去重md5获取到对应的告警
        try:
            alert = AlertDocument.get_by_dedupe_md5(event.dedupe_md5, event.time)
        except AlertNotFoundError:
            return {}
        if alert.strategy_id is None:
            # 如果策略ID不存在，通过target， create_time, 告警名称事件查询
            # 告警ID不存在的，都是通过fta接入
            metric_id = [f"bk_fta.event.{alert.alert_name}", f"bk_fta.alert.{alert.alert_name}"]
            new_event = None
            try:
                new_event = EventDocument.get_by_metric_id_and_target(metric_id, event.target, event.time)
            except BaseException as error:  # NOCC:broad-except(设计如此:)
                logger.info("get event failed %s, alert(%s)", str(error), alert.id)
            if new_event:
                try:
                    alert = AlertDocument.get_by_dedupe_md5(new_event.dedupe_md5, new_event.time)
                except AlertNotFoundError:
                    logger.info(f"no handle alert for event({event.event_id})")

        all_actions = ActionInstanceDocument.mget_by_alert(alert_ids=[alert.id])

        # 根据告警ID获取对应的处理信息
        handle_actions = [
            {
                "status": action.status,
                "action_plugin_type": action.action_plugin_type,
            }
            for action in all_actions
            if action.action_plugin_type != ActionPluginType.NOTICE
        ]
        notice_display_mapping = {msg["type"]: msg["label"] for msg in api.cmsi.get_msg_type()}
        voice_target_string = notice_display_mapping.get(NoticeWay.VOICE)

        voice_notice_actions = [
            {"status": action.status, "failure_type": action.failure_type}
            for action in all_actions
            if action.operate_target_string == voice_target_string
            and action.action_plugin_type == ActionPluginType.NOTICE
        ]

        event_info = {
            "id": event.id,
            "event_id": event.event_id,
            "create_time": utc2localtime(event.create_time),
            "ip": getattr(event, "ip", ""),
            "bk_biz_id": event.bk_biz_id,
            "bk_cloud_id": getattr(event, "bk_cloud_id", ""),
            "target_type": event.target_type,
            "target": event.target,
        }

        is_builtin_assign = AlertAssignGroup.objects.filter(
            id=alert.assign_group.get("group_id"), is_builtin=True
        ).exists()
        result = {
            "id": alert.id,
            "create_time": utc2localtime(alert.create_time),
            "begin_time": utc2localtime(alert.begin_time),
            "end_time": utc2localtime(alert.end_time) if alert.end_time else None,
            "bk_biz_id": event.bk_biz_id,
            "strategy_id": alert.strategy_id,
            "level": alert.severity,
            "status": alert.status,
            "plugin_id": getattr(alert.event, "plugin_id", None),
            "is_builtin_assign": is_builtin_assign,
            "target_key": f"{event.target_type.lower()}|{event.target}",
            "assignee": [assignee for assignee in alert.assignee],
            "event": event_info,
            "is_shielded": alert.is_shielded is True,
            "is_handled": alert.is_handled is True,
            "is_ack": alert.is_ack is True,
            "handle_actions": handle_actions,
            "voice_notice_actions": voice_notice_actions,
        }
        return result


class ListIndexByHost(Resource):
    class RequestSerializer(serializers.Serializer):
        ip = serializers.CharField(required=True, label="主机IP")
        bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID", default=0, allow_null=True)
        bk_biz_id = serializers.IntegerField(required=True, help_text="业务ID")

    def perform_request(self, validated_request_data):
        params = {}
        params.update(validated_request_data)
        params["bk_host_innerip"] = params.pop("ip")
        try:
            result = api.log_search.list_collectors_by_host(params)
        except Exception:
            result = []
        return result


class FeedbackAlertResource(Resource):
    """
    告警反馈
    """

    class RequestSerializer(serializers.Serializer):
        alert_id = AlertIDField(required=True, label="告警ID")
        is_anomaly = serializers.BooleanField(label="是否为异常")
        description = serializers.CharField(label="反馈说明", allow_blank=True, default="")

    def feedback_to_bkdata(self, alert: AlertDocument, is_anomaly: bool, description: str):
        if not settings.IS_ACCESS_BK_DATA:
            # 没接入计算平台的，忽略
            return

        if not alert.strategy:
            # 没有策略的，忽略
            return

        query_config = None
        for item in alert.strategy["items"]:
            for qc in item["query_configs"]:
                if qc.get("intelligent_detect", {}).get("result_table_id"):
                    query_config = qc

        if not query_config:
            # 没有智能异常检测的，忽略
            return

        origin_data = alert.origin_alarm.get("data") if alert.origin_alarm else None
        if not origin_data:
            # 拿不到异常数据，忽略
            return

        dimensions = {
            key: value
            for key, value in origin_data["dimensions"].items()
            if key in query_config.get("agg_dimension", [])
        }

        feedback_data = {
            "dtEventTimeStamp": origin_data["time"] * 1000,
            "is_anomaly": origin_data["values"].get("is_anomaly"),
            "label": 1 if is_anomaly else 0,
            "label_description": description,
            "value": origin_data["value"],
            "extra_info": origin_data["values"].get("extra_info"),
        }

        feedback_data.update(dimensions)

        api.bkdata.sample_set_feedback(
            rt_id=query_config["intelligent_detect"]["result_table_id"],
            feedback_data=[feedback_data],
        )

    def perform_request(self, params):
        alert = AlertDocument.get(params["alert_id"])
        AlertFeedback.objects.create(
            alert_id=params["alert_id"],
            is_anomaly=params["is_anomaly"],
            description=params["description"],
        )

        self.feedback_to_bkdata(alert=alert, is_anomaly=params["is_anomaly"], description=params["description"])


class ListAlertFeedbackResource(ApiAuthResource):
    """
    获取告警反馈
    """

    class RequestSerializer(serializers.Serializer):
        alert_id = AlertIDField(required=True, label="告警ID")

    def perform_request(self, validated_request_data):
        feedback = AlertFeedback.objects.filter(alert_id=validated_request_data["alert_id"])
        return AlertFeedbackSerializer(feedback, many=True).data


class AIOpsBaseResource(Resource, metaclass=ABCMeta):
    """
    AIOps基础资源配置
    """

    CACHE_SCOPE = None

    class RequestSerializer(serializers.Serializer):
        alert_id = AlertIDField(required=True, label="告警ID")

    def get_cache_results(self, alert_id: str) -> dict:
        """获取缓存的AIOps类数据的缓存.

        :param alert_id: 告警ID
        """
        cache_key = f"{alert_id}_{self.CACHE_SCOPE}_cache"
        return cache.get(cache_key)

    def set_cache_results(self, alert_id: str, cache_result: dict, timeout: int = 86400) -> dict:
        """把AIOps类数据缓存到cache中.

        :param alert_id: 告警ID
        """
        cache_key = f"{alert_id}_{self.CACHE_SCOPE}_cache"
        return cache.set(cache_key, cache_result, timeout=timeout)

    def cache_valid(self, alert: AlertDocument, cache_result: dict) -> bool:
        """判断当前cache是否还在有效期内.

        :param alert: 告警详情
        :param cache_result: 缓存的内容
        """
        return True

    def perform_request(self, validated_request_data):
        alert = AlertDocument.get(validated_request_data["alert_id"])
        cache_result = self.get_cache_results(alert.id)

        if not cache_result or not self.cache_valid(alert, cache_result):
            request_result = self.fetch_aiops_result(alert)
            self.set_cache_results(alert.id, request_result)
            cache_result = request_result

        return cache_result

    def fetch_aiops_result(self, alert):
        """各种场景下获取AIOps算法结果.

        :param alert: 告警详情
        """
        pass


class DimensionDrillDownResource(AIOpsBaseResource):
    """
    维度下钻详情
    """

    CACHE_SCOPE = "drill_down"

    def cache_valid(self, alert: AlertDocument, cache_result: dict) -> bool:
        """判断当前cache是否还在有效期内.

        :param cache_result: 缓存的内容
        """
        return cache_result["alert_latest_time"] == alert.latest_time

    def fetch_aiops_result(self, alert):
        return DimensionDrillManager(alert).fetch_aiops_result()


class MetricRecommendationResource(AIOpsBaseResource):
    """
    指标推荐详情
    """

    CACHE_SCOPE = "metric_recommend"

    def fetch_aiops_result(self, alert: AlertDocument) -> dict:
        return RecommendMetricManager(alert).fetch_aiops_result()

    def perform_request(self, validated_request_data):
        result = super().perform_request(validated_request_data)

        # 参数列表,每个列表同位置的元素一一对应，共同组成一对查询参数
        alert_metric_ids = []
        rec_metric_hashs = []
        bk_biz_ids = []
        usernames = []

        username = get_request_username()

        # 收集需要查询的参数
        query_params = {}
        for label_info in result.get("recommended_metrics", []):
            for metric_info in label_info["metrics"]:
                for recommend_panel in metric_info["panels"]:
                    recommend_info = recommend_panel["recommend_info"]
                    alert_metric_id = recommend_info["src_metric_id"]
                    recommendation_metric = recommend_panel["id"]
                    bk_biz_id = recommend_panel["bk_biz_id"]

                    # 将参数放入列表
                    alert_metric_ids.append(alert_metric_id)
                    rec_metric_hashs.append(
                        MetricRecommendationFeedback.generate_recommendation_metric_hash(recommendation_metric)
                    )
                    bk_biz_ids.append(bk_biz_id)
                    usernames.append(username)

                    # 收集查询参数,并保留对应的recommend_panel
                    query_params[(alert_metric_id, recommendation_metric, bk_biz_id, username)] = recommend_panel

        # 批量查询反馈信息
        feedback_results = MetricRecommendationFeedbackResource.get_feedback_batch(
            alert_metric_ids, rec_metric_hashs, bk_biz_ids, usernames
        )

        for (alert_metric_id, recommendation_metric, bk_biz_id, username), recommend_panel in query_params.items():
            try:
                recommend_panel["feedback"] = feedback_results[
                    (alert_metric_id, recommendation_metric, bk_biz_id, username)
                ]
            except KeyError:
                recommend_panel["feedback"] = {
                    "good": 0,
                    "bad": 0,
                    "self": None,
                }

        return result


class MetricRecommendationFeedbackResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        alert_metric_id = serializers.CharField(required=True, label="告警指标ID")
        recommendation_metric_id = serializers.CharField(required=True, label="推荐指标")
        recommendation_metric_class = serializers.CharField(required=True, label="指标分类标签")
        feedback = serializers.ChoiceField(required=True, label="指标推荐反馈", choices=["good", "bad"])

    @staticmethod
    def get_feedback_count(alert_metric_id, recommendation_metric, bk_biz_id):
        """获取业务下，告警指标,被推荐指标关系下的点赞和点踩数

        :param alert_metric_id: 告警指标名
        :param recommendation_metric: 被推荐指标
        :param bk_biz_id: 业务id
        :return: (点赞数,点踩数)
        """
        feedback_annotate = (
            MetricRecommendationFeedback.objects.filter(
                alert_metric_id=alert_metric_id,
                recommendation_metric_hash=MetricRecommendationFeedback.generate_recommendation_metric_hash(
                    recommendation_metric
                ),
                bk_biz_id=bk_biz_id,
            )
            .values("feedback")
            .annotate(Count("feedback"))
        )

        good_count = 0
        bad_count = 0
        for feedback_annotate_item in feedback_annotate:
            if feedback_annotate_item["feedback"] == MetricRecommendationFeedback.FeedBackChoices.GOOD:
                good_count = feedback_annotate_item["feedback__count"]
            elif feedback_annotate_item["feedback"] == MetricRecommendationFeedback.FeedBackChoices.BAD:
                bad_count = feedback_annotate_item["feedback__count"]
        return good_count, bad_count

    @staticmethod
    def get_feedback_count_batch(alert_metric_ids: list, rec_metric_hashs: list, bk_biz_ids: list) -> dict:
        """批量获取业务下，告警指标,被推荐指标关系下的点赞和点踩数
        每个参数列表同位置的元素一一对应，共同组成一对查询参数。
        非批量查询时，model.objects.filter(alert_metric_id=alert_metric_ids[0],
        recommendation_metric_hash=rec_metric_hashs[0], bk_biz_id=bk_biz_ids[0])

        :param alert_metric_ids: 告警指标名列表
        :param rec_metric_hashs: 被推荐指标的hash列表
        :param bk_biz_ids: 业务id列表
        :return: {(alert_metric_id, recommendation_metric, bk_biz_id): (点赞数,点踩数), ...}
        """
        # 提取所有的参数组合
        params = list(zip(alert_metric_ids, rec_metric_hashs, bk_biz_ids))

        # 用于存储最终结果
        result = {}
        # 存储每个组合的具体点赞和点踩数
        feedback_count = defaultdict(lambda: {"good_count": 0, "bad_count": 0})

        # 一次性获取所有需要的数据
        feedback_data = MetricRecommendationFeedback.objects.filter(
            DQ(alert_metric_id__in=alert_metric_ids)
            & DQ(bk_biz_id__in=bk_biz_ids)
            & DQ(recommendation_metric_hash__in=rec_metric_hashs)
        ).values_list("alert_metric_id", "recommendation_metric_hash", "bk_biz_id", "feedback")

        # 统计每个组合的点赞和点踩数
        for alert_id, rec_metric_hash, bk_biz_id, feedback in feedback_data:
            feedback_count[(alert_id, rec_metric_hash, bk_biz_id)][feedback + "_count"] += 1

        # 将最终统计结果存入result
        for alert_id, rec_metric_hash, bk_biz_id in params:
            result[(alert_id, rec_metric_hash, bk_biz_id)] = list(
                feedback_count[(alert_id, rec_metric_hash, bk_biz_id)].values()
            )

        return result

    @classmethod
    def get_feedback(cls, alert_metric_id, recommendation_metric, bk_biz_id, username):
        """获取用户的反馈

        :param alert_metric_id: 告警指标名
        :param recommendation_metric: 被推荐指标
        :param bk_biz_id: 业务id
        :param username: 用户名
        :return: 业务下对应告警指标和被推荐指标的点赞数和点踩数，以及用户的反馈
        """
        good_count, bad_count = cls.get_feedback_count(alert_metric_id, recommendation_metric, bk_biz_id)

        username_feedback = MetricRecommendationFeedback.objects.filter(
            alert_metric_id=alert_metric_id,
            recommendation_metric_hash=MetricRecommendationFeedback.generate_recommendation_metric_hash(
                recommendation_metric
            ),
            bk_biz_id=bk_biz_id,
            create_user=username,
        ).first()

        return {
            "good": good_count,
            "bad": bad_count,
            "self": username_feedback.feedback if username_feedback else None,
        }

    @classmethod
    def get_feedback_batch(
        cls, alert_metric_ids: list, rec_metric_hashs: list, bk_biz_ids: list, usernames: list
    ) -> dict:
        """批量获取用户的反馈
        每个参数列表同位置的元素一一对应，共同组成一对查询参数。
        非批量查询时，model.objects.filter(alert_metric_id=alert_metric_ids[0],
        recommendation_metric_hash=rec_metric_hashs[0], bk_biz_id=bk_biz_ids[0], create_user=usernames[0])

        :param alert_metric_ids: 告警指标名列表
        :param rec_metric_hashs: 被推荐指标的hash列表
        :param bk_biz_ids: 业务id列表
        :param usernames: 用户名列表

        :return: result: {(alert_metric_id, recommendation_metric, bk_biz_id, username): (点赞数,点踩数,用户反馈), ...}
        """

        # 批量查询点赞数和点踩数
        feedback_counts = cls.get_feedback_count_batch(alert_metric_ids, rec_metric_hashs, bk_biz_ids)

        # 批量查询用户反馈
        feedback_objects = MetricRecommendationFeedback.objects.filter(
            DQ(alert_metric_id__in=alert_metric_ids)
            & DQ(recommendation_metric_hash__in=rec_metric_hashs)
            & DQ(bk_biz_id__in=bk_biz_ids)
            & DQ(create_user__in=usernames)
        ).values("alert_metric_id", "recommendation_metric_hash", "bk_biz_id", "create_user", "feedback")

        # 构建字典，用于快速查找反馈对象
        feedback_dict = {
            (fo["alert_metric_id"], fo["recommendation_metric_hash"], fo["bk_biz_id"], fo["create_user"]): fo[
                "feedback"
            ]
            for fo in feedback_objects
        }

        result = {}
        params_list = list(zip(alert_metric_ids, rec_metric_hashs, bk_biz_ids, usernames))
        for alert_metric_id, rec_metric_hash, bk_biz_id, username in params_list:
            # 从之前获取的点赞数和点踩数字典中获取当前组合的点赞数和点踩数
            good_count, bad_count = feedback_counts[(alert_metric_id, rec_metric_hash, bk_biz_id)]
            # 从反馈字典中获取当前用户的反馈信息
            feedback = feedback_dict.get((alert_metric_id, rec_metric_hash, bk_biz_id, username))

            # 将获取到的点赞数、点踩数和用户反馈信息组合成一个新的字典项，并添加到结果字典中
            result[(alert_metric_id, rec_metric_hash, bk_biz_id, username)] = {
                "good": good_count,
                "bad": bad_count,
                "self": feedback,
            }

        return result

    @staticmethod
    def get_recommend_metric_bkdata_rt_id(bk_biz_id):
        """获取被推荐指标的计算平台结果表id

        :param recommend_metric: 被推荐的指标(附带维度,并且使用|(竖线)分割)
        :return: 被推荐指标所在的计算平台结果表
        """
        # 从接入表中找到对应对象，使用统一的属性获取该结果表在计算平台的out_table_name
        return METRIC_RECOMMAND_SCENE_SERVICE_TEMPLATE(bk_biz_id=bk_biz_id)

    @classmethod
    def feedback_to_bkdata(cls, request_user, feedback_obj, good_count, bad_count, recommendation_metric_class):
        """反馈到计算平台

        :param request_user: 反馈用户
        :param feedback_obj: 反馈orm对象()
        :param good_count: 点赞数
        :param bad_count: 点踩数
        :param recommendation_metric_class: 被推荐指标标签
        """
        feedback_info = {
            "user": request_user,
            "good_num": good_count,
            "bad_num": bad_count,
            "class": recommendation_metric_class,
            "target_metric_name": feedback_obj.alert_metric_id,
            "target_series_json": [],
        }

        feedback_data = {
            "series_json": json.dumps([]),
            "metric_name": feedback_obj.recommendation_metric,
            "feedback_info": feedback_info,
        }

        try:
            rt_id = cls.get_recommend_metric_bkdata_rt_id(feedback_obj.bk_biz_id)

            api.bkdata.sample_set_feedback(
                rt_id=rt_id,
                feedback_data=[feedback_data],
            )
        except Exception as e:
            logger.exception(f"metric: [{feedback_obj.recommendation_metric}] feedback failed. exception: {e}")

    def perform_request(self, validated_request_data):
        alert_metric_id = validated_request_data["alert_metric_id"]
        recommendation_metric = validated_request_data["recommendation_metric_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        feedback = validated_request_data["feedback"]
        recommendation_metric_class = validated_request_data["recommendation_metric_class"]

        request_user = get_request_username()

        feedback_obj, _ = MetricRecommendationFeedback.objects.update_or_create(
            alert_metric_id=alert_metric_id,
            recommendation_metric_hash=MetricRecommendationFeedback.generate_recommendation_metric_hash(
                recommendation_metric
            ),
            bk_biz_id=bk_biz_id,
            create_user=request_user,
            defaults={"feedback": feedback, "recommendation_metric": recommendation_metric},
        )

        good_count, bad_count = self.get_feedback_count(alert_metric_id, recommendation_metric, bk_biz_id)

        self.feedback_to_bkdata(
            request_user=request_user,
            feedback_obj=feedback_obj,
            good_count=good_count,
            bad_count=bad_count,
            recommendation_metric_class=recommendation_metric_class,
        )

        result = {"feedback": {"good": good_count, "bad": bad_count, "self": feedback}}

        return result


class MultiAnomalyDetectGraphResource(AIOpsBaseResource):
    """提供主机智能异常检测告警详情的图表配置."""

    def perform_request(self, validated_request_data):
        alert = AlertDocument.get(validated_request_data["alert_id"])

        graph_panels = []
        try:
            strategy_algorithm = alert.strategy["items"][0]["algorithms"][0]
            if strategy_algorithm["type"] == AlgorithmModel.AlgorithmChoices.HostAnomalyDetection:
                anomaly_sort = alert.event.extra_info["origin_alarm"]["data"]["values"]["anomaly_sort"]
                anomaly_metrics = parse_anomaly(anomaly_sort, strategy_algorithm["config"])

                base_graph_panel = AIOPSManager.get_graph_panel(alert, use_raw_query_config=True)
                base_graph_panel["type"] = "performance-chart"
                for anomaly_metric in anomaly_metrics:
                    graph_panel = self.generate_metric_graph_panel(
                        copy.deepcopy(base_graph_panel),
                        anomaly_metric,
                    )
                    if graph_panel:
                        graph_panels.append(graph_panel)
        except (KeyError, IndexError):
            raise AIOpsMultiAnomlayDetectError()

        return graph_panels

    def generate_metric_graph_panel(self, base_graph_panel: dict, anomaly_metric: list) -> dict:
        """根据图表基础配置和指标ID生成指标图表配置

        :param base_graph_panel: 基础图表配置
        :param anomaly_metric: 异常指标
            格式: [指标名, 数值, 异常得分, 带单位的数值, 指标中文名]
            参考: ["bk_monitor.system.net.speed_recv", 2812154.0, 0.9799, "2812154.0Kbs", "网卡入流量"]
        :return: 指标图表配置
        """
        graph_panel = copy.deepcopy(base_graph_panel)

        # 获取当前异常指标的详情
        metric_info = parse_metric_id(anomaly_metric[0])
        if not metric_info:
            return {}

        metric = MetricListCache.objects.filter(bk_tenant_id=get_request_tenant_id(), **metric_info).first()
        if not metric:
            return {}

        anomaly_info = {
            "metric_id": anomaly_metric[0],
            "anomaly_point": anomaly_metric[1],
            "anomaly_score": anomaly_metric[2],
            "anomaly_point_with_unit": anomaly_metric[3],
            "metric_name": _(anomaly_metric[4]),
        }

        graph_panel["id"] = anomaly_metric[0]
        graph_panel["title"] = _(anomaly_metric[4])
        graph_panel["subTitle"] = anomaly_metric[0]
        graph_panel["anomaly_info"] = anomaly_info
        graph_panel["result_table_label"] = metric.result_table_label
        graph_panel["result_table_label_name"] = _(metric.result_table_label_name)
        graph_panel["metric_name_alias"] = _(metric.metric_field_name)
        graph_panel["targets"][0]["api"] = "alert.alertGraphQuery"
        graph_panel["targets"][0]["alias"] = ""

        # 因为推荐指标不一定具有告警相同的维度，因此这里不对维度进行任何聚合，只做指标的推荐
        query_configs = graph_panel["targets"][0]["data"]["query_configs"]
        for query_config in query_configs:
            query_config["where"] = [item for item in query_config["where"] if item["key"] != "is_anomaly"]
            query_config["data_source_label"] = metric.data_source_label
            query_config["data_type_label"] = metric.data_type_label
            query_config["table"] = metric.result_table_id
            query_config["metrics"] = [{"field": metric.metric_field, "method": "AVG", "alias": "a"}]

        return graph_panel


class QuickAlertShield(QuickActionTokenResource):
    class RequestSerializer(serializers.Serializer):
        action_id = serializers.IntegerField(label="告警ID")
        token = serializers.CharField(label="通知token")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        shield_hours = serializers.IntegerField(label="屏蔽时间", default=3)

    def handle(self, params, alert_id):
        shield_params = {
            "end_time": params["end_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "begin_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": params["description"],
            "bk_biz_id": params["bk_biz_id"],
            "shield_notice": False,
            "cycle_config": {"begin_time": "", "type": 1, "end_time": ""},
            "is_quick": True,
        }

        shield_params.update({"category": "event", "dimension_config": {"id": alert_id}})
        return shield_params

    def perform_request(self, validated_data):
        alert_ids = validated_data.pop("alert_ids", [])
        bk_biz_id = validated_data["bk_biz_id"]
        shield_hours = validated_data.get("shield_hours", 3)
        shield_end_time = datetime.now() + timedelta(hours=shield_hours)
        success_alerts = []
        failed_alerts = []
        for alert_id in alert_ids:
            params = {
                "type": "event",
                "event_id": alert_id,
                "end_time": shield_end_time,
                "bk_biz_id": bk_biz_id,
                "description": _("快捷屏蔽3小时"),
            }
            try:
                resource.shield.add_shield(self.handle(params, alert_id))
                success_alerts.append(alert_id)
            except BaseException:
                failed_alerts.append(alert_id)
                logger.exception("quick shield alert(%s) error %s", alert_id)
        if not failed_alerts:
            return self.redirect(bk_biz_id, validated_data["action_id"])

        return _("完成快捷屏蔽{shield_hours}小时, 成功({success_alerts})， 失败({failed_alerts})").format(
            shield_hours=shield_hours, success_alerts=len(success_alerts), failed_alerts=len(failed_alerts)
        )


class QuickAlertAck(QuickActionTokenResource):
    """
    基于告警汇总对事件进行批量确认
    """

    class RequestSerializer(serializers.Serializer):
        action_id = serializers.IntegerField(label="处理记录ID")
        token = serializers.CharField(label="通知token")
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, validated_data):
        result = resource.alert.ack_alert(ids=validated_data["alert_ids"], message=_("移动端通知快捷确认"))

        if not (result["alerts_not_exist"]):
            return self.redirect(validated_data["bk_biz_id"], validated_data["action_id"])

        return _(
            "完成快捷确认, 成功({success_alerts})，失败({failed_alerts})，"
            "已确认({alerts_already_ack})，已结束({alerts_not_abnormal})"
        ).format(
            success_alerts=len(result["alerts_ack_success"]),
            failed_alerts=len(result["alerts_not_exist"]),
            alerts_already_ack=len(result["alerts_already_ack"]),
            alerts_not_abnormal=len(result["alerts_not_abnormal"]),
        )


class GetAlertDataRetrievalResource(Resource):
    """
    获取告警数据检索配置
    """

    EVENT_DATASOURCES = [
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
        (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
    ]

    METRIC_DATASOURCES = [
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES),
    ]

    class RequestSerializer(serializers.Serializer):
        alert_id = AlertIDField(required=True, label="告警ID")

    @classmethod
    def metric_query_config_to_query(cls, query_config: dict, filter_dict: dict) -> dict:
        """
        将query_config转换为图标查询配置
        """
        # 如果存在raw_query_config，直接使用
        if query_config.get("raw_query_config"):
            query_config = query_config["raw_query_config"]

        query = {
            "data_source_label": query_config["data_source_label"],
            "data_type_label": query_config["data_type_label"],
            "functions": query_config.get("functions", []),
            "refId": query_config["alias"],
            "index_set_id": query_config.get("index_set_id"),
            "result_table_id": query_config.get("result_table_id", ""),
            "data_label": query_config.get("data_label"),
            "query_string": query_config.get("query_string", ""),
            "metric_field": query_config.get("metric_field", ""),
            "method": query_config.get("agg_method", "COUNT"),
            "interval": query_config.get("agg_interval", 60),
            "group_by": query_config.get("agg_dimension", []),
            "where": query_config.get("agg_condition", []),
            "time_field": query_config.get("time_field"),
        }

        if filter_dict:
            # 条件中维度字段可能比单个 datasource 中的维度字段多，所以需要过滤。
            # promql 的情况下，维度无法分辨，因此只能全部过滤
            if query_config["data_source_label"] != DataSourceLabel.PROMETHEUS:
                filter_dict = {key: value for key, value in filter_dict.items() if key in query["group_by"]}

            where = AIOPSManager.create_where_with_dimensions(query_config["agg_condition"], filter_dict)
            group_by = list(set(query["group_by"]) & set(filter_dict.keys()))
            if "le" in query_config.get("agg_dimension", []):
                # 针对le做特殊处理
                group_by.append("le")
            query["where"] = where
            query["group_by"] = group_by

        return query

    @classmethod
    def generate_event_query_params(cls, item: dict, filter_dict: dict) -> dict:
        """
        TODO: 事件检索跳转参数
        """
        return {}

    @classmethod
    def generate_metric_query_params(cls, item: dict, filter_dict: dict) -> list[dict]:
        """
        指标检索跳转参数
        """
        query_configs = item["query_configs"]
        data_source = (query_configs[0]["data_source_label"], query_configs[0]["data_type_label"])

        # promql模式查询
        if data_source == (DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES):
            query_config = query_configs[0]
            return [
                {
                    "data": {
                        "mode": "code",
                        "source": query_config["promql"],
                        "format": "time_series",
                        "type": "range",
                        "step": query_config["agg_interval"],
                        "filter_dict": filter_dict,
                    }
                }
            ]

        # UI模式查询
        # 查询配置处理
        queries = []
        for query_config in query_configs:
            query = cls.metric_query_config_to_query(query_config, filter_dict)
            queries.append(query)

        # 表达式处理
        expressions = []
        expression = item["expression"] or "a"
        functions = item.get("functions", [])
        if expression != "a" or functions:
            # 如果添加了表达式，需要将子查询隐藏
            for query in queries:
                query["display"] = False

            expressions.append(
                {
                    "expression": expression,
                    "functions": functions,
                    "alias": chr(ord("a") + len(queries)),
                    "active": True,
                }
            )

        return [{"data": {"mode": "ui", "query_configs": queries, "expressionList": expressions}}]

    def perform_request(self, params: dict[str, Any]):
        alert_id = params["alert_id"]
        alert = AlertDocument.get(alert_id)
        if not alert.strategy:
            return []

        item = alert.strategy["items"][0]
        query_configs = item["query_configs"]
        if not query_configs:
            return []

        data_source: tuple[str, str] = (query_configs[0]["data_source_label"], query_configs[0]["data_type_label"])

        # 根据告警维度生成过滤条件
        filter_dict = {}
        try:
            dimensions = alert.event.extra_info.origin_alarm.data.dimensions.to_dict()
            dimension_fields = alert.event.extra_info.origin_alarm.data.dimension_fields
            dimension_fields = [field for field in dimension_fields if not field.startswith("bk_task_index_")]
            filter_dict = {
                key: value
                for key, value in dimensions.items()
                if key in dimension_fields and not (key == "le" and value is None)
            }
        except Exception:  # noqa
            pass

        # 事件检索
        if data_source in self.EVENT_DATASOURCES:
            result = {"type": "event", "params": self.generate_event_query_params(item, filter_dict)}
        # 指标检索
        elif data_source in self.METRIC_DATASOURCES:
            result = {"type": "metric", "params": self.generate_metric_query_params(item, filter_dict)}
        else:
            result = {}

        return result
