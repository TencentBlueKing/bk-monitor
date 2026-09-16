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
from django.core.exceptions import ImproperlyConfigured

from apps.log_databus.nodeman_v3.constants import (
    NODEMAN_INTEGRATION_MODES,
    NODEMAN_MODE_V2,
    NODEMAN_MODE_V3_FRESH,
    RESOURCE_TYPE_COLLECTOR_CONFIG,
)


def get_nodeman_integration_mode() -> str:
    """
    读取节点管理集成模式。

    只允许 v2 与 v3_fresh 两种取值，不提供 hybrid：V3-only 环境下任何 V3 失败都必须失败关闭，
    一旦允许混合模式，异常路径就会悄悄退回 V2 并产生双写。
    """
    mode = getattr(settings, "NODEMAN_INTEGRATION_MODE", NODEMAN_MODE_V2) or NODEMAN_MODE_V2
    if mode not in NODEMAN_INTEGRATION_MODES:
        raise ImproperlyConfigured(
            f"invalid NODEMAN_INTEGRATION_MODE: {mode}, choices are {list(NODEMAN_INTEGRATION_MODES)}"
        )
    return mode


def is_nodeman_v3_only() -> bool:
    """
    环境是否处于 V3-only 模式。

    这是**环境级**判定，只说明「本环境的 V3 控制面已启用」，不代表某个采集项一定走 V3。
    采集项生命周期与状态回读一律用 should_use_nodeman_v3()，不要用这个函数。
    """
    return get_nodeman_integration_mode() == NODEMAN_MODE_V3_FRESH


def _parse_id_whitelist(raw) -> set[int]:
    """逗号分隔的 ID 白名单。非数字项直接忽略，避免一个笔误把整张白名单废掉。"""
    if not raw:
        return set()
    if isinstance(raw, (list, tuple, set)):
        items = raw
    else:
        items = str(raw).split(",")
    parsed = set()
    for item in items:
        item = str(item).strip()
        if item.lstrip("-").isdigit():
            parsed.add(int(item))
    return parsed


def should_use_nodeman_v3(collector_config) -> bool:
    """
    判断**单个采集项**走 V3 还是 V2。

    为什么需要这一层：`is_nodeman_v3_only()` 是环境级开关，而存量环境装满了带 subscription_id
    的 V2 采集项。整环境打开 v3_fresh 会把这些采集项的状态页、启停、删除全部指向 V3，
    而它们没有 V3 binding —— 表现就是老采集项集体失能。灰度必须以采集项为粒度。

    判定顺序（静态归属，一次判定，不随运行时成败改变）：

    1. 环境模式不是 v3_fresh                       -> V2
    2. 已有 V3 binding                             -> V3
    3. subscription_id 非空（存量 V2 采集项）        -> V2
    4. 白名单为空                                   -> V3（等价于原来 v3_fresh 的全量语义）
    5. 采集项 ID 或业务 ID 命中白名单               -> V3
    6. 其余                                        -> V2

    第 2 条不能省：白名单收窄时，已经通过 V3 下发过的采集项若被踢回 V2，主机上那份
    V3 子配置就再没有任何控制面管它了 —— 既不会被更新也不会被删除，变成永久残留。
    归属一旦确立就只能前进。

    ⚠️ 这**不是**被否决的 hybrid 模式。被否决的是「V3 调用失败后回退 V2」那种动态回退，
    它会让同一个采集项在两套控制面各写一次，产生双写与状态分裂。这里的判据全部来自采集项的
    静态身份，与调用结果无关；归 V3 的采集项遇到任何 V3 失败仍然失败关闭，绝不回退 V2。
    后续新增判定分支必须守住这条边界：判据只能取自采集项身份，不能取自调用结果。
    """
    if not is_nodeman_v3_only():
        return False

    # 局部导入：mode 被大量模块在启动早期引入，模块级导入 models 会把 ORM 拖进导入链
    from apps.log_databus.nodeman_v3.identity import build_resource_key
    from apps.log_databus.nodeman_v3.models import NodeManV3Binding

    collector_config_id = getattr(collector_config, "collector_config_id", None)
    if (
        collector_config_id
        and NodeManV3Binding.objects.filter(
            resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
            resource_key=build_resource_key(collector_config_id),
        ).exists()
    ):
        return True

    if getattr(collector_config, "subscription_id", None):
        return False

    collector_whitelist = _parse_id_whitelist(getattr(settings, "NODEMAN_V3_COLLECTOR_WHITELIST", ""))
    biz_whitelist = _parse_id_whitelist(getattr(settings, "NODEMAN_V3_BIZ_WHITELIST", ""))
    if not collector_whitelist and not biz_whitelist:
        return True

    if collector_config_id and collector_config_id in collector_whitelist:
        return True
    return getattr(collector_config, "bk_biz_id", None) in biz_whitelist
