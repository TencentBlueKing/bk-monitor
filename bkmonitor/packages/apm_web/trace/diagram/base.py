import logging
import random
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
)
from uuid import UUID
from weakref import ReferenceType
from weakref import ref as weak_ref

from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import StatusCode

from apm_web.utils import percentile
from constants.apm import OtlpKey, SpanKind

logger = logging.getLogger(__name__)


@dataclass
class TreeBuildingConfig:
    with_parallel_detection: bool = False
    with_virtual_return: bool = False
    with_group: bool = False
    group_recursive: bool = False
    group_ignore_sequence: bool = False
    min_group_spans_count: int = 5
    min_group_members: int = 2
    min_parallel_members: int = 2
    min_parallel_gap: int = 500

    @classmethod
    def default(cls) -> "TreeBuildingConfig":
        return cls()


class UUIDGenerator:
    """Generate UUIDs."""

    id: str

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls)
        obj.id = cls._generate_id()
        return obj

    @classmethod
    def _generate_id(cls):
        return UUID(int=random.getrandbits(128), version=4).hex


@dataclass
class MemberContainer:
    """A container of members.

    This class mainly handled the logic of adding members to the container.
    """

    parent: "SpanNode"
    config: TreeBuildingConfig
    valid: bool = False
    min_valid_members: int = 2
    _members: List["SpanNode"] = field(default_factory=list)
    _member_ids: List[str] = field(default_factory=list)
    candidates: List["SpanNode"] = field(default_factory=list)

    should_add: ClassVar[Callable[["SpanNode"], bool]]

    @property
    def first(self) -> "SpanNode":
        if not self.members:
            raise ValueError("No members in the container")

        return self.members[0]

    @property
    def members(self) -> List["SpanNode"]:
        return self._members

    @members.setter
    def members(self, value: List["SpanNode"]):
        self._members = value
        self._member_ids = [m.id for m in value]

    @property
    def member_ids(self) -> List[str]:
        return self._member_ids

    @classmethod
    def from_parent(cls, parent: "SpanNode", config: TreeBuildingConfig) -> "MemberContainerType":
        return cls(parent, config)

    def try_add_and_validate(self, node: "SpanNode") -> bool:
        """Whether the node should be taken in."""
        if self.should_add(node):
            self.candidates.append(node)
            return True
        else:
            return False

    def promote(self, ref_field: str):
        """Promote candidates to members."""
        self.members.extend(self.candidates)
        for m in self.members:
            setattr(m, ref_field, self)

            # add cache for member ids
            self._member_ids.append(m.id)

            virtual_m = m.virtual_self
            if virtual_m:
                setattr(virtual_m, ref_field, self)

        self.candidates = []
        self.valid = True

    def finalize(self, ref_field: str):
        """Finalize the container."""
        # virtual_return will be added to candidates too, so have to check the unique ids
        if len({x.id for x in self.candidates}) < self.min_valid_members:
            self.invalidate()
        else:
            self.promote(ref_field)

    def invalidate(self):
        """Mark self as invalid."""
        self.valid = False
        self.candidates = []


MemberContainerType = TypeVar("MemberContainerType", bound="MemberContainer")


@dataclass
class Group(UUIDGenerator, MemberContainer):
    """A group of spans in the trace tree.

    In tracing, some sibling spans could be grouped together.
    """

    # which field should be grouped
    value_field: str = OtlpKey.ELAPSED_TIME

    def __post_init__(self):
        self.min_valid_members = self.config.min_group_members

    @staticmethod
    def compare_descendants(base: "SpanNode", target: "SpanNode") -> bool:
        """Compare all children of two nodes."""
        if len(base.children) != len(target.children):
            return False

        for i, child in enumerate(base.children):
            if child.unique_together != target.children[i].unique_together:
                return False

        # Q: Why not call descendants first?
        # A: Because in most cases, comparing of the children is enough,
        # and descendants property is a little heavy calling.
        base_descendants = base.descendants
        target_descendants = target.descendants
        if len(base_descendants) != len(target_descendants):
            return False

        # Any descendant not the same will block the grouping
        # so the grouping elements must own the same descendants tree.
        for i, child in enumerate(base_descendants):
            if child.unique_together != target_descendants[i].unique_together:
                return False

        return True

    def should_add_to_group(self, adding: "SpanNode"):
        """Should the node be added to the group."""
        # no group if error occurs
        if adding.has_error or adding.children_have_error:
            return False

        if not self.candidates:
            return True

        last_candidate = self.candidates[-1]
        unique_equality = last_candidate.unique_together == adding.unique_together
        if not unique_equality:
            return False

        children_equality = self.compare_descendants(adding, last_candidate)
        return children_equality

    should_add = should_add_to_group

    @property
    def total_value(self) -> int:
        """Total value of the group."""
        return sum([m.details[self.value_field] for m in self.members])

    @property
    def start_and_end(self) -> Tuple[int, int]:
        """Start and end timestamp of the group."""
        start = min([m.details[OtlpKey.START_TIME] for m in self.members])
        end = max([m.details[OtlpKey.END_TIME] for m in self.members])
        return start, end

    @property
    def absolute_duration(self) -> int:
        """Absolute duration of the group."""
        start, end = self.start_and_end
        return end - start

    @property
    def info(self) -> dict:
        """Group info."""

        start, end = self.start_and_end
        return {
            "id": self.id,
            "members": [m.id for m in self.members],
            "total_value": self.total_value,
            "start_time": start,
            "end_time": end,
        }


@dataclass
class Parallel(UUIDGenerator, MemberContainer):
    """An abstract parallel in the trace tree.

    In tracing, a parallel is a group of spans that are executed in parallel, what should be notes is that
    the spans in a parallel are not necessarily executed in parallel, but they are logically parallel.
    And the spans in a parallel should be executed in the same level, which means they should have the same parent.
    """

    def __post_init__(self):
        self.min_valid_members = self.config.min_parallel_members

    def should_add_to_parallel(self, child: "SpanNode") -> bool:
        """Whether the child should be added to the parallel."""
        if not self.candidates:
            return True

        last_candidate = self.candidates[-1]
        # siblings acquired
        if not child.parent.id == last_candidate.parent.id:
            return False

        # if last candidate ends after the child starts, they must be in the same parallel
        last_start_time, last_end_time = last_candidate.start_and_end
        adding_start_time, _ = child.start_and_end
        if last_end_time > adding_start_time:
            return True

        # if no overlapping, check the starting gap
        return abs(last_start_time - adding_start_time) < self.config.min_parallel_gap

    should_add = should_add_to_parallel


@dataclass
class AbstractAggregation(UUIDGenerator):
    name: str
    members: List["SpanNode"] = field(default_factory=list)
    member_ids: Set[str] = field(default_factory=set)

    agg_display_name: ClassVar[str]

    @property
    def details(self) -> dict:
        return {"name": self.name, "values": self.values}

    @property
    def values(self) -> dict:
        if not self.members:
            return {}

        return {
            "max_duration": max(self.durations),
            "min_duration": min(self.durations),
            "avg_duration": round(sum(self.durations) / len(self.durations), 2),
            "sum_duration": sum(self.durations),
            "P95": percentile(self.durations, 95),
            "count": len(self.durations),
        }

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def durations(self) -> list:
        return [m.details[OtlpKey.ELAPSED_TIME] for m in self.members]

    @classmethod
    def get_value_from_span_node(cls, span_node: "SpanNode") -> Any:
        raise NotImplementedError

    def add(self, node: "SpanNode"):
        """Add a node to the service."""
        if node.id in self.member_ids:
            return

        self.members.append(node)
        self.member_ids.add(node.id)


class SpanNameAgg(AbstractAggregation):
    """A span name in the trace tree."""

    agg_display_name = "接口"

    @classmethod
    def get_value_from_span_node(cls, span_node: "SpanNode") -> Any:
        return span_node.name


class ServiceAgg(AbstractAggregation):
    """A service in the trace tree."""

    agg_display_name = "服务"

    @classmethod
    def get_value_from_span_node(cls, span_node: "SpanNode") -> Any:
        return span_node.service_name


class SourceAgg(AbstractAggregation):
    """A source in the trace tree."""

    agg_display_name = "数据来源"

    @classmethod
    def get_value_from_span_node(cls, span_node: "SpanNode") -> Any:
        return span_node.source_name


class KindAgg(AbstractAggregation):
    """A kind in the trace tree."""

    agg_display_name = "Span类型"

    @classmethod
    def get_value_from_span_node(cls, span_node: "SpanNode") -> Any:
        return span_node.kind

    @property
    def display_name(self) -> str:
        return SpanKind.get_label_by_key(self.name)


class TreeTravelPolicy(str, Enum):
    """Policy for tree travel."""

    pre_order = "pre_order"

    @classmethod
    def default(cls):
        return cls.pre_order


@dataclass
class SpanNode:
    """A node in the trace tree."""

    id: str
    config: TreeBuildingConfig
    details: dict = field(default_factory=dict)

    is_root: bool = False
    children: List["SpanNode"] = field(default_factory=list)
    parent: Optional["SpanNode"] = None
    # used to determine index in siblings
    index_refer: int = -1
    # whether the span is a virtual return span
    virtual_return: bool = False
    virtual_self: Optional["SpanNode"] = None

    # tree back ref
    _tree_ref: "ReferenceType[TraceTree]" = None

    # whether children have error
    children_have_error: bool = False

    parallel: Optional[Parallel] = None
    # parallels in children
    children_parallels: List[Parallel] = field(default_factory=list)
    _children_parallel_candidate: Optional[Parallel] = None

    # extra info, injected by upper level
    extra_info: dict = field(default_factory=dict)

    group: Optional[Group] = None
    # groups in children
    children_groups: List[Group] = field(default_factory=list)
    _children_group_candidates: List[Group] = field(default_factory=list)

    _children_maps: Dict[tuple, List["SpanNode"]] = field(default_factory=lambda: defaultdict(list))

    def __repr__(self):
        return f"{self.details[OtlpKey.SPAN_NAME]}-{self.details[OtlpKey.RESOURCE][ResourceAttributes.SERVICE_NAME]}"

    def __str__(self):
        return repr(self)

    def __eq__(self, other: "SpanNode"):
        return self.id == other.id

    @property
    def level(self) -> int:
        """Level of the node in the tree."""
        if self.is_root:
            return 0
        return self.parent.level + 1

    @property
    def index(self) -> int:
        if self.is_root:
            return self._tree_ref().roots.index(self)

        if self.parent is None:
            return -1

        return self.parent.children.index(self)

    @property
    def parallel_path(self) -> List[Parallel]:
        """Parallel path from root to current node."""
        adding = [self.parallel] if self.parallel else []

        if self.is_root:
            return adding

        return self.parent.parallel_path + adding

    @property
    def unique_together(self) -> tuple:
        # TODO: more attributes should be considered
        return (
            self.details[OtlpKey.SPAN_NAME],
            self.details[OtlpKey.RESOURCE][ResourceAttributes.SERVICE_NAME],
        )

    @property
    def value(self) -> int:
        return self.details[OtlpKey.ELAPSED_TIME]

    @property
    def start_and_end(self) -> Tuple[int, int]:
        """Start and end timestamp of the group."""
        if not self.children:
            return self.details[OtlpKey.START_TIME], self.details[OtlpKey.END_TIME]

        start = min([m.details[OtlpKey.START_TIME] for m in self.children])
        end = max([m.details[OtlpKey.END_TIME] for m in self.children])
        return start, end

    @property
    def absolute_duration(self) -> int:
        """Absolute duration of the group."""
        start, end = self.start_and_end
        return end - start

    @property
    def name(self):
        return self.details[OtlpKey.SPAN_NAME]

    @property
    def service_name(self) -> str:
        return self.details[OtlpKey.RESOURCE][ResourceAttributes.SERVICE_NAME]

    @property
    def source_name(self) -> str:
        return self.details[OtlpKey.RESOURCE].get(ResourceAttributes.TELEMETRY_SDK_NAME, "")

    @property
    def kind(self) -> str:
        return self.details[OtlpKey.KIND]

    @property
    def is_relation_ready(self) -> bool:
        if self.is_root:
            return True

        return bool(self.parent) and bool(self.children)

    @property
    def has_error(self) -> bool:
        """Whether the span has error."""
        return self.details[OtlpKey.STATUS]["code"] == StatusCode.ERROR.value

    @property
    def descendants(self) -> List["SpanNode"]:
        """descendants.

        Only call after tree is ready because it will cache the result.
        """
        all_children = []
        for child in self.children:
            all_children.append(child)
            all_children.extend(child.descendants)

        return all_children

    @classmethod
    def from_raw(cls, span: dict, config: TreeBuildingConfig) -> "SpanNode":
        node = SpanNode(id=span[OtlpKey.SPAN_ID], config=config, details=span, index_refer=span[OtlpKey.START_TIME])
        node._children_parallel_candidate = Parallel.from_parent(node, config)
        node._children_group_candidate = Group.from_parent(node, config)
        return node

    @classmethod
    def make_root(cls, span: dict, config: TreeBuildingConfig) -> "SpanNode":
        root = cls.from_raw(span, config)
        root.is_root = True
        return root

    def to_virtual_return(self) -> "SpanNode":
        """Create a virtual return span node."""

        return SpanNode(
            id=self.id,
            config=self.config,
            details=self.details,
            is_root=self.is_root,
            children=self.children,
            parent=self.parent,
            index_refer=self.details[OtlpKey.END_TIME],
            parallel=self.parallel,
            virtual_return=True,
        )

    def add_child(self, child: "SpanNode"):
        """Add a child node to the current node."""

        # find the index to insert the child
        index = len(self.children)
        # Q: Why we choose to insert the child in the reversed order?
        # A: Because the children are tended to be sorted by start time, and we want to keep the order.
        #  So we insert the child from the end of the list.
        for s in range(index - 1, -1, -1):
            c = self.children[s]
            if c.index_refer <= child.index_refer:
                index = s + 1
                break
            else:
                index = s

        child.parent = self
        if child.has_error:
            self.children_have_error = True

        self.children.insert(index, child)
        self._children_maps[child.unique_together].append(child)

        if self.config.with_virtual_return:
            # find the index to insert the virtual return
            virtual_return_child = child.to_virtual_return()
            virtual_index = len(self.children) - 1
            # in most cases, the former end_time should be less than the later start_time
            # if not, means parallel span exists, which we consider as rare case
            # so search the index from the end of the list
            # TODO: too many parallels would cause performance issue
            for i in range(len(self.children) - 1, -1, -1):
                if self.children[i].index_refer < virtual_return_child.index_refer:
                    virtual_index = i + 1
                    break
                else:
                    virtual_index = i

            virtual_return_child.parent = self
            self.children.insert(virtual_index, virtual_return_child)
            child.virtual_self = virtual_return_child

        if self.config.with_parallel_detection:
            if not self._children_parallel_candidate.try_add_and_validate(child):
                if (
                    len(self._children_parallel_candidate.candidates)
                    < self._children_parallel_candidate.min_valid_members
                ):
                    self._children_parallel_candidate.invalidate()
                    # invalidate would clear candidates, this new node should be added for next round
                    self._children_parallel_candidate.try_add_and_validate(child)
                else:
                    self._children_parallel_candidate.promote("parallel")

            # candidate is ready, start a new one
            if self._children_parallel_candidate.valid:
                self.children_parallels.append(self._children_parallel_candidate)
                self._children_parallel_candidate = Parallel.from_parent(self, self.config)
                self._children_parallel_candidate.try_add_and_validate(child)

    def grouping(self, child: "SpanNode", group_class: Optional[Type] = None):
        if self.config.group_ignore_sequence:
            self._grouping_without_sequence(child, group_class)
        else:
            self._grouping_in_sequence(child, group_class)

    def _grouping_in_sequence(self, child: "SpanNode", group_class: Optional[Type[Group]] = None):
        """Grouping spans in sequence."""
        group_class = group_class or Group
        if not self._children_group_candidates:
            new_candidate = group_class.from_parent(self, self.config)
            new_candidate.try_add_and_validate(child)
            self._children_group_candidates = [new_candidate]
            return

        _candidate = self._children_group_candidates[0]

        # trying to add child into the latest candidate
        if not _candidate.try_add_and_validate(child):
            if len({x.id for x in _candidate.candidates}) < _candidate.min_valid_members:
                # new child not added, and the candidate is not ready
                _candidate.invalidate()
                # invalidate would clear candidates, this new node should be added for next round
                _candidate.try_add_and_validate(child)
            else:
                # new child not added, but the candidate is ready
                _candidate.promote("group")

        # candidate is ready, start a new one
        if _candidate.valid:
            self.children_groups.append(_candidate)
            new_candidate = group_class.from_parent(self, self.config)
            new_candidate.try_add_and_validate(child)
            self._children_group_candidates = [new_candidate]

    def _grouping_without_sequence(self, child: "SpanNode", group_class: Optional[Type] = None):
        """Grouping spans without sequence."""
        group_class = group_class or Group
        added_to_existed = False
        for c in self._children_group_candidates:
            if c.try_add_and_validate(child):
                added_to_existed = True

        if not added_to_existed:
            group = group_class.from_parent(self, self.config)
            group.try_add_and_validate(child)
            # candidates will be finalized after all children are added
            self._children_group_candidates.append(group)

    def finalize_candidates(self):
        """Finalize the candidates.

        This method should be called after all children are added.
        """
        if self._children_parallel_candidate:
            self._children_parallel_candidate.finalize(ref_field="parallel")
            if self._children_parallel_candidate.valid:
                self.children_parallels.append(self._children_parallel_candidate)

        for c in self._children_group_candidates:
            c.finalize(ref_field="group")
            if c.valid:
                self.children_groups.append(c)

    def find_similar_child(self, start_index: int, other_child: "SpanNode") -> Optional["SpanNode"]:
        """Find a similar child node after the given index.

        A -> ["HTTP GET service-A", "SELECT service-A", "HTTP POST service-B"]
        B -> ["HTTP GET service-A", "HTTP POST service-B", "SELECT service-A"]

        Diff -> [
            (found)"HTTP GET service-A",
            (new)"HTTP POST service-B",
            (found)"SELECT service-A",
            (removed)"HTTP POST service-B"
        ]
        """

        children = self._children_maps[other_child.unique_together]
        for child in children:
            if child.index >= start_index:
                return child

        return None


@dataclass
class TraceTree:
    """A trace tree with multiple roots."""

    config: TreeBuildingConfig = field(default_factory=TreeBuildingConfig.default)
    roots: List[SpanNode] = field(default_factory=list)
    _roots_map: Dict[tuple, List[SpanNode]] = field(default_factory=lambda: defaultdict(list))

    # id -> node, for quick access
    nodes_map: Dict[str, SpanNode] = field(default_factory=dict)
    # parallel id -> parallel, for quick access
    parallels_map: Dict[str, Parallel] = field(default_factory=dict)

    # Aggregations
    names_map: Dict[str, SpanNameAgg] = field(default_factory=dict)
    services_map: Dict[str, ServiceAgg] = field(default_factory=dict)
    sources_map: Dict[str, SourceAgg] = field(default_factory=dict)
    kinds_map: Dict[str, KindAgg] = field(default_factory=dict)

    _aggregations: Dict[str, Tuple[dict, Type[AbstractAggregation]]] = field(default_factory=dict)

    def __post_init__(self):
        self._aggregations = {
            "name": (self.names_map, SpanNameAgg),
            "service": (self.services_map, ServiceAgg),
            "source": (self.sources_map, SourceAgg),
            "kind": (self.kinds_map, KindAgg),
        }

    def __str__(self):
        return f"TraceTree({self.roots})"

    @property
    def is_ready(self) -> bool:
        return bool(self.roots)

    @property
    def spans_count(self) -> int:
        return len(self.nodes_map)

    # ------
    # Building
    # ------
    def create_node(
        self,
        span: dict,
        all_spans_map: Dict[str, dict],
        config: TreeBuildingConfig,
    ) -> SpanNode:
        """[Deprecated] Create a node from a span.
        Because of recursive call, this method is limited when the trace is very deep.
        """
        parent_id = span[OtlpKey.PARENT_SPAN_ID]
        this_id = span[OtlpKey.SPAN_ID]
        if this_id in self.nodes_map:
            return self.nodes_map[this_id]

        if parent_id not in all_spans_map:
            root = SpanNode.make_root(span, config)
            self.nodes_map[root.id] = root
            self.add_aggregations(root)
            return root

        if parent_id not in self.nodes_map:
            parent_node = self.create_node(all_spans_map[parent_id], all_spans_map, config)
        else:
            parent_node = self.nodes_map[parent_id]

        node = SpanNode.from_raw(span, config)
        parent_node.add_child(node)
        self.nodes_map[node.id] = node
        self.add_aggregations(node)

        return node

    def create_nodes(self, all_spans_map: Dict[str, dict], config: TreeBuildingConfig):
        """Create nodes from spans."""
        needing_parents = defaultdict(list)
        for span in all_spans_map.values():
            parent_id = span[OtlpKey.PARENT_SPAN_ID]

            # root's parent_id is empty
            if parent_id not in all_spans_map or parent_id == span["span_id"]:
                root = SpanNode.make_root(span, config)
                self.add_root(root, config)

                # if this node is other's parent, and needs to be added
                for child in needing_parents[root.id]:
                    root.add_child(child)

                continue

            node = SpanNode.from_raw(span, config)
            self.add_node(node)
            if parent_id not in self.nodes_map:
                # parent has not been added
                needing_parents[parent_id].append(node)
            else:
                if node.id != parent_id:
                    # parent already added
                    self.nodes_map[parent_id].add_child(node)

            # if this node is other's parent, and needs to be added
            for child in needing_parents[node.id]:
                if child.id != node.id:
                    node.add_child(child)

    def add_aggregations(self, node: SpanNode):
        for agg_type, (agg_map, agg_cls) in self._aggregations.items():
            value = agg_cls.get_value_from_span_node(node)

            if value in agg_map:
                agg_map[value].add(node)
                continue

            agg_obj = agg_cls(name=value, members=[node])
            agg_map[value] = agg_obj

    @property
    def aggregations(self) -> dict:
        return self._aggregations

    @classmethod
    def from_raw(
        cls, traces: List[Dict], config: TreeBuildingConfig = TreeBuildingConfig.default(), force_sort: bool = False
    ) -> "TraceTree":
        """Build a FlameTree from trace data."""
        if not traces:
            raise ValueError("Can not build tree from empty traces")

        # make sure traces is sorted by start time
        # which is required by the tree building algorithm
        if force_sort:
            traces.sort(key=lambda x: x[OtlpKey.START_TIME])

        all_spans_map: Dict[str, dict] = {}
        for span in traces:
            all_spans_map[span[OtlpKey.SPAN_ID]] = span

        _tree = TraceTree(config=config)
        _tree.create_nodes(all_spans_map, config)

        if not _tree.is_ready:
            raise Exception("trace tree is not ready, roots missing")

        return _tree

    def find_similar_root(self, start_index: int, other_root: "SpanNode") -> Optional["SpanNode"]:
        """Find a similar root after the given index.

        A -> ["HTTP GET service-A", "SELECT service-A", "HTTP POST service-B"]
        B -> ["HTTP GET service-A", "HTTP POST service-B", "SELECT service-A"]

        Diff -> [
            (found)"HTTP GET service-A",
            (new)"HTTP POST service-B",
            (found)"SELECT service-A",
            (removed)"HTTP POST service-B"
        ]
        """

        for root in self._roots_map[other_root.unique_together]:
            if root.index >= start_index:
                return root

        return None

    def add_node(self, node: "SpanNode"):
        """Add node"""
        self.nodes_map[node.id] = node
        self.add_aggregations(node)

    def add_root(self, root: "SpanNode", config: TreeBuildingConfig):
        """Add root"""
        index = len(self.roots)

        for s in range(index - 1, -1, -1):
            c = self.roots[s]
            if c.index_refer <= root.index_refer:
                index = s + 1
                break
            else:
                index = s

        self.roots.insert(index, root)
        self._roots_map[root.unique_together].append(root)
        # NOTE: only root owns a tree ref
        # use weak ref for saving memory
        # maybe there is a better way to do this
        root._tree_ref = weak_ref(self)

        self.nodes_map[root.id] = root
        self.add_aggregations(root)

        if config.with_virtual_return:
            # find the index to insert the virtual return
            virtual_return_child = root.to_virtual_return()
            virtual_index = index + 1
            for i, s in enumerate(self.roots[index + 1 :]):
                if s.index_refer > virtual_return_child.index_refer:
                    virtual_index += i
                    break
            virtual_return_child.parent = self
            self.roots.insert(virtual_index, virtual_return_child)

    def build_extras(self, return_as_list: bool = True) -> Optional[list]:
        """Build extras for the tree by travelling the tree.

        Q: Why do we build extras by travelling instead build them during building of tree ?
        A: Because like Group need to build after all children are added.

        :param return_as_list: Return as list or not.
        """

        if not self.is_ready:
            raise ValueError("Can not call build_extras when tree is not ready yet.")

        processed_nodes = set()

        def build_node_extras(node: SpanNode):
            """Building node extras."""
            if node.id in processed_nodes:
                return []

            processed_nodes.add(node.id)
            for child in node.children:
                build_node_extras(child)

                if self.config.with_group and self.spans_count >= self.config.min_group_spans_count:
                    node.grouping(child)

            node.finalize_candidates()

            return node.children

        nodes = []
        for root in self.roots:
            nodes.extend(build_node_extras(root))

        if return_as_list:
            return nodes

    # ------
    # Accesses
    # ------
    def get_node_by_id(self, span_id: str) -> Optional[SpanNode]:
        """Get node by span id."""
        return self.nodes_map.get(span_id)

    # ------
    # Travels
    # ------
    def _to_pre_order_tree_list(self, node: SpanNode) -> List[SpanNode]:
        """Convert to pre-order tree list internally."""

        result = []
        for child in node.children:
            if not self.config.with_virtual_return and child.virtual_return:
                continue

            # no matter candidates detection is enabled or not, finalize is safe for all cases
            child.finalize_candidates()
            result.append(child)

            if not child.virtual_return:
                result.extend(self._to_pre_order_tree_list(child))

        return result

    def to_pre_order_tree_list(self) -> List[SpanNode]:
        """Convert to pre-order tree list."""

        result = []
        for root in self.roots:
            if not self.config.with_virtual_return and root.virtual_return:
                continue

            root.finalize_candidates()
            result.append(root)

            if not root.virtual_return:
                result.extend(self._to_pre_order_tree_list(root))

        return result
