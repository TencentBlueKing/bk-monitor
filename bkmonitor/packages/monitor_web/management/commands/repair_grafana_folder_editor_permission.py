"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""One-shot folder Editor repair, available only from the privileged management CLI.

Preview is read-only. Apply additionally requires a protected approval file selected
by GRAFANA_FOLDER_EDITOR_REPAIR_AUTHORIZATION_FILE in deployment settings. The file
records approval and an exclusive maintenance window; it does not establish that
window. Never connect this command to a request, initializer or recurring task.
CONFIRMED means ACL readback only; verify actual user access before closing the window.
"""

import hashlib
import json
import multiprocessing
import os
import re
import stat
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

MAX_FOLDERS = 3
MAX_CHILDREN = 200
MAX_JSON_BYTES = 1024 * 1024
NETWORK_SECONDS = 60
REAP_SECONDS = 1
REQUEST_INTERVAL = 1
UID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,40}\Z")
# Grafana 10.4.10 folder permissions; reject partial/custom action bundles.
VIEW_ACTIONS = {"folders:read", "dashboards:read", "alert.rules:read", "library.panels:read"}
EDIT_ACTIONS = VIEW_ACTIONS | {
    "folders:write",
    "folders:delete",
    "dashboards:create",
    "dashboards:write",
    "dashboards:delete",
    "alert.rules:create",
    "alert.rules:write",
    "alert.rules:delete",
    "library.panels:create",
    "library.panels:write",
    "library.panels:delete",
}
PERMISSION_ACTIONS = {
    "View": VIEW_ACTIONS,
    "Edit": EDIT_ACTIONS,
    "Admin": EDIT_ACTIONS
    | {
        "folders.permissions:read",
        "folders.permissions:write",
        "dashboards.permissions:read",
        "dashboards.permissions:write",
    },
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_json(path, protected=False):
    flags = os.O_RDONLY | os.O_NONBLOCK
    if protected:
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "geteuid"):
            raise ValueError("protected approval files are unsupported on this platform")
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("input must be a regular file")
        if protected and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError("approval must belong to the executor and have mode 0600")
        data = source.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise ValueError("JSON input exceeds the size limit")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def validate_context(context):
    if set(context) != {"schema", "tenant_id", "business_id", "org_id", "grafana_url", "folder_uids"}:
        raise ValueError("invalid context fields")
    if context["schema"] != 1 or not isinstance(context["tenant_id"], str) or not context["tenant_id"]:
        raise ValueError("invalid schema or tenant")
    if any(type(context[key]) is not int or context[key] <= 0 for key in ("business_id", "org_id")):
        raise ValueError("business and org must be positive integers")
    uids = context["folder_uids"]
    if not isinstance(uids, list) or not 1 <= len(uids) <= MAX_FOLDERS or len(set(uids)) != len(uids):
        raise ValueError("provide one to three distinct folder UIDs")
    if any(not isinstance(uid, str) or not UID_PATTERN.fullmatch(uid) for uid in uids):
        raise ValueError("invalid folder UID")
    url = urlsplit(context["grafana_url"])
    if (
        url.scheme not in ("http", "https")
        or not url.netloc
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("invalid deployment Grafana URL")


def check_window(approval):
    window = approval["window"]
    if not window.get("reference"):
        raise ValueError("exclusive maintenance window reference is required")
    start, end = (datetime.fromisoformat(window[key].replace("Z", "+00:00")) for key in ("starts_at", "ends_at"))
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or start.utcoffset().total_seconds()
        or end.utcoffset().total_seconds()
    ):
        raise ValueError("window timestamps must be explicit UTC")
    if not start <= datetime.now(timezone.utc) < end:
        raise ValueError("maintenance window is not active")


def validate_approval(approval, plan, report):
    if approval.get("context") != plan["context"] or approval.get("plan_sha256") != digest(plan):
        raise ValueError("approval does not match the actual plan and deployment")
    if type(approval.get("executor_uid")) is not int or approval["executor_uid"] != os.geteuid():
        raise ValueError("approval does not authorize this OS executor")
    if not approval.get("reference"):
        raise ValueError("approval reference is required")
    if approval.get("report_path") != str(Path(report).absolute()):
        raise ValueError("the single-use report path must be deployment-approved")
    declarations = approval.get("folders", [])
    if len(declarations) != len(plan["context"]["folder_uids"]):
        raise ValueError("all target folders need an explicit approval")
    approved_uids = []
    for item in declarations:
        if (
            not item.get("owner")
            or not item.get("reference")
            or item.get("role") != "Editor"
            or item.get("permission") != "Edit"
            or item.get("all_editor_contents_shared") is not True
        ):
            raise ValueError("each folder needs owner approval for Editor/Edit sharing")
        approved_uids.append(item["uid"])
    if sorted(approved_uids) != sorted(plan["context"]["folder_uids"]):
        raise ValueError("approved folder set differs from the plan")
    check_window(approval)


def local_targets(context):
    from bk_dataview.models import Dashboard, Folder, Org
    from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id

    if bk_biz_id_to_bk_tenant_id(context["business_id"]) != context["tenant_id"]:
        raise ValueError("business tenant mismatch")
    if not Org.objects.filter(id=context["org_id"], name=str(context["business_id"])).exists():
        raise ValueError("business org mismatch; preview never creates an org")
    targets = []
    for uid in context["folder_uids"]:
        folder = Dashboard.objects.filter(org_id=context["org_id"], uid=uid, is_folder=1).values("id", "uid").get()
        if Folder.objects.filter(org_id=context["org_id"], parent_uid=uid).exists():
            raise ValueError("nested folders are unsupported")
        children = list(
            Dashboard.objects.filter(org_id=context["org_id"], folder_id=folder["id"], is_folder=0).values("id", "uid")[
                : MAX_CHILDREN + 1
            ]
        )
        if len(children) > MAX_CHILDREN:
            raise ValueError("folder exceeds the child limit")
        children.sort(key=lambda child: child["uid"])
        targets.append({"folder": folder, "children": children})
    return targets


def normalize_acl(rows):
    if not isinstance(rows, list):
        raise ValueError("invalid ACL response")
    normalized = []
    subjects = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid ACL row")
        actions = row.get("actions")
        if row.get("permission") not in ("View", "Edit", "Admin") or not isinstance(actions, list) or not actions:
            raise ValueError("unsupported permission or action set")
        if any(not isinstance(action, str) or not action for action in actions):
            raise ValueError("invalid permission actions")
        if set(actions) != PERMISSION_ACTIONS[row["permission"]] or len(actions) != len(set(actions)):
            raise ValueError("unsupported partial or custom action bundle")
        if any(type(row.get(key)) is not bool for key in ("isManaged", "isInherited", "isServiceAccount")):
            raise ValueError("invalid ACL origin flags")
        builtin, user_id, team_id = row.get("builtInRole", ""), row.get("userId", 0), row.get("teamId", 0)
        if (
            builtin not in ("", "Viewer", "Editor", "Admin")
            or type(user_id) is not int
            or type(team_id) is not int
            or user_id < 0
            or team_id < 0
            or sum(bool(value) for value in (builtin, user_id, team_id)) != 1
            or (row["isServiceAccount"] and not user_id)
        ):
            raise ValueError("unknown or conflicting ACL subject")
        role_name = (
            f"managed:builtins:{builtin.lower()}:permissions"
            if builtin
            else f"managed:{'users' if user_id else 'teams'}:{user_id or team_id}:permissions"
        )
        if row["isManaged"] and row["isInherited"]:
            raise ValueError("ACL cannot be both direct and inherited")
        if row["isManaged"] or row["isInherited"]:
            if row.get("roleName") != role_name:
                raise ValueError("ACL subject and managed role disagree")
        elif not (
            builtin == "Admin" and row["permission"] == "Admin" and row.get("roleName") == "" and not row["isInherited"]
        ):
            raise ValueError("unsupported unmanaged ACL subject")
        subject = (builtin, user_id, team_id, row["isInherited"])
        if subject in subjects:
            raise ValueError("duplicate ACL subject")
        subjects.add(subject)
        normalized.append(
            {
                key: row.get(key, default)
                for key, default in (
                    ("roleName", ""),
                    ("userId", 0),
                    ("teamId", 0),
                    ("builtInRole", ""),
                    ("isManaged", False),
                    ("isInherited", False),
                    ("isServiceAccount", False),
                    ("permission", ""),
                )
            }
            | {"actions": sorted(actions)}
        )
    return sorted(normalized, key=lambda row: json.dumps(row, sort_keys=True))


def classify(acl):
    editor = [row for row in acl if row["builtInRole"] == "Editor"]
    if any(row["permission"] in ("Edit", "Admin") for row in editor):
        return "NOOP"
    if any(not row["isInherited"] for row in editor):
        return "CONFLICT"
    return "MISSING"


def verify_added(before, after):
    added = [row for row in after if row["builtInRole"] == "Editor" and not row["isInherited"]]
    others = [row for row in after if row not in added]
    return len(added) == 1 and added[0]["permission"] == "Edit" and others == before


class GrafanaHTTP:
    def __init__(self, context, interval=REQUEST_INTERVAL, deadline=None):
        self.context = context
        self.interval = interval
        self.last_started = 0
        self.deadline = deadline
        self.session = requests.Session()

    def request(self, method, path, body=None, before_request=None):
        time.sleep(max(0, self.last_started + self.interval - time.monotonic()))
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise ValueError("network deadline expired")
        if before_request:
            before_request()
        self.last_started = time.monotonic()
        headers = {"X-WEBAUTH-USER": "admin", "X-Grafana-Org-Id": str(self.context["org_id"])}
        with self.session.request(
            method,
            self.context["grafana_url"].rstrip("/") + path,
            headers=headers,
            json=body,
            timeout=(2, 5),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                raise ValueError(f"Grafana HTTP {response.status_code}")
            raw = response.raw.read(MAX_JSON_BYTES + 1, decode_content=True)
            if len(raw) > MAX_JSON_BYTES:
                raise ValueError("Grafana response exceeds the size limit")
            return json.loads(raw)


def network_worker(channel, context, targets, plan, approval, interval=REQUEST_INTERVAL, deadline=None):
    client = GrafanaHTTP(context, interval, deadline)
    pending = current_uid = None
    reason = "API_PREFLIGHT"
    try:
        if client.request("GET", "/api/health").get("version") != "10.4.10":
            raise ValueError("this maintenance command supports Grafana 10.4.10 only")
        description = client.request("GET", "/api/access-control/folders/description")
        if description.get("assignments", {}).get("builtInRoles") is not True or "Edit" not in description.get(
            "permissions", []
        ):
            raise ValueError("folder builtin role API is unavailable")
        for index, target in enumerate(targets):
            uid = target["folder"]["uid"]
            current_uid, reason = uid, "FOLDER_OR_ACL_VALIDATION"
            remote = client.request("GET", f"/api/folders/{uid}")
            if remote.get("uid") != uid or remote.get("id") != target["folder"]["id"] or remote.get("parentUid"):
                raise ValueError("folder identity or hierarchy mismatch")
            acl = normalize_acl(client.request("GET", f"/api/access-control/folders/{uid}"))
            snapshot = {"local": target, "folder": {key: remote.get(key) for key in ("id", "uid", "title")}, "acl": acl}
            state = classify(acl)
            if plan is None:
                channel.send({"uid": uid, "state": state, "snapshot": snapshot})
                continue
            expected = plan["results"][index]
            reason = "SCOPE_OR_ACL_DRIFT"
            if expected["uid"] != uid or snapshot["local"] != expected["snapshot"]["local"]:
                raise ValueError("folder scope changed since preview")
            if state == "NOOP":
                channel.send({"uid": uid, "state": "NOOP", "snapshot": snapshot})
                continue
            if state == "CONFLICT":
                channel.send({"uid": uid, "state": "CONFLICT", "snapshot": snapshot})
                return
            if state != "MISSING" or snapshot != expected["snapshot"]:
                raise ValueError("ACL or folder changed; generate a new preview")
            check_window(approval)
            channel.send({"uid": uid, "state": "PENDING", "snapshot": snapshot})
            if channel.recv() != "ACK":
                raise ValueError("write was not acknowledged by the durable report")
            pending = uid
            reason = "WRITE_READBACK"
            check_window(approval)
            try:
                client.request(
                    "POST",
                    f"/api/access-control/folders/{uid}/builtInRoles/Editor",
                    {"permission": "Edit"},
                    before_request=lambda: check_window(approval),
                )
            except (requests.RequestException, ValueError):
                pass  # The one scheduled readback resolves an ambiguous write; never resend it.
            after = normalize_acl(client.request("GET", f"/api/access-control/folders/{uid}"))
            if not verify_added(acl, after):
                raise ValueError("write result is not confirmed or other grants changed")
            channel.send({"uid": uid, "state": "CONFIRMED", "snapshot": snapshot, "after_acl": after})
            pending = None
        channel.send({"state": "COMPLETE"})
    except Exception as error:
        # Report safe categories only: HTTP exceptions may contain URLs or credentials.
        channel.send(
            {
                "state": "UNKNOWN" if pending else "FAILED",
                "uid": pending or current_uid,
                "error": type(error).__name__,
                "reason": reason,
            }
        )
    finally:
        client.session.close()
        channel.close()


def run_network(context, targets, report, plan=None, approval=None, budget=NETWORK_SECONDS, interval=REQUEST_INTERVAL):
    fd = os.open(report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    results = {
        target["folder"]["uid"]: {"uid": target["folder"]["uid"], "state": "NOT_ATTEMPTED"} for target in targets
    }
    successful = False
    process_context = multiprocessing.get_context("spawn")
    parent, child = process_context.Pipe()
    started = time.monotonic()
    deadline = started + budget
    process = process_context.Process(
        target=network_worker, args=(child, context, targets, plan, approval, interval, deadline)
    )
    finished = threading.Event()

    def supervise():
        # Journal I/O must not delay termination of an in-flight network request.
        if not finished.wait(max(0, deadline - time.monotonic())):
            process.terminate()
            finished.wait(REAP_SECONDS)
            if process.is_alive():
                process.kill()

    watchdog = threading.Thread(target=supervise, daemon=True)
    with os.fdopen(fd, "w") as journal:
        process.start()
        child.close()
        watchdog.start()
        try:
            while True:
                remaining = budget - (time.monotonic() - started)
                if remaining <= 0:
                    break
                if not parent.poll(min(remaining, 0.05)):
                    if not process.is_alive():
                        break
                    continue
                try:
                    message = parent.recv()
                except EOFError:
                    break
                journal.write(json.dumps(message, sort_keys=True) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
                if message.get("uid") in results:
                    results[message["uid"]] = message
                if time.monotonic() >= deadline:
                    break
                if message["state"] == "PENDING":
                    if approval is None:
                        raise ValueError("unexpected write request in preview")
                    check_window(approval)
                    parent.send("ACK")
                if message["state"] in ("COMPLETE", "FAILED", "UNKNOWN", "CONFLICT"):
                    successful = message["state"] == "COMPLETE"
                    break
        finally:
            finished.set()
            watchdog.join()
            if process.is_alive():
                process.terminate()
                process.join(REAP_SECONDS)
                if process.is_alive():
                    process.kill()
            process.join()
            parent.close()
            process.close()
            for result in results.values():
                if result["state"] == "PENDING":
                    result["state"] = "UNKNOWN"
                    successful = False
            summary = {"context": context, "successful": successful, "results": list(results.values())}
            journal.write(json.dumps({"state": "SUMMARY", **summary}, sort_keys=True) + "\n")
            journal.flush()
            os.fsync(journal.fileno())
    return summary


class Command(BaseCommand):
    help = (
        "Preview or repair missing folder Editor/Edit grants (Grafana 10.4.10, <=3 flat folders, <=200 children). "
        "Default is read-only. Apply requires an approved preview and a deployment-configured, protected approval file. "
        "An exclusive ACL and folder-change window must already exist; the file is not a lock. "
        "Never replay UNKNOWN results without a new read-only reconciliation."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", required=True)
        parser.add_argument("--business-id", type=int, required=True)
        parser.add_argument("--org-id", type=int, required=True)
        parser.add_argument("--folder-uid", action="append", required=True)
        parser.add_argument(
            "--report", required=True, help="New private JSONL report; existing files are never overwritten"
        )
        parser.add_argument("--plan", help="JSON preview artifact to apply")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            context = {
                "schema": 1,
                "tenant_id": options["tenant_id"],
                "business_id": options["business_id"],
                "org_id": options["org_id"],
                "grafana_url": settings.GRAFANA_URL.rstrip("/"),
                "folder_uids": options["folder_uid"],
            }
            validate_context(context)
            plan = approval = None
            if options["apply"]:
                path = getattr(settings, "GRAFANA_FOLDER_EDITOR_REPAIR_AUTHORIZATION_FILE", "")
                if not path or not options["plan"]:
                    raise ValueError("apply requires a deployment-authorized approval file and a preview plan")
                plan = read_json(options["plan"])
                if (
                    plan["context"] != context
                    or not plan["successful"]
                    or len(plan["results"]) != len(context["folder_uids"])
                ):
                    raise ValueError("preview does not match the requested scope")
                approval = read_json(path, protected=True)
                validate_approval(approval, plan, options["report"])
            elif options["plan"]:
                raise ValueError("--plan is only used with --apply")
            targets = local_targets(context)
            result = run_network(context, targets, options["report"], plan, approval)
            if not options["apply"]:
                plan_path = str(Path(options["report"])) + ".plan.json"
                fd = os.open(plan_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as output:
                    json.dump(result, output, indent=2, sort_keys=True)
                    output.flush()
                    os.fsync(output.fileno())
                self.stdout.write(f"preview={plan_path} sha256={digest(result)}")
            for item in result["results"]:
                self.stdout.write(f"{item['uid']}: {item['state']}")
            if not result["successful"]:
                raise CommandError("maintenance incomplete; inspect the private report before any further write")
        except CommandError:
            raise
        except Exception as error:
            raise CommandError(f"maintenance rejected ({type(error).__name__}); no automatic retry") from error
