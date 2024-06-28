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

from alarm_backends.core.cache.base import CacheManager
from constants.data_source import DataSourceLabel
from core.drf_resource import api

MAX_FIELD_SUPPORTED = 200


"""
结果表信息缓存
"""


class ResultTableCacheManager(CacheManager):
    """
    结果表缓存
    """

    # 缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".result_table_{}_{}"

    @classmethod
    def refresh_metadata(cls):
        from alarm_backends.core.i18n import i18n

        result_tables = api.metadata.list_result_table()

        pipeline = cls.cache.pipeline()
        for result_table in result_tables:
            i18n.set_biz(result_table["bk_biz_id"])
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
    def refresh_bkdata(cls):
        from alarm_backends.core.i18n import i18n

        business_list = api.cmdb.get_business()

        for biz in business_list:
            i18n.set_biz(biz.bk_biz_id)
            try:
                result_tables = api.bkdata.list_result_table(bk_biz_id=biz.bk_biz_id)
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
            except Exception as e:
                cls.logger.error("update bkdata result table failed for biz({}), {}".format(biz.bk_biz_id, e))

    @classmethod
    def refresh_bklog(cls):
        from alarm_backends.core.i18n import i18n

        business_list = api.cmdb.get_business(all=True)

        for biz in business_list:
            i18n.set_biz(biz.bk_biz_id)
            try:
                pipeline = cls.cache.pipeline()

                index_list = api.log_search.search_index_set(bk_biz_id=biz.bk_biz_id)
                for index in index_list:
                    try:
                        fields = api.log_search.search_index_fields(
                            bk_biz_id=biz.bk_biz_id, index_set_id=index["index_set_id"]
                        )
                    except Exception as e:
                        cls.logger.error(
                            "update bklog result table failed for biz({}), index_set({}), {}".format(
                                biz.bk_biz_id, index["index_set_id"], e
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

            except Exception as e:
                cls.logger.error("update bklog result table failed for biz({}), {}".format(biz.bk_biz_id, e))

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
                    "field_alias":"\u4e1a\u52a1ID",
                    "field_name":"bk_biz_id",
                    "is_dimension":true
                },
                {
                    "field_type":"int",
                    "field_alias":"\u4e91\u533a\u57dfID",
                    "field_name":"bk_cloud_id",
                    "is_dimension":true
                },
                {
                    "field_type":"timestamp",
                    "field_alias":"\u6570\u636e\u4e0a\u62a5\u65f6\u95f4",
                    "field_name":"time",
                    "is_dimension":false
                },
                {
                    "field_type":"int",
                    "field_alias":"Redis\u5206\u914d\u7684\u5185\u5b58\u91cf",
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
        cls.refresh_metadata()

        cls.refresh_bkdata()

        cls.refresh_bklog()


def main():
    ResultTableCacheManager.refresh()
