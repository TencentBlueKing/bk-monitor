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

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """为存量业务主动补建内置告警策略。

    背景：内置策略加载器（run_init_builtin -> run_build_in -> *DefaultAlarmStrategyLoader）仅在用户访问
    SaaS 页面时经 get_extra_context 触发（不在 celery beat 周期表）。单租户迁移多租户后，新增的多租户系统
    事件版本（os v2/v3/v4）只能等业务被访问才补建——发布后无人访问的迁移惰性业务永不触发、永久漏建。

    本命令显式遍历目标业务调用 run_build_in，把"补建"从被动按访问触发改为可主动执行，用于发布后一次性
    补齐存量业务。加载器纯叠加、按版本幂等、从不改/删存量策略，可安全重复执行；指标未就绪的业务本次产
    出 0 条且不登记接入记录，待指标就绪后重跑本命令即可补建（不漏覆盖）。
    """

    help = "为存量业务补建内置告警策略（含多租户系统事件 os v2/v3/v4）。加载器幂等叠加，可安全重复执行。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--bk-biz-ids",
            default="",
            help="指定业务ID列表(逗号分隔)；不传则遍历目标租户下的全部业务。租户按业务自动推导(或由 --bk-tenant-id 指定)。",
        )
        parser.add_argument(
            "--bk-tenant-id",
            default="",
            help="仅处理指定租户；不传则遍历所有租户。",
        )
        parser.add_argument(
            "--modes",
            default="host,k8s",
            help="加载模式(逗号分隔)：host,k8s；默认 host,k8s。host 含主机/GSE 内置，k8s 含容器内置。",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="仅打印将处理的(租户, 业务)清单，不实际加载。",
        )

    def handle(self, *args, **options):
        from bkm_space.api import SpaceApi
        from bkm_space.define import Space
        from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id, set_local_tenant_id
        from bkmonitor.utils.user import get_admin_username, set_local_username
        from core.drf_resource import api
        from monitor_web.strategies.built_in import run_build_in

        if not settings.ENABLE_DEFAULT_STRATEGY:
            self.stdout.write("ENABLE_DEFAULT_STRATEGY=False，内置策略未启用，跳过。")
            return

        modes = [m.strip() for m in options["modes"].split(",") if m.strip()]
        if not modes:
            self.stderr.write("--modes 为空，未指定任何加载模式。")
            return
        dry_run = options["dry_run"]
        explicit_biz_ids = [int(b) for b in options["bk_biz_ids"].split(",") if b.strip()]
        only_tenant_id = options["bk_tenant_id"].strip()

        # 组织待处理的 (bk_tenant_id, [bk_biz_id, ...]) 列表
        if explicit_biz_ids:
            # 显式业务列表：按业务推导租户(或用 --bk-tenant-id 覆盖)，避免把同一业务号跨租户重复处理
            tenant_to_biz_ids: dict[str, list[int]] = {}
            for bk_biz_id in explicit_biz_ids:
                tenant_id = only_tenant_id or bk_biz_id_to_bk_tenant_id(bk_biz_id)
                tenant_to_biz_ids.setdefault(tenant_id, []).append(bk_biz_id)
        else:
            # 全量：遍历目标租户的全部业务
            if only_tenant_id:
                tenant_ids = [only_tenant_id]
            else:
                tenant_ids = [tenant["id"] for tenant in api.bk_login.list_tenant()]
            tenant_to_biz_ids = {}
            for tenant_id in tenant_ids:
                spaces: list[Space] = SpaceApi.list_spaces(bk_tenant_id=tenant_id)
                tenant_to_biz_ids[tenant_id] = [space.bk_biz_id for space in spaces if space.bk_biz_id > 0]

        total_ok = 0
        total_fail = 0
        for bk_tenant_id, biz_ids in tenant_to_biz_ids.items():
            self.stdout.write(f"[tenant={bk_tenant_id}] 待处理业务数: {len(biz_ids)}")
            if dry_run:
                for bk_biz_id in biz_ids:
                    self.stdout.write(f"  [dry-run] tenant={bk_tenant_id} biz={bk_biz_id} modes={modes}")
                continue

            # 设置租户上下文与管理员用户：下游建策略/建通知组/查指标缓存均依赖正确的租户与操作人
            set_local_tenant_id(bk_tenant_id=bk_tenant_id)
            set_local_username(get_admin_username(bk_tenant_id=bk_tenant_id))

            for bk_biz_id in biz_ids:
                for mode in modes:
                    try:
                        run_build_in(int(bk_biz_id), mode=mode)
                        total_ok += 1
                    except Exception:
                        total_fail += 1
                        logger.exception(
                            "[init_builtin_strategies] failed: tenant=%s biz=%s mode=%s",
                            bk_tenant_id,
                            bk_biz_id,
                            mode,
                        )
                        self.stderr.write(f"  FAIL tenant={bk_tenant_id} biz={bk_biz_id} mode={mode}")

        if dry_run:
            self.stdout.write("dry-run 结束（未实际加载）。")
        else:
            self.stdout.write(f"完成。成功 {total_ok} 次 / 失败 {total_fail} 次（(业务 x 模式) 计数）。")
