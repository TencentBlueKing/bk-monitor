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

from apps.log_databus.constants import LogPluginInfo
from apps.log_databus.nodeman_v3.client import get_client
from apps.log_databus.nodeman_v3.identity import build_sub_config_name
from apps.log_databus.nodeman_v3.models import NodeManV3Binding, NodeManV3SubConfigTarget
from apps.utils.log import logger

# 每轮定时收敛抽查的主机数。只为验证文件名契约还成立，不做全量对账
CONTRACT_SAMPLE_SIZE = 3


@dataclass
class HostConfigFacts:
    """一台主机上某插件的全部配置文件事实"""

    bk_host_id: int
    # config_file_name -> 接口返回的原始 item
    files: dict[str, dict] = field(default_factory=dict)
    # template_name -> 该模板在主机上实际的落地文件名
    name_by_template: dict[str, str] = field(default_factory=dict)

    def md5_of(self, config_file_name: str) -> str:
        return (self.files.get(config_file_name) or {}).get("md5") or ""

    def context_of(self, config_file_name: str) -> dict:
        return (self.files.get(config_file_name) or {}).get("custom_config_context") or {}


def read_host_config_facts(bk_biz_id: int, bk_host_id: int, plugin_name: str = LogPluginInfo.NAME) -> HostConfigFacts:
    """
    回读单台主机上的插件配置文件。

    `plugin/list_config_files`（NodeMan v3.0.1-alpha.77+）返回 name / template_name / md5 /
    content / custom_config_context —— 这是我们第一次能拿到「主机上实际生效的那份子配置」。

    ⚠️ **这是单主机接口**（`bk_host_id` 是 int64 而不是数组），N 台主机就是 N 次请求。
    所以它只能用在窄场景，绝不能进状态页主路径：状态页的 per-host 判定仍然走
    workflow → operation 加本地 generation。当前的三个用法：

    1. 用户点开单台主机详情时的精确对账（`CollectorStatusReader.instance_detail`）
    2. 移出范围的主机确认无残留后回收本地行（`purge_removed_targets` 的输入）
    3. 定时收敛里抽查少量主机，校验子配置文件名这个契约还成立

    若节点管理后续把入参改成主机数组，上面第 1、3 条就能合并成状态页的正证，
    届时可以把 BKL-4 的 generation 计数降级成兜底。
    """
    facts = HostConfigFacts(bk_host_id=bk_host_id)
    client = get_client(bk_biz_id)
    items = (client.list_config_files(bk_host_id, plugin_name) or {}).get("items") or []
    for item in items:
        config_file_name = item.get("name")
        if not config_file_name:
            continue
        facts.files[config_file_name] = item
        template_name = item.get("template_name")
        if template_name:
            facts.name_by_template[template_name] = config_file_name
    return facts


def check_sub_config_name_contract(binding: NodeManV3Binding, facts: HostConfigFacts) -> list[str]:
    """
    校验子配置落地文件名规则是否仍然成立，返回失配的模板名列表。

    文件名规则 `<模板名去扩展名>_deploy_<策略ID><扩展名>` 来自 NodeMan 的
    `internal/backend/dpmgr/utils.go`，现已写进
    `docs/integration/deploy_policy/specify_plugin_sub_config_template.md`，
    但仍然是对方可以单方面改的。改了之后我们的本地对账会全面失配，而表现只是
    「状态页永远显示待下发」—— 没有任何报错，是典型的静默失效。

    这里能做交叉校验是因为接口同时回传 `name` 与 `template_name`：按 template_name 找到
    主机上那份文件，再拿它的真实 name 与我们推导的名字比。这是留档 §1.4 一直缺的在线信号。
    """
    if not binding.deploy_policy_id:
        return []

    mismatched = []
    for template_name in binding.sub_config_template_names or []:
        actual = facts.name_by_template.get(template_name)
        if not actual:
            # 模板在主机上压根不存在，属于「没下发」而不是「命名规则变了」，不在本函数职责内
            continue
        if actual != build_sub_config_name(template_name, binding.deploy_policy_id):
            mismatched.append(template_name)

    if mismatched:
        logger.error(
            f"[nodeman_v3] sub config name contract broken, NodeMan may have changed its naming rule; "
            f"fix build_sub_config_name. binding={binding.resource_type}:{binding.resource_key}, "
            f"bk_host_id={facts.bk_host_id}, templates={mismatched}, "
            f"actual={[facts.name_by_template.get(name) for name in mismatched]}"
        )
    return mismatched


def verify_host_targets(binding: NodeManV3Binding, bk_host_id: int, plugin_name: str = LogPluginInfo.NAME) -> dict:
    """
    对账单台主机上本采集项的子配置，并把实际内容 MD5 落到 applied_md5。

    这是**精确对账**，与状态页的推断口径互补：状态页只知道「最近一轮下发成功了」，
    这里直接看主机上有没有那个文件、内容摘要是什么。两者不一致时以本函数为准，
    但不要拿它去覆盖状态页 —— 单主机接口撑不起按主机数放大的请求量。

    返回 {"checked", "present", "missing", "name_contract_mismatched", "pending_removal_clean"}。
    """
    result = {
        "checked": False,
        "present": [],
        "missing": [],
        "name_contract_mismatched": [],
        # 已标记移出且主机上确认无残留 —— purge_removed_targets 的输入条件
        "pending_removal_clean": False,
    }

    rows = list(NodeManV3SubConfigTarget.objects.filter(binding=binding, bk_host_id=bk_host_id))
    if not rows:
        return result

    facts = read_host_config_facts(binding.bk_biz_id, bk_host_id, plugin_name)
    result["checked"] = True
    result["name_contract_mismatched"] = check_sub_config_name_contract(binding, facts)

    for row in rows:
        actual_md5 = facts.md5_of(row.config_file_name)
        if actual_md5:
            result["present"].append(row.config_file_name)
            # 只在变化时写，避免每次点开详情都产生一次无意义的 UPDATE
            if row.applied_md5 != actual_md5:
                row.applied_md5 = actual_md5
                row.save(update_fields=["applied_md5", "updated_at", "updated_by"])
        else:
            result["missing"].append(row.config_file_name)

    # 全部行都已移出期望范围，且主机上一个都不剩，才算清理干净
    result["pending_removal_clean"] = bool(rows) and not any(row.is_desired for row in rows) and not result["present"]
    return result
