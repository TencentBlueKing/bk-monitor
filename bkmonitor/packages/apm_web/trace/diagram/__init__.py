from typing import Any, Dict, Type

from typing_extensions import Protocol

from .flamegraph import FlamegraphDiagrammer
from .sequence import SequenceDiagrammer
from .statistics import StatisticsDiagrammer
from .topo import TopoDiagrammer


class Diagrammer(Protocol):
    def draw(self, trace_detail: list, **options) -> Any:
        raise NotImplementedError

    def diff(self, base: list, comp: list, **options) -> Any:
        raise NotImplementedError


_diagrammer_cls_map: Dict[str, Type[Diagrammer]] = {}


def get_diagrammer(diagram_type: str, extra_init_options: dict) -> Diagrammer:
    return _diagrammer_cls_map[diagram_type].__call__(**extra_init_options)


def register_diagrammer_cls(diagram_type: str, diagrammer_cls: Type[Diagrammer]):
    _diagrammer_cls_map[diagram_type] = diagrammer_cls


register_diagrammer_cls("sequence", SequenceDiagrammer)
register_diagrammer_cls("flamegraph", FlamegraphDiagrammer)
register_diagrammer_cls("topo", TopoDiagrammer)
register_diagrammer_cls("statistics", StatisticsDiagrammer)
