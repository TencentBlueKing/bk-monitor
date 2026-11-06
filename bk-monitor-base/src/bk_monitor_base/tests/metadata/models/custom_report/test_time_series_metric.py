import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.utils import timezone

from bk_monitor_base.metadata.models.custom_report import time_series
from bk_monitor_base.metadata.models.custom_report.time_series import TimeSeriesMetric


def test_bulk_update_metrics_logs_disabled_metric_ids_as_json_list(monkeypatch):
    metric = SimpleNamespace(
        id=1001,
        field_name="disabled_metric",
        field_scope=TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME,
        last_modify_time=timezone.now() - timedelta(days=2),
        tag_list=[],
        scope_id=None,
        field_config={},
        is_active=True,
    )

    objects = MagicMock()
    monkeypatch.setattr(TimeSeriesMetric, "objects", objects)
    monkeypatch.setattr(time_series, "filter_model_by_in_page", MagicMock(return_value=[metric]))

    TimeSeriesMetric._bulk_update_metrics(
        metrics_dict={
            ("disabled_metric", TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME): {
                "field_name": "disabled_metric",
                "is_active": False,
                "last_modify_time": time.time(),
                "tag_list": [],
            }
        },
        need_update_metrics=[("disabled_metric", TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME)],
        group_id=1,
        is_auto_discovery=False,
    )

    objects.filter.return_value.delete.assert_called_once()
