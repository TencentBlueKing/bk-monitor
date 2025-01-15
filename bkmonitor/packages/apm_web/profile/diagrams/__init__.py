"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Any, Dict, Optional, Type, Union

from typing_extensions import Protocol

from apm_web.profile.diagrams.callgraph import CallGraphDiagrammer
from apm_web.profile.diagrams.flamegraph import FlamegraphDiagrammer
from apm_web.profile.diagrams.grafana_flame import GrafanaFlameDiagrammer
from apm_web.profile.diagrams.table import TableDiagrammer
from apm_web.profile.diagrams.tendency import TendencyDiagrammer
from apm_web.profile.diagrams.tree_converter import TreeConverter


class Diagrammer(Protocol):
    """
    Profiling 图表绘制基类
    每个 Diagrammer 都可以绘制各自的特定数据格式
    源数据格式支持:
    1. TreeConverter 适用于: 调用图、火焰图、表格
    2. Dict 适用于: 趋势图
    """

    def draw(self, c: Union[TreeConverter, dict], **options) -> Any:
        raise NotImplementedError

    def diff(
        self,
        base_doris_converter: Union[TreeConverter, dict],
        diff_doris_converter: Union[TreeConverter, dict],
        **options,
    ) -> Any:
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
register_diagrammer_cls("grafana_flame", GrafanaFlameDiagrammer)
