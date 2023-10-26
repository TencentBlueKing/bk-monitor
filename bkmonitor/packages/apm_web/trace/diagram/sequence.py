import hashlib
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import ClassVar, Dict, List, Optional

from apm_web.trace.diagram.base import SpanNode, TraceTree, TreeBuildingConfig
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from constants.apm import OtlpKey, SpanKind


@dataclass
class SequenceDiagrammer:
    """Sequence diagrammer"""

    def draw(self, trace_detail: list, **options) -> dict:
        return trace_to_mermaid_sequence_data(trace_detail=trace_detail)

    def diff(self, base: list, comp: list, **options) -> dict:
        raise NotImplementedError


mermaid_escape_chars = [";", ",", ":"]


def escape_mermaid_chars(s: str) -> str:
    """Escape mermaid special chars"""
    if not isinstance(s, str):
        s = str(s)

    for c in mermaid_escape_chars:
        s = s.replace(c, f"#{ord(c)};")

    return s


class AutoName(str, Enum):
    def _generate_next_value_(self, start, count, last_values):
        return str(self).lower()


class ParticipantType(AutoName):
    COMPONENT = auto()
    ENDPOINT = auto()
    DATABASE = auto()


@dataclass
class Participant:
    type_: ParticipantType
    name: str
    display_name: str
    component_name: str
    span_id: Optional[str] = None

    FORCE_STRING_PREFIX: ClassVar[str] = "p"

    @classmethod
    def get_type_from_span(cls, span: dict) -> ParticipantType:
        """Get type from span"""
        if SpanAttributes.HTTP_TARGET in span[OtlpKey.ATTRIBUTES]:
            return ParticipantType.ENDPOINT
        elif SpanAttributes.DB_SYSTEM in span[OtlpKey.ATTRIBUTES]:
            return ParticipantType.DATABASE
        else:
            return ParticipantType.COMPONENT

    @classmethod
    def get_service_name_else_span_name(cls, span: dict) -> str:
        """Get service name from span, if not exist, use span name"""
        if ResourceAttributes.SERVICE_NAME not in span[OtlpKey.RESOURCE]:
            return span[OtlpKey.SPAN_NAME]
        return span[OtlpKey.RESOURCE][ResourceAttributes.SERVICE_NAME]

    @classmethod
    def from_span_info(cls, span_info: dict) -> "Participant":
        def get_unique_name(_component_name: str, _display_name: str) -> str:
            # FORCE_STRING_PREFIX make sure the name is not numeric, which is not allowed in mermaid
            # Although sha1 is not collision-free, it is enough for our use case and faster than sha2
            return (
                cls.FORCE_STRING_PREFIX
                + hashlib.sha1(f"{_component_name}:{_display_name}".encode("utf-8")).hexdigest()[:8]
            )

        span_id = None
        type_ = cls.get_type_from_span(span_info)
        # TODO: there may be more endpoint types
        if type_ == ParticipantType.ENDPOINT:
            display_name = span_info[OtlpKey.ATTRIBUTES][SpanAttributes.HTTP_TARGET].split("?")[0]
            component_name = span_info[OtlpKey.RESOURCE][ResourceAttributes.SERVICE_NAME]
            name = get_unique_name(component_name, display_name)
            span_id = span_info[OtlpKey.SPAN_ID]
        elif type_ == ParticipantType.DATABASE:
            display_name = span_info[OtlpKey.ATTRIBUTES][SpanAttributes.DB_SYSTEM]
            component_name = span_info[OtlpKey.RESOURCE][ResourceAttributes.SERVICE_NAME]
            name = get_unique_name(component_name, display_name)
            span_id = span_info[OtlpKey.SPAN_ID]
        else:
            name = display_name = cls.get_service_name_else_span_name(span_info)
            component_name = name

        return cls(type_=type_, name=name, component_name=component_name, span_id=span_id, display_name=display_name)


@dataclass
class ParticipantSet:
    """Participant set"""

    START_NAME: ClassVar = "Start"

    # the kind of root span is in [SERVER, CONSUMER], and no parent span
    # add a virtual start span
    contain_virtual_start: bool = False

    name_to_component: Dict[str, Participant] = field(default_factory=dict)
    component_name_to_endpoints: Dict[str, List[Participant]] = field(default_factory=lambda: defaultdict(list))

    id_to_participant: Dict[str, Participant] = field(default_factory=OrderedDict)
    _name_to_participant: Dict[str, Participant] = field(default_factory=OrderedDict)

    def __post_init__(self):
        self._component_index = 0

    def from_span_infos(self, span_infos: List[dict]):
        for span_info in span_infos:
            p = Participant.from_span_info(span_info)
            self.id_to_participant[span_info[OtlpKey.SPAN_ID]] = p

            if p.name not in self._name_to_participant:
                self._name_to_participant[p.name] = p

            if p.type_ == ParticipantType.COMPONENT:
                self.name_to_component[p.name] = p
            else:
                self.component_name_to_endpoints[p.component_name].append(p)

    def to_list(self) -> list:
        participants = []
        if self.contain_virtual_start:
            participants.append(
                {
                    "name": self.START_NAME,
                    "display_name": self.START_NAME,
                    "type": ParticipantType.COMPONENT.value,
                    "component_name": self.START_NAME,
                    "span_id": None,
                }
            )

        # Add all components(services)
        participants.extend(
            {"name": x, "type": ParticipantType.COMPONENT.value, "component_name": x, "span_id": None}
            for x in self.name_to_component
        )

        # Add all endpoints
        for x in self.id_to_participant.values():
            if x.type_ == ParticipantType.COMPONENT:
                continue

            participants.append(
                {  # noqa
                    "name": x.name,
                    "display_name": x.display_name,
                    "type": x.type_.value,
                    "component_name": x.component_name,
                    "span_id": x.span_id,
                }
            )

        return participants

    def __str__(self) -> str:
        target = f"\n%%participants\n"
        added = set()
        if self.contain_virtual_start:
            target += f"participant {self.START_NAME}\n"

        for p in self.name_to_component.values():
            target += f"participant {p.name}\n"
            added.add(p.name)

        for component_name, participants in self.component_name_to_endpoints.items():
            _participants = ""
            for p in participants:
                if p.name in added:
                    continue

                _participants += f"participant {p.name} as {p.display_name}\n"
                added.add(p.name)

            # use box to show certain service
            target += f"box {component_name}\n{_participants}end\n"

        target += "%%end\n\n"
        return target

    def is_parent_ahead(self, parent_name: str, child_name: str) -> bool:
        """Check if parent span is ahead of child span in participant sequence"""
        span_names = [x for x in self._name_to_participant]
        parent_index = span_names.index(parent_name)
        child_index = span_names.index(child_name)
        return parent_index < child_index


@dataclass
class Connection:

    from_: str
    to_: str
    message: str
    parent_message: str = ""
    parent_merged: bool = False
    parallel_id: Optional[str] = None
    parallel_path: List[str] = field(default_factory=list)
    group_info: dict = field(default_factory=dict)
    hyphen: Optional["Hyphen"] = None
    original: dict = field(default_factory=dict)

    def __str__(self) -> str:
        if self.hyphen is None:
            raise ValueError("hyphen is not set")

        return f"{self.from_} {self.hyphen.value} {self.to_}: {self.message}\n"

    def __eq__(self, other: "Connection") -> bool:
        return (
            self.from_ == other.from_
            and self.to_ == other.to_
            and self.message == other.message
            and self.hyphen == other.hyphen
        )

    @property
    def notes(self) -> str:
        notes = []
        for k, v in self.original[OtlpKey.ATTRIBUTES].items():
            notes.append(f"{escape_mermaid_chars(k)}={escape_mermaid_chars(v)}")

        if not notes:
            return ""

        # diagram spread from left to right, so put notes on right
        return f"Note right of {self.to_}:{'<br/>'.join(notes)}\n"

    @property
    def deactivation_str(self) -> str:
        return f"{self.to_} {Hyphen.ACTIVATION_DOTTED_ARROW.value} {self.from_}: \n"

    @property
    def deactivation(self) -> "Connection":
        return Connection(
            from_=self.to_,
            to_=self.from_,
            message=" ",
            hyphen=Hyphen.ACTIVATION_DOTTED_ARROW,
            original=self.original,
            # deactivate should follow activation parallel
            parallel_id=None,
            parallel_path=self.parallel_path,
            group_info=self.group_info,
        )

    @property
    def enable_activation(self) -> bool:
        return self.hyphen == Hyphen.ACTIVATION_SOLID_ARROW

    @classmethod
    def from_span_info(cls, participant_set: ParticipantSet, node: SpanNode) -> "Connection":
        span = node.details
        p = participant_set.id_to_participant[span[OtlpKey.SPAN_ID]]
        kind = span[OtlpKey.KIND]

        # 根 span
        if span[OtlpKey.PARENT_SPAN_ID] not in participant_set.id_to_participant:
            # 当根 span 是被动方时
            if kind in [SpanKind.SPAN_KIND_CONSUMER, SpanKind.SPAN_KIND_SERVER]:
                parent_name = participant_set.START_NAME
            else:
                # 根 span 作为主动方，没有虚拟父节点
                parent_name = p.name
        else:
            parent_name = participant_set.id_to_participant[span[OtlpKey.PARENT_SPAN_ID]].name

        if kind in [SpanKind.SPAN_KIND_CONSUMER, SpanKind.SPAN_KIND_PRODUCER]:
            # async
            hyphen = Hyphen.SOLID_SHARP
        elif kind == SpanKind.SPAN_KIND_INTERNAL:
            hyphen = Hyphen.SOLID_ARROW
        else:
            hyphen = Hyphen.ACTIVATION_SOLID_ARROW

        group_info = {}
        if node.group:
            group_info["id"] = node.group.members[0].id
            group_info["members"] = list({m.id for m in node.group.members})

        return Connection(
            from_=parent_name,
            to_=p.name,
            message=span[OtlpKey.SPAN_NAME],
            hyphen=hyphen,
            original=span,
            parallel_id=node.parallel.id if node.parallel else None,
            parallel_path=[p.id for p in node.parallel_path],
            group_info=group_info,
        )

    def to_dict(self):
        return {
            "from": self.from_,
            "to": self.to_,
            "hyphen": self.hyphen,
            "parent_merged": self.parent_merged,
            "message": self.message,
            "original": self.original,
            "parallel_id": self.parallel_id,
            "parallel_path": self.parallel_path,
            "group_info": self.group_info or None,
        }


class Hyphen(str, Enum):
    """Hyphen Style"""

    SOLID_ARROW = "->>"
    DOTTED_CROSS = "--x"
    SOLID_SHARP = "-)"

    ACTIVATION_SOLID_ARROW = "->>+"
    ACTIVATION_DOTTED_ARROW = "-->>-"


def trace_to_mermaid_sequence_data(trace_detail: list) -> dict:
    """Convert trace detail to mermaid sequence diagram data
    :param trace_detail: trace detail, contains span list
    """
    participant_set = ParticipantSet()
    participant_set.from_span_infos(trace_detail)

    connections: List[Connection] = []
    merging_parents = {}
    merging_children = {}
    for span in trace_detail:
        kind = span[OtlpKey.KIND]
        # 找到所有主调
        if kind in [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_PRODUCER]:
            merging_parents[span[OtlpKey.SPAN_ID]] = span
        elif kind in [SpanKind.SPAN_KIND_CONSUMER, SpanKind.SPAN_KIND_SERVER]:
            merging_children[span[OtlpKey.PARENT_SPAN_ID]] = span

    def add_connections(c_: Connection, virtual_return: bool):
        if virtual_return:
            if c_.enable_activation:
                connections.append(c_.deactivation)
        else:
            connections.append(c_)

    config = TreeBuildingConfig(with_group=True, with_virtual_return=True, with_parallel_detection=True)
    trace_tree = TraceTree.from_raw(trace_detail, config)
    trace_tree.build_extras()

    for node in trace_tree.to_pre_order_tree_list():
        span = node.details
        kind = span[OtlpKey.KIND]
        connection = Connection.from_span_info(participant_set, node)

        # 被调向上与主调内容合并
        if kind in [SpanKind.SPAN_KIND_CONSUMER, SpanKind.SPAN_KIND_SERVER]:
            parent = merging_parents.get(span[OtlpKey.PARENT_SPAN_ID], {})
            if not parent:
                participant_set.contain_virtual_start = True
            else:
                parent_name = participant_set.id_to_participant[span[OtlpKey.PARENT_SPAN_ID]].name
                this_name = participant_set.id_to_participant[span[OtlpKey.SPAN_ID]].name
                connection.message = (
                    f"{parent[OtlpKey.SPAN_NAME]} ---> {connection.message}"
                    if participant_set.is_parent_ahead(parent_name, this_name)
                    else f"{connection.message} <--- {parent[OtlpKey.SPAN_NAME]}"
                )
                connection.parent_merged = True
                if not connection.parallel_id:
                    connection.parallel_id = node.parent.parallel.id if node.parent.parallel else None
                    connection.parallel_path = [x.id for x in node.parent.parallel_path]

            add_connections(connection, node.virtual_return)
        elif kind in [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_PRODUCER]:
            child = merging_children.get(span[OtlpKey.SPAN_ID])
            if not child:
                # 主调没有被调时直接添加
                add_connections(connection, node.virtual_return)
            else:
                # 主调有被调时，等待被调合并
                continue
        else:
            # kind in [SpanKind.SPAN_KIND_INTERNAL, SpanKind.SPAN_KIND_UNSPECIFIED]
            add_connections(connection, node.virtual_return)
            continue

    # make sure disabled on production
    # from .debug import debug_print_trace_tree, debug_print_mermaid_text
    # debug_print_mermaid_text(connections, participant_set)
    # debug_print_trace_tree(trace_tree)

    return {
        "participants": participant_set.to_list(),
        "connections": [x.to_dict() for x in connections],
    }
