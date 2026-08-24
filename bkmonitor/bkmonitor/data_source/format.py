"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import deque


def flatten_dict_data(data_dict: dict) -> dict:
    """将嵌套字典结构扁平化处理"""

    def update_result_dict(result_dict: dict, key: str, value):
        if key not in result_dict:
            result_dict[key] = value
        else:
            if isinstance(result_dict[key], list):
                result_dict[key].append(value)
            else:
                result_dict[key] = [result_dict[key], value]

    result_dict = {}
    q = deque()
    q.append(("", data_dict))
    while q:
        name_prefix, data = q.popleft()
        for field_name, field_value in data.items():
            field_key = f"{name_prefix}.{field_name}" if name_prefix else field_name
            if not field_value:
                update_result_dict(result_dict, field_key, field_value)
                continue

            if isinstance(field_value, dict):
                q.append((field_key, field_value))
            elif isinstance(field_value, list):
                for value in field_value:
                    if isinstance(value, dict):
                        q.append((field_key, value))
                    else:
                        update_result_dict(result_dict, field_key, value)
            else:
                update_result_dict(result_dict, field_key, field_value)
    return result_dict
