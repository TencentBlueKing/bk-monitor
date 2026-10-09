"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""Direct command tests with loopback HTTP; no application bootstrap or live services."""

import json
import os
import sys
import threading
import time
import types
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock

import pytest
from django.conf import settings
from monitor_web.management.commands import repair_grafana_folder_editor_permission as repair


def grant(role="Viewer", permission="View", inherited=False):
    return {
        "roleName": f"managed:builtins:{role.lower()}:permissions",
        "builtInRole": role,
        "permission": permission,
        "actions": sorted(repair.PERMISSION_ACTIONS.get(permission, {"custom:action"})),
        "isManaged": not inherited,
        "isInherited": inherited,
        "isServiceAccount": False,
    }


def context(url="http://127.0.0.1:3000", uids=None):
    return {
        "schema": 1,
        "tenant_id": "test",
        "business_id": 2,
        "org_id": 1,
        "grafana_url": url,
        "folder_uids": uids or ["sample"],
    }


def approval(plan, report):
    now = datetime.now(timezone.utc)
    return {
        "context": plan["context"],
        "plan_sha256": repair.digest(plan),
        "executor_uid": os.geteuid(),
        "reference": "fixture-approval",
        "report_path": str(report.absolute()),
        "window": {
            "reference": "fixture-window",
            "starts_at": (now - timedelta(minutes=1)).isoformat(),
            "ends_at": (now + timedelta(minutes=1)).isoformat(),
        },
        "folders": [
            {
                "uid": uid,
                "owner": "fixture-owner",
                "reference": "fixture-scope",
                "role": "Editor",
                "permission": "Edit",
                "all_editor_contents_shared": True,
            }
            for uid in plan["context"]["folder_uids"]
        ],
    }


@pytest.mark.parametrize(
    "role,permission,inherited,state",
    [
        ("Editor", "Edit", False, "NOOP"),
        ("Editor", "Admin", False, "NOOP"),
        ("Editor", "Edit", True, "NOOP"),
        ("Editor", "Admin", True, "NOOP"),
        ("Editor", "View", False, "CONFLICT"),
        ("Editor", "View", True, "MISSING"),
        ("Viewer", "View", False, "MISSING"),
    ],
)
def test_classification(role, permission, inherited, state):
    assert repair.classify(repair.normalize_acl([grant(role, permission, inherited)])) == state


@pytest.mark.parametrize(
    "rows",
    [
        None,
        [None],
        [{"permission": "View"}],
        [grant(permission="Custom")],
        [dict(grant(), actions=[None])],
        [dict(grant(), actions=["folders:read"])],
        [dict(grant(), isManaged="true")],
        [dict(grant(), isInherited=True)],
        [dict(grant(), builtInRole="")],
        [dict(grant("Editor", "Admin"), builtInRole="")],
        [dict(grant(), userId=1)],
        [dict(grant(), userId=True)],
        [dict(grant(), roleName="unknown")],
        [dict(grant(), isManaged=False)],
        [grant(), grant()],
    ],
)
def test_malformed_acl_is_not_missing(rows):
    with pytest.raises((ValueError, TypeError)):
        repair.normalize_acl(rows)


@pytest.mark.parametrize(
    "field,value",
    [
        ("folder_uids", []),
        ("folder_uids", ["a", "a"]),
        ("folder_uids", ["a", "b", "c", "d"]),
        ("folder_uids", ["../escape"]),
        ("org_id", True),
        ("grafana_url", "http://user:password@example.com"),
    ],
)
def test_invalid_context(field, value):
    with pytest.raises(ValueError):
        repair.validate_context({**context(), field: value})


def test_protected_file_validation(tmp_path):
    path = tmp_path / "approval.json"
    path.write_text('{"approved":true}')
    path.chmod(0o600)
    assert repair.read_json(path, protected=True) == {"approved": True}
    path.chmod(0o644)
    with pytest.raises(ValueError):
        repair.read_json(path, protected=True)
    path.chmod(0o600)
    link = tmp_path / "symlink.json"
    link.symlink_to(path)
    with pytest.raises(OSError):
        repair.read_json(link, protected=True)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError):
        repair.read_json(fifo, protected=True)


@pytest.mark.parametrize(
    "field,value", [("executor_uid", -1), ("plan_sha256", "wrong"), ("reference", ""), ("report_path", "/different")]
)
def test_approval_binding(tmp_path, field, value):
    plan = {"context": context(), "successful": True, "results": []}
    record = approval(plan, tmp_path / "run.jsonl")
    record[field] = value
    with pytest.raises(ValueError):
        repair.validate_approval(record, plan, tmp_path / "run.jsonl")


def test_approval_does_not_enable_viewer_or_unapproved_scope(tmp_path):
    plan = {"context": context(), "successful": True, "results": []}
    for key, value in (("role", "Viewer"), ("owner", ""), ("all_editor_contents_shared", False)):
        record = approval(plan, tmp_path / "run.jsonl")
        record["folders"][0][key] = value
        with pytest.raises(ValueError):
            repair.validate_approval(record, plan, tmp_path / "run.jsonl")


def test_explicit_utc_active_window(tmp_path):
    plan = {"context": context(), "successful": True, "results": []}
    record = approval(plan, tmp_path / "run.jsonl")
    repair.check_window(record)
    for key, value in (
        ("ends_at", "2000-01-01T00:00:00Z"),
        ("starts_at", "2100-01-01T00:00:00Z"),
        ("starts_at", "2000-01-01T00:00:00"),
    ):
        with pytest.raises(ValueError):
            repair.check_window({**record, "window": {**record["window"], key: value}})


@pytest.fixture
def api_server():
    state = {
        "calls": [],
        "acls": {uid: [grant()] for uid in ("one", "two", "three")},
        "post_fail": False,
        "post_fail_uid": None,
        "post_delay": 0,
        "health_delay": 0,
        "folder_delays": {},
        "drip": False,
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, value, status=200):
            encoded = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            try:
                if state["drip"]:
                    for byte in encoded:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.03)
                else:
                    self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            state["calls"].append(("GET", self.path, time.monotonic()))
            if self.path == "/api/health":
                time.sleep(state["health_delay"])
                return self.respond({"version": "10.4.10"})
            if self.path.endswith("/description"):
                return self.respond({"assignments": {"builtInRoles": True}, "permissions": ["View", "Edit", "Admin"]})
            uid = self.path.rsplit("/", 1)[-1]
            if self.path.startswith("/api/access-control/"):
                return self.respond(state["acls"][uid])
            time.sleep(state["folder_delays"].get(uid, 0))
            return self.respond({"uid": uid, "id": ("one", "two", "three").index(uid) + 1, "title": uid})

        def do_POST(self):
            state["calls"].append(("POST", self.path, time.monotonic()))
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body == {"permission": "Edit"} and self.path.endswith("/builtInRoles/Editor")
            uid = self.path.split("/")[-3]
            if state["post_fail"] or state["post_fail_uid"] == uid:
                return self.respond({"message": "failure"}, 500)
            state["acls"][uid].append(grant("Editor", "Edit"))
            time.sleep(state["post_delay"])
            return self.respond({"message": "updated"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", state
    server.shutdown()
    server.server_close()
    thread.join()


def targets(uids):
    return [{"folder": {"uid": uid, "id": ("one", "two", "three").index(uid) + 1}, "children": []} for uid in uids]


def preview(tmp_path, url, uids=None):
    scope = context(url, uids or ["one"])
    return repair.run_network(
        scope, targets(scope["folder_uids"]), tmp_path / "preview.jsonl", budget=10, interval=0.01
    )


def test_http_counts_preservation_noop_and_report_not_reused(tmp_path, api_server):
    url, state = api_server
    plan = preview(tmp_path, url, ["one", "two", "three"])
    assert plan["successful"] and len(state["calls"]) == 8
    report = tmp_path / "apply.jsonl"
    state["calls"].clear()
    result = repair.run_network(
        plan["context"],
        targets(["one", "two", "three"]),
        report,
        plan,
        approval(plan, report),
        budget=10,
        interval=0.01,
    )
    assert result["successful"] and all(item["state"] == "CONFIRMED" for item in result["results"])
    assert len(state["calls"]) == 14 and sum(call[0] == "POST" for call in state["calls"]) == 3
    assert report.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        repair.run_network(plan["context"], targets(["one", "two", "three"]), report, plan, approval(plan, report))
    state["calls"].clear()
    repeated = repair.run_network(
        plan["context"],
        targets(["one", "two", "three"]),
        tmp_path / "noop.jsonl",
        plan,
        approval(plan, tmp_path / "noop.jsonl"),
        budget=10,
        interval=0.01,
    )
    assert repeated["successful"] and all(item["state"] == "NOOP" for item in repeated["results"])
    assert len(state["calls"]) == 8 and not any(call[0] == "POST" for call in state["calls"])


def test_unknown_stops_remaining_targets_without_replay(tmp_path, api_server):
    url, state = api_server
    plan = preview(tmp_path, url, ["one", "two"])
    state["post_fail"] = True
    state["calls"].clear()
    report = tmp_path / "unknown.jsonl"
    result = repair.run_network(
        plan["context"], targets(["one", "two"]), report, plan, approval(plan, report), budget=10, interval=0.01
    )
    assert not result["successful"]
    assert [item["state"] for item in result["results"]] == ["UNKNOWN", "NOT_ATTEMPTED"]
    assert sum(call[0] == "POST" for call in state["calls"]) == 1


def test_drift_has_no_post(tmp_path, api_server):
    url, state = api_server
    plan = preview(tmp_path, url)
    state["acls"]["one"].append({**grant(), "builtInRole": "", "roleName": "managed:users:7:permissions", "userId": 7})
    state["calls"].clear()
    report = tmp_path / "drift.jsonl"
    result = repair.run_network(
        plan["context"], targets(["one"]), report, plan, approval(plan, report), budget=10, interval=0.01
    )
    assert not result["successful"] and not any(call[0] == "POST" for call in state["calls"])
    assert result["results"][0]["uid"] == "one" and result["results"][0]["reason"] == "SCOPE_OR_ACL_DRIFT"


def test_conflict_is_reported_without_post(tmp_path, api_server):
    url, state = api_server
    plan = preview(tmp_path, url)
    state["acls"]["one"].append(grant("Editor", "View"))
    state["calls"].clear()
    report = tmp_path / "conflict.jsonl"
    result = repair.run_network(
        plan["context"], targets(["one"]), report, plan, approval(plan, report), budget=10, interval=0
    )
    assert not result["successful"] and result["results"][0]["state"] == "CONFLICT"
    assert not any(call[0] == "POST" for call in state["calls"])


def test_partial_success_stops_after_second_unknown(tmp_path, api_server):
    url, state = api_server
    plan = preview(tmp_path, url, ["one", "two", "three"])
    state["post_fail_uid"] = "two"
    state["calls"].clear()
    report = tmp_path / "partial.jsonl"
    result = repair.run_network(
        plan["context"], targets(["one", "two", "three"]), report, plan, approval(plan, report), budget=10, interval=0
    )
    assert not result["successful"]
    assert [item["state"] for item in result["results"]] == ["CONFIRMED", "UNKNOWN", "NOT_ATTEMPTED"]
    assert sum(call[0] == "POST" for call in state["calls"]) == 2


def test_fsync_failure_before_ack_has_no_post(tmp_path, api_server, monkeypatch):
    url, state = api_server
    plan = preview(tmp_path, url)
    state["calls"].clear()

    def fail_fsync(fd):
        raise OSError("fixture disk full")

    monkeypatch.setattr(repair.os, "fsync", fail_fsync)
    report = tmp_path / "disk-full.jsonl"
    with pytest.raises(OSError):
        repair.run_network(
            plan["context"], targets(["one"]), report, plan, approval(plan, report), budget=10, interval=0.01
        )
    assert not any(call[0] == "POST" for call in state["calls"])


@pytest.mark.parametrize("mode", ["hang", "drip"])
def test_hard_deadline_during_inflight_request(tmp_path, api_server, mode):
    url, state = api_server
    state["health_delay"] = 3 if mode == "hang" else 0
    state["drip"] = mode == "drip"
    started = time.monotonic()
    result = repair.run_network(
        context(url, ["one"]), targets(["one"]), tmp_path / "deadline.jsonl", budget=0.8, interval=0
    )
    assert time.monotonic() - started < 2 and not result["successful"] and state["calls"]
    assert result["results"][0]["state"] == "NOT_ATTEMPTED"


def test_hard_deadline_after_server_write_is_unknown(tmp_path, api_server):
    url, state = api_server
    plan = preview(tmp_path, url)
    state["post_delay"] = 3
    state["calls"].clear()
    report = tmp_path / "late-write.jsonl"
    result = repair.run_network(
        plan["context"], targets(["one"]), report, plan, approval(plan, report), budget=1, interval=0
    )
    assert not result["successful"] and result["results"][0]["state"] == "UNKNOWN"
    assert repair.classify(repair.normalize_acl(state["acls"]["one"])) == "NOOP"
    assert sum(call[0] == "POST" for call in state["calls"]) == 1


def capture_process(monkeypatch, ignore_terminate=False):
    original = repair.multiprocessing.get_context("spawn")
    captured = {}

    def make_process(*args, **kwargs):
        process = original.Process(*args, **kwargs)
        captured["process"] = process
        if ignore_terminate:
            original_kill = type(process).kill

            def kill(instance):
                captured["killed"] = True
                original_kill(instance)

            monkeypatch.setattr(type(process), "terminate", lambda _: None)
            monkeypatch.setattr(type(process), "kill", kill)
        return process

    monkeypatch.setattr(
        repair.multiprocessing, "get_context", lambda _: types.SimpleNamespace(Pipe=original.Pipe, Process=make_process)
    )
    return captured


@pytest.mark.parametrize("slow_message", ["PENDING", "CONFIRMED"])
def test_journal_io_does_not_block_network_supervision(tmp_path, api_server, monkeypatch, slow_message):
    url, state = api_server
    plan = preview(tmp_path, url, ["one", "two"])
    state["folder_delays"]["two"] = 3
    state["calls"].clear()
    captured = capture_process(monkeypatch)
    original_fsync = repair.os.fsync
    fsync_calls = 0

    def slow_fsync(fd):
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == (1 if slow_message == "PENDING" else 2):
            time.sleep(1.1)
            assert not captured["process"].is_alive()
        original_fsync(fd)

    monkeypatch.setattr(repair.os, "fsync", slow_fsync)
    report = tmp_path / "slow-journal.jsonl"
    result = repair.run_network(
        plan["context"], targets(["one", "two"]), report, plan, approval(plan, report), budget=0.8, interval=0
    )
    assert not result["successful"] and result["results"][1]["state"] == "NOT_ATTEMPTED"
    posts = [call for call in state["calls"] if call[0] == "POST"]
    if slow_message == "PENDING":
        assert not posts
    else:
        assert len(posts) == 1 and any(call[1] == "/api/folders/two" for call in state["calls"])
        assert result["results"][0]["state"] == "CONFIRMED"


def test_kill_after_terminate_grace(tmp_path, api_server, monkeypatch):
    url, state = api_server
    state["health_delay"] = 3
    captured = capture_process(monkeypatch, ignore_terminate=True)
    started = time.monotonic()
    result = repair.run_network(
        context(url, ["one"]), targets(["one"]), tmp_path / "kill.jsonl", budget=0.5, interval=0
    )
    assert captured["killed"] and not result["successful"] and time.monotonic() - started < 2.2


def test_slow_journal_does_not_restart_kill_grace(tmp_path, api_server, monkeypatch):
    url, state = api_server
    plan = preview(tmp_path, url)
    captured = capture_process(monkeypatch, ignore_terminate=True)
    original_fsync = repair.os.fsync
    first = True

    def slow_fsync(fd):
        nonlocal first
        if first:
            first = False
            time.sleep(1.2)
        original_fsync(fd)

    monkeypatch.setattr(repair.os, "fsync", slow_fsync)
    report = tmp_path / "slow-kill.jsonl"
    started = time.monotonic()
    result = repair.run_network(
        plan["context"], targets(["one"]), report, plan, approval(plan, report), budget=0.8, interval=0
    )
    assert captured["killed"] and not result["successful"] and time.monotonic() - started < 1.95


def test_expired_window_after_pacing_never_posts(tmp_path, api_server):
    url, state = api_server
    record = approval({"context": context()}, tmp_path / "unused.jsonl")
    client = repair.GrafanaHTTP(context(url), interval=0.3)
    try:
        client.request("GET", "/api/health")
        record["window"]["ends_at"] = (datetime.now(timezone.utc) + timedelta(seconds=0.1)).isoformat()
        with pytest.raises(ValueError):
            client.request("POST", "/unused", {}, before_request=lambda: repair.check_window(record))
    finally:
        client.session.close()
    assert len(state["calls"]) == 1


@pytest.fixture
def local_models(monkeypatch):
    dashboard, folder, org = Mock(), Mock(), Mock()
    org.objects.filter.return_value.exists.return_value = True
    folder.objects.filter.return_value.exists.return_value = False
    lookup, children = Mock(), Mock()
    lookup.values.return_value.get.return_value = {"id": 9, "uid": "sample"}
    children.values.return_value = [{"id": 10, "uid": "child"}]
    dashboard.objects.filter.side_effect = [lookup, children]
    models = types.ModuleType("bk_dataview.models")
    models.Dashboard, models.Folder, models.Org = dashboard, folder, org
    tenant = types.ModuleType("bkmonitor.utils.tenant")
    tenant.bk_biz_id_to_bk_tenant_id = Mock(return_value="test")
    monkeypatch.setitem(sys.modules, "bk_dataview.models", models)
    monkeypatch.setitem(sys.modules, "bkmonitor.utils.tenant", tenant)
    return dashboard, folder, org, children, tenant


def test_local_scope_uses_only_exact_org_and_bounded_children(local_models):
    dashboard, folder, org, _, _ = local_models
    assert repair.local_targets(context()) == [
        {"folder": {"id": 9, "uid": "sample"}, "children": [{"id": 10, "uid": "child"}]}
    ]
    org.objects.filter.assert_called_once_with(id=1, name="2")
    folder.objects.filter.assert_called_once_with(org_id=1, parent_uid="sample")
    assert [call.kwargs for call in dashboard.objects.filter.call_args_list] == [
        {"org_id": 1, "uid": "sample", "is_folder": 1},
        {"org_id": 1, "folder_id": 9, "is_folder": 0},
    ]


@pytest.mark.parametrize("invalid", ["tenant", "org", "nested", "over_limit"])
def test_local_scope_rejects_mismatch_nesting_and_over_limit(local_models, invalid):
    _, folder, org, children, tenant = local_models
    if invalid == "tenant":
        tenant.bk_biz_id_to_bk_tenant_id.return_value = "other"
    elif invalid == "org":
        org.objects.filter.return_value.exists.return_value = False
    elif invalid == "nested":
        folder.objects.filter.return_value.exists.return_value = True
    else:
        children.values.return_value = [{"id": n, "uid": str(n)} for n in range(201)]
    with pytest.raises(ValueError):
        repair.local_targets(context())


def test_actual_request_start_rate(api_server):
    url, state = api_server
    client = repair.GrafanaHTTP(context(url))
    try:
        client.request("GET", "/api/health")
        client.request("GET", "/api/health")
    finally:
        client.session.close()
    assert state["calls"][1][2] - state["calls"][0][2] >= 0.95


def test_cli_no_deployment_authorization_never_starts_network(tmp_path, monkeypatch):
    if not settings.configured:
        settings.configure(GRAFANA_URL="http://127.0.0.1:3000")
    monkeypatch.setattr(settings, "GRAFANA_FOLDER_EDITOR_REPAIR_AUTHORIZATION_FILE", "", raising=False)
    called = []
    monkeypatch.setattr(repair, "run_network", lambda *a, **kw: called.append(True))
    with pytest.raises(repair.CommandError):
        repair.Command().handle(
            tenant_id="test",
            business_id=2,
            org_id=1,
            folder_uid=["sample"],
            report=str(tmp_path / "run.jsonl"),
            plan=None,
            apply=True,
        )
    assert not called
