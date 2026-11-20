# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from typing import Any, Dict

import requests
from elasticsearch import exceptions as EsExceptions
from elasticsearch5 import exceptions as EsExceptions5
from elasticsearch6 import exceptions as EsExceptions6

from apps.log_esquery.exceptions import EsTimeoutException


class QueryClientTemplate(object):  # pylint: disable=invalid-name
    def __init__(self):
        self.host: str = ""
        self.port: int = -1
        self.username: str = ""
        self.password: str = ""
        self._active: bool = False

    def query(self, index: str, body: Dict[str, Any], scroll=None, track_total_hits=False):
        raise NotImplementedError()

    def mapping(self, index: str, add_settings_details: bool = False) -> Dict:
        raise NotImplementedError()

    def es_route(self, url: str, index=None):
        raise NotImplementedError()

    @classmethod
    def catch_timeout_raise(cls, e):
        if isinstance(
            e,
            (
                EsExceptions.ConnectionTimeout,
                EsExceptions5.ConnectionTimeout,
                EsExceptions6.ConnectionTimeout,
                requests.exceptions.Timeout,
            ),
        ):
            raise EsTimeoutException

    @staticmethod
    def add_analyzer_details(_mappings: Dict[str, Any], _settings: Dict[str, Any]):
        def _fill_properties_analyzer(
            properties_dict: Dict[str, Any], analyzers: Dict[str, Any], tokenizers: Dict[str, Any]
        ):
            for properties in properties_dict.values():
                if not isinstance(properties, dict):
                    continue
                analyzer_name = properties.get("analyzer")
                if not analyzer_name:
                    continue
                analyzer_details = analyzers.get(analyzer_name)
                if not analyzer_details:
                    continue
                properties["analyzer_details"] = analyzer_details
                if analyzer_details.get("tokenizer"):
                    properties["analyzer_details"]["tokenizer_details"] = tokenizers.get(analyzer_details["tokenizer"])

        for index_name, index_mapping in _mappings.items():
            if not isinstance(index_mapping, dict):
                continue
            index_settings = _settings.get(index_name, {}).get("settings", {}).get("index", {})
            analyzers = index_settings.get("analysis", {}).get("analyzer", {})
            tokenizers = index_settings.get("analysis", {}).get("tokenizer", {})
            mappings = index_mapping.get("mappings") or {}
            if not isinstance(mappings, dict):
                continue

            if isinstance(mappings.get("properties"), dict):
                _fill_properties_analyzer(mappings["properties"], analyzers, tokenizers)
                continue

            # 兼容 ES 5.x/6.x 的 typed mapping，同时跳过 ES 7+/8/9 仅含 dynamic_templates 等非字典节点
            for index_type in mappings.values():
                if isinstance(index_type, dict) and isinstance(index_type.get("properties"), dict):
                    _fill_properties_analyzer(index_type["properties"], analyzers, tokenizers)
        return _mappings
