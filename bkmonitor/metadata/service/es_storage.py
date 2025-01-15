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

import logging
from typing import Dict, List

from metadata import models

logger = logging.getLogger("metadata")


class ESIndex:
    def __init__(self):
        pass

    def query_es_index(self, table_id_list: List) -> Dict:
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

    def _query_current_index(self, es_obj: models.ESStorage) -> Dict:
        try:
            return es_obj.current_index_info()
        except Exception as e:
            logger.error("query current index error, %s", e)
            return {}

    def _query_all_index(self, es_obj: models.ESStorage) -> Dict:
        try:
            es_client = es_obj.get_client()
            return es_client.indices.get("{}*".format(es_obj.index_name))
        except Exception as e:
            logger.error("query all index error, %s", e)
            return {}

    def _refine_index_and_aliases(self, index_info: Dict) -> Dict:
        """获取索引和别名"""
        data = {}
        for index, detail in index_info.items():
            aliases = list(detail.get("aliases", {}).keys())
            data[index] = aliases
        return data

    def _refine_deleted_index(self, es_obj: models.ESStorage, index_info: Dict) -> List:
        """获取可以删除的index

        - 索引的别名已经过期
        - 超过保存时间的索引
        """
        # 可以删除的索引
        can_delete_index = set()
        # 组装参数，获取过期别名的索引
        index_aliases = {}
        for index in index_info:
            index_aliases[index] = {"aliases": index_info[index].get("aliases", {})}
        filter_result = es_obj.group_expired_alias(index_aliases, es_obj.retention)
        for index, aliases in filter_result.items():
            # 回溯的索引不经过正常删除的逻辑删除
            if index.startswith(es_obj.restore_index_prefix):
                continue
            if not aliases["not_expired_alias"]:
                can_delete_index.add(index)

        return list(can_delete_index)
