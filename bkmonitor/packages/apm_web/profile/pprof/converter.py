"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import gzip
from dataclasses import dataclass
from typing import Optional

from apm_web.profile.constants import InputType
from apm_web.profile.converter import Converter, register_converter
from apm_web.profile.models import Label, Profile


@dataclass
class PprofConverter(Converter):
    """Convert binary to Profile object"""

    def convert(self, raw: bytes) -> Optional[Profile]:
        """Convert binary to Profile object"""
        self.init_profile()
        try:
            self.profile.parse(gzip.decompress(raw))
        except Exception:  # pylint: disable=broad-except
            self.profile.parse(raw)

        if not self.preset_profile_id:
            return self.profile

        for s in self.profile.sample:
            s.label.append(
                Label(
                    key=self.add_string("profile_id"),
                    str=self.add_string(self.preset_profile_id),
                )
            )
            for k, v in self.inject_labels.items():
                s.label.append(
                    Label(
                        key=self.add_string(k),
                        str=self.add_string(v),
                    )
                )

        return self.profile


register_converter(InputType.PPROF.value, PprofConverter)
