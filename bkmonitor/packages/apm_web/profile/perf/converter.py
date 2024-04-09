"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
from dataclasses import dataclass
from typing import List, Optional

from apm_web.profile.constants import InputType
from apm_web.profile.converter import Converter, register_converter
from apm_web.profile.models import (
    Function,
    Label,
    Line,
    Location,
    Mapping,
    Profile,
    Sample,
    ValueType,
)


@dataclass
class PerfScriptConverter(Converter):
    """Convert perf script to Profile object"""

    def convert(self, raw: bytes) -> Optional[Profile]:
        """parse single raw perf script data to Profile object"""
        self.profile.sample_type = [ValueType(self.add_string("samples"), self.add_string("count"))]
        self.profile.period_type = ValueType(self.add_string("cpu"), self.add_string("nanoseconds"))
        self.profile.period = 1000000

        # only uptime is available, we can not get the exact time of the profile
        self.profile.time_nanos = int(datetime.datetime.now().timestamp() * 10**9)

        mapping = Mapping(
            id=1,
            memory_start=0,
            memory_limit=0,
            file_offset=0,
            filename=self.add_string("perf_script_file"),
            build_id=self.add_string(""),
        )
        self.profile.mapping.append(mapping)

        sample_texts = []
        for line in raw.decode().split("\n"):
            if not line:
                self._parse_lines(sample_texts)
                sample_texts = []
                continue
            sample_texts.append(line)

        self.profile.duration_nanos = self._get_sample_ns_timestamp(
            self.profile.sample[-1]
        ) - self._get_sample_ns_timestamp(self.profile.sample[0])

        print(f"samples: {len(self.profile.sample)}")
        print(f"locations: {len(self.profile.location)}")
        print(f"functions: {len(self.profile.function)}")
        print(f"mappings: {len(self.profile.mapping)}")
        return self.profile

    def _get_sample_ns_timestamp(self, s: Sample) -> int:
        """get sample timestamp"""
        index = self.profile.string_table.index("timestamp")
        for lab in s.label:
            if lab.key == index:
                return lab.num

    def _parse_lines(self, lines: List[str]):
        """parse multiple lines to a single sample"""
        if not lines:
            return

        event_fields = [x for x in lines[0].split(" ") if x]
        process_name = event_fields[0]
        pid = event_fields[1]
        cpu = event_fields[2][1:-1]

        # got duration for the profile by
        timestamp = int(float(event_fields[3][:-1]) * 10**9)
        event_type = event_fields[4]
        event_name, event_extra, *_ = event_fields[5].split(":")

        sample_locations = []
        for stack_line in lines[1:]:
            stack_fields = stack_line.split(" ")
            if len(stack_fields) != 3:
                continue

            addr = int(stack_fields[0], 16)
            location = self._location_mapping.get(str(addr))
            if location is None:
                location = Location(
                    id=len(self.profile.location) + 1,
                    mapping_id=self.profile.mapping[0].id,
                    address=addr,
                    is_folded=False,
                )

                self._location_mapping[str(addr)] = location
                self._location_id_mapping[location.id] = location

                self.profile.location.append(location)

            func_name = stack_fields[1]
            if len(func_name.split("+")) == 2:
                func_name = func_name.split("+")[0]
            file_name = stack_fields[2][1:-1]
            function = self._function_mapping.get(func_name)
            if function is None:
                function = Function(
                    id=len(self.profile.function) + 1,
                    name=self.add_string(func_name),
                    system_name=self.add_string(func_name),
                    filename=self.add_string(file_name),
                    # function line is not clearly in binary
                    start_line=0,
                )
                self._function_mapping[func_name] = function
                self._function_id_mapping[function.id] = function

                self.profile.function.append(function)

                location.line.append(Line(function_id=function.id, line=1))

            # locations only for this sample
            sample_locations.append(location)

        sample = Sample(
            value=[1],
            location_id=[loc.id for loc in sample_locations],
            label=[
                Label(key=self.add_string("process_name"), str=self.add_string(process_name)),
                Label(key=self.add_string("pid"), str=self.add_string(pid)),
                Label(key=self.add_string("cpu"), str=self.add_string(cpu)),
                Label(key=self.add_string("timestamp"), num=timestamp, num_unit=self.add_string("nanoseconds")),
                Label(key=self.add_string("event_type"), str=self.add_string(event_type)),
                Label(key=self.add_string("event_name"), str=self.add_string(event_name)),
                Label(key=self.add_string("event_extra"), str=self.add_string(event_extra)),
            ],
        )

        if self.preset_profile_id:
            sample.label.append(
                Label(
                    key=self.add_string("profile_id"),
                    str=self.add_string(self.preset_profile_id),
                )
            )

        self.profile.sample.append(sample)


register_converter(InputType.PERF_SCRIPT.value, PerfScriptConverter)
