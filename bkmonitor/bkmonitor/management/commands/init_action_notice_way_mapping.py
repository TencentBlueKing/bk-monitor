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

from django.core.management.base import BaseCommand, CommandError

from bkmonitor.documents import ActionInstanceDocument
from bkmonitor.utils.elasticsearch.action_index import index_has_field, list_action_indices
from constants.action import NoticeWay

logger = logging.getLogger("bkmonitor.commands.init_action_notice_way_mapping")

# 与写入、回填、查询共用同一常量，避免字段名在多处漂移
FIELD = NoticeWay.NOTICE_WAY_FIELD
FIELD_MAPPING = {"type": "keyword"}


class Command(BaseCommand):
    """为 bkfta_action 全部历史物理索引补齐字段（默认 dry-run，--apply 才写）。

    使用场景：
      - 部署「按通知记录统计」新查询之前，先给历史索引加字段，
        避免查询已上线但索引未映射的 400 窗口；
      - 漏跑或新增索引后补字段（幂等，可重复执行）。

    字段名固定为 NoticeWay.NOTICE_WAY_FIELD，不提供 --field：写入、回填、查询三处必须同名。

    当前索引无需手工处理：部署时 post_migrate → rollover_es_indices 会再补一次。

    安全约束：
      - 索引列表为空时直接报错退出：index="" 会被拼成 /_mapping，作用到集群全部索引；
      - 逐索引执行，单个失败不影响其余索引，失败时进程以非 0 退出，便于重跑。
    """

    help = (
        "为 bkfta_action 历史物理索引补齐字段（默认 dry-run）。"
        "需在部署新查询代码之前执行，当前索引由 post_migrate 的 rollover 自动补齐"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--indices",
            default="",
            help="逗号分隔的索引名，默认枚举 bkfta_action_* 物理索引（自动过滤读写别名）",
        )
        parser.add_argument("--apply", action="store_true", help="真正执行 put_mapping；默认只打印计划")

    def handle(self, *args, **options):
        field = FIELD
        es = ActionInstanceDocument._index._get_connection()

        indices = [name.strip() for name in options["indices"].split(",") if name.strip()]
        if not indices:
            indices = list_action_indices(es)
        if not indices:
            raise CommandError("未找到 bkfta_action 物理索引，停止执行")

        existing, missing, check_failed = [], [], []
        for name in indices:
            try:
                has_field = index_has_field(es, name, field)
            except Exception as error:  # noqa: BLE001
                # 单个索引（如临时不可用）失败不应中断整批处理
                logger.exception("get mapping failed, index=%s field=%s", name, field)
                check_failed.append(name)
                self.stderr.write(self.style.ERROR(f"  读取 mapping 失败: {name} -> {error}"))
                continue
            (existing if has_field else missing).append(name)

        self.stdout.write(
            f"共 {len(indices)} 个索引：已有 {field} 字段 {len(existing)} 个，"
            f"待补齐 {len(missing)} 个，读取失败 {len(check_failed)} 个"
        )
        for name in missing:
            self.stdout.write(f"  待补齐: {name}")

        if not missing:
            if check_failed:
                raise CommandError(f"{len(check_failed)} 个索引 mapping 读取失败，可重跑本命令")
            return
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("dry-run 结束，未写入；确认后加 --apply 执行"))
            return

        failed = []
        for name in missing:
            try:
                es.indices.put_mapping(index=name, body={"properties": {field: FIELD_MAPPING}})
            except Exception as error:  # noqa: BLE001
                logger.exception("put mapping failed, index=%s field=%s", name, field)
                failed.append(name)
                self.stderr.write(self.style.ERROR(f"  失败: {name} -> {error}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"  已补齐: {name}"))

        if failed or check_failed:
            raise CommandError(
                f"{len(failed) + len(check_failed)} 个索引未处理成功"
                f"（补齐失败 {len(failed)} 个，读取失败 {len(check_failed)} 个），可重跑本命令"
            )

        self.stdout.write(self.style.SUCCESS("全部索引已补齐"))
