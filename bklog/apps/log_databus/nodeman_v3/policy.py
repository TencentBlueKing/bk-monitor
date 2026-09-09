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

import copy
import hashlib
import json

from django.utils.translation import gettext as _

from apps.log_databus.constants import LogPluginInfo
from apps.log_databus.nodeman_v3.constants import (
    SPEC_TYPE_SPECIFY_PLUGIN,
    SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE,
)
from apps.log_databus.nodeman_v3.exceptions import NodeManV3CapabilityBlocked
from apps.log_databus.nodeman_v3.identity import build_plugin_policy_name, build_policy_name
from apps.log_databus.nodeman_v3.scopes import build_scopes


class SubscriptionStepsTranslator:
    """
    把 V2 订阅 steps 翻译成 V3 部署策略 specs。

    刻意复用 collector_scenario.get_subscription_steps 的产物，而不是为 V3 重写六种场景的参数生成：
    行/段/WinEvent/Redis/Syslog/Kafka 的 local 参数口径分散在各 scenario 里，重写一遍等于把出数
    正确性重新赌一次。V3 侧同样是「插件包模板 + 渲染上下文」的组合，因此 steps 可以无损映射：

      <plugin> 步（子配置模板 + context） -> specify_plugin_sub_config_template

    V2 的 main:<plugin> 步（MAIN_INSTALL_PLUGIN）**不**翻译成本策略的 specify_plugin spec，
    改由业务级安装策略承载，原因见 build_plugin_install_payload。
    """

    def __init__(self, plugin_name: str = LogPluginInfo.NAME):
        self.plugin_name = plugin_name

    def _pick_sub_step(self, steps: list[dict]) -> dict:
        for step in steps:
            if step.get("id") == self.plugin_name:
                return step

        # syslog 场景只有一个步骤，且该步骤的 id 就是插件名；这里兜底取末个 PLUGIN 步
        plugin_steps = [step for step in steps if step.get("type") == "PLUGIN"]
        if not plugin_steps:
            raise NodeManV3CapabilityBlocked(
                NodeManV3CapabilityBlocked.MESSAGE.format(err=_("订阅步骤中不存在 PLUGIN 步骤"))
            )
        return plugin_steps[-1]

    @staticmethod
    def _sub_config_template_names(step: dict) -> list[str]:
        templates = (step.get("config") or {}).get("config_templates") or []
        # 主配置由安装策略负责，子配置 spec 只能带非主配置模板：
        # 把 is_main 的模板混进子配置会让节点管理重写主配置，进而影响同机其它采集项
        return [tpl["name"] for tpl in templates if not tpl.get("is_main")]

    def build_specs(self, steps: list[dict]) -> list[dict]:
        sub_step = self._pick_sub_step(steps)

        template_names = self._sub_config_template_names(sub_step)
        if not template_names:
            raise NodeManV3CapabilityBlocked(
                NodeManV3CapabilityBlocked.MESSAGE.format(err=_("订阅步骤中未找到子配置模板"))
            )

        context = (sub_step.get("params") or {}).get("context") or {}
        if not context.get("dataid"):
            # dataid 是采集项出数的唯一标识，缺失会导致数据落到错误的链路上
            raise NodeManV3CapabilityBlocked(
                NodeManV3CapabilityBlocked.MESSAGE.format(err=_("子配置渲染上下文缺少 dataid"))
            )

        return [
            {
                "type": SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE,
                "param": {
                    "plugin_name": self.plugin_name,
                    "config_files_detail": [
                        {"template_name": name, "is_main_config": False} for name in template_names
                    ],
                    # Jinja2 渲染时 custom_config_context 的键会直接合并到模板顶层作用域
                    # （NodeMan action_render_plugin_config.go:172-175），与 V2 params.context 一致，
                    # 因此这里原样透传 {dataid, local}，插件包模板无需改动。
                    "custom_config_context": context,
                },
            },
        ]

    def sub_config_template_names(self, steps: list[dict]) -> list[str]:
        return self._sub_config_template_names(self._pick_sub_step(steps))


def build_policy_payload(
    *,
    collector_config_id: int,
    bk_biz_id: int,
    target_node_type: str,
    target_nodes: list[dict] | None,
    steps: list[dict],
    description: str = "",
    plugin_name: str = LogPluginInfo.NAME,
) -> dict:
    """
    生成采集项子配置策略的期望态（不含 deploy_policy_id，create/update 各自再补）。
    """
    translator = SubscriptionStepsTranslator(plugin_name=plugin_name)
    return {
        "name": build_policy_name(collector_config_id),
        "description": description or f"bklog collector config {collector_config_id}",
        # enabled 恒为 True：采集项停用不是把策略停掉，而是把 scopes 清空让收敛器反删子配置。
        # 策略被 disable 后收敛器不再处理它（discoverEnabledPoliciesBySpec 只捞 enabled 策略），
        # 已下发的子配置会永久残留在主机上继续采集。
        "enabled": True,
        "specs": translator.build_specs(steps),
        "scopes": build_scopes(bk_biz_id, target_node_type, target_nodes),
    }


def build_plugin_install_payload(
    *,
    bk_biz_id: int,
    plugin_version: str,
    scopes: list[dict],
    plugin_name: str = LogPluginInfo.NAME,
) -> dict:
    """
    生成业务级「采集器安装」策略的期望态。

    为什么安装能力必须与子配置分成两条策略：

    带 specify_plugin 的策略会被策略发现按插件名扩散——`discoverEnabledPoliciesBySpecifyPlugin`
    的过滤条件只有「spec 类型 + plugin_name」（NodeMan
    internal/backend/storage/deploypolicy/domain_dpmgr.go:51-65），于是执行任意一条采集项策略
    都会把同插件的全部 enabled 策略拉进同一次收敛。进入同一闭包后冲突消解按 spec.UniqueID() 分组，
    而子配置模板 spec 的 UniqueID 就是插件名（pkg/types/deploy_policy.go:289-294），
    同类型无条件判冲突（同文件 :124-127），因此按创建时间靠后的采集项会在共享主机上被整体剔除
    （internal/backend/dpmgr/conflict_resolver.go:48-50、:109-120）。
    主机被剔除后又会命中「不在目标范围内」分支，把该采集项**已经生效**的子配置删掉
    （analyze_specific_plugin_sub_config_template.go:228-236）。
    净效果是同机第二个采集项静默失效，且 execute 照常返回 trigger_id。

    只声明子配置 spec 的策略在策略发现里是叶子节点，不查库不扩散
    （internal/backend/dpmgr/discover.go:218-222），因此永远是单例闭包，目标完整保留。
    把 specify_plugin 收敛到「一个业务一条」之后，带 specify_plugin 的策略在同业务内只有一条，
    也就不存在互相剔除。

    另外 specify_plugin 的收敛只做安装与升级，不会因为主机移出范围而卸载插件
    （internal/backend/dpmgr/analyzer.go:139-170 只遍历 params.Targets），
    所以安装策略缩容不会把还在被其它采集项使用的采集器卸掉。
    """
    return {
        "name": build_plugin_policy_name(bk_biz_id, plugin_name),
        "description": f"bklog collector plugin for biz {bk_biz_id}",
        "enabled": True,
        "specs": [
            {
                "type": SPEC_TYPE_SPECIFY_PLUGIN,
                "param": {
                    "plugin_name": plugin_name,
                    "version": plugin_version,
                },
            },
        ],
        "scopes": scopes,
    }


def merge_scopes(scope_groups: list[list[dict]]) -> list[dict]:
    """
    把各采集项的 scope 条目并成安装策略的目标范围。

    只在范围表达式层面求并集，不把拓扑/模板/动态分组展开成主机：范围表达式的展开由节点管理的
    ScopeCalculator 负责，日志侧自己展开会与对方口径不一致（BKL-3 的期望快照是另一件事，
    只用于状态回读与差异可见，不作为下发口径）。
    """
    merged: list[dict] = []
    groups: dict[tuple, dict] = {}
    for scopes in scope_groups:
        for scope in scopes or []:
            body = scope.get("scope") or {}
            # 同类型、同粒度、同业务的条目合并成一条，把各自的目标列表求并集。
            # 不合并的话条目数会随采集项数量线性增长（一个业务几百个采集项就是几百条 scope），
            # 既撑大 update 请求，也让节点管理每轮收敛都要把同一个拓扑算上几百遍。
            group_key = (scope.get("type"), body.get("granularity"), body.get("bk_biz_id"))
            target = groups.get(group_key)
            if target is None:
                target = copy.deepcopy(scope)
                groups[group_key] = target
                merged.append(target)
                continue

            target_body = target["scope"]
            for field, values in body.items():
                if not isinstance(values, list):
                    continue
                existing = target_body.setdefault(field, [])
                # topo 的 paths 是 dict 列表，按序列化结果去重
                seen = {json.dumps(item, sort_keys=True, ensure_ascii=False) for item in existing}
                for value in values:
                    marker = json.dumps(value, sort_keys=True, ensure_ascii=False)
                    if marker in seen:
                        continue
                    seen.add(marker)
                    existing.append(value)
    return merged


def calculate_fingerprint(payload: dict) -> str:
    """
    期望态指纹，用于跳过无变化的收敛。

    只覆盖 specs 与 scopes：name/description 变化不影响主机上的实际配置，
    没必要为一次改名触发全量重新下发。
    """
    material = {"specs": payload.get("specs"), "scopes": payload.get("scopes")}
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
