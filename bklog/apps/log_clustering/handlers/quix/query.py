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

import hashlib
from collections import defaultdict
from copy import deepcopy

from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.api import BkLogApi, TransferApi
from apps.log_clustering.handlers.pattern import PatternHandler
from apps.log_clustering.models import LogClusteringRuntime
from apps.log_search.handlers.index_set import BaseIndexSetHandler
from apps.log_search.models import LogIndexSet, Scenario
from apps.log_search.utils import get_search_request_scope
from apps.log_unifyquery.handler.pattern import UnifyQueryPatternHandler
from apps.utils.local import get_request_tenant_id


def get_query_runtime(index_set_id):
    return LogClusteringRuntime.objects.filter(index_set_id=index_set_id, bk_tenant_id=get_request_tenant_id()).first()


def apply_query_scope(index_set, params, request):
    biz_id, space_uid = get_search_request_scope(request, params)
    biz_id, space_uid = LogIndexSet.resolve_search_scope(index_set, biz_id, space_uid)
    # C12 的两条路由只登记在源空间，不能把平台级索引的跨空间查询提升到归属空间。
    if space_uid != index_set.space_uid:
        raise PermissionDenied("聚类查询需要源索引集空间的访问权限")
    params["bk_biz_id"] = biz_id


def signature_condition(field):
    return field in ("signature", "log_signature") or field.startswith("__dist_")


def result_query(index_set_id, config, params):
    threshold = config["distance_threshold"]
    params = deepcopy(params)
    params["addition"] = params.get("addition") or []
    for condition in params["addition"]:
        field = condition.get("field", "")
        if field.startswith("__dist_"):
            if field != f"__dist_{threshold.replace('.', '')}":
                raise ValidationError("签名过滤条件与生效的聚类档位不一致")
        if signature_condition(field):
            condition["field"] = "log_signature"
    params["addition"].append({"field": "log_cluster_distance_threshold", "operator": "is", "value": [threshold]})
    return ClusteredLogQuery({**params, "index_set_ids": [index_set_id]})


class ClusteredLogQuery(UnifyQueryPatternHandler):
    def init_base_dict(self):
        query = super().init_base_dict()
        query["query_list"][0]["table_id"] = BaseIndexSetHandler.get_data_label(
            self.index_set_ids[0], clustered_rt=True
        )
        return query

    @staticmethod
    def query_ts_reference(search_dict, raise_exception=True):
        return UnifyQueryPatternHandler.query_ts_reference(search_dict, raise_exception=raise_exception)


class QuixPatternHandler(PatternHandler):
    def __init__(self, runtime, query):
        super().__init__(runtime.index_set_id, query)
        self.runtime = runtime

    def pattern_search(self):
        config = self.runtime.active_config
        if not config or self._pattern_level != config["distance_threshold"].replace(".", ""):
            return []
        rows = super().pattern_search()
        if self._include_origin_log:
            self._fill_origin_logs(rows)
        return rows

    def _fill_origin_logs(self, rows):
        # 同组内按签名折叠，避免每个 Pattern 都发一次原文请求。
        groups = defaultdict(list)
        for row in rows:
            groups[tuple(row["group"])].append(row)
        config = self.runtime.active_config
        for group, group_rows in groups.items():
            for batch in self._chunk_values(group_rows, 500):
                addition = [
                    {"field": key, "operator": "is", "value": [value]} for key, value in zip(self._group_by, group)
                ]
                addition.append(
                    {"field": "log_signature", "operator": "is one of", "value": [r["signature"] for r in batch]}
                )
                params = {**self._query, "addition": self._query.get("addition", []) + addition}
                query = result_query(self._index_set_id, config, params)
                request = {**query.base_dict, "limit": len(batch)}
                request["query_list"][0]["collapse"] = {"field": "log_signature"}
                hits = query._deal_query_result(query.query_ts_raw(request))["origin_log_list"]
                samples = {}
                for hit in hits:
                    message = hit
                    for key in config["input_mapping"]["log"].split("."):
                        message = message.get(key, "") if isinstance(message, dict) else ""
                    samples[hit.get("log_signature", hit.get("signature"))] = message
                for row in batch:
                    row["origin_log"] = samples.get(row["signature"], "")

    def _get_pattern_aggs_result(self, index_set_id, query):
        return result_query(
            index_set_id, self.runtime.active_config, {**query, "agg_field": "log_signature"}
        ).query_pattern()

    def _run_multi_execute(self, multi_execute_func):
        results = multi_execute_func.run(return_exception=True)
        for result in results.values():
            if isinstance(result, Exception):
                raise result
        return results

    def _signature_patterns(self, signatures):
        if not signatures:
            return []
        # Pattern 文档无事件时间。由已鉴权的源索引集派生标签，按已注册的查询目标做无时间过滤的精确查找。
        label = f"{BaseIndexSetHandler.get_data_label(self._index_set_id)}_pattern"
        rt = f"{label}.__default__"
        tenant = self.runtime.bk_tenant_id
        storage = TransferApi.get_result_table_storage(
            {"result_table_list": rt, "storage_type": "elasticsearch", "data_label": label},
            bk_tenant_id=tenant,
        ).get(rt)
        if not storage or storage["storage_config"].get("index_set") != self.runtime.pattern_index:
            raise ValidationError("Pattern 路由未就绪或与生效的 Pattern 索引不一致")
        records = []
        threshold = self.runtime.active_config["distance_threshold"]
        for batch in self._chunk_values(signatures, 500):
            # BKBase save_pattern 的文档主键：SHA256(index_id + NUL + threshold + NUL + signature)。
            ids = [
                hashlib.sha256(f"{self._index_set_id}\0{threshold}\0{signature}".encode()).hexdigest()
                for signature in batch
            ]
            result = BkLogApi.dsl(
                {
                    "index_set_id": self._index_set_id,
                    "indices": self.runtime.pattern_index,
                    "scenario_id": Scenario.ES,
                    "storage_cluster_id": storage["cluster_config"]["cluster_id"],
                    "body": {"size": len(ids), "query": {"ids": {"values": ids}}, "_source": ["signature", "pattern"]},
                },
                bk_tenant_id=tenant,
            )
            if result.get("timed_out") or result.get("_shards", {}).get("failed"):
                raise ValidationError("Pattern 映射表查询未完整返回")
            records.extend(hit["_source"] for hit in result["hits"]["hits"])
        return records
