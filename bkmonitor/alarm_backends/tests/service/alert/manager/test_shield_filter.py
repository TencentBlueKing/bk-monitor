"""托管隔离复用 manager 的缓存读取，缺缓存才回读快照。"""

import json
from types import SimpleNamespace
from unittest import TestCase, mock

from alarm_backends.core.alert.alert import Alert
from alarm_backends.service.alert.manager import processor


class TestManagerShieldFilter(TestCase):
    @staticmethod
    def alert(alert_id, shielded=False):
        return Alert(
            {
                "id": str(alert_id),
                "strategy_id": 7,
                "dedupe_md5": str(alert_id),
                "status": "ABNORMAL",
                "shield_end_close": shielded,
            }
        )

    def run_filter(self, alerts, cached, latest):
        with (
            mock.patch.object(processor.ALERT_DEDUPE_CONTENT_KEY, "client") as client,
            mock.patch.object(processor.Alert, "mget", return_value=latest) as mget,
        ):
            client.mget.return_value = [json.dumps(alert.data) if alert else None for alert in cached]
            result = processor.AlertManager.filter_alerts(SimpleNamespace(logger=mock.Mock()), alerts)
            client.mget.assert_called_once()
            requested_ids = [key.alert_id for key in mget.call_args.args[0]] if mget.called else []
            return result, requested_ids, mget.call_count

    def test_latest_cached_takeover_excludes_queued_alert_without_mget(self):
        queued = self.alert(1)
        result, requested, calls = self.run_filter([queued], [self.alert(1, True)], [])
        self.assertEqual(result, [])
        self.assertEqual(requested, [])
        self.assertEqual(calls, 0)

    def test_missing_cache_reads_snapshot_and_excludes_takeover(self):
        queued = self.alert(1)
        result, requested, calls = self.run_filter([queued], [None], [self.alert(1, True)])
        self.assertEqual(result, [])
        self.assertEqual(requested, ["1"])
        self.assertEqual(calls, 1)

    def test_ordinary_cached_alert_is_preserved_without_mget(self):
        queued = self.alert(1)
        result, requested, calls = self.run_filter([queued], [self.alert(1)], [])
        self.assertEqual(result, [queued])
        self.assertEqual(requested, [])
        self.assertEqual(calls, 0)

    def test_mixed_batch_only_reloads_missing_cache_entries(self):
        cached, missing = self.alert(1), self.alert(2)
        result, requested, calls = self.run_filter([cached, missing], [self.alert(1), None], [self.alert(2, True)])
        self.assertEqual(result, [cached])
        self.assertEqual(requested, ["2"])
        self.assertEqual(calls, 1)

    def test_missing_cache_ordinary_snapshot_is_preserved(self):
        queued = self.alert(1)
        result, requested, calls = self.run_filter([queued], [None], [self.alert(1)])
        self.assertEqual(result, [queued])
        self.assertEqual(requested, ["1"])
        self.assertEqual(calls, 1)
