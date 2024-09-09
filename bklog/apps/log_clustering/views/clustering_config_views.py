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
import re

from pipeline.service import task_service
from rest_framework.response import Response

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import BKDATA_CLUSTERING_TOGGLE
from apps.generic import APIViewSet
from apps.log_clustering.constants import CLUSTERING_CONFIG_DEFAULT
from apps.log_clustering.exceptions import ClusteringClosedException
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.serializers import (
    ClusteringConfigSerializer,
    ClusteringDebugSerializer,
)
from apps.utils.drf import detail_route, list_route
from apps.utils.log import logger


class ClusteringConfigViewSet(APIViewSet):
    lookup_field = "index_set_id"

    def get_permissions(self):
        return []

    @detail_route(methods=["GET"], url_path="config")
    def get_config(self, request, *args, index_set_id=None, **kwargs):
        """
        @api {get} /clustering_config/$index_set_id/config 1_聚类设置-详情
        @apiName get_clustering_config
        @apiGroup log_clustering
        @apiParam {Int} collector_config_id 采集项id
        @apiSuccess {Int} collector_config_id 采集项id
        @apiSuccess {Str} collector_config_name_en 采集项名称
        @apiSuccess {Int} index_set_id 索引集id
        @apiSuccess {Int} min_members 最小日志数量
        @apiSuccess {Str} max_dist_list 敏感度
        @apiSuccess {Str} predefined_varibles 预先定义的正则表达式
        @apiSuccess {Str} delimeter 分词符
        @apiSuccess {Int} max_log_length 最大日志长度
        @apiSuccess {Int} is_case_sensitive 是否大小写忽略
        @apiSuccess {Str} clustering_fields 聚合字段
        @apiSuccess {Int} bk_biz_id 业务id
        @apiSuccess {List} filter_rules 过滤规则
        @apiSuccess {Str} filter_rules.fields_name 过滤规则字段名
        @apiSuccess {Str} filter_rules.op 过滤规则操作符号
        @apiSuccess {Str} filter_rules.value 过滤规则字段值
        @apiSuccess {Str} filter_rules.logic_operator 过滤规则逻辑运算符号
        @apiSuccessExample {json} 成功返回:
        {
            "collector_config_id":1,
            "collector_config_name_en":"test",
            "index_set_id":1,
            "min_members":1,
            "max_dist_list":"0.1,0.2,0.3,0.4,0.5",
            "predefined_varibles":"xxx",
            "delimeter":"xx",
            "max_log_length":1,
            "is_case_sensitive":1,
            "clustering_fields":"LOG",
            "bk_biz_id":1,
            "filter_rules":[
                {
                    "fields_name":"test",
                    "op":"=",
                    "value":1，
                    "logic_operator": ""
                }
            ]
        }
        """
        return Response(ClusteringConfigHandler(index_set_id=index_set_id).retrieve())

    @detail_route(methods=["GET"], url_path="start")
    def start(self, request, *args, index_set_id=None, **kwargs):
        return Response(ClusteringConfigHandler(index_set_id=index_set_id).online_start())

    @detail_route(methods=["GET"], url_path="offline_start")
    def offline_start(self, request, *args, index_set_id=None, **kwargs):
        return Response(ClusteringConfigHandler(index_set_id=index_set_id).start())

    @list_route(methods=["GET"], url_path="pipeline/state")
    def get_pipeline_state(self, request, *args, **kwargs):
        return Response(task_service.get_state(request.query_params.get("node_id", "")))

    @list_route(methods=["GET"], url_path="pipeline/retry")
    def retry_pipeline(self, request, *args, **kwargs):
        action_result = task_service.retry_activity(request.query_params.get("node_id", ""))
        return Response({"result": action_result.result, "message": action_result.message})

    @list_route(methods=["GET"], url_path="pipeline/skip")
    def skip_pipeline(self, request, *args, **kwargs):
        action_result = task_service.skip_activity(request.query_params.get("node_id", ""))
        return Response({"result": action_result.result, "message": action_result.message})

    @list_route(methods=["GET"], url_path="pipeline/fail")
    def fail_pipeline(self, request, *args, **kwargs):
        action_result = task_service.forced_fail(request.query_params.get("node_id", ""))
        return Response({"result": action_result.result, "message": action_result.message})

    @detail_route(methods=["POST"], url_path="access/create")
    def create_access(self, request, index_set_id, *args, **kwargs):
        """
        @api {post} /clustering_config/$index_set_id/access/create/ 2_聚类设置-接入
        @apiName access_clustering_config
        @apiGroup log_clustering
        @apiParam {Int} bk_biz_id 业务id
        @apiParam {Str} clustering_fields 聚合字段
        @apiParam {Int} [min_members] 最小日志数量
        @apiParam {Str} [predefined_varibles] 预先定义的正则表达式
        @apiParam {Str} [delimeter] 分词符
        @apiParam {Int} [max_log_length] 最大日志长度
        @apiParam {Int} [is_case_sensitive] 是否大小写忽略
        @apiParam {Boolean} [new_class_strategy_enable=false] 是否开启告警
        @apiParam {Boolean} [normal_strategy_enable=false] 是否开启数量突增告警
        @apiParam {List} filter_rules 过滤规则
        @apiParam {Str} [filter_rules.fields_name] 过滤规则字段名
        @apiParam {Str} [filter_rules.op] 过滤规则操作符号
        @apiParam {Str} [filter_rules.value] 过滤规则字段值
        @apiParam {Str} [filter_rules.logic_operator] 过滤规则逻辑运算符号
        @apiSuccessExample {json} 成功返回:
        {
            "message":"",
            "code":0,
            "data":{
                "collector_config_id":1,
                "collector_config_name_en":"test",
                "index_set_id":1,
                "min_members":1,
                "max_dist_list":"0.1,0.2,0.3,0.4,0.5",
                "predefined_varibles":"xxx",
                "delimeter":"xx",
                "max_log_length":1,
                "is_case_sensitive":1,
                "clustering_fields":"log",
                "bk_biz_id":1,
                "new_class_strategy_enable": true,
                "normal_strategy_enable": true,
                "filter_rules":[
                    {
                        "fields_name":"test",
                        "op":"=",
                        "value":1,
                        "logic_operator": ""
                    }
                ]
            },
            "result":true
        }
        """
        params = self.params_valid(ClusteringConfigSerializer)
        return Response(ClusteringConfigHandler().create(index_set_id=index_set_id, params=params))

    @detail_route(methods=["POST"], url_path="access/update")
    def update_access(self, request, index_set_id, *args, **kwargs):
        """
        @api {post} /clustering_config/$index_set_id/access/update/ 2_聚类设置-更新接入
        @apiName access_clustering_config
        @apiGroup log_clustering
        @apiParam {Int} bk_biz_id 业务id
        @apiParam {Str} clustering_fields 聚合字段
        @apiParam {Int} [min_members] 最小日志数量
        @apiParam {Str} [predefined_varibles] 预先定义的正则表达式
        @apiParam {Str} [delimeter] 分词符
        @apiParam {Int} [max_log_length] 最大日志长度
        @apiParam {Int} [is_case_sensitive] 是否大小写忽略
        @apiParam {Boolean} [new_class_strategy_enable=false] 是否开启告警
        @apiParam {Boolean} [normal_strategy_enable=false] 是否开启数量突增告警
        @apiParam {List} filter_rules 过滤规则
        @apiParam {Str} [filter_rules.fields_name] 过滤规则字段名
        @apiParam {Str} [filter_rules.op] 过滤规则操作符号
        @apiParam {Str} [filter_rules.value] 过滤规则字段值
        @apiParam {Str} [filter_rules.logic_operator] 过滤规则逻辑运算符号
        @apiSuccessExample {json} 成功返回:
        {
            "message":"",
            "code":0,
            "data":{
                "index_set_id":1,
                "min_members":1,
                "predefined_varibles":"xxx",
                "delimeter":"xx",
                "max_log_length":1,
                "is_case_sensitive":1,
                "clustering_fields":"log",
                "bk_biz_id":1,
                "new_class_strategy_enable": true,
                "normal_strategy_enable": true,
                "filter_rules":[
                    {
                        "fields_name":"test",
                        "op":"=",
                        "value":1,
                        "logic_operator": ""
                    }
                ]
            },
            "result":true
        }
        """
        params = self.params_valid(ClusteringConfigSerializer)
        return Response(ClusteringConfigHandler(index_set_id=index_set_id).update(params=params))

    @detail_route(methods=["GET"], url_path="access/status")
    def access_status(self, request, index_set_id, *args, **kwargs):
        """
        @api {post} /clustering_config/$index_set_id/access/status/ 2_聚类设置-接入状态
        @apiSuccessExample {json} 成功返回:
        {
            "message":"",
            "code":0,
            "data": {
                "flow_create": {
                    "status": "SUCCESS",  // 可选 PENDING, RUNNING, SUCCESS, FAILED
                    "message": "步骤完成",
                },
                "flow_run": {
                    "status": "FAILED",
                    "message": "步骤执行失败，原因: xxx",
                },
                "data_check": {
                    "status": "PENDING",
                    "message": "等待执行",
                }
            }
            "result":true
        }
        """
        task_id = request.query_params.get("task_id")
        include_update = request.query_params.get("include_update")
        return Response(
            ClusteringConfigHandler(index_set_id=index_set_id).get_access_status(
                task_id=task_id, include_update=include_update
            )
        )

    @list_route(methods=["GET"], url_path="default_config")
    def get_default_config(self, request, *args, **kwargs):
        """
        @api {post} /clustering_config/default_config/ 3_聚类设置-获取默认配置
        @apiName get_default_config
        @apiGroup log_clustering
        @apiSuccess {Int} min_members 最小日志数量
        @apiSuccess {Str} max_dist_list 敏感度
        @apiSuccess {Str} predefined_varibles 预先定义的正则表达式
        @apiSuccess {Str} delimeter 分词符
        @apiSuccess {Int} max_log_length 最大日志长度
        @apiSuccess {Int} is_case_sensitive 是否大小写忽略
        @apiSuccess {Str} clustering_fields 聚合字段
        @apiSuccessExample {json} 成功返回:
        {
            "message":"",
            "code":0,
            "data":{
                "min_members":1,
                "max_dist_list":"0.1,0.2,0.3,0.4,0.5",
                "predefined_varibles":"xxx",
                "delimeter":"xx",
                "max_log_length":1,
                "is_case_sensitive":1,
                "clustering_fields":"LOG",
            },
            "result":true
        }
        @apiSuccessExample {json} 无默认配置
        {
            "message":"",
            "code":0,
            "data": null,
            "result": true
        }
        """
        if not FeatureToggleObject.switch(BKDATA_CLUSTERING_TOGGLE):
            raise ClusteringClosedException()
        return Response(
            FeatureToggleObject.toggle(BKDATA_CLUSTERING_TOGGLE).feature_config.get(CLUSTERING_CONFIG_DEFAULT)
        )

    @list_route(methods=["POST"], url_path="debug")
    def debug(self, request, *args, **kwargs):
        """
        @api {post} /clustering_config/debug/ 4_聚类设置-调试
        @apiName preview clustering solution
        @apiGroup log_clustering
        @apiParam {Str} input_data 输入日志
        @apiParam {Str} predefined_varibles 预先定义的正则表达式
        @apiSuccessExample {json} 成功返回:
        {
            "message":"",
            "code":0,
            "data": "1234",
            "result":true
        }
        """
        params = self.params_valid(ClusteringDebugSerializer)
        return Response(
            ClusteringConfigHandler().debug(
                input_data=params["input_data"],
                predefined_varibles=params["predefined_varibles"],
            )
        )

    @list_route(methods=["POST"], url_path="check_regexp")
    def check(self, request, *args, **kwargs):
        """
        @api {post} /clustering_config/check_regexp/ 5_聚类设置-调试正则
        @apiName check regexp invalid
        @apiGroup log_clustering
        @apiParam {Str} regexp 正则表达式
        @apiSuccessExample {json} 正确的正则表达式:
        {
            "message":"",
            "code":0,
            "data":true,
            "result":true
        }
        @apiSuccessExample {json} 错误的正则表达式
        {
            "message":"",
            "code":0,
            "data":false,
            "result":true
        }
        """
        regexp_str = request.data.get("regexp")
        if not regexp_str:
            return Response(False)

        try:
            re.compile(regexp_str)
        except BaseException as e:  # pylint: disable=broad-except
            logger.error("check regexp failed: %s", e)
            return Response(False)
        return Response(True)
