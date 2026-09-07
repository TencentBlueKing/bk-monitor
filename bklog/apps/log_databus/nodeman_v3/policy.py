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

import hashlib
import json

from django.utils.translation import gettext as _

from apps.log_databus.constants import LogPluginInfo
from apps.log_databus.nodeman_v3.constants import (
    SPEC_TYPE_SPECIFY_PLUGIN,
    SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE,
)
from apps.log_databus.nodeman_v3.exceptions import NodeManV3CapabilityBlocked
from apps.log_databus.nodeman_v3.identity import build_policy_name
from apps.log_databus.nodeman_v3.scopes import build_scopes
from apps.utils.log import logger


class SubscriptionStepsTranslator:
    """
    把 V2 订阅 steps 翻译成 V3 部署策略 specs。

    刻意复用 collector_scenario.get_subscription_steps 的产物，而不是为 V3 重写六种场景的参数生成：
    行/段/WinEvent/Redis/Syslog/Kafka 的 local 参数口径分散在各 scenario 里，重写一遍等于把出数
    正确性重新赌一次。V3 侧同样是「插件包模板 + 渲染上下文」的组合，因此 steps 可以无损映射：

      main:<plugin> 步（MAIN_INSTALL_PLUGIN） -> specify_plugin（保证进程存在且版本正确）
      <plugin> 步（子配置模板 + context）      -> specify_plugin_sub_config_template

    节点管理只对「插件进程已 running」的主机下发子配置
    （internal/backend/dpmgr/analyze_specific_plugin_sub_config_template.go:108-112），
    所以两个 spec 必须同时存在，缺了 specify_plugin 会出现「策略下发成功但一台机器都没生效」。
    """

    def __init__(self, plugin_name: str = LogPluginInfo.NAME):
        self.plugin_name = plugin_name

    def _pick_steps(self, steps: list[dict]) -> tuple[dict | None, dict]:
        main_step = None
        sub_step = None
        for step in steps:
            step_id = step.get("id")
            if step_id == f"main:{self.plugin_name}":
                main_step = step
            elif step_id == self.plugin_name:
                sub_step = step

        if sub_step is None:
            # syslog 场景只有一个步骤，且该步骤的 id 就是插件名；这里兜底取首个 PLUGIN 步
            plugin_steps = [step for step in steps if step.get("type") == "PLUGIN"]
            if not plugin_steps:
                raise NodeManV3CapabilityBlocked(
                    NodeManV3CapabilityBlocked.MESSAGE.format(err=_("订阅步骤中不存在 PLUGIN 步骤"))
                )
            sub_step = plugin_steps[-1]

        return main_step, sub_step

    @staticmethod
    def _sub_config_template_names(step: dict) -> list[str]:
        templates = (step.get("config") or {}).get("config_templates") or []
        # 主配置由 specify_plugin 负责，子配置 spec 只能带非主配置模板：
        # 把 is_main 的模板混进子配置会让节点管理重写主配置，进而影响同机其它采集项
        return [tpl["name"] for tpl in templates if not tpl.get("is_main")]

    def build_specs(self, steps: list[dict], plugin_version: str) -> list[dict]:
        main_step, sub_step = self._pick_steps(steps)
        if main_step is None:
            logger.info(
                f"[nodeman_v3] subscription steps without main step, plugin={self.plugin_name}, "
                f"specify_plugin spec is still generated to ensure the process exists"
            )

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
                "type": SPEC_TYPE_SPECIFY_PLUGIN,
                "param": {
                    "plugin_name": self.plugin_name,
                    "version": plugin_version,
                },
            },
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
        _main_step, sub_step = self._pick_steps(steps)
        return self._sub_config_template_names(sub_step)


def build_policy_payload(
    *,
    collector_config_id: int,
    bk_biz_id: int,
    target_node_type: str,
    target_nodes: list[dict] | None,
    steps: list[dict],
    plugin_version: str,
    description: str = "",
    plugin_name: str = LogPluginInfo.NAME,
) -> dict:
    """
    生成部署策略的期望态（不含 deploy_policy_id，create/update 各自再补）。
    """
    translator = SubscriptionStepsTranslator(plugin_name=plugin_name)
    return {
        "name": build_policy_name(collector_config_id),
        "description": description or f"bklog collector config {collector_config_id}",
        # enabled 恒为 True：采集项停用不是把策略停掉，而是把 scopes 清空让收敛器反删子配置。
        # 策略被 disable 后收敛器不再处理它（discoverEnabledPoliciesBySpec 只捞 enabled 策略），
        # 已下发的子配置会永久残留在主机上继续采集。
        "enabled": True,
        "specs": translator.build_specs(steps, plugin_version),
        "scopes": build_scopes(bk_biz_id, target_node_type, target_nodes),
    }


def calculate_fingerprint(payload: dict) -> str:
    """
    期望态指纹，用于跳过无变化的收敛。

    只覆盖 specs 与 scopes：name/description 变化不影响主机上的实际配置，
    没必要为一次改名触发全量重新下发。
    """
    material = {"specs": payload.get("specs"), "scopes": payload.get("scopes")}
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
