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
# Selector 工厂 —— DynamicCompositionPolicy 的 selector 构造抽象
#
# DynamicCompositionPolicy.selector 是无参 callable（`Callable[[], str]`），
# 但配置文件里没法直接序列化 callable。本模块的职责是把"配置字典"翻译成
# "运行期可调用对象"，抽象出以下两点：
#
#   1. 配置期规格 → 运行期 callable 的翻译"发生在哪"、"由谁做"是显式的、
#      可命名、可复用、可单测的东西，不再是内联在 django/conf.py 里的匿名闭包。
#   2. 未来接第二种 selector 数据源（etcd / apollo / 环境变量），只需要新
#      注册一个 factory 或传一个 dotted path，django/conf.py 一行都不用改。
#
# 配置规格：
#   selector = {
#       "type": "<内置名称 或 dotted path>",
#       # 其余键作为 kwargs 透传给 factory
#       ...
#   }
#
# 内置类型：
#   - django_setting: 从 django.conf.settings 读某个属性（走 DynamicSettings +
#     GlobalConfig 通道），是"运维改配置 ≤180s 全集群生效"的落点
#   - static:         始终返回固定字符串；主要给单测/纯 Python 场景用，
#     构造 DynamicCompositionPolicy 时完全绕开 django
#
# 扩展：业务侧可以直接把 `type` 写成 dotted path（如 `myapp.selectors.EtcdSelector`），
# 只要该路径可以被 `import_class` 加载且加载结果 callable(**kwargs) 后返回
# `Callable[[], str]`，就能无缝接入。
# ---------------------------------------------------------------------------

from collections.abc import Callable
from typing import Any

from ...core.utils import import_class

# selector 名称 → factory 的注册表。factory 签名为
# `Callable[..., Callable[[], str]]`：接受配置里除 `type` 之外的 kwargs，
# 返回真正的 selector（无参 callable）。
SelectorFactory = Callable[..., Callable[[], str]]

_SELECTOR_REGISTRY: dict[str, SelectorFactory] = {}


def register_selector(name: str) -> Callable[[SelectorFactory], SelectorFactory]:
    """把 factory 函数注册到内置 selector 名下。

    使用装饰器语法：::

        @register_selector("django_setting")
        def _django_setting_selector(attr: str, default: str = "") -> Callable[[], str]: ...

    重复注册同名会直接覆盖（框架内当前只在本模块内部使用，不对外暴露注册接口）。
    """

    def _decorator(factory: SelectorFactory) -> SelectorFactory:
        _SELECTOR_REGISTRY[name] = factory
        return factory

    return _decorator


def build_selector(spec: dict[str, Any]) -> Callable[[], str]:
    """按配置字典构造 selector。

    Args:
        spec: 形如 ``{"type": "<name or dotted path>", ...kwargs}`` 的字典。
              ``type`` 必填；其余键会以 kwargs 形式透传给 factory。

    Returns:
        无参 callable，每次调用返回一个字符串（selector 当前值）。

    Raises:
        ValueError: spec 非法（缺 type、type 未知、type 加载失败等）。
    """
    if not isinstance(spec, dict):
        raise ValueError(f"selector spec must be a dict, got {type(spec).__name__}")
    if "type" not in spec:
        raise ValueError(f"selector spec missing 'type': {spec!r}")

    type_ = spec["type"]
    if not isinstance(type_, str) or not type_:
        raise ValueError(f"selector spec 'type' must be a non-empty string, got {type_!r}")

    kwargs = {k: v for k, v in spec.items() if k != "type"}

    factory: SelectorFactory
    if "." in type_:
        # 业务侧自定义：dotted path 直接加载。import_class 失败时会抛 ConfigError。
        factory = import_class(type_)  # type: ignore[assignment]
    else:
        if type_ not in _SELECTOR_REGISTRY:
            raise ValueError(
                f"unknown selector type {type_!r}; "
                f"available built-ins: {sorted(_SELECTOR_REGISTRY)} "
                f"(or use a dotted path to a custom factory)"
            )
        factory = _SELECTOR_REGISTRY[type_]

    selector = factory(**kwargs)
    if not callable(selector):
        raise ValueError(f"selector factory {type_!r} returned non-callable {type(selector).__name__}")
    return selector


# ---------------------------------------------------------------------------
# 内置 selector 类型
# ---------------------------------------------------------------------------


@register_selector("django_setting")
def _django_setting_selector(attr: str = "", default: str = "") -> Callable[[], str]:
    """从 ``django.conf.settings`` 动态读取指定属性。

    走 DynamicSettings + GlobalConfig 通道：运维在 Django Admin 改后
    ≤180s 全集群生效，无需重启进程。属性缺失时回退到 ``default``。

    注意：django 的 import 延后到 factory 内部触发；只要没有配置
    ``type=django_setting`` 的 selector，本文件的加载**完全不依赖 django**，
    保持 iam_engine 框架层 0 Django 耦合。
    """
    if not isinstance(attr, str) or not attr:
        raise ValueError("django_setting selector requires non-empty 'attr'")

    from django.conf import settings  # 延迟导入，避免污染框架层

    def _read() -> str:
        return getattr(settings, attr, default)

    return _read


@register_selector("static")
def _static_selector(value: str) -> Callable[[], str]:
    """始终返回固定字符串的 selector。

    典型用途：
      * 单元测试里配置 ``{"type": "static", "value": "any_of"}`` 完全绕开 django。
      * 灰度/发布过程需要临时"钉住"某个策略时的兜底配置。
    """
    if not isinstance(value, str):
        raise ValueError(f"static selector requires 'value' to be str, got {type(value).__name__}")

    def _read() -> str:
        return value

    return _read
