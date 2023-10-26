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


class EventGroupCacheManager(CacheManager):
    """
    用户自定义事件分组缓存
    """

    # 缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".event_group_{}_{}"

    @classmethod
    def get_connect_info(cls, data_source_type, result_table_id):
        """
        获取用户自定义事件分组配置信息
        :param data_source_type:  数据来源类型
        :param bk_event_group_id: 事件分组ID
        :return: dict
        {
            "event_info_list":[
                {
                    "dimension_list":[
                        {
                            "dimension_name":"bk_target"
                        },
                        {
                            "dimension_name":"field_name1"
                        }
                    ],
                    "custom_event_id":4,
                    "custom_event_name":"event_1"
                },
                {
                    "dimension_list":[
                        {
                            "dimension_name":"bk_target"
                        },
                        {
                            "dimension_name":"field_name2"
                        }
                    ],
                    "custom_event_id":3,
                    "custom_event_name":"event_2"
                }
            ],
            "bk_event_group_id":20,
            "event_group_name":"test custom event",
            "datasource_info":{
                "mq_config":{
                    "topic":"0bkmonitor_12001990",
                    "partition":1,
                    "domain_name":"kafka.service.consul",
                    "port":9092
                }
            }
        }
        """
        data = cls.cache.get(cls.CACHE_KEY_TEMPLATE.format(data_source_type, result_table_id))
        if data:
            return json.loads(data)

    @classmethod
    def refresh_metadata(cls):
        """
        {
            "bk_biz_id":2,
            "bk_data_id":1200199,
            "event_group_name":"test custom event",
            "creator":"admin",
            "datasource_info":{
                "mq_config":{
                    "topic":"0bkmonitor_12001990",
                    "partition":1,
                    "domain_name":"kafka.service.consul",
                    "port":9092
                }
            },
            "last_modify_time":"2019-11-23 12:12:38",
            "event_info_list":[
                {
                    "dimension_list":[
                        {
                            "dimension_name":"bk_target"
                        },
                        {
                            "dimension_name":"field_name1"
                        }
                    ],
                    "custom_event_id":4,
                    "custom_event_name":"event_1"
                },
                {
                    "dimension_list":[
                        {
                            "dimension_name":"bk_target"
                        },
                        {
                            "dimension_name":"field_name2"
                        }
                    ],
                    "custom_event_id":3,
                    "custom_event_name":"event_2"
                }
            ],
            "create_time":"2019-11-23 12:12:38",
            "last_modify_user":"blueking",
            "is_enable":true,
            "label":"applications",
            "bk_event_group_id":20
        }
        """
        event_group_list = api.metadata.query_event_group()

        pipeline = cls.cache.pipeline()
        for event_group in event_group_list:
            bk_event_group_id = event_group["event_group_id"]

            shipper_list = []
            try:
                event_group_info = api.metadata.get_event_group(
                    event_group_id=bk_event_group_id, with_result_table_info=True
                )
                shipper_list = event_group_info.get("shipper_list", [])
            except:  # noqa
                pass
            for cluster_config in shipper_list:
                if cluster_config["cluster_type"] != "elasticsearch":
                    continue
                datasource_info = {
                    "domain_name": cluster_config["cluster_config"]["domain_name"],
                    "port": cluster_config["cluster_config"]["port"],
                    "is_ssl_verify": cluster_config["cluster_config"]["is_ssl_verify"],
                    "auth_info": cluster_config["auth_info"],
                }
                data = {
                    "base_index": cluster_config["storage_config"]["base_index"],
                    "table_id": event_group["table_id"],
                    "bk_event_group_id": bk_event_group_id,
                    "event_group_name": event_group["event_group_name"],
                    "datasource_info": datasource_info,
                    "event_info_list": event_group.get("event_info_list", []),
                    "doc_type": "_doc",
                }

                pipeline.set(
                    cls.CACHE_KEY_TEMPLATE.format(DataSourceLabel.CUSTOM, event_group["table_id"]),
                    json.dumps(data),
                    cls.CACHE_TIMEOUT,
                )
        pipeline.execute()

    @classmethod
    def refresh(cls):
        cls.refresh_metadata()


def main():
    EventGroupCacheManager.refresh()
