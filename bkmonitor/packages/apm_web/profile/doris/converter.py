"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import dataclass

import json
from django.conf import settings

from apm_web.profile.models import (
    Function,
    Line,
    Location,
    Mapping,
    Profile,
    Sample,
    ValueType,
)
from apm_web.profile.profileconverter import ProfileConverter


@dataclass
class DorisProfileConverter(ProfileConverter):
    """Convert data in doris(pprof json) to Profile object"""

    @classmethod
    def _align_agg_interval(cls, t, interval):
        return int(t / interval) * interval

    @staticmethod
    def _resolve_agg_method(agg_method: str | None, sample_type: str) -> str:
        supported = {"AVG", "SUM", "LAST"}
        default_method = settings.APM_PROFILING_AGG_METHOD_MAPPING.get(sample_type.upper(), "SUM")
        if agg_method in supported:
            return agg_method
        return default_method if default_method in supported else "SUM"

    @staticmethod
    def _normalize_json_text(value: str | None, default: str) -> str:
        """Normalize JSON text while keeping list order unchanged."""
        if not value:
            return default
        try:
            normalized = json.dumps(json.loads(value), sort_keys=True)
        except Exception:
            normalized = value
        return normalized

    @classmethod
    def _build_avg_samples(cls, samples_info: list[dict], agg_interval: int) -> list[dict]:
        snapshot_len = len(
            {cls._align_agg_interval(int(s["dtEventTimeStamp"]), agg_interval * 1000) for s in samples_info}
        )
        if snapshot_len <= 1:
            return samples_info

        grouped = {}
        for sample_info in samples_info:
            stacktrace_key = cls._normalize_json_text(sample_info.get("stacktrace"), "[]")
            if stacktrace_key not in grouped:
                sample = sample_info.copy()
                sample["stacktrace"] = stacktrace_key
                grouped[stacktrace_key] = {"sample": sample, "total": 0}
            grouped[stacktrace_key]["total"] += int(sample_info["value"])

        avg_samples = []
        for item in grouped.values():
            sample = item["sample"]
            sample["value"] = str(int(round(item["total"] / snapshot_len)))
            avg_samples.append(sample)
        return avg_samples

    def convert(self, raw: dict, agg_method=None, agg_interval=60) -> Profile | None:
        """parse single raw json data to Profile object"""
        samples_info = raw["list"]
        if not samples_info:
            return

        sample_type = samples_info[0]["sample_type"].split("/")[0]
        effective_agg_method = self._resolve_agg_method(agg_method, sample_type)
        if effective_agg_method == "LAST":
            # 只保留最后一个时间戳的所有 sample 数据
            interval = agg_interval * 1000
            last_snapshot = max({self._align_agg_interval(int(s["dtEventTimeStamp"]), interval) for s in samples_info})
            samples_info = [
                s
                for s in samples_info
                if self._align_agg_interval(int(s["dtEventTimeStamp"]), interval) == last_snapshot
            ]
            self.raw_data = samples_info
        elif effective_agg_method == "AVG":
            samples_info = self._build_avg_samples(samples_info, agg_interval)
            self.raw_data = samples_info
        else:
            self.raw_data = samples_info

        first_sample = samples_info[0]
        period_type, period_unit = first_sample["period_type"].split("/")
        self.profile.period_type = ValueType(self.add_string(period_type), self.add_string(period_unit))
        self.profile.period = first_sample["period"]
        sample_type, sample_unit = first_sample["sample_type"].split("/")
        self.profile.sample_type = [ValueType(self.add_string(sample_type), self.add_string(sample_unit))]
        self.profile.default_sample_type = 0

        for sample_info in samples_info:
            labels = json.loads(sample_info.get("labels", "{}"))
            sample = Sample(value=[int(sample_info["value"])], label=labels)
            for stacktrace in json.loads(sample_info["stacktrace"]):
                location = self.stacktrace_to_location(stacktrace)
                sample.location_id.append(location.id)

            self.profile.sample.append(sample)

        return self.profile

    def stacktrace_to_location(self, stacktrace: dict) -> Location:
        mapping_id = 0
        mapping_info = stacktrace["mapping"]
        if mapping_info is not None:
            mapping = self._mapping_mapping.get(mapping_info["fileName"])
            if mapping is None:
                mapping = Mapping(
                    id=len(self.profile.mapping) + 1,
                    memory_start=mapping_info["memoryStart"],
                    memory_limit=mapping_info["memoryLimit"],
                    file_offset=mapping_info["fileOffset"],
                    filename=self.add_string(mapping_info["fileName"]),
                    build_id=self.add_string(mapping_info["buildId"]),
                    has_functions=mapping_info["hasFunctions"],
                    has_filenames=mapping_info["hasFilenames"],
                    has_line_numbers=mapping_info["hasLineNumbers"],
                    has_inline_frames=mapping_info["hasInlineFrames"],
                )
                self._mapping_mapping[mapping_info["fileName"]] = mapping
                self._mapping_id_mapping[mapping.id] = mapping
                self.profile.mapping.append(mapping)

            mapping_id = mapping.id

        location = self._location_mapping.get(stacktrace["address"])
        if location is None:
            location = Location(
                id=len(self.profile.location) + 1,
                mapping_id=mapping_id,
                address=stacktrace["address"],
                is_folded=stacktrace["isFolded"],
            )
            self._location_mapping[stacktrace["address"]] = location
            self._location_id_mapping[location.id] = location
            self.profile.location.append(location)

            for line_info in stacktrace["lines"]:
                function = self._function_mapping.get(line_info["function"]["name"])
                if function is None:
                    function = Function(
                        id=len(self.profile.function) + 1,
                        name=self.add_string(line_info["function"]["name"]),
                        system_name=self.add_string(line_info["function"]["systemName"]),
                        filename=self.add_string(line_info["function"]["fileName"]),
                        start_line=line_info["function"]["startLine"],
                    )
                    self._function_mapping[line_info["function"]["name"]] = function
                    self._function_id_mapping[function.id] = function
                    self.profile.function.append(function)

                location.line.append(Line(function_id=function.id, line=line_info["line"]))

        return location

    def __len__(self):
        return len(self.raw_data)
