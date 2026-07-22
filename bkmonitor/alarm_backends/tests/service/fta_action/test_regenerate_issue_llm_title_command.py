"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from io import StringIO

import pytest
from django.core.management import CommandError, call_command


COMMAND = "regenerate_issue_llm_title"


def _output_rows(output: StringIO) -> list[dict]:
    return [json.loads(line) for line in output.getvalue().splitlines() if line.strip()]


def test_command_requires_explicit_mode():
    with pytest.raises(CommandError, match="one of the arguments --dry-run --execute is required"):
        call_command(
            COMMAND,
            "--bk-biz-id",
            "2",
            "--issue-id",
            "issue1",
            "--operator",
            "alice",
        )


def test_dry_run_deduplicates_in_order_and_never_regenerates(monkeypatch):
    from alarm_backends.service.fta_action.tasks import issue_tasks

    inspected = []

    def _inspect(issue_id, bk_biz_id):
        inspected.append((issue_id, bk_biz_id))
        return {
            "issue_id": issue_id,
            "bk_biz_id": bk_biz_id,
            "safe_to_regenerate": issue_id == "issue2",
            "result": "eligible" if issue_id == "issue2" else "skipped_user_renamed",
        }

    monkeypatch.setattr(issue_tasks, "inspect_issue_llm_title_regeneration", _inspect, raising=False)
    monkeypatch.setattr(
        issue_tasks,
        "regenerate_issue_llm_title",
        lambda *args, **kwargs: pytest.fail("dry-run must not regenerate titles"),
    )
    output = StringIO()

    call_command(
        COMMAND,
        "--bk-biz-id",
        "2",
        "--issue-id",
        "issue2",
        "--issue-id",
        "issue1",
        "--issue-id",
        "issue2",
        "--operator",
        "alice",
        "--dry-run",
        stdout=output,
    )

    assert inspected == [("issue2", 2), ("issue1", 2)]
    rows = _output_rows(output)
    assert [row["issue_id"] for row in rows[:-1]] == ["issue2", "issue1"]
    assert rows[-1] == {
        "type": "summary",
        "mode": "dry_run",
        "requested_count": 2,
        "processed_count": 2,
        "safe_count": 1,
        "success_count": 0,
        "failed_count": 0,
        "result_counts": {"eligible": 1, "skipped_user_renamed": 1},
    }


def test_execute_runs_sequentially_with_operator(monkeypatch):
    from alarm_backends.service.fta_action.tasks import issue_tasks

    calls = []

    def _regenerate(issue_id, bk_biz_id, *, operator):
        calls.append((issue_id, bk_biz_id, operator))
        return {
            "issue_id": issue_id,
            "bk_biz_id": bk_biz_id,
            "result": "ok",
            "old_name": "默认标题",
            "new_name": f"生成标题-{issue_id}",
        }

    monkeypatch.setattr(issue_tasks, "regenerate_issue_llm_title", _regenerate)
    output = StringIO()

    call_command(
        COMMAND,
        "--bk-biz-id",
        "2",
        "--issue-id",
        "issue2",
        "--issue-id",
        "issue1",
        "--operator",
        "alice",
        "--execute",
        stdout=output,
    )

    assert calls == [("issue2", 2, "alice"), ("issue1", 2, "alice")]
    rows = _output_rows(output)
    assert rows[-1] == {
        "type": "summary",
        "mode": "execute",
        "requested_count": 2,
        "processed_count": 2,
        "safe_count": 0,
        "success_count": 2,
        "failed_count": 0,
        "result_counts": {"ok": 2},
    }


def test_command_rejects_more_than_twenty_unique_issues(monkeypatch):
    from alarm_backends.service.fta_action.tasks import issue_tasks

    monkeypatch.setattr(
        issue_tasks,
        "inspect_issue_llm_title_regeneration",
        lambda *args, **kwargs: pytest.fail("limit must be checked before inspection"),
        raising=False,
    )
    args = [COMMAND, "--bk-biz-id", "2", "--operator", "alice", "--dry-run"]
    for index in range(21):
        args.extend(["--issue-id", f"issue-{index}"])

    with pytest.raises(CommandError, match="最多允许 20 个"):
        call_command(*args)
