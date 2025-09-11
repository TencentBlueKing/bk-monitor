"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc

from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id


class TranslationField:
    def __init__(self, name, value, display_name=None, display_value=None):
        self.name = name
        self.value = value
        self.display_name = name if display_name is None else display_name
        self.display_value = value if display_value is None else display_value

    def to_dict(self):
        return {
            "value": self.value,
            "display_name": self.display_name,
            "display_value": self.display_value,
        }

    def __repr__(self):
        return f"<TranslationField {self.name}({self.display_name}): {self.value}({self.display_value})>"


class BaseTranslator:
    """
    字段翻译类
    """

    def __init__(self, item, strategy):
        self.item = item
        self.strategy = strategy
        self.bk_tenant_id = bk_biz_id_to_bk_tenant_id(strategy["bk_biz_id"])

        self.data_source_label = item["query_configs"][0]["data_source_label"]
        self.data_type_label = item["query_configs"][0]["data_type_label"]
        self.result_table_id = item["query_configs"][0].get("result_table_id", "")

    @abc.abstractmethod
    def is_enabled(self):
        """
        判断是否需要启用此翻译
        """
        raise NotImplementedError

    @abc.abstractmethod
    def translate(self, data):
        """
        字段翻译逻辑，具体实现可由子类重写
        :param dict[str,TranslationField] data: 翻译数据
        :rtype dict[str,TranslationField]
        """
        raise NotImplementedError

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}: {self.data_source_label} - {self.data_type_label} - {self.result_table_id}>"
        )
