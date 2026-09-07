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

from django.utils.translation import gettext as _

from apps.log_databus.constants import LogPluginInfo
from apps.log_databus.nodeman_v3.exceptions import NodeManV3CapabilityBlocked

# 已发布插件包代次，V3 固定为 2
RELEASE_PACKAGE_GENERATION = 2

# 日志侧插件版本常量是 "latest"（apps/log_databus/constants.py 的 LogPluginInfo.VERSION），
# 而 V3 specify_plugin 的 version 必选且不接受占位符
# （NodeMan pkg/types/deploy_policy.go:321-330 只校验非空，不认识 latest），
# 直接透传会被当成字面量版本号去匹配插件包，匹配不到就整策略下发失败。
PLACEHOLDER_VERSIONS = {"latest", ""}


def resolve_plugin_version(client, plugin_name: str = LogPluginInfo.NAME, configured_version: str = "") -> str:
    """
    把 latest 解析成节点管理侧「已启用且为默认版本」的具体版本号。

    多平台默认版本不一致时直接失败关闭而不是随便挑一个：specify_plugin 只能表达单一版本，
    若 linux 与 windows 的默认版本不同，挑错会把一批主机的采集器降级或升级，
    这类变更必须由人显式决定。
    """
    configured_version = (configured_version or LogPluginInfo.VERSION or "").strip()
    if configured_version.lower() not in PLACEHOLDER_VERSIONS:
        return configured_version

    payload = {
        "generation": RELEASE_PACKAGE_GENERATION,
        "page": {"offset": 0, "limit": 1000},
        "exact_include_conditions": {
            "name": [plugin_name],
            "enabled": [True],
            "as_default": [True],
        },
    }
    items = (client.list_release_plugin_brief(payload) or {}).get("items") or []
    versions = {item.get("version") for item in items if item.get("version")}

    if not versions:
        raise NodeManV3CapabilityBlocked(
            NodeManV3CapabilityBlocked.MESSAGE.format(
                err=_("节点管理没有 {} 的默认已发布版本，无法确定采集器版本").format(plugin_name)
            )
        )
    if len(versions) > 1:
        platforms = [
            f"{item.get('os_type')}/{item.get('cpu_arch')}={item.get('version')}"
            for item in items
            if item.get("version")
        ]
        raise NodeManV3CapabilityBlocked(
            NodeManV3CapabilityBlocked.MESSAGE.format(
                err=_("{} 各平台默认版本不一致（{}），请先统一默认版本或在采集项上指定版本").format(
                    plugin_name, ", ".join(sorted(platforms))
                )
            )
        )

    return versions.pop()
