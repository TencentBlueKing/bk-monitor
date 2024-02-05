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

from abc import ABC

from django.conf import settings

from bkmonitor.dataflow.node.base import Node


class StorageNode(Node, ABC):
    def __init__(self, source_rt_id, storage_expires, *args, **kwargs):
        super(StorageNode, self).__init__(*args, **kwargs)
        self.source_rt_id = source_rt_id
        self.bk_biz_id, _, self.process_rt_id = source_rt_id.partition("_")
        self.bk_biz_id = int(self.bk_biz_id)

        if storage_expires < 0 or storage_expires > settings.BK_DATA_DATA_EXPIRES_DAYS:
            self.storage_expires = settings.BK_DATA_DATA_EXPIRES_DAYS
        else:
            self.storage_expires = storage_expires

    def __eq__(self, other):
        if isinstance(other, dict):
            config = self.config
            if (
                config.get("from_result_table_ids") == other.get("from_result_table_ids")
                and config.get("table_name") == other.get("table_name")
                and config.get("bk_biz_id") == other.get("bk_biz_id")
                and config.get("cluster") == other.get("cluster")
            ):
                return True
        elif isinstance(other, self.__class__):
            return self == other.config
        return False

    @property
    def name(self):
        return "{}({})".format(self.get_node_type(), self.source_rt_id)

    @property
    def output_table_name(self):
        return self.source_rt_id


class TSpiderStorageNode(StorageNode):
    """
    tspider存储节点
    """

    NODE_TYPE = "tspider_storage"

    @property
    def config(self):
        return {
            "from_result_table_ids": [self.source_rt_id],
            "bk_biz_id": self.bk_biz_id,
            "result_table_id": self.source_rt_id,
            "name": self.name,
            "expires": self.storage_expires,
            "cluster": settings.BK_DATA_MYSQL_STORAGE_CLUSTER_NAME,
        }

    def get_node_type(self):
        return settings.BK_DATA_MYSQL_STORAGE_CLUSTER_TYPE


class DruidStorageNode(StorageNode):
    """
    druid存储节点
    """

    NODE_TYPE = "druid_storage"

    @property
    def config(self):
        return {
            "from_result_table_ids": [self.source_rt_id],
            "bk_biz_id": self.bk_biz_id,
            "result_table_id": self.source_rt_id,
            "name": self.name,
            "expires": self.storage_expires,
            "cluster": settings.BK_DATA_DRUID_STORAGE_CLUSTER_NAME,
        }


class HDFSStorageNode(StorageNode):
    """
    HDFS存储节点
    """

    NODE_TYPE = "hdfs_storage"

    def __init__(self, source_rt_id, storage_expires, *args, **kwargs):
        super(HDFSStorageNode, self).__init__(source_rt_id, storage_expires, *args, **kwargs)
        self.storage_expires = storage_expires

    @property
    def config(self):
        return {
            "from_result_table_ids": [self.source_rt_id],
            "bk_biz_id": self.bk_biz_id,
            "result_table_id": self.source_rt_id,
            "name": self.name,
            "expires": self.storage_expires,
            "cluster": settings.BK_DATA_HDFS_STORAGE_CLUSTER_NAME,
        }


class DorisStorageNode(StorageNode):
    """
    Doris存储节点
    """

    NODE_TYPE = "doris"

    def __init__(self, cluster, *args, **kwargs):
        super(DorisStorageNode, self).__init__(*args, **kwargs)
        self.cluster = cluster

    @property
    def fields(self):
        raise NotImplementedError

    @property
    def config(self):
        return {
            "bk_biz_id": self.bk_biz_id,
            "result_table_id": self.source_rt_id,
            "name": self.name,
            "cluster": self.cluster,
            "custom_param_config": {
                "data_model": "duplicate",
                "expires_dup": f"{self.storage_expires}d",
                "expires_uniq": "-1",
                "fields": self.fields,
            },
            "storage_field_config": {},
            "udc_name": "doris",
            "from_result_table_ids": [self.source_rt_id],
        }


class ElasticsearchStorageNode(StorageNode):
    """
    ES存储节点
    """

    NODE_TYPE = "elastic_storage"

    def __init__(
        self,
        cluster,
        storage_keys=None,
        analyzed_fields=None,
        doc_values_fields=None,
        json_fields=None,
        date_fields=None,
        has_replica=False,
        has_unique_key=False,
        physical_table_name=False,
        *args,
        **kwargs,
    ):
        super(ElasticsearchStorageNode, self).__init__(*args, **kwargs)
        self.has_replica = has_replica
        self.storage_keys = storage_keys or []
        self.analyzed_fields = analyzed_fields or []
        self.doc_values_fields = doc_values_fields or []
        self.json_fields = json_fields or []
        self.date_fields = date_fields or []
        self.cluster = cluster
        self.has_unique_key = has_unique_key
        self.physical_table_name = physical_table_name

    @property
    def config(self):
        params = {
            "bk_biz_id": self.bk_biz_id,
            "result_table_id": self.source_rt_id,
            "name": self.name,
            "cluster": self.cluster,
            "date_fields": self.date_fields,
            "expires": self.storage_expires,
            "has_replica": self.has_replica,
            "has_unique_key": self.has_unique_key,
            "storage_keys": self.storage_keys,
            "analyzed_fields": self.analyzed_fields,
            "doc_values_fields": self.doc_values_fields,
            "json_fields": self.json_fields,
            "from_result_table_ids": [self.source_rt_id],
        }
        if self.physical_table_name:
            # 如果开启了自托管 需要额外处理表名
            params["physical_table_name"] = f"write_{{yyyyMMdd}}_{self.physical_table_name}"

        return params


def create_tspider_or_druid_node(source_rt_id, storage_expires, parent):
    is_system_rt = str(source_rt_id).startswith(f"{settings.BK_DATA_BK_BIZ_ID}_{settings.BK_DATA_RT_ID_PREFIX}_system_")
    if settings.BK_DATA_DRUID_STORAGE_CLUSTER_NAME and is_system_rt:
        return DruidStorageNode(
            source_rt_id=source_rt_id,
            storage_expires=storage_expires,
            parent=parent,
        )
    else:
        return TSpiderStorageNode(
            source_rt_id=source_rt_id,
            storage_expires=storage_expires,
            parent=parent,
        )
