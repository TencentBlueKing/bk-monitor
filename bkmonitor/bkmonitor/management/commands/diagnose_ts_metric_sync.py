"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

命令使用说明:
    1. 建议在 api 角色执行，用来确认当前 web/api 环境看到的 source、metadata、web 缓存状态。
    2. 基本用法:
       python manage.py diagnose_ts_metric_sync --data_id 1579347 --metrics wea_agent_http_request
    3. 同时排查多个指标:
       python manage.py diagnose_ts_metric_sync --data_id 1579347 --metrics wea_agent_http_request,wea_agent_cmd_request
    4. 输出 JSON 结果:
       python manage.py diagnose_ts_metric_sync --data_id 1579347 --metrics wea_agent_http_request --json
    5. 自定义时间窗口:
       python manage.py diagnose_ts_metric_sync --data_id 1579347 --metrics wea_agent_http_request \\
           --window-seconds 7200 --history-seconds 2592000
"""

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bkmonitor.utils.ts_metric_diagnosis import diagnose_ts_metric_sync, render_text


class Command(BaseCommand):
    """诊断自定义时序指标在 source、metadata、web 缓存三层中的同步状态。"""

    help = (
        "诊断自定义时序指标在 source、metadata、web 指标缓存三层中的同步状态。"
        "示例: python manage.py diagnose_ts_metric_sync --data_id 1579347 --metrics metric_a,metric_b"
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--data_id", type=int, required=True, help="待排查的自定义时序 DataID")
        parser.add_argument(
            "--metrics",
            type=str,
            required=True,
            help="待排查的指标名列表，支持逗号分隔，例如 'metric_a,metric_b'",
        )
        parser.add_argument(
            "--window-seconds",
            type=int,
            default=settings.FETCH_TIME_SERIES_METRIC_INTERVAL_SECONDS,
            help="近期发现窗口，默认取 FETCH_TIME_SERIES_METRIC_INTERVAL_SECONDS",
        )
        parser.add_argument(
            "--history-seconds",
            type=int,
            default=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS,
            help="历史存在窗口，默认取 TIME_SERIES_METRIC_EXPIRED_SECONDS",
        )
        parser.add_argument(
            "--redis-prefix",
            type=str,
            default="BK_MONITOR_TRANSFER",
            help="source Redis 的配置前缀，默认 BK_MONITOR_TRANSFER",
        )
        parser.add_argument("--json", action="store_true", help="以 JSON 输出详细诊断结果")

    def handle(self, *args, **options) -> None:
        metrics = [m.strip() for m in options["metrics"].split(",") if m.strip()]
        if not metrics:
            raise CommandError("metrics is required")

        try:
            report = diagnose_ts_metric_sync(
                data_id=options["data_id"],
                metrics=metrics,
                window_seconds=options["window_seconds"],
                history_seconds=options["history_seconds"],
                redis_prefix=options["redis_prefix"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if options["json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            self.stdout.write(render_text(report))
