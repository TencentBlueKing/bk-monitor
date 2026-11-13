#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "package/skills/bkm-grafana-dashboard/scripts"
sys.path.insert(0, str(ROOT))

from dashboard_tools import (  # noqa: E402
    apply_operations,
    build_save_payload,
    dashboard_summary,
    extract_promqls,
    locate_panels,
    unwrap_dashboard,
    validate_panel_queries,
)


def mini_dashboard():
    return {
        "uid": "host-monitor-dashboard",
        "title": "主机监控仪表盘",
        "id": 3303,
        "version": 1,
        "bk_extra": "keep-me",
        "panels": [
            {
                "id": 1,
                "title": "CPU使用率",
                "type": "timeseries",
                "bk_custom": 1,
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                "datasource": {"type": "bkmonitor-timeseries-datasource", "uid": "000000002"},
                "targets": [
                    {
                        "mode": "ui",
                        "source": "",
                        "query_configs": [
                            {
                                "alias": "今日",
                                "data_source_label": "bk_monitor",
                                "metric_field": "usage",
                                "result_table_id": "system.cpu_summary",
                                "method": "AVG",
                                "refId": "a",
                                "functions": [],
                            }
                        ],
                        "refId": "A",
                    }
                ],
            },
            {
                "id": 10,
                "title": "当前TPS",
                "type": "stat",
                "gridPos": {"h": 4, "w": 4, "x": 0, "y": 8},
                "targets": [
                    {
                        "mode": "code",
                        "source": 'round(sum(increase(rpc_server_handled_total{namespace=~"$namespace"}[1m]))) / 60',
                        "query_configs": [],
                        "refId": "A",
                    }
                ],
            },
        ],
        "templating": {"list": [{"name": "namespace", "type": "query", "label": "环境"}]},
        "time": {"from": "now-1h", "to": "now"},
    }


class UnwrapTests(unittest.TestCase):
    def test_mcp_envelope_string_data(self):
        grafana = mini_dashboard()
        envelope = {
            "response_body": {
                "data": {
                    "id": 3303,
                    "uid": "host-monitor-dashboard",
                    "title": "主机监控仪表盘",
                    "slug": "host",
                    "version": 1,
                    "data": json.dumps(grafana, ensure_ascii=False),
                }
            }
        }
        dash, meta = unwrap_dashboard(envelope)
        self.assertEqual(dash["uid"], "host-monitor-dashboard")
        self.assertEqual(meta["slug"], "host")
        self.assertEqual(dash["bk_extra"], "keep-me")


class SummaryTests(unittest.TestCase):
    def test_summary_and_locate(self):
        dash = mini_dashboard()
        summary = dashboard_summary(dash, {"slug": "host"})
        self.assertEqual(summary["panelCount"], 2)
        self.assertEqual(summary["iframe_path"], "/grafana/d/host-monitor-dashboard/host")
        hits = locate_panels(dash, "CPU")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], 1)
        self.assertEqual(len(locate_panels(dash, "使用")), 1)


class ApplyTests(unittest.TestCase):
    def test_set_title_preserves_unknown_fields(self):
        dash = mini_dashboard()
        apply_operations(dash, [{"op": "set_title", "panel_id": 1, "title": "当前 CPU"}])
        self.assertEqual(dash["panels"][0]["title"], "当前 CPU")
        self.assertEqual(dash["panels"][0]["bk_custom"], 1)
        self.assertEqual(dash["uid"], "host-monitor-dashboard")
        self.assertEqual(dash["bk_extra"], "keep-me")

    def test_set_type_and_add_remove(self):
        dash = mini_dashboard()
        results = apply_operations(
            dash,
            [
                {"op": "set_type", "panel_id": 1, "type": "stat"},
                {
                    "op": "add_panel",
                    "placement": {"after_panel_id": 1},
                    "panel": {
                        "type": "timeseries",
                        "title": "内存趋势",
                        "targets": [
                            {
                                "mode": "code",
                                "source": "avg(avg_over_time(bkmonitor:system:mem:pct_used[1m]))",
                                "query_configs": [],
                                "refId": "A",
                            }
                        ],
                    },
                },
            ],
        )
        self.assertEqual(dash["panels"][0]["type"], "stat")
        new_id = results[1]["panel_id"]
        self.assertEqual(new_id, 11)
        self.assertEqual(dash["panels"][-1]["title"], "内存趋势")
        apply_operations(dash, [{"op": "remove_panel", "panel_id": 10}])
        ids = [p["id"] for p in dash["panels"]]
        self.assertNotIn(10, ids)

    def test_set_query_ui_and_code(self):
        dash = mini_dashboard()
        apply_operations(
            dash,
            [
                {
                    "op": "set_query",
                    "panel_id": 1,
                    "mode": "code",
                    "source": "avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))",
                }
            ],
        )
        target = dash["panels"][0]["targets"][0]
        self.assertEqual(target["mode"], "code")
        self.assertEqual(target["query_configs"], [])
        apply_operations(
            dash,
            [
                {
                    "op": "set_query",
                    "panel_id": 1,
                    "mode": "ui",
                    "query_configs": [
                        {
                            "alias": "今日",
                            "data_source_label": "bk_monitor",
                            "metric_field": "usage",
                            "result_table_id": "system.cpu_summary",
                            "method": "AVG",
                            "refId": "a",
                            "functions": [],
                        }
                    ],
                }
            ],
        )
        self.assertEqual(dash["panels"][0]["targets"][0]["source"], "")

    def test_set_viz_transformations(self):
        dash = mini_dashboard()
        apply_operations(
            dash,
            [
                {
                    "op": "set_viz",
                    "panel_id": 1,
                    "transformations": [
                        {
                            "id": "calculateField",
                            "options": {
                                "alias": "较昨日变化",
                                "mode": "binary",
                                "binary": {
                                    "left": "今日",
                                    "operator": "-",
                                    "right": "昨日",
                                },
                                "replaceFields": False,
                            },
                        }
                    ],
                    "options": {"legend": {"displayMode": "table", "placement": "right"}},
                    "transparent": False,
                }
            ],
        )
        panel = dash["panels"][0]
        self.assertEqual(panel["transformations"][0]["id"], "calculateField")
        self.assertEqual(panel["transformations"][0]["options"]["alias"], "较昨日变化")
        self.assertEqual(panel["options"]["legend"]["displayMode"], "table")
        self.assertFalse(panel["transparent"])

    def test_bad_metric_field_rejected(self):
        dash = mini_dashboard()
        with self.assertRaises(Exception):
            apply_operations(
                dash,
                [
                    {
                        "op": "set_query",
                        "panel_id": 1,
                        "mode": "ui",
                        "query_configs": [
                            {
                                "alias": "今日",
                                "data_source_label": "bk_monitor",
                                "metric_field": "cpu_summary.usage",
                                "result_table_id": "system.cpu_summary",
                            }
                        ],
                    }
                ],
            )


class QueryTests(unittest.TestCase):
    def test_extract_and_validate(self):
        dash = mini_dashboard()
        cpu = extract_promqls(dash["panels"][0])
        self.assertEqual(cpu[0]["raw_metric"], "bkmonitor:system:cpu_summary:usage")
        tps = extract_promqls(dash["panels"][1])
        self.assertTrue(tps[0]["has_variables"])
        self.assertTrue(validate_panel_queries(dash["panels"][0])["ok"])


class SaveTests(unittest.TestCase):
    def test_build_save_string_configs(self):
        dash = mini_dashboard()
        payload = build_save_payload(dash, 2, "主机监控")
        self.assertIn("grafana/", payload["path"])
        configs = payload["mcp_arguments"]["body_param"]["configs"]
        self.assertIsInstance(configs, dict)
        inner = json.loads(next(iter(configs.values())))
        self.assertEqual(inner["uid"], "host-monitor-dashboard")
        self.assertTrue(inner["__inputs"])
        self.assertEqual(inner["bk_extra"], "keep-me")


class CliSmoke(unittest.TestCase):
    def test_ingest_cli(self):
        import subprocess
        import sys

        grafana = mini_dashboard()
        envelope = {"data": {"uid": "x", "slug": "s", "data": json.dumps(grafana)}}
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "mcp.json"
            out = Path(tmp) / "dash.json"
            src.write_text(json.dumps(envelope), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "dashboard_tools.py"),
                    "ingest",
                    "--input",
                    str(src),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            saved = json.loads(out.read_text())
            self.assertEqual(saved["title"], "主机监控仪表盘")


if __name__ == "__main__":
    unittest.main()
