# -*- coding: utf-8 -*-
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
from apps.log_clustering.constants import StrategiesType
from apps.log_clustering.handlers.clustering_monitor import ClusteringMonitorHandler
from apps.log_clustering.models import SignatureStrategySettings
from apps.log_clustering.serializers import (
    NewClsStrategySerializer,
    NormalStrategySerializer,
    StrategyTypeSerializer,
    UserGroupsSerializer,
)
from apps.utils.drf import detail_route, list_route


class ClusteringMonitorViewSet(APIViewSet):
    lookup_field = "index_set_id"

    @list_route(methods=["post"], url_path="search_user_groups")
    def search_user_groups(self, request):
        """
        @api {get} clustering_monitor/search_user_groups/ 查询通知组
        @apiName search user groups
        @apiGroup log_clustering
        @apiSuccessExample {json} 成功返回:
        {
        "result": true,
        "data": [
            {
                "id": 12,
                "name": "Kafka_1",
                "bk_biz_id": 12,
                "need_duty": false,
                "channels": [
                    "user"
                ],
                "desc": "",
                "timezone": "Asia/Shanghai",
                "update_user": "admin",
                "update_time": "2024-07-22 11:05:28+0800",
                "create_user": "db",
                "create_time": "2023-10-24 14:32:30+0800",
                "duty_rules": [],
                "mention_list": [],
                "mention_type": 1,
                "app": "",
                "users": [
                    {
                        "id": "admin",
                        "display_name": "admin",
                        "type": "user"
                    }
                ],
                "strategy_count": 0,
                "rules_count": 1,
                "delete_allowed": false,
                "edit_allowed": true,
                "config_source": "UI"
                }
            ]
        }
        """
        params = self.params_valid(UserGroupsSerializer)
        data = MonitorApi.search_user_groups({"bk_biz_ids": [params["bk_biz_id"]], "ids": params["ids"]})
        return Response(data)

    @detail_route(methods=["get"], url_path="get_strategy")
    def get_strategy(self, request, index_set_id=None):
        """
        @api {get} clustering_monitor/$index_set_id/get_strategy?strategy_type=$strategy_type 获取告警策略信息
        @apiName get_strategies
        @apiGroup log_clustering
        @apiSuccess {Str} index_set_id 索引集ID
        @apiParams {Str} strategy_type 策略类型
        @apiSuccessExample {json} 成功返回:
        {
        "result": true,
        "data": {
             "strategy_id": 123,
             "interval": "7",
             "threshold": 1,
             "level": "8",
             "user_groups": [1,2]
          }
          }
         },
        "code": 0,
        "message": ""
        }
        """
        strategy_type = request.query_params.get("strategy_type", "")
        obj = SignatureStrategySettings.objects.filter(
            index_set_id=index_set_id,
            strategy_type=strategy_type,
            signature="",
        ).first()
        if not obj or not obj.strategy_id:
            return Response({})
        strategy_id = obj.strategy_id
        return Response(ClusteringMonitorHandler(index_set_id=index_set_id).get_strategy(strategy_type, strategy_id))

    @detail_route(methods=["post"], url_path="new_cls_strategy")
    def create_or_update_new_cls_strategy(self, request, index_set_id=None):
        """
        @api {get} clustering_monitor/$index_set_id/new_cls_strategy/ 更新或创建新类告警策略
        @apiName new_cls_strategy
        @apiGroup log_clustering
        @apiSuccess {Str} index_set_id 索引集ID
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": 12345
            "code": 0,
            "message": ""
        }
        """
        strategy_type = StrategiesType.NEW_CLS_strategy
        params = self.params_valid(NewClsStrategySerializer)
        return Response(
            ClusteringMonitorHandler(index_set_id=index_set_id).create_or_update_clustering_strategy(
                params, strategy_type
            )
        )

    @detail_route(methods=["post"], url_path="normal_strategy")
    def create_or_update_normal_strategy(self, request, index_set_id=None):
        """
        @api {get} clustering_monitor/$index_set_id/new_cls_strategy/ 更新或创建数量突增告警策略
        @apiName normal_strategy
        @apiGroup log_clustering
        @apiSuccess {Str} index_set_id 索引集ID
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": 12345
            "code": 0,
            "message": ""
        }
        """
        strategy_type = StrategiesType.NORMAL_STRATEGY
        params = self.params_valid(NormalStrategySerializer)

        return Response(
            ClusteringMonitorHandler(index_set_id=index_set_id).create_or_update_clustering_strategy(
                params, strategy_type
            )
        )

    def destroy(self, request, index_set_id=None):
        """
        @api {delete} clustering_monitor/$index_set_id/ 删除告警策略
        @apiName delete_strategy
        @apiGroup log_clustering
        @apiSuccess {Str} index_set_id 索引集ID
        @apiParams {Str} strategy_type 策略类型
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": "26",
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(StrategyTypeSerializer)
        strategy_type = params["strategy_type"]
        return Response(ClusteringMonitorHandler(index_set_id=index_set_id).delete_strategy(strategy_type))
