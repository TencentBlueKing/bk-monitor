"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# CompositionPolicy 名称 → 类 的注册表（框架层）
#
# 存在动机：
#   * 集成层（iam_engine/django/conf.py）过去自己维护 _POLICY_CLASS_MAP，
#     导致 DynamicCompositionPolicy 想在 from_options 里根据"子策略名"实例化
#     嵌套子策略时必须回过头去 import django 层的私有映射，破坏了"框架层
#     零集成层依赖"的方向性。
#   * 把注册表下沉到 composition 目录，让 dynamic.from_options / conf.py
#     共用同一份，dotted path/自定义扩展也走同一套 API。
#
# 使用：
#   from .resolver import resolve_policy_class, register_policy_class
#   policy_cls = resolve_policy_class("any_of")
#
# 支持业务侧扩展：``resolve_policy_class`` 收到含 "." 的字符串时会走
# ``import_class`` 加载 dotted path，不需要预注册。
# ---------------------------------------------------------------------------

from ...core.utils import import_class
from .all_of import AllOfPolicy
from .any_of import AnyOfPolicy
from .base import CompositionPolicy
from .primary import PrimaryPolicy
from .single import SinglePolicy

# 内置策略名 → 类。DynamicCompositionPolicy 在 dynamic.py 的模块加载完成之后
# 通过 register_policy_class("dynamic", DynamicCompositionPolicy) 追加进来，
# 避免 resolver ↔ dynamic 的循环导入。
_POLICY_CLASS_MAP: dict[str, type[CompositionPolicy]] = {
    "single": SinglePolicy,
    "any_of": AnyOfPolicy,
    "all_of": AllOfPolicy,
    "primary": PrimaryPolicy,
}


def register_policy_class(name: str, cls: type[CompositionPolicy]) -> None:
    """注册一个 CompositionPolicy 子类到全局名称表。
    重复注册同名会直接覆盖。
    """
    if not isinstance(name, str) or not name:
        raise ValueError(f"policy name must be a non-empty string, got {name!r}")
    if not isinstance(cls, type) or not issubclass(cls, CompositionPolicy):
        raise ValueError(f"policy class must subclass CompositionPolicy, got {cls!r}")
    _POLICY_CLASS_MAP[name] = cls


def resolve_policy_class(policy_name: str) -> type[CompositionPolicy]:
    """根据策略名返回 CompositionPolicy 子类。

    * 内置名（``single`` / ``any_of`` / ``all_of`` / ``primary`` / ``dynamic``）
      直接查表命中；
    * 含 ``.`` 的字符串被视为 dotted path，走 :func:`import_class` 动态加载，
      允许业务侧不改框架代码就接入自定义 CompositionPolicy 子类。
    """
    if not isinstance(policy_name, str) or not policy_name:
        raise ValueError(f"policy name must be a non-empty string, got {policy_name!r}")

    if "." in policy_name:
        cls = import_class(policy_name)
        if not isinstance(cls, type) or not issubclass(cls, CompositionPolicy):
            raise ValueError(f"dotted policy {policy_name!r} did not resolve to a CompositionPolicy subclass")
        return cls

    policy_cls = _POLICY_CLASS_MAP.get(policy_name)
    if policy_cls is None:
        raise ValueError(f"Unknown composition policy {policy_name!r}. Available: {sorted(_POLICY_CLASS_MAP)}")
    return policy_cls
