"""Static, configuration-bound references for notification templates."""

import re
from collections import defaultdict

from elasticsearch_dsl import AttrDict
from jinja2 import Environment, nodes
from jinja2.exceptions import SecurityError
from jinja2.visitor import NodeTransformer


class RefValueTemplateError(SecurityError):
    pass


def match_reference(reference, names):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", reference):
        raise RefValueTemplateError(f"invalid named output reference: {reference}")
    names = set(names)
    if reference in names:
        return reference
    matches = [name for name in names if name.lower() == reference.lower()]
    if len(matches) != 1:
        reason = "ambiguous" if matches else "unconfigured"
        raise RefValueTemplateError(f"{reason} named output reference: {reference}")
    return matches[0]


def output_references(config):
    return [output["reference_name"] for output in (config or {}).get("output_list", [])]


def hide_reference_containers(value):
    """Keep raw event dictionaries usable without exposing their snapshot containers."""
    if isinstance(value, AttrDict):
        value = value.to_dict()
    if isinstance(value, dict):
        projected = {
            key: hide_reference_containers(child)
            for key, child in value.items()
            if key not in {"ref_values", "_ref_values_"}
        }
        return defaultdict(value.default_factory, projected) if isinstance(value, defaultdict) else projected
    if isinstance(value, list | tuple):
        projected = [hide_reference_containers(child) for child in value]
        return tuple(projected) if isinstance(value, tuple) else projected
    return value


def reference_leaf(node):
    parts = []
    while isinstance(node, nodes.Getattr):
        parts.append(node.attr)
        node = node.node
    if isinstance(node, nodes.Name) and node.name == "alarm" and len(parts) == 3:
        field, reference, root = parts
        if root == "ref_values" and field in {"value", "state"}:
            return reference, field
    return None


class _ReferenceTransformer(NodeTransformer):
    def __init__(self, resolve):
        self.resolve = resolve

    def visit_Output(self, node, *args, **kwargs):
        for index, child in enumerate(node.nodes):
            leaf = reference_leaf(child)
            if leaf:
                node.nodes[index] = nodes.Const(self.resolve(*leaf), lineno=child.lineno)
        return self.generic_visit(node, *args, **kwargs)

    def visit_Getattr(self, node, *args, **kwargs):
        if node.attr == "ref_values":
            self.fail()
        return self.generic_visit(node, *args, **kwargs)

    def visit_Getitem(self, node, *args, **kwargs):
        if isinstance(node.arg, nodes.Const) and node.arg.value == "ref_values":
            self.fail()
        return self.generic_visit(node, *args, **kwargs)

    def visit_Call(self, node, *args, **kwargs):
        if (
            isinstance(node.node, nodes.Getattr)
            and node.node.attr == "get"
            and node.args
            and isinstance(node.args[0], nodes.Const)
            and node.args[0].value == "ref_values"
        ):
            self.fail()
        return self.generic_visit(node, *args, **kwargs)

    def visit_Filter(self, node, *args, **kwargs):
        if node.name == "attr" and node.args:
            if isinstance(node.args[0], nodes.Const) and node.args[0].value == "ref_values":
                self.fail()
            if (
                isinstance(node.node, nodes.Name)
                and node.node.name == "alarm"
                and not isinstance(node.args[0], nodes.Const)
            ):
                self.fail()
        for keyword in node.kwargs:
            if keyword.key == "attribute" and isinstance(keyword.value, nodes.Const):
                if "ref_values" in str(keyword.value.value).split("."):
                    self.fail()
        return self.generic_visit(node, *args, **kwargs)

    @staticmethod
    def fail():
        raise RefValueTemplateError("only {{ alarm.ref_values.<reference>.value }} / .state are allowed")


def prepare_ref_value_template(environment, content, resolve):
    return _ReferenceTransformer(resolve).visit(environment.parse(content))


def validate_ref_value_template(content, names=None):
    def resolve(reference, field):
        if names is not None:
            match_reference(reference, names)
        return ""

    prepare_ref_value_template(Environment(extensions=["jinja2.ext.i18n"]), content, resolve)


def snapshot_leaf(snapshot, reference, field):
    entry = snapshot.get(reference) or {}
    if not isinstance(entry, dict):
        entry = {}
    state = entry.get("state", "MISSING")
    if state not in {"SUCCESS", "PARTIAL", "MISSING", "ERROR", "UNSUPPORTED"}:
        state = "MISSING"
    if field == "state":
        return state
    value = entry.get("value") if state in {"SUCCESS", "PARTIAL"} else None
    return value if type(value) in {str, int, float, bool} else "--"
