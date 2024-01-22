"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Any, Dict, Optional, Type

from typing_extensions import Protocol

from apm_web.profile.converter import Converter

from .callgraph import CallGraphDiagrammer
from .flamegraph import FlamegraphDiagrammer
from .table import TableDiagrammer
from .tendency import TendencyDiagrammer


class Diagrammer(Protocol):
    def draw(self, c: Converter, **options) -> Any:
        raise NotImplementedError

    def diff(self, base_doris_converter: Converter, diff_doris_converter: Converter, **options) -> Any:
        raise NotImplementedError


_diagrammer_cls_map: Dict[str, Type[Diagrammer]] = {}


def get_diagrammer(diagram_type: str, extra_init_options: Optional[dict] = None) -> Diagrammer:
    extra_init_options = extra_init_options or {}
    return _diagrammer_cls_map[diagram_type].__call__(**extra_init_options)


def register_diagrammer_cls(diagram_type: str, diagrammer_cls: Type[Diagrammer]):
    _diagrammer_cls_map[diagram_type] = diagrammer_cls


register_diagrammer_cls("flamegraph", FlamegraphDiagrammer)
register_diagrammer_cls("callgraph", CallGraphDiagrammer)
register_diagrammer_cls("table", TableDiagrammer)
register_diagrammer_cls("tendency", TendencyDiagrammer)
