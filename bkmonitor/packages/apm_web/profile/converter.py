"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import random
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type
from uuid import UUID

from apm_web.profile.models import Function, Location, Mapping, Profile


def generate_profile_id() -> str:
    return UUID(int=random.getrandbits(128), version=4).hex


@dataclass
class Converter:
    """Any input format should be converted to Profile"""

    profile: Optional[Profile] = None
    # preset profile_id for querying
    # if preset_profile_id is not None, force insert it to labels of sample
    preset_profile_id: Optional[str] = None
    inject_labels: dict = field(default_factory=dict)
    raw_data: list = field(default_factory=list)
    init_first_empty_str: bool = True

    # mappings for deduplication
    _location_mapping: Dict[str, Location] = field(default_factory=dict)
    _mapping_mapping: Dict[str, Mapping] = field(default_factory=dict)
    _function_mapping: Dict[str, Function] = field(default_factory=dict)

    # mappings for quick query by id
    _location_id_mapping: Dict[int, Location] = field(default_factory=dict)
    _mapping_id_mapping: Dict[int, Mapping] = field(default_factory=dict)
    _function_id_mapping: Dict[int, Function] = field(default_factory=dict)

    def __post_init__(self):
        self.init_profile()

    def convert(self, raw: Any) -> Optional[Profile]:
        raise NotImplementedError

    def init_profile(self):
        self.profile = Profile()

        if self.init_first_empty_str:
            self.profile.string_table.append("")

    def add_string(self, value: str) -> int:
        """add string to profile string table"""
        if value in self.profile.string_table:
            return self.profile.string_table.index(value)

        self.profile.string_table.append(value)
        return len(self.profile.string_table) - 1

    def get_string(self, index: int) -> str:
        """get string from profile string table"""
        return self.profile.string_table[index]

    def get_function(self, function_id: int) -> Function:
        return self._function_id_mapping.get(function_id)

    def get_function_name(self, function_id: int) -> str:
        return self.get_string(self.get_function(function_id).name)

    def get_location(self, location_id: int) -> Location:
        return self._location_id_mapping.get(location_id)

    def get_mapping(self, mapping_id: int) -> Mapping:
        return self._mapping_id_mapping.get(mapping_id)

    def get_sample_type(self) -> dict:
        """get sample type for profile"""
        # sometimes we would remove the first value of sample_type, which is describing the number of samples
        target_sample_type = self.profile.sample_type[0]

        # by convention, the first value on all profiles is the number of samples collected at this call stack,
        if len(self.profile.sample_type) > 1:
            target_sample_type = self.profile.sample_type[1]

        return {"type": self.get_string(target_sample_type.type), "unit": self.get_string(target_sample_type.unit)}


_converters: Dict[str, Type[Converter]] = {}


def register_converter(input_type: str, converter: Type[Converter]):
    _converters[input_type] = converter


def get_converter_by_input_type(input_type: str):
    if input_type not in _converters:
        raise ValueError(f"Converter for {input_type} not found")

    return _converters[input_type]


def list_converter() -> Dict[str, Type[Converter]]:
    return _converters
