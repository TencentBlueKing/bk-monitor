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

        valid_modes = {"host", "k8s"}
        modes = [m.strip() for m in options["modes"].split(",") if m.strip()]
        bad_modes = [m for m in modes if m not in valid_modes]
        if not modes or bad_modes:
            self.stderr.write(f"--modes 非法: {bad_modes or '(空)'}；仅支持 {sorted(valid_modes)}。")
            return
        dry_run = options["dry_run"]
        explicit_biz_ids = [int(b) for b in options["bk_biz_ids"].split(",") if b.strip()]
        only_tenant_id = options["bk_tenant_id"].strip()

        # 组织待处理的 {bk_tenant_id: [bk_biz_id, ...]}。租户一律由业务真实推导（与 loader 内部
        # bk_biz_id_to_bk_tenant_id 同口径），--bk-tenant-id 只作过滤、不覆盖业务真实租户——否则会把业务
        # 挂到错误租户上下文里建策略/通知组。枚举/解析阶段对单点失败 skip-and-continue，避免一个坏租户/
        # 坏业务号拖垮整轮（不漏覆盖）。
        tenant_to_biz_ids: dict[str, list[int]] = {}
        skipped = 0
        if explicit_biz_ids:
            for bk_biz_id in explicit_biz_ids:
                try:
                    tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
                except Exception:
                    skipped += 1
                    logger.exception("[init_builtin_strategies] resolve tenant failed, skip biz=%s", bk_biz_id)
                    self.stderr.write(f"  SKIP biz={bk_biz_id}（租户解析失败）")
                    continue
                if only_tenant_id and tenant_id != only_tenant_id:
                    continue  # --bk-tenant-id 作为过滤：跳过不属于该租户的业务
                tenant_to_biz_ids.setdefault(tenant_id, []).append(bk_biz_id)
        else:
            if only_tenant_id:
                tenant_ids = [only_tenant_id]
            else:
                try:
                    tenant_ids = [tenant["id"] for tenant in api.bk_login.list_tenant()]
                except Exception:
                    logger.exception("[init_builtin_strategies] list_tenant failed")
                    self.stderr.write("list_tenant 失败，无法枚举租户。")
                    return
            for tenant_id in tenant_ids:
                try:
                    spaces: list[Space] = SpaceApi.list_spaces(bk_tenant_id=tenant_id)
                except Exception:
                    skipped += 1
                    logger.exception("[init_builtin_strategies] list_spaces failed, skip tenant=%s", tenant_id)
                    self.stderr.write(f"  SKIP tenant={tenant_id}（list_spaces 失败）")
                    continue
                tenant_to_biz_ids[tenant_id] = [space.bk_biz_id for space in spaces if space.bk_biz_id > 0]

        triggered = 0
        for bk_tenant_id, biz_ids in tenant_to_biz_ids.items():
            self.stdout.write(f"[tenant={bk_tenant_id}] 待处理业务数: {len(biz_ids)}")
            if dry_run:
                for bk_biz_id in biz_ids:
                    self.stdout.write(f"  [dry-run] tenant={bk_tenant_id} biz={bk_biz_id} modes={modes}")
                continue

            # 设置租户上下文与管理员用户：下游建策略/建通知组/查指标缓存均依赖正确的租户与操作人。
            # 单个租户取管理员/设置上下文失败（如停用租户、list_tenant 含 disabled）不应中断整轮——
            # 记录并跳过该租户、继续其余，保证"不漏覆盖"不被单点失败拖垮。
            try:
                set_local_tenant_id(bk_tenant_id=bk_tenant_id)
                set_local_username(get_admin_username(bk_tenant_id=bk_tenant_id))
            except Exception:
                skipped += 1
                logger.exception("[init_builtin_strategies] setup failed, skip tenant=%s", bk_tenant_id)
                self.stderr.write(f"  SKIP tenant={bk_tenant_id}（管理员/上下文设置失败）")
                continue

            for bk_biz_id in biz_ids:
                for mode in modes:
                    try:
                        run_build_in(int(bk_biz_id), mode=mode)
                        triggered += 1
                    except Exception:
                        # run_build_in 正常会内部吞掉各 loader 异常；此处兜底捕获意外异常并继续。
                        logger.exception(
                            "[init_builtin_strategies] run_build_in failed: tenant=%s biz=%s mode=%s",
                            bk_tenant_id,
                            bk_biz_id,
                            mode,
                        )
                        self.stderr.write(f"  FAIL tenant={bk_tenant_id} biz={bk_biz_id} mode={mode}")

        if dry_run:
            self.stdout.write("dry-run 结束（未实际加载）。")
        else:
            # 注意：run_build_in 内部已吞掉各 loader 异常并返回 None，下面是"已触发的 (业务 x 模式) 次数"，
            # 不等于"成功补建的策略数"；指标未就绪的业务本轮产出 0 条也计入触发。实际补建结果（v2/v3/v4 是否
            # 建出、接入记录是否登记）须按发布后验证方案查 StrategyModel / DefaultStrategyBizAccessModel 复核。
            self.stdout.write(
                f"完成。已触发 {triggered} 个 (业务 x 模式)；跳过 {skipped} 个(租户/业务，枚举或上下文设置失败)。"
                "实际补建结果请按验证方案查 DB 复核。"
            )
