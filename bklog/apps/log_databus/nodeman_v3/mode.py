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

from django.conf import settings

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import NODEMAN_V3_COLLECTOR
from apps.log_databus.nodeman_v3.constants import RESOURCE_TYPE_COLLECTOR_CONFIG


def _parse_ids(raw) -> set[int]:
    """容忍数字、字符串及逗号分隔值，非法项忽略并保持 fail-closed。"""
    if not raw:
        return set()
    if isinstance(raw, (list, tuple, set)):
        items = raw
    else:
        items = str(raw).split(",")
    return {int(item) for item in (str(item).strip() for item in items) if item.lstrip("-").isdigit()}


def _toggle_allows(toggle, bk_biz_id: int | None, collector_config_id: int | None = None) -> bool:
    """
    按 FeatureToggle 快照判断一个**尚未建立 V3 binding**的采集项是否允许进入 V3。

    FeatureToggleObject.switch() 会再次查库；这里复用已经读取的 toggle，避免批量列表按采集项产生
    N 次重复查询。只接受 off/debug/on，未知状态 fail-closed。
    """
    if not toggle or toggle.status == "off":
        return False

    feature_config = toggle.feature_config if isinstance(toggle.feature_config, dict) else {}
    collector_ids = _parse_ids(feature_config.get("collector_config_ids"))
    if collector_config_id and collector_config_id in collector_ids:
        return True

    if toggle.status == "on":
        return True
    if toggle.status != "debug":
        return False

    biz_whitelist = _parse_ids(toggle.biz_id_white_list)
    if biz_whitelist:
        return bk_biz_id in biz_whitelist
    if collector_ids:
        # debug 下显式配置 collector IDs 时，它本身就是完整灰度范围，不能再因 dev/stag
        # 环境兜底而把其它新采集项一并放行
        return False

    biz_blacklist = _parse_ids(toggle.biz_id_black_list)
    if biz_blacklist:
        return bk_biz_id not in biz_blacklist

    return settings.ENVIRONMENT in {"dev", "stag"}


def get_nodeman_v3_toggle():
    """读取 NodeMan V3 准入开关；DB 异常或记录缺失时返回 None，新采集项自动留在 V2。"""
    return FeatureToggleObject.toggle(NODEMAN_V3_COLLECTOR)


def is_nodeman_v3_admitted(bk_biz_id: int | None, collector_config_id: int | None = None) -> bool:
    """业务或特殊采集项是否被 FeatureToggle 准入 V3。"""
    return _toggle_allows(get_nodeman_v3_toggle(), bk_biz_id, collector_config_id)


def has_nodeman_v3_bindings() -> bool:
    """是否已存在必须继续由 V3 管理的采集项。"""
    from apps.log_databus.nodeman_v3.models import NodeManV3Binding

    return NodeManV3Binding.objects.filter(resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG).exists()


def is_nodeman_v3_available() -> bool:
    """
    是否可能出现 V3 字符串任务 ID。

    toggle 关闭只停止新准入；已有 binding 仍需查询历史 workflow、状态和详情。
    """
    toggle = get_nodeman_v3_toggle()
    return bool(toggle and toggle.status in {"debug", "on"}) or has_nodeman_v3_bindings()


def resolve_nodeman_v3_collector_ids(collector_configs) -> set[int]:
    """
    批量解析采集项归属，一次读取 toggle 和 binding，避免列表接口 N+1。

    归属顺序：
    1. 已有 V3 binding                              -> V3（粘性归属）
    2. subscription_id 非空                         -> V2
    3. FeatureToggle off / 缺失 / DB 异常           -> V2
    4. FeatureToggle on                              -> V3
    5. FeatureToggle debug 命中业务或特殊采集项       -> V3
    6. 其余                                          -> V2
    """
    configs = list(collector_configs)
    collector_ids = {
        int(config.collector_config_id) for config in configs if getattr(config, "collector_config_id", None)
    }

    binding_ids = set()
    if collector_ids:
        from apps.log_databus.nodeman_v3.models import NodeManV3Binding

        binding_ids = set(
            NodeManV3Binding.objects.filter(
                resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
                collector_config_id__in=collector_ids,
            ).values_list("collector_config_id", flat=True)
        )

    toggle = get_nodeman_v3_toggle()
    result = set()
    for config in configs:
        collector_config_id = getattr(config, "collector_config_id", None)
        if collector_config_id in binding_ids:
            result.add(collector_config_id)
            continue
        if getattr(config, "subscription_id", None):
            continue
        if _toggle_allows(toggle, getattr(config, "bk_biz_id", None), collector_config_id):
            result.add(collector_config_id)
    return result


def should_use_nodeman_v3(collector_config) -> bool:
    """判断单个采集项走 V3 还是 V2；归属只取自静态身份，不按调用结果回退。"""
    collector_config_id = getattr(collector_config, "collector_config_id", None)
    return collector_config_id in resolve_nodeman_v3_collector_ids([collector_config])
