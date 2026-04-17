"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import ClassVar, Any, Self
from dataclasses import dataclass, fields


VALUE_UNSET = object()  # 用于表示未设置的参数


@dataclass
class BaseUnsetDTO:
    LOCAL_TO_REMOTE_MAP: ClassVar[dict[str, str]] = {}

    def __post_init__(self):
        pass

    def _get_remote_dict(self) -> dict[str, Any]:
        remote_dict: dict[str, Any] = {}
        for local_field_name, remote_field_name in self.LOCAL_TO_REMOTE_MAP.items():
            if getattr(self, local_field_name, None) is not VALUE_UNSET:
                remote_dict[remote_field_name] = getattr(self, local_field_name, None)
        return remote_dict

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        field_names = {field.name for field in fields(cls)}
        create_dict: dict[str, Any] = {k: v for k, v in data.items() if k in field_names}
        return cls(**create_dict)
