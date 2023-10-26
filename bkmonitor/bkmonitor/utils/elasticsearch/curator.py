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

from curator import utils, IndexList


class IndexList(IndexList):
    """
    扩展原有IndexList功能，使其支持索引前置过滤
    """

    def __init__(self, client, index_names: list = None):
        """
        :param client: ES client 对象
        :param index_names: 需要搜索的索引名称列表，支持通配符
        """
        self.index_names = index_names
        self.loggit = logging.getLogger("metadata")
        #: An Elasticsearch Client object
        #: Also accessible as an instance variable.
        self.client = client
        #: Instance variable.
        #: Information extracted from indices, such as segment count, age, etc.
        #: Populated at instance creation time, and by other private helper
        #: methods, as needed. **Type:** ``dict()``
        self.index_info = {}
        #: Instance variable.
        #: The running list of indices which will be used by an Action class.
        #: Populated at instance creation time. **Type:** ``list()``
        self.indices = []
        #: Instance variable.
        #: All indices in the cluster at instance creation time.
        #: **Type:** ``list()``
        self.all_indices = []
        self.__get_indices()

    def __get_indices(self):
        """
        Pull all indices into `all_indices`, then populate `indices` and
        `index_info`
        """
        if not self.index_names:
            # 如果不传索引名称，则不做任何查询
            return

        index_lists = utils.chunk_index_list(self.index_names)

        for index in index_lists:
            self.loggit.debug("Getting indices: {}".format(index))
            self.all_indices.extend(
                list(
                    self.client.indices.get_settings(
                        index=utils.to_csv(index), params={"expand_wildcards": "open,closed"}
                    )
                )
            )
        self.indices = self.all_indices[:]
        if self.indices:
            for index in self.indices:
                self.__build_index_info(index)
            self._get_metadata()
            self._get_index_stats()
