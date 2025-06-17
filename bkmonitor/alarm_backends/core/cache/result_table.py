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

from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from bkmonitor.utils.thread_backend import ThreadPool
from constants.data_source import DataSourceLabel
from core.drf_resource import api
from core.errors.api import BKAPIError

MAX_FIELD_SUPPORTED = 200


class ResultTableCacheManager(CacheManager):
    """
    结果表缓存
    """

    # 缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".result_table_{}_{}"

    # 线程池大小
    THREAD_POOL_SIZE = 9

    # 业务ID列表分片大小
    BK_BIZ_ID_CHUNK_SIZE = 10

    @classmethod
    def refresh_metadata(cls, bk_biz_ids: list[int]):
        """
        刷新元数据结果表缓存

        Args:
            bk_biz_ids: 业务ID列表
        """
        for bk_biz_id in bk_biz_ids:
            # 查询元数据结果表
            try:
                result_tables = api.metadata.list_result_table(bk_biz_id=bk_biz_id)
            except BKAPIError as e:
                cls.logger.error(
                    f"ResultTableCacheManager: update metadata result table failed for biz({bk_biz_id}), {e}"
                )
                continue

            # 如果业务下没有结果表，则跳过
            if not result_tables:
                continue

            pipeline = cls.cache.pipeline()
            for result_table in result_tables:
                table_id = result_table["table_id"]
                data = {
                    "table_id": table_id,
                    "table_name": result_table["table_name_zh"],
                    "fields": [
                        {
                            "field_name": field["field_name"],
                            "field_type": field["type"],
                            "field_alias": field["description"],
                            "is_dimension": field["tag"] in ["dimension", "group"],
                        }
                        for field in result_table["field_list"][:MAX_FIELD_SUPPORTED]
                    ],
                }

                pipeline.set(
                    cls.CACHE_KEY_TEMPLATE.format(
                        result_table.get("source_label", DataSourceLabel.BK_MONITOR_COLLECTOR), data["table_id"]
                    ),
                    json.dumps(data),
                    cls.CACHE_TIMEOUT,
                )
            pipeline.execute()

    @classmethod
    def refresh_bkdata(cls, bk_biz_ids: list[int]):
        """
        刷新数据平台结果表缓存

        Args:
            bk_biz_ids: 业务ID列表
        """
        for bk_biz_id in bk_biz_ids:
            # 数据平台仅支持cmdb业务
            if bk_biz_id <= 0:
                continue

            # 查询数据平台结果表
            try:
                result_tables = api.bkdata.list_result_table(bk_biz_id=bk_biz_id)
            except BKAPIError as e:
                cls.logger.error(
                    f"ResultTableCacheManager: update bkdata result table failed for biz({bk_biz_id}), {e}"
                )
                continue

            # 如果业务下没有结果表，则跳过
            if not result_tables:
                continue

            pipeline = cls.cache.pipeline()
            for result_table in result_tables:
                data = {
                    "table_id": result_table["result_table_id"],
                    "table_name": result_table["result_table_name_alias"],
                    "fields": [
                        {
                            "field_name": field["field_name"],
                            "field_type": field["field_type"],
                            "field_alias": field["field_alias"],
                            "is_dimension": field["is_dimension"],
                        }
                        for field in result_table["fields"][:MAX_FIELD_SUPPORTED]
                    ],
                }

                pipeline.set(
                    cls.CACHE_KEY_TEMPLATE.format(DataSourceLabel.BK_DATA, data["table_id"]),
                    json.dumps(data),
                    cls.CACHE_TIMEOUT,
                )
            pipeline.execute()

    @classmethod
    def refresh_bklog(cls, bk_biz_ids: list[int]):
        """
        刷新日志平台结果表缓存

        Args:
            bk_biz_ids: 业务ID列表
        """
        for bk_biz_id in bk_biz_ids:
            # 查询日志平台索引集
            try:
                index_list = api.log_search.search_index_set(bk_biz_id=bk_biz_id)
            except BKAPIError as e:
                cls.logger.error(f"ResultTableCacheManager: update bklog result table failed for biz({bk_biz_id}), {e}")
                continue

            # 如果业务下没有索引集，则跳过
            if not index_list:
                continue

            pipeline = cls.cache.pipeline()
            for index in index_list:
                try:
                    fields = api.log_search.search_index_fields(bk_biz_id=bk_biz_id, index_set_id=index["index_set_id"])
                except Exception as e:
                    cls.logger.error(
                        "update bklog result table failed for biz({}), index_set({}), {}".format(
                            bk_biz_id, index["index_set_id"], e
                        )
                    )
                    continue

                data = {
                    "table_id": index["index_set_id"],
                    "table_name": index["index_set_name"],
                    "fields": [
                        {
                            "field_name": field["field_name"],
                            "field_type": field["field_type"],
                            "field_alias": field["description"],
                            "is_dimension": field["tag"] == "dimension",
                        }
                        for field in fields["fields"][:MAX_FIELD_SUPPORTED]
                    ],
                }

                pipeline.set(
                    cls.CACHE_KEY_TEMPLATE.format(DataSourceLabel.BK_LOG_SEARCH, data["table_id"]),
                    json.dumps(data),
                    cls.CACHE_TIMEOUT,
                )
            pipeline.execute()

    @classmethod
    def get_result_table_by_id(cls, source_type, table_id):
        """
        获取结果表
        :param source_type: 数据源
        :param table_id: 表名
        :return: dict
        {
            "table_id":"redis.mem",
            "table_name":"redis.mem",
            "fields":[
                {
                    "field_type":"int",
                    "field_alias":"业务ID",
                    "field_name":"bk_biz_id",
                    "is_dimension":true
                },
                {
                    "field_type":"int",
                    "field_alias":"云区域ID",
                    "field_name":"bk_cloud_id",
                    "is_dimension":true
                },
                {
                    "field_type":"timestamp",
                    "field_alias":"数据上报时间",
                    "field_name":"time",
                    "is_dimension":false
                },
                {
                    "field_type":"int",
                    "field_alias":"Redis分配的内存量",
                    "field_name":"used",
                    "is_dimension":false
                }
            ]
        }
        """
        data = cls.cache.get(cls.CACHE_KEY_TEMPLATE.format(source_type, table_id))
        if data:
            return json.loads(data)

    @classmethod
    def refresh(cls):
        bk_biz_ids: list[int] = StrategyCacheManager.get_all_bk_biz_ids()

        pool = ThreadPool(cls.THREAD_POOL_SIZE)
        for bk_biz_id_list in [
            bk_biz_ids[i : i + cls.BK_BIZ_ID_CHUNK_SIZE] for i in range(0, len(bk_biz_ids), cls.BK_BIZ_ID_CHUNK_SIZE)
        ]:
            pool.apply_async(cls.refresh_metadata, args=(bk_biz_id_list,))
            pool.apply_async(cls.refresh_bkdata, args=(bk_biz_id_list,))
            pool.apply_async(cls.refresh_bklog, args=(bk_biz_id_list,))
        # 刷新系统级别的元数据结果表
        pool.apply_async(cls.refresh_metadata, args=([0],))
        pool.close()
        pool.join()


def main():
    ResultTableCacheManager.refresh()
