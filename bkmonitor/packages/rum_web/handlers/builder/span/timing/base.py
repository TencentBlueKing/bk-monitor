"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rum_web.handlers.builder.base import BaseComponent
from rum_web.handlers.builder.utils import get_safe_number


Phase = tuple[str, int | float, int | float]


class TimingLayout(BaseComponent):
    """按子类声明的字段前缀读取时间点，输出相对 start_time 的阶段起点和耗时。"""

    TIMING_PREFIX: str

    def point(self, name: str) -> int | float | None:
        return get_safe_number(self.flatten_data.get(f"{self.TIMING_PREFIX}{name}"), None)

    def span(self, key: str, start: int | float | None, end: int | float | None) -> Phase | None:
        start_time = self.point("start_time")
        if start_time is None or start is None or end is None or not start_time <= start < end:
            return None
        return key, start - start_time, end - start

    def matches(self) -> bool:
        raise NotImplementedError

    def phases(self) -> list[Phase | None]:
        raise NotImplementedError
