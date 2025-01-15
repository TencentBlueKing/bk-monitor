# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
from typing import Any

# 参数最大字符限制
MAX_PARAMS_SIZE = 10000


def jsonify(data: Any) -> str:
    """尝试将数据转为 JSON 字符串"""
    try:
        return json.dumps(data)
    except (TypeError, ValueError):
        if isinstance(data, dict):
            return json.dumps({k: v for k, v in data.items() if not v or isinstance(v, (str, int, float, bool))})
        if isinstance(data, bytes):
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                return str(data)
        return str(data)
