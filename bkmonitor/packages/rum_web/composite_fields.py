"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from bkmonitor.data_source.format import flatten_dict_data
from semconv.rum.field import CompositeFieldConfig


def format_list_record(record: dict[str, Any], composites: dict[str, CompositeFieldConfig]) -> dict[str, Any]:
    """先展平成员值，再组装复合单元格，避免 sections 被通用展平逻辑拆散。

    成员保留原始值及 field_name，单位格式化和交互能力继续复用 view_config。
    """
    result: dict[str, Any] = flatten_dict_data(record)
    for field_name, config in composites.items():
        sections: list[dict[str, Any]] = []
        for section in config["sections"]:
            populated: dict[str, Any] = dict(section)
            for group in ("items", "badges"):
                if (items := section.get(group)) is not None:
                    populated[group] = [{**item, "value": result.get(item["field_name"])} for item in items]
            sections.append(populated)
        result[field_name] = {"sections": sections}
    return result
