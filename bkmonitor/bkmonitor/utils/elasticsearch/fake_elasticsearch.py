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
from collections import defaultdict

import jmespath
from elasticmock.fake_elasticsearch import (
    FakeElasticsearch,
    FakeQueryCondition,
    MetricType,
    QueryType,
)
from elasticmock.utilities import get_random_id
from elasticsearch.client.utils import query_params
from mock import patch

from bkmonitor.documents import (
    ActionInstanceDocument,
    AlertDocument,
    AlertLog,
    EventDocument,
)


class FakeElasticsearchBucket(FakeElasticsearch):
    """
    测试ES操作可用
    """

    def __init__(self, hosts=None, transport_class=None, **kwargs):
        super(FakeElasticsearchBucket, self).__init__(hosts, transport_class, **kwargs)
        self.__documents_dict = {}
        self.scrolls = {}
        self.fake_get_document_index()

    @staticmethod
    def fake_get_document_index():
        """
        :return:
        """
        patch("bkmonitor.documents.AlertDocument._get_index", return_value=AlertDocument.Index.name).start()
        patch(
            "bkmonitor.documents.AlertDocument.build_index_name_by_time", return_value=AlertDocument.Index.name
        ).start()
        patch(
            "bkmonitor.documents.AlertDocument.build_all_indices_read_index_name", return_value=AlertDocument.Index.name
        ).start()

        patch(
            "bkmonitor.documents.ActionInstanceDocument._get_index", return_value=ActionInstanceDocument.Index.name
        ).start()
        patch(
            "bkmonitor.documents.ActionInstanceDocument.build_index_name_by_time",
            return_value=ActionInstanceDocument.Index.name,
        ).start()
        patch(
            "bkmonitor.documents.ActionInstanceDocument.build_all_indices_read_index_name",
            return_value=ActionInstanceDocument.Index.name,
        ).start()

        patch("bkmonitor.documents.AlertLog._get_index", return_value=AlertLog.Index.name).start()
        patch("bkmonitor.documents.AlertLog.build_index_name_by_time", return_value=AlertLog.Index.name).start()
        patch(
            "bkmonitor.documents.AlertLog.build_all_indices_read_index_name", return_value=AlertLog.Index.name
        ).start()

        patch("bkmonitor.documents.EventDocument._get_index", return_value=EventDocument.Index.name).start()
        patch(
            "bkmonitor.documents.EventDocument.build_index_name_by_time", return_value=EventDocument.Index.name
        ).start()
        patch(
            "bkmonitor.documents.EventDocument.build_all_indices_read_index_name", return_value=EventDocument.Index.name
        ).start()

    # @query_params(*es_query_params, **kwargs)
    @query_params(
        "_source",
        "_source_excludes",
        "_source_includes",
        "allow_no_indices",
        "allow_partial_search_results",
        "analyze_wildcard",
        "analyzer",
        "batched_reduce_size",
        "ccs_minimize_roundtrips",
        "default_operator",
        "df",
        "docvalue_fields",
        "expand_wildcards",
        "explain",
        "from_",
        "ignore_throttled",
        "ignore_unavailable",
        "lenient",
        "max_concurrent_shard_requests",
        "min_compatible_shard_node",
        "pre_filter_shard_size",
        "preference",
        "q",
        "request_cache",
        "rest_total_hits_as_int",
        "routing",
        "scroll",
        "search_type",
        "seq_no_primary_term",
        "size",
        "sort",
        "stats",
        "stored_fields",
        "suggest_field",
        "suggest_mode",
        "suggest_size",
        "suggest_text",
        "terminate_after",
        "timeout",
        "track_scores",
        "track_total_hits",
        "typed_keys",
        "version",
        request_mimetypes=["application/json"],
        response_mimetypes=["application/json"],
        body_params=[
            "_source",
            "aggregations",
            "aggs",
            "collapse",
            "docvalue_fields",
            "explain",
            "fields",
            "from_",
            "highlight",
            "indices_boost",
            "min_score",
            "pit",
            "post_filter",
            "profile",
            "query",
            "rescore",
            "runtime_mappings",
            "script_fields",
            "search_after",
            "seq_no_primary_term",
            "size",
            "slice",
            "sort",
            "stats",
            "stored_fields",
            "suggest",
            "terminate_after",
            "timeout",
            "track_scores",
            "track_total_hits",
            "version",
        ],
    )
    def search(self, index=None, doc_type=None, body=None, params=None, headers=None, **kwargs):
        result = super(FakeElasticsearchBucket, self).search(
            index=index, doc_type=doc_type, body=body, params=params, headers=headers
        )
        if 'scroll' in params and len(result['hits']['hits']) > int(body["size"]):
            self.scrolls[result.pop('_scroll_id')] = {
                'index': index,
                'doc_type': doc_type,
                'body': body,
                'params': params,
            }
        return result

    @query_params(
        "rest_total_hits_as_int",
        "scroll",
        "scroll_id",
        request_mimetypes=["application/json"],
        response_mimetypes=["application/json"],
        body_params=["scroll", "scroll_id"],
    )
    def scroll(self, body=None, scroll_id=None, params=None, headers=None):
        scroll_id = scroll_id or body.get("scroll_id")
        scroll = self.scrolls.pop(scroll_id, None)
        if scroll:
            result = self.search(
                index=scroll.get('index'),
                doc_type=scroll.get('doc_type'),
                body=scroll.get('body'),
                params=scroll.get('params'),
            )
            return result
        return {}

    def make_aggregation_buckets(self, aggregation, documents):
        if 'composite' in aggregation:
            return self.make_composite_aggregation_buckets(aggregation, documents)
        return self.make_normal_aggregation_buckets(aggregation, documents)

    def make_bucket(self, bucket_key, bucket, aggregation):
        out = {
            "key": bucket_key,
            "key_as_string": str(bucket_key),
            "doc_count": len(bucket),
        }
        if aggregation.get("aggs"):
            for sub_aggregation, defenition in aggregation.get("aggs").items():
                out[sub_aggregation] = {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": self.make_aggregation_buckets(defenition, bucket),
                }
        return out

    def make_normal_aggregation_buckets(self, aggregation, documents):
        buckets = defaultdict(list)
        bucket_documents = defaultdict(list)

        for document in documents:
            doc_src = document["_source"]
            key = jmespath.search(aggregation["terms"]["field"], doc_src)
            buckets[key].append(doc_src)
            bucket_documents[key].append(document)

        bucket_documents = sorted(((k, v) for k, v in bucket_documents.items()), key=lambda x: x[0])
        buckets = [self.make_bucket(bucket_key, bucket, aggregation) for bucket_key, bucket in bucket_documents]
        return buckets

    def make_composite_aggregation_buckets(self, aggregation, documents):
        def make_key(doc_source, agg_source):
            attr = list(agg_source.values())[0]["terms"]["field"]
            return doc_source[attr]

        def make_bucket(bucket_key, bucket):
            out = {
                "key": {k: v for k, v in zip(bucket_key_fields, bucket_key)},
                "doc_count": len(bucket),
            }

            for metric_key, metric_definition in aggregation.get("aggs", {}).items():
                metric_type_str = list(metric_definition)[0]
                metric_type = MetricType.get_metric_type(metric_type_str)
                attr = metric_definition[metric_type_str]["field"]
                data = [doc[attr] for doc in bucket]

                if metric_type == MetricType.CARDINALITY:
                    value = len(set(data))
                else:
                    raise NotImplementedError(f"Metric type '{metric_type}' not implemented")

                out[metric_key] = {"value": value}
            return out

        agg_sources = aggregation["composite"]["sources"]
        buckets = defaultdict(list)
        bucket_key_fields = [list(src)[0] for src in agg_sources]
        for document in documents:
            doc_src = document["_source"]
            key = tuple(make_key(doc_src, agg_src) for agg_src in aggregation["composite"]["sources"])
            buckets[key].append(doc_src)

        buckets = sorted(((k, v) for k, v in buckets.items()), key=lambda x: x[0])
        buckets = [make_bucket(bucket_key, bucket) for bucket_key, bucket in buckets]
        return buckets

    @query_params(
        "_source",
        "_source_excludes",
        "_source_includes",
        "pipeline",
        "refresh",
        "require_alias",
        "routing",
        "timeout",
        "wait_for_active_shards",
        request_mimetypes=["application/x-ndjson"],
        response_mimetypes=["application/json"],
    )
    def bulk(self, body, index=None, doc_type=None, params=None, headers=None):
        new_body = ""
        index_line = ""
        for raw_line in body.splitlines():
            if len(raw_line.strip()) > 0:
                line = json.loads(raw_line)
                if any(action in line for action in ['index', 'create', 'update', 'delete']):
                    action = next(iter(line.keys()))
                    index_line = raw_line
                    document_id = line[action].get('_id', get_random_id())
                    index = line[action].get('_index') or index
                    doc_type = line[action].get('_type', "_doc")  # _type is deprecated in 7.x

                else:
                    doc_as_upsert = line.get("doc_as_upsert")
                    if (
                        doc_as_upsert
                        and action == "update"
                        and not self.exists(index, id=document_id, doc_type=doc_type, params=params)
                    ):
                        index_line = index_line.replace("update", "create")
                        if "doc" in line:
                            raw_line = json.dumps(line["doc"])
                    new_body += "\n".join([index_line, raw_line])
                    new_body += "\n"
        return super(FakeElasticsearchBucket, self).bulk(new_body, index, doc_type, params=params, headers=headers)

    def _get_fake_query_condition(self, query_type_str, condition):
        return LocalFakeQueryCondition(QueryType.get_query_type(query_type_str), condition)


class LocalFakeQueryCondition(FakeQueryCondition):
    def evaluate(self, document):
        try:
            return super(LocalFakeQueryCondition, self).evaluate(document)
        except NotImplementedError:
            # 不存在的内容直接返回True
            return True
