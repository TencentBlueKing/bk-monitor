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
from typing import List

import arrow
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
    PatternEnum,
)
from apps.log_clustering.models import (
    AiopsSignatureAndPattern,
    ClusteringConfig,
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
        if self._clustering_config.model_output_rt:
            # 在线训练逻辑适配
            pattern_map = AiopsSignatureAndPattern.objects.filter(
                model_id=self._clustering_config.model_output_rt
            ).values("signature", "pattern", "label", "remark", "owners")
        else:
            pattern_map = AiopsSignatureAndPattern.objects.filter(model_id=self._clustering_config.model_id).values(
                "signature", "pattern", "label", "remark", "owners"
            )
        signature_map_pattern = array_hash(pattern_map, "signature", "pattern")
        signature_map_label = array_hash(pattern_map, "signature", "label")
        signature_map_remark = array_hash(pattern_map, "signature", "remark")
        signature_map_owners = array_hash(pattern_map, "signature", "owners")
        sum_count = sum([pattern.get("doc_count", MIN_COUNT) for pattern in pattern_aggs])
        result = []
        for pattern in pattern_aggs:
            count = pattern["doc_count"]
            signature = pattern["key"]
            group_key = f"{signature}|{pattern.get('group', '')}"
            year_on_year_compare = year_on_year_result.get(group_key, MIN_COUNT)
            result.append(
                {
                    "pattern": signature_map_pattern.get(signature, ""),
                    "label": signature_map_label.get(signature, ""),
                    "remark": signature_map_remark.get(signature, []),
                    "owners": signature_map_owners.get(signature, []),
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

    def set_signature_config(self, signature: str, configs: dict):
        """
        日志聚类-数据指纹 页面展示信息修改
        """
        if self._clustering_config.model_output_rt:
            qs = AiopsSignatureAndPattern.objects.filter(
                model_id=self._clustering_config.model_output_rt, signature=signature
            )
        else:
            qs = AiopsSignatureAndPattern.objects.filter(model_id=self._clustering_config.model_id, signature=signature)
        qs_obj = qs.first()
        if not qs_obj:
            return
        for k, v in configs.items():
            if k == "label":
                qs_obj.label = v
            if k == "owners":
                qs_obj.owners = v
        qs_obj.save()
        return model_to_dict(qs_obj)

    def set_clustering_remark(self, signature: str, configs: dict, method: str = "create"):
        """
        日志聚类-数据指纹 页面展示信息修改
        """
        if self._clustering_config.model_output_rt:
            qs = AiopsSignatureAndPattern.objects.filter(
                model_id=self._clustering_config.model_output_rt, signature=signature
            )
        else:
            qs = AiopsSignatureAndPattern.objects.filter(model_id=self._clustering_config.model_id, signature=signature)
        qs_obj = qs.first()
        if not qs_obj:
            return
        now = int(arrow.now().timestamp * 1000)
        if method == "create":
            current_remark = {
                "username": get_request_username(),
                "create_time": now,
                "remark": configs["remark"],
            }
            if qs_obj.remark:
                qs_obj.remark.append(current_remark)
            else:
                qs_obj.remark = [current_remark]
        elif method == "update":
            for remark in qs_obj.remark:
                # 完全匹配才能修改成功
                if (
                    remark["create_time"] == configs["create_time"]
                    and remark["username"] == get_request_username()
                    and remark["remark"] == configs["old_remark"]
                ):
                    remark["remark"] = configs["new_remark"]
                    remark["create_time"] = now
                    break
        elif method == "delete":
            for remark in qs_obj.remark:
                # 完全匹配才能删除成功
                if (
                    remark["create_time"] == configs["create_time"]
                    and remark["username"] == get_request_username()
                    and remark["remark"] == configs["remark"]
                ):
                    qs_obj.remark.remove(remark)
                    break
        else:
            return
        qs_obj.save()
        return model_to_dict(qs_obj)

    @classmethod
    def _generate_strategy_result(cls, strategy_result):
        default_labels_set = set(DEFAULT_LABEL)
        result = []
        for strategy_obj in strategy_result:
            labels = map_if(strategy_obj["labels"], if_func=lambda x: x not in default_labels_set)
            result.append({"strategy_id": strategy_obj["id"], "labels": labels})
        return result
