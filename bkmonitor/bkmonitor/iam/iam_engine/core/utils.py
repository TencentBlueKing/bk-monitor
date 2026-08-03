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
# 框架内部通用工具
#
# 规则：
#   1. 不 import django、iam SDK、requests 等外部依赖
#   2. 每个函数保持无状态、纯函数
#   3. 只放"跨 3 个以上模块被复用"的东西，避免 utils 膨胀
# ---------------------------------------------------------------------------

import importlib
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from typing import TypeVar

from ..core.exceptions import ConfigError

_T = TypeVar("_T")


def chunked(items: Sequence[_T], size: int) -> Iterator[Sequence[_T]]:
    """把序列按固定大小切片。

    典型使用场景：v4 Provider 内部把批量鉴权拆成 <=20 条一批。

    Args:
        items: 待切分的序列
        size: 每片大小；必须 > 0

    Yields:
        序列切片；最后一片可能不满

    Example:
        >>> list(chunked([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    if size <= 0:
        raise ValueError(f"chunk size must be positive, got {size}")
    for i in range(0, len(items), size):
        yield items[i : i + size]


def import_class(dotted_path: str) -> type:
    """按点分路径动态导入类。

    用于从 settings 里的字符串配置解析出真实类。

    Args:
        dotted_path: 形如 "pkg.module.ClassName" 的完整路径

    Returns:
        导入到的类对象

    Raises:
        ConfigError: 路径非法、模块不存在、类不存在时统一抛出
    """
    if "." not in dotted_path:
        raise ConfigError(f"invalid dotted path (missing module): {dotted_path!r}")

    module_path, _, class_name = dotted_path.rpartition(".")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ConfigError(f"cannot import module {module_path!r}: {exc}") from exc

    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise ConfigError(f"module {module_path!r} has no attribute {class_name!r}") from exc


def retry(
    fn: Callable[[], _T],
    *,
    attempts: int = 3,
    delay: float = 0.2,
    backoff: float = 2.0,
    retry_on: type[BaseException] | tuple[type[BaseException], ...] = Exception,
) -> _T:
    """带退避的重试执行。

    只重试指定类型的异常；其它异常（如 PermissionDenied）直接向上抛。

    Args:
        fn: 无参可调用；重试的执行单元
        attempts: 最大尝试次数（含首次），必须 >= 1
        delay: 首次重试前的等待秒数
        backoff: 每次等待时间的倍增因子
        retry_on: 需要重试的异常类型；默认所有 Exception

    Returns:
        fn 的返回值

    Raises:
        最后一次尝试抛出的异常
    """
    if attempts < 1:
        raise ValueError(f"attempts must be >= 1, got {attempts}")

    current_delay = delay
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return fn()
        except retry_on as exc:
            last_exc = exc
            if i == attempts - 1:
                break
            time.sleep(current_delay)
            current_delay *= backoff
    assert last_exc is not None  # 循环里保证会赋值
    raise last_exc


def deduplicate(items: Iterable[_T]) -> list[_T]:
    """保序去重。

    dict.fromkeys 在 Python 3.7+ 保序，用它去重比手写 seen set 更简洁。

    Args:
        items: 可迭代对象；元素必须可哈希

    Returns:
        保持首次出现顺序的去重列表
    """
    return list(dict.fromkeys(items))
