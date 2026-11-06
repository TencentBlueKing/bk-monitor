"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# Issue 系 ID：10 位秒级时间戳 + 8 位随机后缀。
# Issue、Issue 活动、源码分析执行记录共用同一形态，生成与解析集中在此，避免各处内联实现走散。
# 放在 utils 而非 documents，是为了让不依赖 ES 栈的模型层也能直接使用。

import time
import uuid

ID_TIMESTAMP_LENGTH = 10


def generate_issue_style_id(timestamp: int | float | None = None) -> str:
    """生成 Issue 系 ID，timestamp 为空时取当前秒级时间戳。"""

    now = int(time.time()) if timestamp is None else int(timestamp)
    return f"{now}{uuid.uuid4().hex[:8]}"


def parse_timestamp_by_id(obj_id: str) -> int:
    """从 Issue 系 ID 前缀还原秒级时间戳。"""

    return int(str(obj_id)[:ID_TIMESTAMP_LENGTH])
