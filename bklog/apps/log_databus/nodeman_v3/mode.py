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
from apps.log_search.constants import CollectorScenarioEnum

# custom / client 场景没有实现 get_subscription_steps（见 collector_scenario/custom.py、client.py），
# 这两个场景由自定义上报创建，没有物理机插件需要下发。进入 V3 只会在构造期望态时抛 NotImplementedError，
# 因此不允许新准入；已有 binding 仍按粘性归属继续由 V3 管理。
V2_ONLY_COLLECTOR_SCENARIOS = frozenset({CollectorScenarioEnum.CUSTOM.value, CollectorScenarioEnum.CLIENT.value})

# 显式取值档位。与「未设置」必须分开：前者是运维主动配置，后者沿用历史默认关闭。
# true 是现网固定取值，与 on 同为强制打开，运维不必再改 DB 灰度。
ENV_FORCED_ON_VALUES = frozenset({"on", "true", "1", "yes"})
ENV_FORCED_OFF_VALUES = frozenset({"off", "false", "0", "no"})


def _parse_ids(raw) -> set[int]:
    """容忍数字、字符串及逗号分隔值，非法项忽略并保持 fail-closed。"""
    if not raw:
        return set()
    if isinstance(raw, list | tuple | set):
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


def get_nodeman_v3_env_value() -> str | None:
    """
    环境变量取值，小写去空白；未设置或空白返回 None。

    必须保留字符串：解析成布尔后无法区分「没配」与「配了关闭」，而这两者的灰度行为不同。
    """
    raw = getattr(settings, "ENABLE_NODEMAN_V3_VALUE", None)
    value = str(raw).strip().lower() if raw is not None else ""
    if value:
        return value
    # 原值为空时回退布尔开关：生产环境两者由同一环境变量推导；这里主要兼容
    # override_settings(ENABLE_NODEMAN_V3=True) 的既有用法，等价于环境变量 true。
    return "true" if getattr(settings, "ENABLE_NODEMAN_V3", False) is True else None


def _env_forced_state() -> bool | None:
    """
    环境变量的强制档位：True 强制准入、False 强制关闭、None 交给 FeatureToggle 灰度。

    true 与 on 都是强制打开：运维环境的变量取值已固定为 true，若仍要灰度就还得再改 DB，
    与「环境变量是运维主入口」冲突。未设置与非法值都走 DB 灰度——否则 DB 灰度开关永远
    不可达，等于把它留成死代码。
    """
    env_value = get_nodeman_v3_env_value()
    if env_value in ENV_FORCED_ON_VALUES:
        return True
    if env_value in ENV_FORCED_OFF_VALUES:
        return False
    return None


def is_nodeman_v3_admitted(bk_biz_id: int | None, collector_config_id: int | None = None) -> bool:
    """业务或特殊采集项是否准入 V3；环境变量强制档位优先于 FeatureToggle 灰度。"""
    forced = _env_forced_state()
    if forced is not None:
        return forced
    return _toggle_allows(get_nodeman_v3_toggle(), bk_biz_id, collector_config_id)


def has_nodeman_v3_bindings() -> bool:
    """是否已存在必须继续由 V3 管理的采集项。"""
    from apps.log_databus.nodeman_v3.models import NodeManV3Binding

    return NodeManV3Binding.objects.filter(resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG).exists()


def is_nodeman_v3_available() -> bool:
    """
    是否可能出现 V3 字符串任务 ID。

    toggle 关闭只停止新准入；已有 binding 仍需查询历史 workflow、状态和详情。
    on 档位下 DB 可能是 off，此时 V3 仍会产生字符串任务标识，不能按 toggle 判定。
    """
    forced = _env_forced_state()
    if forced is not None:
        return forced or has_nodeman_v3_bindings()
    toggle = get_nodeman_v3_toggle()
    return bool(toggle and toggle.status in {"debug", "on"}) or has_nodeman_v3_bindings()


def resolve_nodeman_v3_collector_ids(collector_configs) -> set[int]:
    """
    批量解析采集项归属，一次读取 toggle 和 binding，避免列表接口 N+1。

    归属顺序：
    1. 已有 V3 binding                              -> V3（粘性归属）
    2. subscription_id 非空                         -> V2
    3. 采集场景没有订阅步骤实现                       -> V2
    4. 环境变量 on / true                            -> V3（跳过灰度）
    5. 环境变量 off / false                          -> V2
    6. FeatureToggle off / 缺失 / DB 异常           -> V2
    7. FeatureToggle on                              -> V3
    8. FeatureToggle debug 命中业务或特殊采集项       -> V3
    9. 其余（含环境变量未设置）                       -> V2
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

    # 强制档位下不查 toggle，避免 DB 记录反过来限制 on；其余情况沿用原有灰度读取。
    # 前置条件（binding、subscription_id、场景）仍在环境变量之前判定：环境变量只替换灰度这一层，
    # 不能把 custom/client 重新拉进 V3，否则会在构造期望态时抛 NotImplementedError。
    forced = _env_forced_state()
    toggle = None
    if forced is None:
        toggle = get_nodeman_v3_toggle()
    result = set()
    for config in configs:
        collector_config_id = getattr(config, "collector_config_id", None)
        if collector_config_id in binding_ids:
            result.add(collector_config_id)
            continue
        if getattr(config, "subscription_id", None):
            continue
        if getattr(config, "collector_scenario_id", None) in V2_ONLY_COLLECTOR_SCENARIOS:
            continue
        if forced:
            result.add(collector_config_id)
            continue
        if forced is False:
            continue
        if _toggle_allows(toggle, getattr(config, "bk_biz_id", None), collector_config_id):
            result.add(collector_config_id)
    return result


def should_use_nodeman_v3(collector_config) -> bool:
    """判断单个采集项走 V3 还是 V2；归属只取自静态身份，不按调用结果回退。"""
    collector_config_id = getattr(collector_config, "collector_config_id", None)
    return collector_config_id in resolve_nodeman_v3_collector_ids([collector_config])
