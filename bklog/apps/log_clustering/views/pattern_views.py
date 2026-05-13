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
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF  OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import arrow
from django.http import StreamingHttpResponse
from rest_framework import serializers
from rest_framework.response import Response

from apps.generic import APIViewSet
from apps.iam import ActionEnum, ResourceEnum
from apps.log_clustering.handlers.clustering_monitor import ClusteringMonitorHandler
from apps.log_clustering.handlers.placeholder_analysis import PlaceholderAnalysisHandler
from apps.log_clustering.handlers.pattern import PatternHandler
from apps.log_clustering.models import ClusteringConfig
from apps.log_clustering.permission import PatternPermission
from apps.log_clustering.serializers import (
    DeleteRemarkSerializer,
    PlaceholderDistributionSerializer,
    PlaceholderExportSerializer,
    PlaceholderSamplesSerializer,
    PlaceholderTrendSerializer,
    PatternSearchSerlaizer,
    PatternStrategySerializer,
    SetOwnerSerializer,
    SetRemarkSerializer,
    UpdateGroupFieldsSerializer,
    UpdateRemarkSerializer,
)
from apps.utils.drf import detail_route


class PatternViewSet(APIViewSet):
    lookup_field = "index_set_id"
    serializer_class = serializers.Serializer

    def get_permissions(self):
        return [PatternPermission([ActionEnum.SEARCH_LOG], ResourceEnum.INDICES)]

    @detail_route(methods=["POST"])
    def search(self, request, index_set_id):
        """
        @api {post} /pattern/$index_set_id/search/ 日志聚类-聚类检索
        @apiName pattern_search
        @apiGroup log_clustering
        @apiParam {String} pattern_level 聚类敏感度 01 03 05 06 07 08
        @apiParam {Number} start_time 开始时间，毫秒时间戳
        @apiParam {Number} end_time 结束时间，毫秒时间戳
        @apiParam {String} time_range 时间标识符符["15m", "30m", "1h", "4h", "12h", "1d", "customized"]
        @apiParam {String} keyword 搜索关键字
        @apiParam {Json} ip IP列表
        @apiParam {Json} addition 搜索条件
        @apiParam {Int} year_on_year_hour 同比周期 单位小时 n小时前
        @apiParam {Int} size 条数
        @apiParam {Array} group_by 分组字段
        @apiSuccess {Object[]} data.placeholders 从 pattern 中按出现顺序解析的占位符，用于渲染可点击标签；与 placeholder_distribution 的 placeholder_index 对应
        @apiSuccess {String} data.placeholders.name 占位符名，如 PATH、NUMBER
        @apiSuccess {Number} data.placeholders.index 占位符在 pattern 中的序号，从 0 开始
        @apiParamExample {Json} 请求参数
        {
            "year_on_year_hour": 1,
            "pattern_level": "01",
            "start_time": "2019-06-11 00:00:00",
            "end_time": "2019-06-12 11:11:11",
            "time_range": "customized"
            "keyword": "error",
            "group_by": ["serverIp", "cloudId", ....],
            "host_scopes": {
            "modules": [
                {
                    "bk_obj_id": "module",
                    "bk_inst_id": 4
                },
                {
                    "bk_obj_id": "set",
                    "bk_inst_id": 4
                }
            ],
            "ips": "x.x.x.x, xx.xx.xx.xx"
            },
            "addition": [
                {
                "key": "ip",
                "method": "is",
                "value": "127.0.0.1",
                "condition": "and", (默认不传是and，只支持and or)
                "type": "field"(默认field
                    目前支持field，其他无效)
                }
            ],
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "pattern": "xx [ip] [xxxxx] xxxxx]",
                    "placeholders": [
                        {
                            "name": "IP",
                            "index": 0
                        },
                        {
                            "name": "NUMBER",
                            "index": 1
                        }
                    ],
                    "signature": "xxxxxxxxxxxx",
                    "count": 123,
                    "year_on_year": -10,
                    "percentage": 12,
                    "is_new_class": true,
                    "year_on_year_count": 12,
                    "year_on_year_percentage": 10,
                    "labels": ["xxxx", "xxxx"],
                    "remark": "xxxx",
                    "group": ["xxx"],
                    "monitor":
                    {
                    "is_active": true,
                    "strategy_id": 1,
                    }
                }
            ],
            "result": true
        }
        """
        if index_set_id.startswith("flow-"):
            # 通过 dataflow id 查询 pattern
            flow_id = index_set_id[len("flow-") :]
            clustering_config = ClusteringConfig.get_by_flow_id(flow_id)
            index_set_id = clustering_config.index_set_id

        query_data = self.params_valid(PatternSearchSerlaizer)
        return Response(PatternHandler(index_set_id, query_data).pattern_search())

    @detail_route(methods=["POST"], url_path="placeholder_distribution")
    def placeholder_distribution(self, request, index_set_id):
        """
        @api {post} /pattern/$index_set_id/placeholder_distribution/ 日志聚类-占位符值分布
        @apiName placeholder_distribution
        @apiGroup log_clustering
        @apiDescription 点击 Pattern 中某个占位标签后，返回该占位符在当前 signature、时间范围与过滤上下文下的真实值分布。仅当聚类结果为 Doris 存储且已配置 clustered_rt 时可用；否则返回聚类模块统一「不支持」异常。
        @apiParam {String} index_set_id 索引集 ID（路径参数，须为数值 ID）
        @apiParam {String} signature 当前 Pattern 的 signature，作为 __dist_05 等值条件参与子查询
        @apiParam {String} pattern 当前 Pattern 展示文本，仅作为展示 DSL 输入，用于生成 regexp_extract 规则
        @apiParam {Int} placeholder_index 占位符在 Pattern 中的顺序，从 0 开始，须与 pattern_search 返回的 placeholders[].index 一致
        @apiParam {Number} start_time 开始时间，毫秒时间戳
        @apiParam {Number} end_time 结束时间，毫秒时间戳
        @apiParam {String} [sort] 排序，仅支持 count_desc，默认 count_desc
        @apiParam {Int} [limit] 返回值分布条数上限，默认 100，最小 1，最大 100
        @apiParam {Object} [groups] 当前聚类行的 group_by 上下文；key 须为聚类配置 group_fields 子集，后端合并为等值过滤；若与 addition 同字段语义冲突则参数错误
        @apiParam {String} [keyword] 检索关键字，透传给 UnifyQuery
        @apiParam {String} [value_keyword] 值分布搜索关键字；对占位符值做模糊搜索
        @apiParam {Array} [addition] 检索条件，含 field、operator、value 等，透传给 UnifyQuery
        @apiParam {Object} [host_scopes] 主机过滤范围，透传给 UnifyQuery
        @apiParam {Object} [ip_chooser] 主机选择器，透传给 UnifyQuery
        @apiParam {Int} [bk_biz_id] 业务 ID，不传时默认使用当前聚类配置的业务
        @apiSuccess {String} data.placeholder_name 当前分析的占位符名称
        @apiSuccess {Number} data.placeholder_index 当前分析的占位符序号
        @apiSuccess {Number} data.unique_count regexp 提取非空的去重取值个数（独立 COUNT DISTINCT，非由 TopN 推导）
        @apiSuccess {Number} data.total_count regexp_extract 成功提取非空值的总次数，用于顶部摘要与百分比分母
        @apiSuccess {Object[]} data.values 按 count 降序的 TopN 分布
        @apiSuccess {String} data.values.value 提取到的原始字符串
        @apiSuccess {Number} data.values.count 该取值出现次数
        @apiSuccess {Number} data.values.percentage 占本查询内「regexp 提取非空总行数」的百分比（保留两位小数），非占全量日志行数
        @apiParamExample {json} 请求参数
        {
            "signature": "e4b60ecf",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "start_time": 1773916800000,
            "end_time": 1773920400000,
            "sort": "count_desc",
            "limit": 100,
            "groups": {
                "service_name": "api"
            },
            "keyword": "request failed",
            "value_keyword": "404",
            "addition": [
                {
                    "field": "level",
                    "operator": "is",
                    "value": "error"
                }
            ]
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "placeholder_name": "NUMBER",
                "placeholder_index": 1,
                "unique_count": 3,
                "total_count": 10,
                "values": [
                    {
                        "value": "404",
                        "count": 6,
                        "percentage": 60.0
                    },
                    {
                        "value": "500",
                        "count": 4,
                        "percentage": 40.0
                    }
                ]
            },
            "result": true
        }
        @apiError 非 Doris 或未配置 clustered_rt 时抛 PlaceholderAnalysisNotSupportedException；groups 非法或与 addition 冲突时为参数校验错误
        """
        params = self.params_valid(PlaceholderDistributionSerializer)
        return Response(PlaceholderAnalysisHandler(index_set_id=index_set_id, params=params).get_distribution())

    @detail_route(methods=["POST"], url_path="placeholder_trend")
    def placeholder_trend(self, request, index_set_id):
        """
        @api {post} /pattern/$index_set_id/placeholder_trend/ 日志聚类-占位符趋势分析
        @apiName placeholder_trend
        @apiGroup log_clustering
        @apiDescription 在当前 Pattern、分组与检索上下文下，返回占位符整体趋势与选中值趋势。仅支持 Doris 聚类结果表。
        @apiParam {Number} index_set_id 索引集 ID
        @apiParam {String} signature Pattern 指纹
        @apiParam {String} pattern Pattern 内容
        @apiParam {Number} placeholder_index 占位符索引
        @apiParam {String="01","03","05","07","09"} [pattern_level="05"] 聚类敏感度
        @apiParam {String} [value=""] 当前选中的占位符值；为空时仅返回整体趋势
        @apiParam {String="auto"} [interval="auto"] 时间粒度；支持 auto 或 date_histogram 风格值，如 1m、5m、1h、1d
        @apiParam {Number} start_time 开始时间，毫秒时间戳
        @apiParam {Number} end_time 结束时间，毫秒时间戳
        @apiParam {Object} [groups] 当前 Pattern 分组上下文
        @apiParam {String} [keyword] 关键词检索条件
        @apiParam {Object[]} [addition] 附加检索条件
        @apiParam {Object} [host_scopes] 主机范围
        @apiParam {Object} [ip_chooser] IP 选择器
        @apiParam {Number} [bk_biz_id] 业务 ID
        @apiParamExample {json} 请求参数
        {
            "signature": "e4b60ecf",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "pattern_level": "05",
            "value": "404",
            "interval": "auto",
            "start_time": 1773916800000,
            "end_time": 1774003200000,
            "groups": {
                "service_name": "api"
            },
            "keyword": "request failed",
            "addition": [
                {
                    "field": "level",
                    "operator": "is",
                    "value": "error"
                }
            ]
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "placeholder_name": "NUMBER",
                "placeholder_index": 1,
                "selected_value": "404",
                "interval": "1h",
                "overall": [
                    {
                        "time": 1710864000000,
                        "count": 10
                    }
                ],
                "selected": [
                    {
                        "time": 1710864000000,
                        "count": 3
                    }
                ]
            },
            "result": true
        }
        @apiError 非 Doris 或未配置 clustered_rt 时抛 PlaceholderAnalysisNotSupportedException；groups 非法或与 addition 冲突时为参数校验错误
        """
        params = self.params_valid(PlaceholderTrendSerializer)
        return Response(PlaceholderAnalysisHandler(index_set_id=index_set_id, params=params).get_trend())

    @detail_route(methods=["POST"], url_path="placeholder_samples")
    def placeholder_samples(self, request, index_set_id):
        """
        @api {post} /pattern/$index_set_id/placeholder_samples/ 日志聚类-占位符相关样本
        @apiName placeholder_samples
        @apiGroup log_clustering
        @apiDescription 返回当前选中占位符值的相关样本记录。仅支持 Doris 聚类结果表，返回完整行数据及字段信息，前端按实际表结构渲染。
        @apiParam {Number} index_set_id 索引集 ID
        @apiParam {String} signature Pattern 指纹
        @apiParam {String} pattern Pattern 内容
        @apiParam {Number} placeholder_index 占位符索引
        @apiParam {String="01","03","05","07","09"} [pattern_level="05"] 聚类敏感度
        @apiParam {String} value 当前选中的占位符值，不能为空
        @apiParam {Number} start_time 开始时间，毫秒时间戳
        @apiParam {Number} end_time 结束时间，毫秒时间戳
        @apiParam {Int} [limit=20] 样本返回条数，最小 1，最大 100
        @apiParam {Object} [groups] 当前 Pattern 分组上下文
        @apiParam {String} [keyword] 关键词检索条件
        @apiParam {Object[]} [addition] 附加检索条件
        @apiParam {Object} [host_scopes] 主机范围
        @apiParam {Object} [ip_chooser] IP 选择器
        @apiParam {Number} [bk_biz_id] 业务 ID
        @apiParamExample {json} 请求参数
        {
            "signature": "e4b60ecf",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "pattern_level": "05",
            "value": "404",
            "limit": 20,
            "start_time": 1773916800000,
            "end_time": 1773920400000,
            "groups": {
                "service_name": "api"
            },
            "keyword": "request failed",
            "addition": [
                {
                    "field": "level",
                    "operator": "is",
                    "value": "error"
                }
            ]
        }
        @apiSuccess {String} data.placeholder_name 当前分析的占位符名称
        @apiSuccess {Number} data.placeholder_index 当前分析的占位符序号
        @apiSuccess {String} data.selected_value 当前选中的占位符值
        @apiSuccess {Object[]} data.samples 相关样本完整记录列表
        @apiSuccess {Object[]} data.result_schema 查询结果字段 schema
        @apiSuccess {String[]} data.select_fields_order 查询结果字段顺序
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "placeholder_name": "NUMBER",
                "placeholder_index": 1,
                "selected_value": "404",
                "samples": [
                    {
                        "dtEventTimeStamp": "1710000000000",
                        "serverIp": "1.1.1.1",
                        "message": "request failed, code=404"
                    }
                ],
                "result_schema": [
                    {
                        "field_alias": "dtEventTimeStamp"
                    },
                    {
                        "field_alias": "serverIp"
                    },
                    {
                        "field_alias": "message"
                    }
                ],
                "select_fields_order": ["dtEventTimeStamp", "serverIp", "message"]
            },
            "result": true
        }
        @apiError 非 Doris 或未配置 clustered_rt 时抛 PlaceholderAnalysisNotSupportedException；value 为空、groups 非法或与 addition 冲突时为参数校验错误
        """
        params = self.params_valid(PlaceholderSamplesSerializer)
        return Response(PlaceholderAnalysisHandler(index_set_id=index_set_id, params=params).get_samples())

    @detail_route(methods=["POST"], url_path="placeholder_export")
    def placeholder_export(self, request, index_set_id):
        """
        @api {post} /pattern/$index_set_id/placeholder_export/ 日志聚类-占位符值分布导出
        @apiName placeholder_export
        @apiGroup log_clustering
        @apiDescription 导出当前占位符值分布表，导出内容与 placeholder_distribution 查询上下文保持一致。支持按值模糊搜索。导出使用独立上限 10000 条，超出时按出现次数降序截断。
        @apiParam {Number} index_set_id 索引集 ID
        @apiParam {String} signature Pattern 指纹
        @apiParam {String} pattern Pattern 内容
        @apiParam {Number} placeholder_index 占位符索引
        @apiParam {String="01","03","05","07","09"} [pattern_level="05"] 聚类敏感度
        @apiParam {Number} start_time 开始时间，毫秒时间戳
        @apiParam {Number} end_time 结束时间，毫秒时间戳
        @apiParam {String="count_desc"} [sort="count_desc"] 排序方式
        @apiParam {Object} [groups] 当前 Pattern 分组上下文
        @apiParam {String} [keyword] 关键词检索条件
        @apiParam {String} [value_keyword] 值分布搜索关键字；对占位符值做模糊搜索
        @apiParam {Object[]} [addition] 附加检索条件
        @apiParam {Object} [host_scopes] 主机范围
        @apiParam {Object} [ip_chooser] IP 选择器
        @apiParam {Number} [bk_biz_id] 业务 ID
        @apiParam {Number} [limit] 页面展示参数，导出时忽略；导出固定最多 10000 条
        @apiParamExample {json} 请求参数
        {
            "signature": "e4b60ecf",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "pattern_level": "05",
            "sort": "count_desc",
            "start_time": 1773916800000,
            "end_time": 1773920400000,
            "groups": {
                "service_name": "api"
            },
            "keyword": "request failed",
            "value_keyword": "404",
            "addition": [
                {
                    "field": "level",
                    "operator": "is",
                    "value": "error"
                }
            ]
        }
        @apiSuccessExample {text/csv} 成功返回:
        value,count,percentage
        404,6,60.00%
        500,4,40.00%
        @apiError 非 Doris 或未配置 clustered_rt 时抛 PlaceholderAnalysisNotSupportedException；groups 非法或与 addition 冲突时为参数校验错误
        """
        params = self.params_valid(PlaceholderExportSerializer)
        handler = PlaceholderAnalysisHandler(index_set_id=index_set_id, params=params)
        file_name = f"bklog_placeholder_{index_set_id}_{arrow.now().format('YYYYMMDD_HHmmss')}.csv"
        response = StreamingHttpResponse(
            handler.export_distribution(),
            content_type="application/octet-stream",
        )
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        return response

    @detail_route(methods=["POST"], url_path="remark")
    def set_remark(self, request, index_set_id):
        """
        @api {post} /pattern/$index_set_id/remark/ 日志聚类-设置备注
        @apiName set_remark
        @apiGroup log_clustering
        @apiParam {String} signature 数据指纹
        @apiParam {String} remark 备注内容
        @apiParamExample {json} 请求参数
        {
          "signature": "123",
          "remark": "remark",
          "origin_pattern": "xxx",
          "groups": {"a": "xxx", "b": "xxxx"}
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "id": 1,
                "created_at": "2023-11-03T08:02:44.675115Z",
                "created_by": "xxx",
                "updated_at": "2023-11-09T02:44:58.997461Z",
                "updated_by": "xxx",
                "is_deleted": false,
                "deleted_at": null,
                "deleted_by": null,
                "model_id": "xxx_xxx_xxx",
                "signature": "456",
                "origin_pattern": "xxx",
                "groups": {"a": "xxx", "b": "xxxx"},
                "group_hash": "xxx",
                "label": "合并label",
                "remark": [
                    {
                        "remark": "remark",
                        "username": "",
                        "create_time": 1699497898000
                    },
                    {
                        "username": "xxx",
                        "create_time": 1699497898000,
                        "remark": "备注信息"
                    }
                ],
                "owners": []
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(SetRemarkSerializer)
        return Response(PatternHandler(index_set_id, {}).set_clustering_remark(params=params, method="create"))

    @detail_route(methods=["PUT"], url_path="update_remark")
    def update_remark(self, request, index_set_id):
        """
        @api {post} /pattern/$index_set_id/remark/edit/ 日志聚类-编辑备注
        @apiName set_remark
        @apiGroup log_clustering
        @apiParam {String} signature 数据指纹
        @apiParam {String} remark 备注内容
        @apiParamExample {json} 请求参数
        {
          "signature": "xxx",
          "old_remark": "remark",
          "new_remark": "new_remark",
          "create_time": 1709633753000,
          "origin_pattern": "xxx",
          "groups": {"a": "xxx", "b": "xxxx"}
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "id": 1,
                "created_at": "2023-11-03T08:02:44.675115Z",
                "created_by": "xxx",
                "updated_at": "2023-11-09T02:44:58.997461Z",
                "updated_by": "xxx",
                "is_deleted": false,
                "deleted_at": null,
                "deleted_by": null,
                "model_id": "xxx_xxx_xxx",
                "signature": "456",
                "pattern": "",
                "label": "合并label",
                "remark": [
                    {
                        "remark": "new_remark",
                        "username": "xxx",
                        "create_time": 1709633753000
                    },
                    {
                        "username": "xxx",
                        "create_time": 1699497898000,
                        "remark": "备注信息"
                    }
                ],
                "owners": []
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(UpdateRemarkSerializer)
        return Response(PatternHandler(index_set_id, {}).set_clustering_remark(params=params, method="update"))

    @detail_route(methods=["DELETE"], url_path="delete_remark")
    def delete_remark(self, request, index_set_id):
        """
        @api {delete} /pattern/$index_set_id/remark/ 日志聚类-删除备注
        @apiName delete_remark
        @apiGroup log_clustering
        @apiParam {String} signature 数据指纹
        @apiParam {String} remark 备注内容
        {
          "signature": "xxx",
          "remark": "new_remark",
          "create_time": 1709634004000,
          "origin_pattern": "xxx",
          "groups": {"a": "xxx", "b": "xxxx"}
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "id": 1,
                "created_at": "2023-11-03T08:02:44.675115Z",
                "created_by": "xxx",
                "updated_at": "2023-11-09T02:44:58.997461Z",
                "updated_by": "xxx",
                "is_deleted": false,
                "deleted_at": null,
                "deleted_by": null,
                "model_id": "xxx_xxx_xxx",
                "signature": "456",
                "pattern": "",
                "label": "合并label",
                "remark": [
                    {
                        "remark": "合并label",
                        "username": "",
                        "create_time": 0
                    },
                    {
                        "username": "xxx",
                        "create_time": 1699497898000,
                        "remark": "备注信息"
                    }
                ],
                "owners": []
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(DeleteRemarkSerializer)
        return Response(PatternHandler(index_set_id, {}).set_clustering_remark(params=params, method="delete"))

    @detail_route(methods=["POST"], url_path="owner")
    def set_owner(self, request, index_set_id):
        """
        @api {post} /pattern/$index_set_id/owner/ 日志聚类-设置负责人
        @apiName set_owner
        @apiGroup log_clustering
        @apiParam {String} signature 数据指纹
        @apiParam {String} owners 负责人
        @apiParamExample {json} 请求参数
        {
          "signature": "xxx",
          "owners": ["xx", "a"],
          "origin_pattern": "xxx",
          "groups": {"a": "xxx", "b": "xxxx"}
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "id": 1,
                "created_at": "2023-11-03T08:02:44.675115Z",
                "created_by": "xxx",
                "updated_at": "2023-11-09T02:44:58.997461Z",
                "updated_by": "xxx",
                "is_deleted": false,
                "deleted_at": null,
                "deleted_by": null,
                "model_id": "xxx_xxx_xxx",
                "signature": "123",
                "pattern": "",
                "label": "",
                "remark": [],
                "owners": ["xxx", "a"]
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(SetOwnerSerializer)
        return Response(PatternHandler(index_set_id, {}).set_clustering_owner(params=params))

    @detail_route(methods=["GET"], url_path="list_owners")
    def get_owners(self, request, index_set_id):
        """
        @api {get} /pattern/$index_set_id/owner/ 日志聚类-获取当前维度下的负责人列表
        @apiName get_owner
        @apiGroup log_clustering
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": ["xxx", "xxx"],
            "code": 0,
            "message": ""
        }
        """
        return Response(PatternHandler(index_set_id, {}).get_signature_owners())

    @detail_route(methods=["POST"], url_path="group_fields")
    def update_group_fields(self, request, index_set_id):
        """
        @api {post} /pattern/$index_set_id/group_fields/ 日志聚类-更新分组字段
        @apiName update_group_fields
        @apiGroup log_clustering
        @apiParam {String} group_fields 分组字段列表
        @apiParamExample {json} 请求参数
        {
          "group_fields": {"a": "b", "c": "d"}
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {"a": "b", "c": "d"},
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(UpdateGroupFieldsSerializer)
        return Response(PatternHandler(index_set_id, {}).update_group_fields(group_fields=params["group_fields"]))

    @detail_route(methods=["POST"], url_path="pattern_strategy")
    def pattern_strategy(self, request, index_set_id):
        """
        @api {post} /pattern/$index_set_id/pattern_strategy/ 日志聚类-告警策略开关
        @apiName pattern_strategy
        @apiGroup log_clustering
        @apiParam {String} pattern_strategy 告警策略开关
        @apiParamExample {json} 请求参数
        {
            "signature": "xxxxxxxxxx",
            "origin_pattern": "xxxxx",
            "groups": {
                "__ext.container_id": "xxxxxxxxxx"
            },
            "strategy_enabled": true
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {"strategy_id": 1234},
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(PatternStrategySerializer)
        return Response(ClusteringMonitorHandler(index_set_id=index_set_id).create_or_update_pattern_strategy(params))
