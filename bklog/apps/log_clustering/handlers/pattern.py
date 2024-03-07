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
import copy
import hashlib
import json
from typing import List

import arrow
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.functional import cached_property

from apps.log_clustering.constants import (
    AGGS_FIELD_PREFIX,
    DEFAULT_LABEL,
    DOUBLE_PERCENTAGE,
    HOUR_MINUTES,
    IS_NEW_PATTERN_PREFIX,
    MIN_COUNT,
    NEW_CLASS_FIELD_PREFIX,
    NEW_CLASS_QUERY_FIELDS,
    NEW_CLASS_QUERY_TIME_RANGE,
    NEW_CLASS_SENSITIVITY_FIELD,
    PERCENTAGE_RATE,
    OwnerConfigEnum,
    PatternEnum,
    RemarkConfigEnum,
)
from apps.log_clustering.models import (
    AiopsSignatureAndPattern,
    ClusteringConfig,
    ClusteringRemark,
    SignatureStrategySettings,
)
from apps.log_search.handlers.search.aggs_handlers import AggsHandlers
from apps.models import model_to_dict
from apps.utils.bkdata import BkData
from apps.utils.db import array_hash
from apps.utils.function import map_if
from apps.utils.local import get_local_param, get_request_username
from apps.utils.thread import MultiExecuteFunc
from apps.utils.time_handler import generate_time_range, generate_time_range_shift


class PatternHandler:
    def __init__(self, index_set_id, query):
        self._index_set_id = index_set_id
        self._pattern_level = query.get("pattern_level", PatternEnum.LEVEL_05.value)
        self._show_new_pattern = query.get("show_new_pattern", False)
        self._year_on_year_hour = query.get("year_on_year_hour", 0)
        self._group_by = query.get("group_by", [])
        self._clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=index_set_id)
        self._query = query

        self._remark_config = query.get("remark_config", RemarkConfigEnum.ALL.value)
        self._owner_config = query.get("owner_config", OwnerConfigEnum.ALL.value)
        self._owners = query.get("owners", [])

    def pattern_search(self):
        """
        aggs_result
        {
            "aggs": {
                "log_signature_01": {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": [
                        {
                            "key": "8d96a0935c848f8e9c876369d301d76e",
                            "doc_count": 10
                        },
                        {
                            "key": "43ba9231388c90ca3802e47f713a7a85",
                            "doc_count": 9
                        }
                    ]
                }
            }
        }
        """

        result = self._multi_query()
        pattern_aggs = result.get("pattern_aggs", [])
        year_on_year_result = result.get("year_on_year_result", {})
        new_class = result.get("new_class", set())
        # 同步的pattern保存信息
        if self._clustering_config.model_output_rt:
            # 在线训练逻辑适配
            pattern_map = AiopsSignatureAndPattern.objects.filter(
                model_id=self._clustering_config.model_output_rt
            ).values("signature", "pattern", "origin_pattern", "label")
        else:
            pattern_map = AiopsSignatureAndPattern.objects.filter(model_id=self._clustering_config.model_id).values(
                "signature", "pattern", "origin_pattern", "label"
            )
        signature_map_pattern = array_hash(pattern_map, "signature", "pattern")
        signature_map_origin_pattern = array_hash(pattern_map, "signature", "origin_pattern")
        signature_map_label = array_hash(pattern_map, "signature", "label")
        sum_count = sum([pattern.get("doc_count", MIN_COUNT) for pattern in pattern_aggs])

        # 符合当前分组hash的所有clustering_remark  signature和origin_pattern可能不相同
        clustering_remarks = ClusteringRemark.objects.filter(
            group_hash=self._convert_groups_to_groups_hash(self._clustering_config.group_fields),
        ).values_list("signature", "origin_pattern", "remark", "owners")
        clustering_remark_list = []
        clustering_remark_dict = {}
        for clustering_remark in clustering_remarks:
            signature, origin_pattern, remark, owners = clustering_remark
            clustering_remark_dict["signature"] = signature
            clustering_remark_dict["origin_pattern"] = origin_pattern
            clustering_remark_dict["remark"] = remark
            clustering_remark_dict["owners"] = owners
            clustering_remark_list.append(clustering_remark_dict)

        result = []
        for pattern in pattern_aggs:
            count = pattern["doc_count"]
            signature = pattern["key"]
            signature_pattern = signature_map_pattern.get(signature, "")
            signature_origin_pattern = signature_map_origin_pattern.get(signature, "")
            group_key = f"{signature}|{pattern.get('group', '')}"
            year_on_year_compare = year_on_year_result.get(group_key, MIN_COUNT)
            remark = []
            owners = []
            for clustering_remark in clustering_remark_list:
                # signature或origin_pattern匹配的，找到一条就行，如果没有就为[]
                if (
                    signature == clustering_remark["signature"]
                    or signature_origin_pattern == clustering_remark["origin_pattern"]
                ):
                    remark = clustering_remark["remark"]
                    owners = clustering_remark["owners"]
                    break
            result.append(
                {
                    "pattern": signature_pattern,
                    "origin_pattern": signature_origin_pattern,
                    "label": signature_map_label.get(signature, ""),
                    "remark": remark,
                    "owners": owners,
                    "count": count,
                    "signature": signature,
                    "percentage": self.percentage(count, sum_count),
                    "is_new_class": signature in new_class,
                    "year_on_year_count": year_on_year_compare,
                    "year_on_year_percentage": self._year_on_year_calculate_percentage(count, year_on_year_compare),
                    "group": str(pattern.get("group", "")).split("|") if pattern.get("group") else [],
                    "monitor": SignatureStrategySettings.get_monitor_config(
                        signature=signature, index_set_id=self._index_set_id, pattern_level=self._pattern_level
                    ),
                }
            )
        if self._show_new_pattern:
            result = map_if(result, if_func=lambda x: x["is_new_class"])
        result = self._get_remark_and_owner(result)
        return result

    def _get_remark_and_owner(self, result):
        if self._remark_config == RemarkConfigEnum.REMARKED.value:
            result = [pattern for pattern in result if pattern["remark"]]
        elif self._remark_config == RemarkConfigEnum.NO_REMARK.value:
            result = [pattern for pattern in result if not pattern["remark"]]

        if self._owner_config == OwnerConfigEnum.NO_OWNER.value:
            result = [pattern for pattern in result if not pattern["owners"]]
        elif self._owner_config == OwnerConfigEnum.OWNER.value:
            if not self._owners:
                return result
            result = [pattern for pattern in result if pattern["owners"] and set(self._owners) & set(pattern["owners"])]
        return result

    def _multi_query(self):
        multi_execute_func = MultiExecuteFunc()
        multi_execute_func.append(
            "pattern_aggs",
            lambda p: self._get_pattern_aggs_result(p["index_set_id"], p["query"]),
            {"index_set_id": self._index_set_id, "query": self._query},
        )
        multi_execute_func.append("year_on_year_result", lambda: self._get_year_on_year_aggs_result())
        multi_execute_func.append("new_class", lambda: self._get_new_class())
        return multi_execute_func.run()

    def _get_pattern_aggs_result(self, index_set_id, query):
        query["fields"] = [{"field_name": self.pattern_aggs_field, "sub_fields": self._build_aggs_group}]
        aggs_result = AggsHandlers.terms(index_set_id, query)
        return self._parse_pattern_aggs_result(self.pattern_aggs_field, aggs_result)

    @property
    def _build_aggs_group(self):
        aggs_group = {}
        aggs_group_reuslt = aggs_group
        for group_key in self._group_by:
            aggs_group["field_name"] = group_key
            aggs_group["sub_fields"] = {}
            aggs_group = aggs_group["sub_fields"]
        return aggs_group_reuslt

    def _get_year_on_year_aggs_result(self) -> dict:
        if self._year_on_year_hour == MIN_COUNT:
            return {}
        new_query = copy.deepcopy(self._query)
        start_time, end_time = generate_time_range_shift(
            self._query["start_time"], self._query["end_time"], self._year_on_year_hour * HOUR_MINUTES
        )
        new_query["start_time"] = start_time.strftime("%Y-%m-%d %H:%M:%S")
        new_query["end_time"] = end_time.strftime("%Y-%m-%d %H:%M:%S")
        new_query["time_range"] = "customized"
        buckets = self._get_pattern_aggs_result(self._index_set_id, new_query)
        for bucket in buckets:
            bucket["key"] = f"{bucket['key']}|{bucket.get('group', '')}"
        return array_hash(buckets, "key", "doc_count")

    @staticmethod
    def _year_on_year_calculate_percentage(target, compare):
        if compare == MIN_COUNT:
            return DOUBLE_PERCENTAGE
        return ((target - compare) / compare) * PERCENTAGE_RATE

    @staticmethod
    def percentage(count, sum_count) -> int:
        # avoid division by zero
        if sum_count == 0:
            return MIN_COUNT
        return (count / sum_count) * PERCENTAGE_RATE

    @cached_property
    def pattern_aggs_field(self) -> str:
        return f"{AGGS_FIELD_PREFIX}_{self._pattern_level}"

    @cached_property
    def new_class_field(self) -> str:
        return f"{NEW_CLASS_FIELD_PREFIX}_{self._pattern_level}"

    def _parse_pattern_aggs_result(self, pattern_field: str, aggs_result: dict) -> List[dict]:
        aggs = aggs_result.get("aggs")
        pattern_field_aggs = aggs.get(pattern_field)
        if not pattern_field_aggs:
            return []
        return self._get_group_by_value(pattern_field_aggs.get("buckets", []))

    def _get_group_by_value(self, bucket):
        for group_key in self._group_by:
            result_buckets = []
            for iter_bucket in bucket:
                doc_key = iter_bucket.get("key")
                group_buckets = iter_bucket.get(group_key, {}).get("buckets", [])
                for group_bucket in group_buckets:
                    # 这里是为了兼容字符串空值，数值为0的情况
                    result_buckets.append(
                        {
                            **group_bucket,
                            "key": doc_key,
                            "doc_count": group_bucket.get("doc_count", 0),
                            "group": (
                                f"{iter_bucket.get('group', '')}|{group_bucket['key']}"
                                if iter_bucket.get("group") is not None  # noqa
                                else group_bucket["key"]
                            ),
                        }
                    )
            bucket = result_buckets
        return bucket

    def _get_new_class(self):
        start_time, end_time = generate_time_range(
            NEW_CLASS_QUERY_TIME_RANGE, self._query["start_time"], self._query["end_time"], get_local_param("time_zone")
        )
        if self._clustering_config.log_count_agg_rt:
            # 新类异常检测逻辑适配
            new_classes = (
                BkData(self._clustering_config.log_count_agg_rt)
                .select(*NEW_CLASS_QUERY_FIELDS)
                .where(NEW_CLASS_SENSITIVITY_FIELD, "=", self.pattern_aggs_field)
                .where(IS_NEW_PATTERN_PREFIX, "=", 1)
                .time_range(start_time.timestamp, end_time.timestamp)
                .query()
            )
        else:
            new_classes = (
                BkData(self._clustering_config.new_cls_pattern_rt)
                .select(*NEW_CLASS_QUERY_FIELDS)
                .where(NEW_CLASS_SENSITIVITY_FIELD, "=", self.new_class_field)
                .time_range(start_time.timestamp, end_time.timestamp)
                .query()
            )
        return {new_class["signature"] for new_class in new_classes}

    def set_signature_config(self, params: dict):
        """
        日志聚类-数据指纹 页面展示信息修改
        """

        qs_objs = ClusteringRemark.objects.filter(
            Q(signature=params["signature"]) | Q(origin_pattern=params["origin_pattern"])
        )
        current_qs_obj = qs_objs.filter(group_hash=self._convert_groups_to_groups_hash(params["groups"])).first()
        if not current_qs_obj:
            return
        if params.get("label", ""):
            current_qs_obj.label = params["label"]
            current_qs_obj.save()
            if qs_objs.exclude(id=current_qs_obj.id):
                for q in qs_objs.exclude(id=current_qs_obj.id):
                    q.label = params.get("label", "")
                    q.save()
        if params.get("owners", []):
            if current_qs_obj.owners:
                for o in params.get("owners", []):
                    if o not in current_qs_obj.owners:
                        current_qs_obj.owners.append(o)
            else:
                current_qs_obj.owners = params["owners"]
            current_qs_obj.save()
            if qs_objs.exclude(id=current_qs_obj.id):
                for q in qs_objs.exclude(id=current_qs_obj.id):
                    if q.owners:
                        for o in params.get("owners", []):
                            if o not in q.owners:
                                q.owners.append(o)
                    else:
                        q.owners = params.get("owners", [])
                    q.save()
        return model_to_dict(current_qs_obj)

    def update_group_fields(self, params: dict):
        """
        更新分组字段
        """
        self._clustering_config.group_fields = params["group_fields"]
        self._clustering_config.save()
        return model_to_dict(self._clustering_config)

    def _convert_groups_to_groups_hash(self, groups: dict) -> str:
        """
        对 groups 字段进行 hash
        """
        groups = dict(sorted(groups.items(), key=lambda x: x[1]))
        return hashlib.md5(json.dumps(groups).encode()).hexdigest()

    @atomic
    def set_clustering_remark(self, params: dict, method: str = "create"):
        """
        日志聚类-数据指纹 页面展示信息修改
        """
        qs_objs = ClusteringRemark.objects.filter(
            Q(signature=params["signature"]) | Q(origin_pattern=params["origin_pattern"])
        )
        current_qs_obj = qs_objs.filter(group_hash=self._convert_groups_to_groups_hash(params["groups"])).first()
        now = int(arrow.now().timestamp * 1000)
        # 如果不存在则新建  同时同步其它signature或origin_pattern相同的ClusteringRemark
        if method == "create":
            remark_info = {"username": get_request_username(), "create_time": now, "remark": params["remark"]}
            if not current_qs_obj:
                new_qs_obj = ClusteringRemark.objects.create(
                    bk_biz_id=self._clustering_config.bk_biz_id,
                    signature=params["signature"],
                    origin_pattern=params["origin_pattern"],
                    groups=params["groups"],
                    group_hash=self._convert_groups_to_groups_hash(params["groups"]),
                    remark=[remark_info],
                )
                # signature 或者origin_pattern 相同的需要同步 新增
                if qs_objs.exclude(id=new_qs_obj.id):
                    for q in qs_objs.exclude(id=new_qs_obj.id):
                        if q.remark:
                            q.remark.append(remark_info)
                        else:
                            q.remark = [remark_info]
                        q.save()
                return model_to_dict(new_qs_obj)
            else:
                if current_qs_obj.remark:
                    current_qs_obj.remark.append(remark_info)
                else:
                    current_qs_obj.remark = [remark_info]
                current_qs_obj.save()
                # signature 或者origin_pattern 相同的需要同步 新增
                if qs_objs.exclude(id=current_qs_obj.id):
                    for q in qs_objs.exclude(id=current_qs_obj.id):
                        if q.remark:
                            q.remark.append(remark_info)
                        else:
                            q.remark = [remark_info]
                        q.save()
        elif method == "update":
            if current_qs_obj:
                # 当前备注信息修改
                for remark in current_qs_obj.remark:
                    if (
                        remark["create_time"] == params["create_time"]
                        and remark["username"] == get_request_username()
                        and remark["remark"] == params["old_remark"]
                    ):
                        remark["remark"] = params["new_remark"]
                        remark["create_time"] = now
                        break
                current_qs_obj.save()
                # signature 或者origin_pattern 相同的需要同步 修改
                if qs_objs.exclude(id=current_qs_obj.id):
                    for q in qs_objs.exclude(id=current_qs_obj.id):
                        # 如果有备注
                        if q.remark:
                            for remark in q.remark:
                                if (
                                    remark["create_time"] == params["create_time"]
                                    and remark["username"] == get_request_username()
                                    and remark["remark"] == params["old_remark"]
                                ):
                                    remark["remark"] = params["new_remark"]
                                    remark["create_time"] = now
                        # 如果没有备注则需要添加一条
                        else:
                            q.remark = [
                                {"username": get_request_username(), "create_time": now, "remark": params["new_remark"]}
                            ]
                        q.save()
            else:
                return
        elif method == "delete":
            if current_qs_obj:
                for remark in current_qs_obj.remark:
                    if (
                        remark["create_time"] == params["create_time"]
                        and remark["username"] == get_request_username()
                        and remark["remark"] == params["remark"]
                    ):
                        current_qs_obj.remark.remove(remark)
                        break
                current_qs_obj.save()
                if qs_objs.exclude(id=current_qs_obj.id):
                    for q in qs_objs.exclude(id=current_qs_obj.id):
                        if q.remark:
                            for remark in q.remark:
                                if (
                                    remark["create_time"] == params["create_time"]
                                    and remark["username"] == get_request_username()
                                    and remark["remark"] == params["remark"]
                                ):
                                    q.remark.remove(remark)
                                    break
                        else:
                            continue
                        q.save()
            else:
                return
        else:
            return
        return model_to_dict(current_qs_obj)

        #
        #
        #
        # # 如果不存在
        # if not qs_obj:
        #     return
        # now = int(arrow.now().timestamp * 1000)
        # result = []
        # for q in qs_obj:
        #     if method == "create":
        #         current_remark = {
        #             "username": get_request_username(),
        #             "create_time": now,
        #             "remark": params["remark"],
        #         }
        #         if q.remark:
        #             q.remark.append(current_remark)
        #         else:
        #             q.remark = [current_remark]
        #     elif method == "update":
        #         for remark in q.remark:
        #             # 完全匹配才能修改成功
        #             if (
        #                 remark["create_time"] == params["create_time"]
        #                 and remark["username"] == get_request_username()
        #                 and remark["remark"] == params["old_remark"]
        #             ):
        #                 remark["remark"] = params["new_remark"]
        #                 remark["create_time"] = now
        #                 break
        #     elif method == "delete":
        #         for remark in q.remark:
        #             # 完全匹配才能删除成功
        #             if (
        #                 remark["create_time"] == params["create_time"]
        #                 and remark["username"] == get_request_username()
        #                 and remark["remark"] == params["remark"]
        #             ):
        #                 q.remark.remove(remark)
        #                 break
        #     else:
        #         return
        #     q.bk_biz_id = self._clustering_config.bk_biz_id
        #     q.save()
        #     result.append(model_to_dict(q))
        # return result

    @classmethod
    def _generate_strategy_result(cls, strategy_result):
        default_labels_set = set(DEFAULT_LABEL)
        result = []
        for strategy_obj in strategy_result:
            labels = map_if(strategy_obj["labels"], if_func=lambda x: x not in default_labels_set)
            result.append({"strategy_id": strategy_obj["id"], "labels": labels})
        return result

    def get_signature_owners(self) -> list:
        # 获取 AiopsSignatureAndPattern 表中的 signature 和 origin_pattern 字段的值
        signature_values = AiopsSignatureAndPattern.objects.values_list('signature', 'origin_pattern')
        query = Q()
        for signature, origin_pattern in signature_values:
            query |= Q(signature=signature) | Q(origin_pattern=origin_pattern)
        owners = ClusteringRemark.objects.values_list('owners', flat=True).distinct()
        result = set()
        for owner in owners:
            result.update(owner)
        return list(result)
