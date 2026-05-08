"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any


from django.conf import settings
from apm_web.handlers import metric_group
from apm_web.handlers.metric_group import PreCalculateHelper
from bkmonitor.utils.common_utils import format_percent


class PreCalculateHelperMixin:
    DEFAULT_APP_CONFIG_KEY: str = "APM_CUSTOM_METRIC_SDK_MAPPING_CONFIG"

    @classmethod
    def get_helper_or_none(
        cls, bk_biz_id: str, app_name: str, app_config_key: str | None = None
    ) -> PreCalculateHelper | None:
        try:
            app_config: dict[str, Any] = getattr(settings, app_config_key or cls.DEFAULT_APP_CONFIG_KEY)
            pre_calculate_config: dict[str, Any] = app_config[f"{bk_biz_id}-{app_name}"]["pre_calculate"]
        except (KeyError, AttributeError):
            return None

        return PreCalculateHelper(pre_calculate_config)


class RecordHelperMixin:
    @classmethod
    def _process_sorted(cls, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not records:
            return []
        if "time" in records[0].get("dimensions") or {}:
            return sorted(records, key=lambda _d: -_d.get("dimensions", {}).get("time", 0))
        return records

    @classmethod
    def format_value(cls, metric_cal_type: str, value: Any) -> float:
        try:
            value = float(value)
        except Exception:  # pylint: disable=broad-except
            value = 0

        if metric_cal_type == metric_group.CalculationType.REQUEST_TOTAL.value:
            # 请求量必须是整型
            value = int(value)
        elif metric_cal_type in [
            metric_group.CalculationType.TIMEOUT_RATE.value,
            metric_group.CalculationType.SUCCESS_RATE.value,
            metric_group.CalculationType.EXCEPTION_RATE.value,
        ]:
            value = format_percent(value, precision=3, sig_fig_cnt=2)
        else:
            value = round(value, 2)

        return value
