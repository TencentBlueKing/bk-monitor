"""Offline contract runner: execute production models/resources with ES/CC/Django IO isolated.

Reads stored snapshot JSON from stdin and emits only rendered topology. No SDK,
algorithm, broker or network client is loaded. Private inputs need not be committed.
"""

import ast
import copy
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any


class Content(dict):
    def to_dict(self):
        return copy.deepcopy(self)


class Document(SimpleNamespace):
    def __getitem__(self, key):
        return getattr(self, key)


def environment():
    monitor = Path(__file__).resolve().parents[3]
    module = ModuleType("snapshot_contract")
    sys.modules[module.__name__] = module
    namespace = module.__dict__
    namespace.update(
        dict(
            copy=copy,
            defaultdict=defaultdict,
            dataclass=dataclass,
            field=field,
            asdict=asdict,
            CustomEnum=Enum,
            Any=Any,
            __name__="snapshot_contract",
            _=lambda value: value,
            AlertDocument=SimpleNamespace(get=lambda _: SimpleNamespace(alert_name="stored alert")),
            resource=SimpleNamespace(cc=SimpleNamespace(get_app_by_id=lambda _: SimpleNamespace(name="business"))),
        )
    )
    for path in ("bkmonitor/aiops/incident/graph_snapshot.py", "bkmonitor/aiops/incident/topology_validation.py"):
        exec(compile((monitor / path).read_text(), path, "exec"), namespace)
    sources = (
        ("constants/alert.py", {"EventStatus"}),
        (
            "constants/incident.py",
            {
                "IncidentGraphEdgeType",
                "IncidentGraphEdgeEventType",
                "IncidentGraphEdgeEventDirection",
                "IncidentGraphComponentType",
            },
        ),
        ("bkmonitor/aiops/incident/models.py", None),
        ("packages/monitor_web/incident/resources.py", {"IncidentBaseResource", "IncidentTopologyResource"}),
    )
    for path, names in sources:
        for node in ast.parse((monitor / path).read_text()).body:
            if not isinstance(node, ast.ClassDef) or names is not None and node.name not in names:
                continue
            if path.endswith("resources.py"):
                node.bases = (
                    [] if node.name == "IncidentBaseResource" else [ast.Name(id="IncidentBaseResource", ctx=ast.Load())]
                )
                node.body = [
                    method for method in node.body if isinstance(method, ast.FunctionDef) and method.name != "__init__"
                ]
            module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
            exec(compile(module, path, "exec", flags=__import__("__future__").annotations.compiler_flag), namespace)
    return namespace


def render(payload):
    ns = environment()
    original = copy.deepcopy(payload)
    snapshots = [
        Document(
            id=index, incident_id=1, fpp_snapshot_id=f"stored-{index}", create_time=index + 1, content=Content(content)
        )
        for index, content in enumerate(payload["snapshots"])
    ]
    empty = Document(fpp_snapshot_id="fpp:None", content=Content())
    incident = Document(
        incident_id=1, snapshot=snapshots[-1] if snapshots else empty, feedback=SimpleNamespace(incident_root=None)
    )
    ns["IncidentDocument"] = SimpleNamespace(get=lambda _: incident)
    ns["IncidentSnapshotDocument"] = SimpleNamespace(list_by_incident_id=lambda *args: snapshots)
    resource = ns["IncidentTopologyResource"]()
    modes = {}
    for name, only_diff, start in (("history", True, 1), ("full", False, 1), ("latest", True, None)):
        modes[name] = resource.perform_request(
            {
                "id": 1,
                "bk_biz_id": 1,
                "only_diff": only_diff,
                "start_time": start,
                "auto_aggregate": payload.get("auto_aggregate", False),
            }
        )
    assert payload == original, "stored input was mutated"
    assert all(snapshot.content == original["snapshots"][index] for index, snapshot in enumerate(snapshots)), (
        "stored document was mutated"
    )
    return modes


if __name__ == "__main__":
    print(json.dumps(render(json.load(sys.stdin)), ensure_ascii=False))
