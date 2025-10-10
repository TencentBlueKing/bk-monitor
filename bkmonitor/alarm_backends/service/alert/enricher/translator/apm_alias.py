"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
APM 维度别名翻译器

场景：APM 统一查询(custom)未在 metadata 注册物理结果表，结果表别名翻译器无法生效。
本翻译器基于 APM 常量与配置为维度键名填充 display_name，仅在尚未被其他翻译器翻译时生效。
"""

from django.utils.translation import gettext as _

from alarm_backends.service.alert.enricher.translator.base import BaseTranslator
from constants.apm import RPCMetricTag, CommonMetricTag, DEFAULT_DATA_LABEL
from constants.data_source import DataSourceLabel


def _safe_get(obj, key, default=None):
    """同时兼容 dict/对象属性的读取。"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class ApmAliasTranslator(BaseTranslator):
    """APM 维度别名翻译器。

    触发条件：
    - data_source_label == custom 且（result_table_id 以 "APM." 开头 或 data_label == "APM"）
    - 可选：strategy 场景为 APM

    生效规则：
    - 仅在 field.display_name 仍为原始 name 时覆盖 display_name；不修改 value/display_value。
    """

    def is_enabled(self) -> bool:
        query_configs = _safe_get(self.item, "query_configs", []) or []
        if not query_configs:
            return False

        qc = query_configs[0]
        data_source_label = _safe_get(qc, "data_source_label")
        result_table_id = _safe_get(qc, "result_table_id", "") or ""
        data_label = _safe_get(qc, "data_label", "") or ""
        scenario = _safe_get(self.strategy, "scenario", "") or ""

        if data_source_label != DataSourceLabel.CUSTOM:
            return False

        if (
            result_table_id.startswith(f"{DEFAULT_DATA_LABEL}.")
            or data_label == DEFAULT_DATA_LABEL
            or scenario == DEFAULT_DATA_LABEL
        ):
            return True

        return False

    @staticmethod
    def _process_tag_class(tag_class, alias: dict[str, str]):
        """处理单个标签类，提取别名映射。"""
        for item in getattr(tag_class, "tags")():
            key = item.get("value")
            text = item.get("text")
            if key and text:
                alias.setdefault(key, str(_(text)))

    def _build_alias_from_constants(self) -> dict[str, str]:
        """从 constants.apm 聚合默认文案。失败时返回空，不抛异常。"""
        alias: dict[str, str] = {}

        # 处理各种标签类
        self._process_tag_class(CommonMetricTag, alias)
        self._process_tag_class(RPCMetricTag, alias)

        return alias

    def translate(self, data):
        alias_map: dict[str, str] = self._build_alias_from_constants()

        if not alias_map:
            return data

        for name, field in list(data.items()):
            # 仅在未被翻译过的情况下覆盖
            if field.display_name != field.name:
                continue
            alias = alias_map.get(name)
            if alias:
                field.display_name = str(_(alias))

        return data
