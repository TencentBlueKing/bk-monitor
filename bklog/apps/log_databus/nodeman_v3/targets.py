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

from dataclasses import dataclass, field

from django.db import transaction
from django.utils.translation import gettext as _

from apps.api import CCApi
from apps.log_databus.constants import TargetNodeTypeEnum
from apps.log_databus.nodeman_v3.exceptions import NodeManV3CapabilityBlocked
from apps.log_databus.nodeman_v3.identity import build_sub_config_name
from apps.log_databus.nodeman_v3.models import (
    NodeManV3Binding,
    NodeManV3SubConfigTarget,
)
from apps.log_search.constants import CMDB_HOST_SEARCH_FIELDS
from apps.log_search.handlers.biz import BizHandler
from apps.utils.log import logger


@dataclass
class TargetDiff:
    """一次目标快照收敛的差异结果。"""

    added: set[int] = field(default_factory=set)
    removed: set[int] = field(default_factory=set)
    unchanged: set[int] = field(default_factory=set)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.removed)

    def summary(self) -> dict:
        return {"added": sorted(self.added), "removed": sorted(self.removed), "unchanged": len(self.unchanged)}


def expand_target_hosts(bk_biz_id: int, target_node_type: str, target_nodes: list[dict] | None) -> set[int]:
    """
    把采集目标展开成主机 ID 集合。

    **这不是下发口径。** 下发给节点管理的仍然是范围表达式（scopes），主机集合由对方的
    ScopeCalculator 计算；这里展开出来的快照只用于三件事：

    1. 识别目标变化并触发收敛——节点管理不会自己重算策略（execute 建的是一次性 trigger），
       主机加入/移出拓扑后必须由日志侧发现并再执行一次
    2. 主机反查采集项（BKL-4 用它替代 V2 的 query_host_subscriptions）
    3. 让「新增主机不漏、移除主机只删本采集项子配置」在本地可验证

    刻意复用 V2 状态页的同一条 CMDB 展开路径（BizHandler.search_host / execute_dynamic_group），
    而不是另写一套：自写展开会同时与节点管理、与旧状态页两边都不一致，出现「页面说有这台机器、
    实际没下发」时无法判断是谁错。两侧口径仍可能有偏差（见 reconcile_binding_targets 的说明），
    但至少偏差只有一处来源。
    """
    target_nodes = target_nodes or []
    if not target_nodes:
        return set()

    if target_node_type == TargetNodeTypeEnum.INSTANCE.value:
        if any(not node.get("bk_host_id") for node in target_nodes):
            # 与 scopes.build_scopes 保持同一条失败关闭线：历史采集项可能只存了 ip + bk_cloud_id，
            # 这类目标在 V3 下根本下发不了，快照里也不能静默少算，否则会掩盖下发缺口
            raise NodeManV3CapabilityBlocked(
                NodeManV3CapabilityBlocked.MESSAGE.format(
                    err=_("采集目标存在缺少 bk_host_id 的主机实例，无法展开期望快照")
                )
            )
        return {node["bk_host_id"] for node in target_nodes}

    if target_node_type == TargetNodeTypeEnum.DYNAMIC_GROUP.value:
        host_ids: set[int] = set()
        for node in target_nodes:
            hosts = CCApi.execute_dynamic_group.bulk_request(
                params={
                    "bk_biz_id": bk_biz_id,
                    "id": node["bk_inst_id"],
                    "fields": CMDB_HOST_SEARCH_FIELDS,
                }
            )
            host_ids.update(host["bk_host_id"] for host in hosts if host.get("bk_host_id"))
        return host_ids

    if target_node_type in (
        TargetNodeTypeEnum.TOPO.value,
        TargetNodeTypeEnum.SERVICE_TEMPLATE.value,
        TargetNodeTypeEnum.SET_TEMPLATE.value,
    ):
        conditions = [
            {"bk_obj_id": node["bk_obj_id"], "bk_inst_id": node["bk_inst_id"]}
            for node in target_nodes
            if node.get("bk_obj_id") and node.get("bk_inst_id") is not None
        ]
        if not conditions:
            return set()
        hosts = BizHandler(bk_biz_id).search_host(conditions)
        return {host["bk_host_id"] for host in hosts if host.get("bk_host_id")}

    raise NodeManV3CapabilityBlocked(
        NodeManV3CapabilityBlocked.MESSAGE.format(err=_("不支持的采集目标类型: {}").format(target_node_type))
    )


def reconcile_binding_targets(
    binding: NodeManV3Binding,
    desired_host_ids: set[int],
    sub_config_names: list[str],
) -> TargetDiff:
    """
    把期望快照写进 NodeManV3SubConfigTarget，并返回与上一轮的差异。

    移出范围的行**保留**且只标 is_desired=False，不物理删除。两个原因：

    - 删除是异步的。标记完成时节点管理可能还没把子配置从主机上摘掉，行删了就再也查不到
      「这台机器还残留着本采集项的配置」，而这正是「移除主机只删该采集项子配置」的验收依据。
    - 行还在，状态页才能把这台主机显示成 PENDING_REMOVAL 而不是凭空消失。

    真正的行回收交给 purge_removed_targets：确认主机上已经没有本采集项的子配置文件之后再删。
    """
    if not binding.deploy_policy_id:
        # 还没建策略就推不出落地文件名（文件名含 deploy_policy_id）。
        # 这里返回空差异而不是抛错：新建采集项在 create 之前跑到定时任务是正常时序。
        logger.info(
            f"[nodeman_v3] binding has no deploy_policy_id yet, skip target snapshot, "
            f"binding={binding.resource_type}:{binding.resource_key}"
        )
        return TargetDiff()

    config_file_names = [build_sub_config_name(name, binding.deploy_policy_id) for name in sub_config_names or []]
    if not config_file_names:
        logger.warning(
            f"[nodeman_v3] no sub config template recorded, skip target snapshot, "
            f"binding={binding.resource_type}:{binding.resource_key}"
        )
        return TargetDiff()

    with transaction.atomic():
        existing = {
            (row.bk_host_id, row.config_file_name): row
            for row in NodeManV3SubConfigTarget.objects.select_for_update().filter(binding=binding)
        }

        previous_desired = {host_id for (host_id, _name), row in existing.items() if row.is_desired}
        diff = TargetDiff(
            added=desired_host_ids - previous_desired,
            removed=previous_desired - desired_host_ids,
            unchanged=desired_host_ids & previous_desired,
        )

        for host_id in desired_host_ids:
            for config_file_name in config_file_names:
                row = existing.get((host_id, config_file_name))
                if row is None:
                    NodeManV3SubConfigTarget.objects.create(
                        binding=binding,
                        bk_host_id=host_id,
                        config_file_name=config_file_name,
                        # 新目标只是进入期望范围，尚未证明配置已落地。生效代次只能由
                        # workflow operation 成功或可靠的配置文件对账推进。
                        generation=0,
                        is_desired=True,
                    )
                    continue
                if row.is_desired:
                    continue
                # 主机移出后又被加回来：复位 is_desired，但**不要**动 generation 与 applied_md5。
                # generation 表示「已生效的是哪一代」，由状态回读推进；在这里改会让一台从未成功
                # 下发过的主机显示成已生效最新。
                row.is_desired = True
                row.save(update_fields=["is_desired", "updated_at", "updated_by"])

        # 两类行都要标记移出：
        #   1. 主机已不在范围内 —— 该机器上本采集项的全部子配置都要摘掉
        #   2. 主机还在范围内，但这个文件名已经不在期望集合里 —— 改采集场景会换模板名
        #      （文件名由模板名推出），旧文件名的行若一直留在 is_desired=True，状态页会把它
        #      当成「期望有但主机上没有」，永久显示缺配置，而 purge_removed_targets 只回收
        #      is_desired=False 的行，也永远清不掉
        stale_pks = [
            row.pk
            for (host_id, config_file_name), row in existing.items()
            if row.is_desired and (host_id not in desired_host_ids or config_file_name not in config_file_names)
        ]
        if stale_pks:
            NodeManV3SubConfigTarget.objects.filter(pk__in=stale_pks).update(is_desired=False)

    if diff.changed:
        logger.info(
            f"[nodeman_v3] target snapshot changed, "
            f"binding={binding.resource_type}:{binding.resource_key}, diff={diff.summary()}"
        )
    return diff


def purge_removed_targets(binding: NodeManV3Binding, host_ids_without_config: set[int]) -> int:
    """
    回收已确认无残留子配置的移出主机行。

    只有状态回读确认过「这台主机上已经没有本采集项的子配置文件」才删行，否则会把「删除任务
    还没执行完」与「删除已完成」混为一谈。
    """
    if not host_ids_without_config:
        return 0
    deleted, _ = NodeManV3SubConfigTarget.objects.filter(
        binding=binding, is_desired=False, bk_host_id__in=host_ids_without_config
    ).delete()
    return deleted


def collector_config_ids_by_host(bk_biz_id: int, bk_host_ids: list[int]) -> dict[int, list[int]]:
    """
    主机反查采集项，替代 V2 的 query_host_subscriptions。

    改用本地快照而不是问节点管理：V3 的 process/list 只到进程粒度，同机多采集项共用一个
    bkunifylogbeat 进程，从对方查不出「这台机器上跑着哪几个采集项」。而按策略名/文件名反解
    需要先把全业务策略拉回来再解析文件名，成本与口径都不如本地快照。
    """
    if not bk_host_ids:
        return {}
    rows = NodeManV3SubConfigTarget.objects.filter(
        binding__bk_biz_id=bk_biz_id,
        binding__is_enabled=True,
        bk_host_id__in=bk_host_ids,
        is_desired=True,
    ).values_list("bk_host_id", "binding__collector_config_id")

    mapping: dict[int, set[int]] = {}
    for bk_host_id, collector_config_id in rows:
        mapping.setdefault(bk_host_id, set()).add(collector_config_id)
    return {host_id: sorted(ids) for host_id, ids in mapping.items()}
