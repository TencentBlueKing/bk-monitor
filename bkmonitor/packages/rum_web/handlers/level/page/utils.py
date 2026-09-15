"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


def get_safe_number(value: str | int | float | None, default: int | float = 0) -> int | float:
    """安全地将任意值转换为数字（int 或 float）。

    支持 str / int / float / None；转换失败时返回 default 而非 nan，
    避免 nan 参与后续比较/计算产生隐蔽错误。
    """
    if value is None:
        return default
    try:
        numeric_value = float(value)
        return int(numeric_value) if numeric_value.is_integer() else numeric_value
    except (TypeError, ValueError):
        return default
