from abc import ABC

from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.dataflow.node.base import Node


class StorageNode(Node, ABC):
    def __init__(self, source_rt_id, storage_expires, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_rt_id = source_rt_id
        self.bk_biz_id, _, self.process_rt_id = source_rt_id.partition("_")
        self.bk_biz_id = int(self.bk_biz_id)

        if storage_expires < 0 or storage_expires > settings.metadata.bk_data_data_expires_days:
            self.storage_expires = settings.metadata.bk_data_data_expires_days
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
        return f"{self.get_node_type()}({self.source_rt_id})"

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
            "cluster": settings.metadata.bk_data_mysql_storage_cluster_name,
        }

    def get_node_type(self):
        return settings.metadata.bk_data_mysql_storage_cluster_type


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
            "cluster": settings.metadata.bk_data_druid_storage_cluster_name,
        }


class HDFSStorageNode(StorageNode):
    """
    HDFS存储节点
    """

    NODE_TYPE = "hdfs_storage"

    def __init__(self, source_rt_id, storage_expires, *args, **kwargs):
        super().__init__(source_rt_id, storage_expires, *args, **kwargs)
        self.storage_expires = storage_expires

    @property
    def config(self):
        return {
            "from_result_table_ids": [self.source_rt_id],
            "bk_biz_id": self.bk_biz_id,
            "result_table_id": self.source_rt_id,
            "name": self.name,
            "expires": self.storage_expires,
            "cluster": settings.metadata.bk_data_hdfs_storage_cluster_name,
        }


class DorisStorageNode(StorageNode):
    """
    Doris存储节点
    """

    NODE_TYPE = "doris"

    def __init__(self, cluster, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        super().__init__(*args, **kwargs)
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
    is_system_rt = str(source_rt_id).startswith(
        f"{settings.metadata.bk_data_bk_biz_id}_{settings.metadata.bk_data_rt_id_prefix}_system_"
    )
    if settings.metadata.bk_data_druid_storage_cluster_name and is_system_rt:
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
