"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from rest_framework.response import Response

from apps.api import MonitorApi
from apps.generic import APIViewSet
from apps.iam import ActionEnum, ResourceEnum
from apps.iam.handlers.drf import InstanceActionPermission
from apps.log_search.handlers.alert_strategy import AlertStrategyHandler
from apps.log_search.serializers import (
    AlertRecordSerializer,
    LogRelatedInfoSerializer,
    StrategyRecordSerializer,
)
from apps.utils.drf import detail_route


class AlertStrategyViewSet(APIViewSet):
    lookup_field = "index_set_id"

    def get_permissions(self):
        return [InstanceActionPermission([ActionEnum.SEARCH_LOG], ResourceEnum.INDICES)]

    @detail_route(methods=["post"], url_path="alert_records")
    def get_alert_records(self, request, index_set_id=None):
        """
        @api {post} alert_strategy/$index_set_id/alert_records/ 查询告警
        @apiName alert_record
        @apiGroup alert_strategy
        @apiParam {String} space_uid 空间唯一标识
        @apiParam {String} status 状态
        @apiParam {Int} page 页数
        @apiParam {Int} page_size 每页条数
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                {
                    "id": "1741686571487423209",
                    "strategy_id": 1234567,
                    "alert_name": "告警能力补齐-test1",
                    "first_anomaly_time": 1741685940,
                    "duration": "10m",
                    "status": "CLOSED",
                    "severity": 2,
                    "assignee": "xxx",
                    "appointee": "xxx,
                    "end_time": 17416865714,
                }
            ],
            "code": 0,
            "message": ""
        }
        """

        params = self.params_valid(AlertRecordSerializer)
        data = AlertStrategyHandler(index_set_id=index_set_id, space_uid=params["space_uid"]).get_alert_records(
            params["status"],
            params["page"],
            params["page_size"],
        )
        return Response(data)

    @detail_route(methods=["post"], url_path="strategy_records")
    def get_strategy_records(self, request, index_set_id=None):
        """
        @api {post} alert_strategy/$index_set_id/strategy_records/ 查询策略
        @apiName alert_record
        @apiGroup alert_strategy
        @apiParam {String} space_uid 空间唯一标识
        @apiParam {Int} page 页数
        @apiParam {Int} page_size 每页条数
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                {
                  'strategy_id': 156827,
                  'name': '告警能力补齐-test2',
                  'query_string': '*',
                  'latest_time': 1741750200},
                 {
                  'strategy_id': 156728,
                  'name': '告警能力补齐-test',
                  'query_string': 'serverIp : 11.154.220',
                  'latest_time': 1741749840}
                ]
            "code": 0,
            "message": ""
        }
        """

        params = self.params_valid(StrategyRecordSerializer)
        data = AlertStrategyHandler(index_set_id=index_set_id, space_uid=params["space_uid"]).get_strategy_records(
            params["page"],
            params["page_size"],
        )
        return Response(data)

    @detail_route(methods=["get"], url_path="log_related_info")
    def log_related_info(self, request, index_set_id=None):
        """
        @api {get} alert_strategy/$index_set_id/log_related_info/ 日志平台关联信息
        @apiName log_related_info
        @apiGroup alert_strategy
        @apiParam {Int} alert_id 告警id
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "query_string": "*",
                "agg_condition": [
                    {
                        "condition": "and",
                        "method": "eq",
                        "dimension_name": "云区域ID",
                        "value": [
                            "0"
                        ],
                        "key": "cloudId"
                    }
                ]
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(LogRelatedInfoSerializer)
        alert_id = params["alert_id"]
        alert_infos = MonitorApi.get_alert_detail({"id": alert_id})
        query_config = alert_infos.get("extend_info", {})
        query_string = query_config.get("query_string", "*")
        agg_condition = query_config.get("agg_condition", [])
        extra_info = alert_infos.get("extra_info", {})
        dimensions = extra_info.get("origin_alarm", {}).get("data", {}).get("dimensions", {})
        # 把维度信息追加到agg_condition中
        for key, value in dimensions.items():
            agg_condition.append(
                {
                    "condition": "and",
                    "method": "eq",
                    "dimension_name": key,
                    "value": [f"{value}"],
                    "key": key,
                }
            )
        return Response(
            {
                "query_string": query_string,
                "agg_condition": agg_condition,
            }
        )
