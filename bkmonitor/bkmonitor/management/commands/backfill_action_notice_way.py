"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from bkmonitor.documents import ActionInstanceDocument
from bkmonitor.utils.elasticsearch.action_index import filter_indices_by_date, list_action_indices
from constants.action import NoticeWay

logger = logging.getLogger("bkmonitor.commands.backfill_action_notice_way")

# 源字段与目标字段同名：painless 从 inputs.notice_way 读、写到文档的 notice_way。
# 不暴露 --field 参数：只改目标字段会让源字段与目标字段错位
FIELD = NoticeWay.NOTICE_WAY_FIELD
POLL_INTERVAL_SECONDS = 10

# 原始渠道缺失时写哨兵，保证回填后「字段不存在」的记录数归零。
# inputs 虽然 enabled=false，但原始文档里仍有完整值，painless 可以直接读取。
SCRIPT_TEMPLATE = """
def w = ctx._source.inputs?.notice_way;
if (w instanceof List) {
  ctx._source.__FIELD__ = w.isEmpty() ? ['__NONE__'] : w;
} else if (w == null || w == '') {
  ctx._source.__FIELD__ = ['__NONE__'];
} else {
  ctx._source.__FIELD__ = [w];
}
"""


class Command(BaseCommand):
    """回填非父通知记录的原始渠道字段（默认 dry-run）。

    使用场景：
      - 部署开启开关前，为存量通知记录补 notice_way，消除「结果不完整」标记；
      - 漏跑或部分失败后重跑（查询带 exists 过滤，天然幂等）。

    实现要点：
      - 用 ES 侧 update_by_query + painless 计算，不回读文档、不依赖 Django 模型；
      - conflicts=proceed：回填期间被实时写入覆盖的文档本身已带新字段，跳过冲突不丢数据；
      - 默认提交异步任务并打印 task_id；--wait 时轮询到完成并复验剩余数。
    """

    help = "回填非父通知记录的原始渠道字段（默认 dry-run；ES 侧 update_by_query，可重复执行）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--indices",
            default="",
            help="逗号分隔的索引名，默认枚举 bkfta_action_* 物理索引",
        )
        parser.add_argument("--start", default="", help="起始日期 YYYY-MM-DD（按索引日期过滤）")
        parser.add_argument("--end", default="", help="结束日期 YYYY-MM-DD（按索引日期过滤，含当天）")
        parser.add_argument("--requests-per-second", type=float, default=500, help="ES 写入限速，-1 表示不限")
        parser.add_argument("--slices", default="auto", help="并发切片数，默认 auto")
        parser.add_argument("--wait", action="store_true", help="提交后轮询任务直到完成，并复验剩余数")
        parser.add_argument("--timeout", type=int, default=3 * 3600, help="--wait 的超时时间（秒）")
        parser.add_argument("--dry-run", action="store_true", help="只统计待回填文档数，不写入")

    def handle(self, *args, **options):
        es = ActionInstanceDocument._index._get_connection()
        indices = self._resolve_indices(es, options)
        if not indices:
            raise CommandError("未找到 bkfta_action 物理索引，停止执行")

        index_expr = ",".join(indices)
        query = self._build_query()
        # 先刷新：update_by_query 的统计与复验都读搜索视图，不刷新会看到旧值
        es.indices.refresh(index=index_expr)
        pending = es.count(index=index_expr, body={"query": query})["count"]
        self.stdout.write(f"待回填文档数: {pending}，涉及索引 {len(indices)} 个")
        if not pending:
            return
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry-run 结束，未写入"))
            return

        result = es.update_by_query(
            index=index_expr,
            body={
                "query": query,
                "script": {
                    "lang": "painless",
                    # 用 replace 而不是 str.format：painless 的花括号与 format 语法冲突
                    "source": SCRIPT_TEMPLATE.replace("__FIELD__", FIELD).replace(
                        "__NONE__", NoticeWay.NOTICE_WAY_NONE
                    ),
                },
            },
            params={
                "conflicts": "proceed",
                "slices": options["slices"],
                "requests_per_second": options["requests_per_second"],
                "wait_for_completion": "false",
            },
        )
        task_id = result["task"]
        self.stdout.write(f"已提交异步任务 task_id={task_id}")

        if not options["wait"]:
            self.stdout.write("查看进度: GET _tasks/{task_id}?pretty；完成后可重跑本命令（--dry-run）复验")
            return

        response = self._wait_task(es, task_id, options["timeout"])
        failures = response.get("failures") or []
        self.stdout.write(
            f"任务完成：updated={response.get('updated')} "
            f"version_conflicts={response.get('version_conflicts')} failures={len(failures)}"
        )
        if failures:
            logger.error("backfill failures: %s", failures[:5])
            raise CommandError(f"回填存在 {len(failures)} 条失败，请检查日志后重跑")

        # update_by_query 不会自动 refresh，复验前必须刷新搜索视图，否则会读到旧值误判
        es.indices.refresh(index=index_expr)
        remaining = es.count(index=index_expr, body={"query": query})["count"]
        self.stdout.write(f"复验：剩余未回填 {remaining} 条")
        if remaining:
            raise CommandError("仍有未回填文档，可重跑本命令")

    def _resolve_indices(self, es, options) -> list[str]:
        indices = [name.strip() for name in options["indices"].split(",") if name.strip()]
        if not indices:
            indices = list_action_indices(es)
        start = self._parse_date(options["start"], "--start")
        end = self._parse_date(options["end"], "--end")
        if start or end:
            indices = filter_indices_by_date(indices, start, end)
        return indices

    @staticmethod
    def _parse_date(value: str, name: str) -> str:
        if not value:
            return ""
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")
        except ValueError as error:
            raise CommandError(f"{name} 需为 YYYY-MM-DD 格式: {value}") from error

    @staticmethod
    def _build_query() -> dict:
        return {
            "bool": {
                "filter": [{"term": {"action_plugin_type": "notice"}}],
                "must_not": [
                    {"term": {"is_parent_action": True}},
                    {"exists": {"field": FIELD}},
                ],
            }
        }

    def _wait_task(self, es, task_id: str, timeout: int) -> dict:
        deadline = time.time() + timeout
        while True:
            status = es.tasks.get(task_id=task_id)
            if status.get("error"):
                raise CommandError(f"回填任务失败: {status['error']}")
            if status.get("completed"):
                return status.get("response") or {}
            if time.time() > deadline:
                raise CommandError(f"等待回填任务超时（{timeout}s），可稍后用 --dry-run 复验或重跑")
            time.sleep(POLL_INTERVAL_SECONDS)
