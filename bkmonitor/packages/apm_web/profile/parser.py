"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional

from .models import Function, Line, Location, Mapping, Profile, Sample, ValueType


@dataclass
class ProfileParser:
    """Pprof JSON data Parser"""

    # mappings for deduplication
    _location_mapping: Dict[str, Location] = field(default_factory=dict)
    _mapping_mapping: Dict[str, Mapping] = field(default_factory=dict)
    _function_mapping: Dict[str, Function] = field(default_factory=dict)

    # mappings for quick query by id
    _location_id_mapping: Dict[int, Location] = field(default_factory=dict)
    _mapping_id_mapping: Dict[int, Mapping] = field(default_factory=dict)
    _function_id_mapping: Dict[int, Function] = field(default_factory=dict)

    profile: Optional[Profile] = None

    def raw_to_profile(self, raw: dict):
        """parse single raw json data to Profile object"""
        samples_info = raw["list"]
        if not samples_info:
            return

        self.profile = Profile(
            period=samples_info[0]["period"],
            default_sample_type=samples_info[0]["sample_type"],
            period_type=ValueType(*samples_info[0]["period_type"].split("/")),
            sample_types=[ValueType(*samples_info[0]["sample_type"].split("/"))],
        )

        for sample_info in samples_info:
            sample = Sample(values=[sample_info["value"]], labels=sample_info.get("labels", {}))
            for stacktrace in sample_info["stacktrace"]:
                location = self.stacktrace_to_location(stacktrace)
                sample.locations.append(location)

            self.profile.samples.append(sample)

    def stacktrace_to_location(self, stacktrace: dict) -> Location:
        mapping_info = stacktrace["mapping"]

        mapping = self._mapping_mapping.get(mapping_info["fileName"])
        if mapping is None:
            mapping = Mapping(
                id=len(self.profile.mappings) + 1,
                memory_start=mapping_info["memoryStart"],
                memory_limit=mapping_info["memoryLimit"],
                file_offset=mapping_info["fileOffset"],
                filename=mapping_info["fileName"],
                build_id=mapping_info["buildId"],
                has_functions=mapping_info["hasFunctions"],
                has_filenames=mapping_info["hasFilenames"],
                has_line_numbers=mapping_info["hasLineNumbers"],
                has_inline_frames=mapping_info["hasInlineFrames"],
            )
            self._mapping_mapping[mapping_info["fileName"]] = mapping
            self._mapping_id_mapping[mapping.id] = mapping
            self.profile.mappings.append(mapping)

        location = self._location_mapping.get(stacktrace["address"])
        if location is None:
            location = Location(
                id=len(self.profile.locations) + 1,
                mapping=mapping,
                address=stacktrace["address"],
                is_folded=stacktrace["isFolded"],
            )
            self._location_mapping[stacktrace["address"]] = location
            self._location_id_mapping[location.id] = location
            self.profile.locations.append(location)

        for line_info in stacktrace["lines"]:
            function = self._function_mapping.get(line_info["function"]["name"])
            if function is None:
                function = Function(
                    id=len(self.profile.functions) + 1,
                    name=line_info["function"]["name"],
                    system_name=line_info["function"]["systemName"],
                    filename=line_info["function"]["fileName"],
                    start_line=line_info["function"]["startLine"],
                )
                self._function_mapping[line_info["function"]["name"]] = function
                self._function_id_mapping[function.id] = function
                self.profile.functions.append(function)

            # add function only once
            location.lines.append(Line(function=function, line=line_info["line"]))

        return location

    def get_function(self, function_id: int) -> Function:
        return self._function_id_mapping.get(function_id)

    def get_location(self, location_id: int) -> Location:
        return self._location_id_mapping.get(location_id)
