import logging
from typing import Any

from bk_monitor_base.metadata import models

logger = logging.getLogger("metadata")


class ESIndex:
    def __init__(self):
        pass

    def query_es_index(self, table_id_list: list[str]) -> dict[str, Any]:
        """查询结果表对应的es索引"""
        es_objs = models.ESStorage.objects.filter(table_id__in=table_id_list)
        data = {}
        for obj in es_objs:
            item = {"current_index": self._query_current_index(obj)}
            all_index_info = self._query_all_index(obj)
            item["all_index_and_alias"] = self._refine_index_and_aliases(all_index_info)
            item["can_delete_index"] = self._refine_deleted_index(obj, all_index_info)
            data[obj.table_id] = item
        return data

    def _query_current_index(self, es_obj: models.ESStorage) -> dict[str, Any]:
        try:
            return es_obj.current_index_info()
        except Exception as e:
            logger.error("query current index error, %s", e)
            return {}

    def _query_all_index(self, es_obj: models.ESStorage) -> dict[str, Any]:
        try:
            es_client = es_obj.get_client()
            return es_client.indices.get(f"{es_obj.index_name}*")
        except Exception as e:
            logger.error("query all index error, %s", e)
            return {}

    def _refine_index_and_aliases(self, index_info: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """获取索引和别名"""
        data = {}
        for index, detail in index_info.items():
            aliases = list(detail.get("aliases", {}).keys())
            data[index] = aliases
        return data

    def _refine_deleted_index(self, es_obj: models.ESStorage, index_info: dict[str, Any]) -> list[str]:
        """获取可以删除的index

        - 索引的别名已经过期
        - 超过保存时间的索引
        """
        # 可以删除的索引
        can_delete_index: set[str] = set()
        # 组装参数，获取过期别名的索引
        index_aliases = {}
        for index in index_info:
            index_aliases[index] = {"aliases": index_info[index].get("aliases", {})}
        filter_result: dict[str, Any] = es_obj.group_expired_alias(index_aliases, es_obj.retention)
        for index, aliases in filter_result.items():
            # 回溯的索引不经过正常删除的逻辑删除
            if index.startswith(es_obj.restore_index_prefix):
                continue
            if not aliases["not_expired_alias"]:
                can_delete_index.add(index)

        return list(can_delete_index)
