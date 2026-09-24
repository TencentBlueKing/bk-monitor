"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import datetime

from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab
from django.utils import timezone

from apps.log_databus.models import CollectorConfig
from apps.log_databus.nodeman_v3.constants import (
    FULL_HEAL_INTERVAL_MINUTES,
    NodeManV3OperationStatus,
    RECONCILE_BATCH_LIMIT,
    RESOURCE_TYPE_COLLECTOR_CONFIG,
    RESOURCE_TYPE_COLLECTOR_PLUGIN,
    TARGET_RECONCILE_INTERVAL_MINUTES,
)
from apps.log_databus.nodeman_v3.models import (
    NodeManV3Binding,
    NodeManV3Operation,
    NodeManV3SubConfigTarget,
)
from apps.log_databus.nodeman_v3.targets import (
    expand_target_hosts,
    purge_removed_targets,
    reconcile_binding_targets,
)
from apps.utils.log import logger

# 派发中/结果未知超过这个时长仍未推进，认为进程在派发过程中挂了，由定时任务重放
STUCK_OPERATION_MINUTES = 15


@periodic_task(run_every=crontab(minute=f"*/{TARGET_RECONCILE_INTERVAL_MINUTES}"))
def reconcile_nodeman_v3_targets():
    """
    采集目标动态收敛。

    节点管理**不会**自己重算部署策略：deploy_policy/execute 建的是一次性 trigger
    （internal/backend/manager/deploypolicy_manager.go:31 用 trigger.CategoryOnce），
    全仓库唯一的执行入口是 execute 接口。因此以下两类变化只能靠日志侧定时发现并重新触发：

    1. **目标集合变化**：主机加入/移出拓扑、模板成员变更、动态分组结果变化。
       采集项本身没被编辑过，不会有任何人去调 execute。
    2. **已生效子配置被回收**：采集器进程不 running 时（重启、临时 stop、机器重启窗口），
       节点管理会把该策略在这台主机上的子配置记录删掉
       （analyze_specific_plugin_sub_config_template.go:228-236）。
       这不是异常路径而是常态，所以周期重放是正确性必需，不是优化项。

    对应地本任务有两条触发线：目标变了就立刻收敛；目标没变也每 FULL_HEAL_INTERVAL_MINUTES
    兜底重放一次。
    """
    # binding 是已确立的粘性归属。FeatureToggle 关闭只停止新准入，不能停止历史 V3 采集项收敛
    bindings = NodeManV3Binding.objects.filter(
        resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
        is_enabled=True,
        deploy_policy_id__isnull=False,
    ).order_by("target_snapshot_at", "id")[:RECONCILE_BATCH_LIMIT]

    for binding in bindings:
        try:
            _reconcile_one_binding(binding)
        except Exception:  # pylint: disable=broad-except
            # 单个采集项失败不能中断整轮：一个业务的 CMDB 抖动会让其它业务整轮收敛都停摆
            logger.exception(
                f"[nodeman_v3] reconcile targets failed, binding={binding.resource_type}:{binding.resource_key}"
            )
            # 失败也要推进快照时间，否则它下一轮还排在队首（排序键 target_snapshot_at 升序、
            # NULL 最前）。永久失败的采集项（如目标类型不支持）攒够 RECONCILE_BATCH_LIMIT 个
            # 就会把配额占满，其余采集项永远收敛不到 —— 表现为静默漏采，没有任何报错
            _touch_snapshot(binding)


def _sample_verify(binding: NodeManV3Binding) -> None:
    """
    抽查少量主机：校验子配置文件名契约，并回收已确认无残留的移出主机行。

    抽样而不是全量，因为 `plugin/list_config_files` 是单主机接口（见 config_files 模块说明），
    全量会把每轮收敛的请求数放大到主机数量级。

    这两件事都不影响本轮收敛的正确性，所以整体 fail-open 且自己吞异常：
    在这里抛出去会让一次成功的收敛被记成失败，还会白推一次快照时间。
    联调环境的节点管理若低于 v3.0.1-alpha.77 没有这个接口，也只应该记日志。
    """
    try:
        from apps.log_databus.nodeman_v3.config_files import CONTRACT_SAMPLE_SIZE, verify_host_targets

        def sample(is_desired: bool) -> list[int]:
            return list(
                NodeManV3SubConfigTarget.objects.filter(binding=binding, is_desired=is_desired)
                .values_list("bk_host_id", flat=True)
                .distinct()[:CONTRACT_SAMPLE_SIZE]
            )

        clean_hosts = set()
        for bk_host_id in sample(True) + sample(False):
            if verify_host_targets(binding, bk_host_id).get("pending_removal_clean"):
                clean_hosts.add(bk_host_id)

        purged = purge_removed_targets(binding, clean_hosts)
        if purged:
            logger.info(
                f"[nodeman_v3] purged removed targets, "
                f"binding={binding.resource_type}:{binding.resource_key}, rows={purged}"
            )
    except Exception:  # pylint: disable=broad-except
        logger.exception(f"[nodeman_v3] sample verify failed, binding={binding.resource_type}:{binding.resource_key}")


def _touch_snapshot(binding: NodeManV3Binding) -> None:
    """
    只推进快照时间，不动其它字段。

    仅在异常处理路径里调用，所以自身必须不抛 —— 在这里再抛一次会把「单个采集项失败不中断整轮」
    那层保护直接击穿，等于回到一个业务抖动拖停全环境收敛。

    用 save(update_fields=...) 而不是 queryset.update()：后者会被 OperateRecordQuerySet
    静默覆写 updated_at（apps/models.py:188-191），让基于 updated_at 的卡单检测永远检不出来。
    """
    try:
        binding.target_snapshot_at = timezone.now()
        binding.save(update_fields=["target_snapshot_at", "updated_at", "updated_by"])
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            f"[nodeman_v3] touch target snapshot failed, binding={binding.resource_type}:{binding.resource_key}"
        )


def _reconcile_one_binding(binding: NodeManV3Binding) -> None:
    collector_config = CollectorConfig.objects.filter(collector_config_id=binding.collector_config_id).first()
    if not collector_config:
        logger.warning(
            f"[nodeman_v3] collector config gone, skip target reconcile, "
            f"collector_config_id={binding.collector_config_id}"
        )
        # 同样要推进快照时间。采集项被硬删而 binding 残留时，这条记录的 target_snapshot_at
        # 永远不变，就会一直排在队首（升序、NULL 最前）并占着 RECONCILE_BATCH_LIMIT 的配额；
        # 攒够一批之后其余采集项就再也收敛不到，表现是静默漏采而不是报错
        _touch_snapshot(binding)
        return

    desired_host_ids = expand_target_hosts(
        collector_config.bk_biz_id,
        collector_config.target_node_type,
        collector_config.target_nodes,
    )
    diff = reconcile_binding_targets(binding, desired_host_ids, binding.sub_config_template_names or [])

    # 放在收敛判断之前：目标没变的那一轮同样需要抽查，文件名契约失配与残留子配置
    # 都与目标有没有变化无关
    _sample_verify(binding)

    now = timezone.now()
    needs_heal = binding.last_heal_at is None or binding.last_heal_at < now - datetime.timedelta(
        minutes=FULL_HEAL_INTERVAL_MINUTES
    )
    if not diff.changed and not needs_heal:
        binding.target_snapshot_at = now
        binding.save(update_fields=["target_snapshot_at", "updated_at", "updated_by"])
        return

    # 重放走与手工保存完全相同的收敛入口，force=True 跳过指纹短路。
    # 这里不能只 execute 已有策略：目标变化时策略的 scopes 本身也要改写，
    # 而 execute 只会按策略**当前**的期望态收敛。
    from apps.log_databus.nodeman_v3.installer import NodeManV3CollectorInstaller

    NodeManV3CollectorInstaller(collector_config).rerun()

    binding.refresh_from_db()
    binding.target_snapshot_at = now
    binding.last_heal_at = now
    binding.save(update_fields=["target_snapshot_at", "last_heal_at", "updated_at", "updated_by"])
    logger.info(
        f"[nodeman_v3] target reconcile dispatched, "
        f"collector_config_id={binding.collector_config_id}, "
        f"diff={diff.summary()}, heal={needs_heal}"
    )


@periodic_task(run_every=crontab(minute=f"*/{TARGET_RECONCILE_INTERVAL_MINUTES}"))
def recover_nodeman_v3_operations():
    """
    中断恢复：重放卡在派发中/结果未知的控制面动作。

    进程在 create/update/execute 之间被杀掉时，本地会留下一条 dispatching 或 unknown 的
    operation，而指纹**没有**推进（指纹只在成功派发后写入）。所以这里直接走一次普通收敛就能恢复：
    指纹不匹配会让它重新推一遍期望态。

    重放安全性来自三个写操作本身可重放：create 之前先按策略名反查已有策略、update 是整体
    期望态覆盖、execute 重复触发只是多跑一轮收敛。新增其它写操作时必须先确认幂等，
    否则不能挂到这条恢复路径上。
    """
    # operation 是已发生过的 V3 事实；即使准入开关关闭，卡住的历史操作仍必须恢复
    threshold = timezone.now() - datetime.timedelta(minutes=STUCK_OPERATION_MINUTES)
    stuck = (
        NodeManV3Operation.objects.filter(
            status__in=[NodeManV3OperationStatus.DISPATCHING, NodeManV3OperationStatus.UNKNOWN],
            updated_at__lt=threshold,
            binding__resource_type__in=[RESOURCE_TYPE_COLLECTOR_CONFIG, RESOURCE_TYPE_COLLECTOR_PLUGIN],
        )
        .select_related("binding")
        .order_by("updated_at")[:RECONCILE_BATCH_LIMIT]
    )

    for operation in stuck:
        if operation.binding.resource_type == RESOURCE_TYPE_COLLECTOR_PLUGIN:
            try:
                from apps.log_databus.nodeman_v3.reconciler import CollectorPluginReconciler

                plugin_name = operation.binding.resource_key.partition(":")[2]
                CollectorPluginReconciler(operation.binding.bk_biz_id, plugin_name=plugin_name).reconcile()
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    f"[nodeman_v3] failed to recover stuck plugin operation {operation.id}, "
                    f"bk_biz_id={operation.binding.bk_biz_id}"
                )
                continue
            _close_superseded_operation(operation)
            continue

        collector_config = CollectorConfig.objects.filter(
            collector_config_id=operation.binding.collector_config_id
        ).first()
        if not collector_config:
            # 采集项已被硬删，这条 operation 永远恢复不了。必须落终态，否则它会一直停在
            # dispatching + 旧 updated_at 上被每轮重新选中，占着 RECONCILE_BATCH_LIMIT 的配额，
            # 攒够一批之后真正卡住的动作就再也轮不到恢复
            operation.status = NodeManV3OperationStatus.FAILED
            operation.error_message = "collector config gone, nothing to recover"
            operation.save(update_fields=["status", "error_message", "updated_at", "updated_by"])
            logger.warning(
                f"[nodeman_v3] collector config gone, close stuck operation {operation.id}, "
                f"collector_config_id={operation.binding.collector_config_id}"
            )
            continue
        try:
            from apps.log_databus.nodeman_v3.installer import NodeManV3CollectorInstaller

            # 这里刻意用 apply 而不是 rerun：rerun 带 force=True 会跳过指纹判断，
            # 把已经派发成功、只是状态没回读到的动作再推一遍，白白触发一次全量插件 reload。
            NodeManV3CollectorInstaller(collector_config).apply(collector_config.params or {})
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                f"[nodeman_v3] failed to recover stuck operation {operation.id}, "
                f"collector_config_id={operation.binding.collector_config_id}"
            )
            continue

        _close_superseded_operation(operation)
        logger.info(
            f"[nodeman_v3] recovered stuck operation {operation.id}, "
            f"collector_config_id={operation.binding.collector_config_id}"
        )


def _close_superseded_operation(operation: NodeManV3Operation) -> None:
    """
    恢复动作会创建新 operation，旧记录必须结束，否则每轮都会再次被选中。

    旧轮次真实结果未知，不能写 SUCCESS；新 operation 负责记录本次恢复结果。
    """
    operation.status = NodeManV3OperationStatus.FAILED
    operation.error_message = f"operation stuck over {STUCK_OPERATION_MINUTES}min, superseded by periodic recovery"
    operation.save(update_fields=["status", "error_message", "updated_at", "updated_by"])
