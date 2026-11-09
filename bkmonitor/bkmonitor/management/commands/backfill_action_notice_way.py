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
from elasticsearch.exceptions import NotFoundError

from bkmonitor.documents import ActionInstanceDocument
from bkmonitor.utils.elasticsearch.action_index import (
    filter_indices_by_date,
    index_has_field,
    invalid_index_names,
    list_action_indices,
)
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
      - 默认只统计待回填数（dry-run），显式 --apply 才提交任务；
      - 统计与复验都会校验分片完整性，分片失败时不允许判定为"已完成"。
    """

    help = "回填非父通知记录的原始渠道字段（默认 dry-run，--apply 才写入；ES 侧 update_by_query，可重复执行）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--indices",
            default="",
            help="逗号分隔的物理索引名（如 bkfta_action_20261028_0），不支持别名；默认枚举全部，可再用 --start/--end 过滤",
        )
        parser.add_argument("--start", default="", help="起始日期 YYYY-MM-DD（按索引日期过滤）")
        parser.add_argument("--end", default="", help="结束日期 YYYY-MM-DD（按索引日期过滤，含当天）")
        parser.add_argument(
            "--requests-per-second", type=float, default=500, help="（仅 --apply 生效）ES 写入限速，-1 表示不限"
        )
        parser.add_argument("--slices", default="auto", help="（仅 --apply 生效）并发切片数，默认 auto")
        parser.add_argument("--wait", action="store_true", help="提交后轮询任务直到完成并复验（需配合 --apply 使用）")
        parser.add_argument("--timeout", type=int, default=3 * 3600, help="（仅 --wait 生效）超时时间（秒）")
        parser.add_argument("--apply", action="store_true", help="真正提交回填任务；默认只统计待回填数")

    def handle(self, *args, **options):
        # 参数契约：--wait 只对已提交的任务有意义，单独使用应报错而不是静默按 dry-run 处理
        if options["wait"] and not options["apply"]:
            raise CommandError("--wait 需配合 --apply 使用")

        es = ActionInstanceDocument._index._get_connection()
        indices = self._resolve_indices(es, options)
        if not indices:
            raise CommandError("未找到 bkfta_action 物理索引，停止执行")

        index_expr = ",".join(indices)
        query = self._build_query()

        # mapping 覆盖检查：索引 dynamic=false 时，未建 mapping 的字段只会写进 _source、不进索引，
        # 于是 must_not exists 永远命中、count 降不下来，命令会反复报「仍有未回填文档」并白写一遍
        not_found, missing, unreadable = [], [], []
        for name in indices:
            try:
                has_field = index_has_field(es, name, FIELD)
            except NotFoundError:
                # 名字不存在（多为 --indices 拼写错误），不能和不存在的字段混为一谈
                not_found.append(name)
                continue
            except Exception:  # noqa: BLE001
                logger.exception("get mapping failed, index=%s field=%s", name, FIELD)
                unreadable.append(name)
                continue
            if not has_field:
                missing.append(name)
        if not_found:
            # 自动枚举与读 mapping 之间也可能被删除/轮转，所以不能只提示检查 --indices
            raise CommandError(f"索引不存在：{','.join(not_found)}，可能是 --indices 拼写错误，或索引刚被删除/轮转")
        if missing or unreadable:
            # 两类根因处置不同：缺字段去补 mapping，读取失败先查连接/权限，不能给同一条建议
            details = []
            if missing:
                details.append(f"缺 {FIELD} 字段 {len(missing)} 个（请先执行 init_action_notice_way_mapping --apply）")
            if unreadable:
                details.append(f"读取 mapping 失败 {len(unreadable)} 个（请检查 ES 连接/权限后重跑）")
            raise CommandError(f"{len(missing) + len(unreadable)} 个索引无法回填：{'；'.join(details)}")

        # 先刷新：update_by_query 的统计与复验都读搜索视图，不刷新会看到旧值
        es.indices.refresh(index=index_expr)
        pending = self._count_documents(es, index_expr, query)
        self.stdout.write(f"待回填文档数: {pending}，涉及索引 {len(indices)} 个")
        if not pending:
            self.stdout.write("无需回填")
            return
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("dry-run 结束，未写入；确认后加 --apply 提交"))
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
            self.stdout.write(f"查看进度: GET _tasks/{task_id}?pretty；完成后可重跑本命令（不带 --apply）复验")
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
        remaining = self._count_documents(es, index_expr, query)
        self.stdout.write(f"复验：剩余未回填 {remaining} 条")
        if remaining:
            raise CommandError("仍有未回填文档，可重跑本命令")

    def _resolve_indices(self, es, options) -> list[str]:
        explicit = [name.strip() for name in options["indices"].split(",") if name.strip()]
        if explicit:
            # 只接受物理索引名：写别名只指向当天最新的 _N 索引，会静默漏掉更早的物理索引；
            # 且别名第三段不是日期，--start/--end 会把别名误滤成空列表
            invalid = invalid_index_names(explicit)
            if invalid:
                raise CommandError(
                    f"只支持物理索引名（形如 bkfta_action_20261028_0）：{','.join(invalid)}；"
                    f"按时间段回填请用 --start/--end，或省略 --indices 自动枚举"
                )
            indices = explicit
        else:
            indices = list_action_indices(es)

        start = self._parse_date(options["start"], "--start")
        end = self._parse_date(options["end"], "--end")
        if start or end:
            indices = filter_indices_by_date(indices, start, end)
            if not indices:
                # 显式传了索引却被日期过滤为空，不能报"未找到索引"，否则看着像命令自身枚举失败
                scope = "指定的索引" if explicit else "全部索引"
                raise CommandError(f"{scope}均不在 --start/--end 范围内，请检查日期参数")
        return indices

    @staticmethod
    def _count_documents(es, index_expr: str, query: dict) -> int:
        """统计待处理文档数；有分片失败时不能据此判断"已回填完成"，必须直接报错"""
        result = es.count(index=index_expr, body={"query": query})
        failed = (result.get("_shards") or {}).get("failed", 0)
        if failed:
            raise CommandError(f"统计请求有 {failed} 个分片失败，无法判定回填状态；请重跑本命令，若持续失败请检查集群")
        return result["count"]

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
                raise CommandError(f"等待回填任务超时（{timeout}s），可稍后重跑本命令（不带 --apply）复验或重跑")
            time.sleep(POLL_INTERVAL_SECONDS)
