"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import itertools
import time
from collections import defaultdict


from apm_web.constants import DataStatus, ServiceRelationLogTypeChoices
from apm_web.handlers.host_handler import HostHandler
from apm_web.models import LogServiceRelation
from apm_web.topo.handle.relation.define import (
    SourceDatasource,
    SourceK8sPod,
    SourceService,
    SourceSystem,
)
from apm_web.topo.handle.relation.query import RelationQ
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.cache import CacheType, using_cache
from constants.apm import FIVE_MIN_SECONDS
from core.drf_resource import api


@using_cache(CacheType.APM(FIVE_MIN_SECONDS))
def get_biz_index_sets_with_cache(bk_biz_id):
    return api.log_search.search_index_set(bk_biz_id=bk_biz_id)


class ServiceLogHandler:
    """
    服务 - 日志工具类
    服务日志的来源：
    1. 应用自定义上报
    2. span 中主机关联采集项
    3. 服务关联日志
    """

    # ES 查询最大的服务数量
    SERVICE_MAX_SIZE = 1000
    # 通过 unifyquery 接口关联日志索引集的最大数量
    LOG_RELATION_BY_UNIFY_QUERY = 10
    # log 默认查询语句最大 value 数量
    LOG_DEFAULT_QUERY_CONDITION_MAX_SIZE = 20

    ONE_HOUR_SECONDS = 3600

    @classmethod
    def get_log_count_mapping(cls, bk_biz_id, app_name, start_time, end_time):
        """获取所有服务的关联日志的数据量"""

        # Step1: 找到此应用所有服务关联的日志
        service_mapping = defaultdict(dict)
        relations = LogServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name)
        for i in relations:
            if i.log_type == ServiceRelationLogTypeChoices.BK_LOG:
                service_mapping[i.service_name][i.related_bk_biz_id] = {
                    int(val) for val in (i.value_list + [i.value]) if val
                }

        # Step2: 查询业务的所有索引集 (避免每个 relation 都单独查询)
        pool = ThreadPool()
        futures = []
        for i in service_mapping.values():
            for related_biz_id in i.keys():
                futures.append(pool.apply_async(get_biz_index_sets_with_cache, kwds={"bk_biz_id": related_biz_id}))
        index_set = list(itertools.chain(*[i.get() for i in futures]))

        # Step3: 根据 index_set_id 进行匹配
        res = {}
        for service_name, info in service_mapping.items():
            info_index_set_ids = {item for value_set in info.values() for item in value_set}
            index_info = next((i for i in index_set if i.get("index_set_id") in info_index_set_ids), None)
            if index_info:
                # tag_id == 4 为无数据 (bk_log 固定值)
                if all(i.get("tag_id") != 4 for i in index_info.get("tags", [])):
                    res[service_name] = DataStatus.NORMAL

        # Step4: 对没有数据的服务进行自定义上报查询
        log_datasource = cls.get_log_datasource(bk_biz_id, app_name)
        if log_datasource:
            table_id = log_datasource["result_table_id"].replace("-", "_").replace(".", "_")
            futures = []
            service_name_field_list = ["resource.service.name", "resource.server"]
            for label in service_name_field_list:
                futures.append(
                    pool.apply_async(cls.get_label_values_in_table, args=(table_id, label, start_time, end_time))
                )
            has_data_service_list = list(itertools.chain(*[f.get() for f in futures]))
            res.update({s: DataStatus.NORMAL for s in has_data_service_list})

        return res

    @classmethod
    def get_label_values_in_table(cls, table_id, label, start_time, end_time) -> list:
        response = api.log_search.es_query_dsl(
            indices=f"{table_id}*",
            body={
                "size": 0,
                "query": {
                    "range": {
                        "time": {
                            "format": "epoch_second",
                            "gte": start_time,
                            "lte": end_time,
                        }
                    }
                },
                "aggs": {
                    "service_names": {
                        "terms": {
                            "field": label,
                        }
                    }
                },
            },
        )

        ret = []
        if response:
            for svr in response.get("aggregations", {}).get("service_names", {}).get("buckets", []):
                ret.append(svr["key"])
        return ret

    @classmethod
    def get_and_check_datasource_index_set_id(cls, bk_biz_id, app_name, full_indexes=None):
        """获取并校验 LogDatasource 的 IndexSetId"""

        ds = cls.get_log_datasource(bk_biz_id, app_name)
        if not ds:
            return None
        index_set_id = ds["index_set_id"]
        if not full_indexes:
            full_indexes = get_biz_index_sets_with_cache(bk_biz_id=bk_biz_id)

        index_set_info = next(
            (i for i in full_indexes if str(i.get("index_set_id", "")) == str(index_set_id)),
            None,
        )
        if index_set_info:
            return index_set_id

        # 如果不在接口返回的索引集中 说明此自定义上报在日志平台中已经停止
        return None

    @classmethod
    def get_log_datasource(cls, bk_biz_id, app_name):
        application_info = api.apm_api.detail_application(bk_biz_id=bk_biz_id, app_name=app_name)
        if not application_info.get("log_config"):
            return None
        return application_info["log_config"]

    @classmethod
    def list_host_indexes_by_span(cls, bk_biz_id, app_name, span_id, span_detail=None):
        """从 span 中找主机关联的采集项"""
        span_hosts = HostHandler.find_host_in_span(bk_biz_id, app_name, span_id, span_detail)

        if span_hosts:
            from monitor_web.scene_view.resources import HostIndexQueryMixin

            pool = ThreadPool()
            indies = pool.map_ignore_exception(
                HostIndexQueryMixin.query_indexes,
                [({"bk_biz_id": bk_biz_id, "bk_host_id": i["bk_host_id"]},) for i in span_hosts],
            )

            res = []
            for index, i in enumerate(indies):
                if not i:
                    continue
                for j in i:
                    res.append(
                        {
                            **j,
                            "addition": [
                                {
                                    "field": "*",
                                    "operator": "contains match phrase",
                                    "value": [span_hosts[index]["bk_host_innerip"]],
                                }
                            ],
                        }
                    )
            return res

        return []

    @classmethod
    def get_log_relations(cls, bk_biz_id: int, app_name: str, service_names: list[str]) -> list[LogServiceRelation]:
        """获取服务关联的日志"""
        return list(
            LogServiceRelation.objects.filter(
                bk_biz_id=bk_biz_id,
                app_name=app_name,
                log_type=ServiceRelationLogTypeChoices.BK_LOG,
                service_name__in=service_names,
            )
        )

    @classmethod
    def list_indexes_by_relation(cls, bk_biz_id, app_name, service_name, start_time=None, end_time=None):
        """
        通过关联查询获取服务的 dataId 关联并拼接默认查询
        """
        if not start_time or not end_time:
            end_time = int(time.time())
            start_time = end_time - cls.ONE_HOUR_SECONDS

        datasource_infos = defaultdict(list)
        data_ids = set()
        paths = [(SourceK8sPod, (SourceDatasource, SourceK8sPod)), (SourceSystem, (SourceDatasource, SourceSystem))]
        relation_qs = []
        for path_item in paths:
            relation_qs += RelationQ.generate_q(
                bk_biz_id=bk_biz_id,
                source_info=SourceService(
                    apm_application_name=app_name,
                    apm_service_name=service_name,
                ),
                target_type=SourceDatasource,
                start_time=start_time,
                end_time=end_time,
                path_resource=[path_item[0]],
            )
        relations = RelationQ.query(relation_qs, fill_with_empty=True)
        for index, r in enumerate(relations):
            if not r:
                continue
            for n in r.nodes:
                source_info = n.source_info.to_source_info()
                bk_data_id = source_info.get("bk_data_id")
                if bk_data_id and bk_data_id not in data_ids and len(data_ids) <= cls.LOG_RELATION_BY_UNIFY_QUERY:
                    datasource_infos[paths[index][-1]].append(SourceDatasource(bk_data_id=bk_data_id))
                    data_ids.add(bk_data_id)

        if not datasource_infos:
            return []

        res = []
        table_id_list = cls.list_tables_by_data_ids(list(data_ids))
        full_indexes = get_biz_index_sets_with_cache(bk_biz_id=bk_biz_id)  # 这里也会返回业务下关联项目的索引集
        for index in full_indexes:
            indices = index.get("indices") or []
            if indices and len(indices) == 1 and indices[0].get("result_table_id") in table_id_list:
                res.append({"index_set_id": index["index_set_id"], "addition": []})
        return res

    @classmethod
    def list_tables_by_data_ids(cls, data_ids: list[int | str]) -> list[str]:
        """通过 data_id 列表获取对应的 result_table_id 列表"""

        # 这里直接从 metadata 查询，是为了解决跨业务关联的场景
        # data_id -> table_id -> index_set_id
        # 这里待 metadata 有相关接口后，需要改为走 api 形式查询，去掉模块之间的依赖
        from metadata import models

        return list(
            models.DataSourceResultTable.objects.filter(bk_data_id__in=data_ids).values_list("table_id", flat=True)
        )
