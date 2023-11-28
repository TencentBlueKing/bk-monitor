"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import pytest

from apm_web.profile.diagrams.flamegraph import FlamegraphDiagrammer
from apm_web.profile.parser import ProfileParser

from .utils import read_profile


class TestProfileFlamegraph:
    @pytest.fixture(scope="class")
    def diagrammer(self):
        return FlamegraphDiagrammer()

    @pytest.fixture(scope="class")
    def parser(self):
        return ProfileParser()

    def test_draw(self, diagrammer, parser):
        """test for drawing"""
        parser.raw_to_profile(read_profile())
        assert parser.profile
        assert diagrammer.draw(parser)
