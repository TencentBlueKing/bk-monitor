# 为第三方库补充类型注解指南

当第三方库缺少类型注解时，我们可以通过创建类型存根（Type Stubs）文件来补充类型信息。这样可以让类型检查器（如 `basedpyright`）更好地理解第三方库的 API，提供更好的类型检查和 IDE 支持。

## 方法概述

主要有以下几种方法：

1. **使用 `.pyi` 存根文件**（推荐）：在项目中创建类型存根文件
2. **使用 `types-*` 包**：如果 PyPI 上有对应的 types 包，可以直接安装
3. **内联类型注解**：在代码中使用 `TYPE_CHECKING` 和类型注解

## 方法一：使用 `.pyi` 存根文件（推荐）

### 1. 创建存根文件目录结构

在项目根目录创建 `typings/` 目录，然后按照第三方库的包结构创建对应的 `.pyi` 文件：

```
typings/
├── django_redis/
│   ├── __init__.pyi
│   └── client.pyi
└── some_other_lib/
    └── __init__.pyi
```

### 2. 配置类型检查器

在 `pyproject.toml` 中配置 `basedpyright`，添加 `stubPath` 配置：

```toml
[tool.basedpyright]
extraPaths = ["src"]
stubPath = "typings"  # 添加这一行
# ... 其他配置
```

### 3. 编写存根文件

存根文件（`.pyi`）只包含类型信息，不包含实现。例如，为 `django_redis` 创建存根：

```python
# typings/django_redis/__init__.pyi
from typing import Any
from redis import Redis

def get_redis_connection(alias: str = "default") -> Redis[Any]: ...
```

### 4. 注意事项

- 存根文件应该被 `.gitignore` 忽略（如果存根是项目特定的），或者提交到版本控制（如果对团队有用）
- 存根文件只需要包含你实际使用的 API，不需要为整个库创建完整的存根
- 存根文件中的 `...` 表示省略的函数体

## 方法二：使用 `types-*` 包

许多流行的第三方库在 PyPI 上有对应的 `types-*` 包，例如：

- `types-redis` - Redis 的类型存根
- `types-requests` - Requests 的类型存根
- `types-python-dateutil` - python-dateutil 的类型存根

### 安装方式

```bash
# 作为开发依赖安装
uv add types-redis --group dev
```

安装后，类型检查器会自动识别这些类型存根。

## 方法三：内联类型注解

对于简单的类型补充，可以在代码中使用 `TYPE_CHECKING` 和类型别名：

```python
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis import Redis

# 为没有类型注解的函数添加类型注解
def my_function() -> "Redis[Any]":
    from django_redis import get_redis_connection
    return get_redis_connection()  # type: ignore[no-any-return]
```

## 实际示例

### 示例 1：为 `django_redis.get_redis_connection` 创建存根

假设 `django_redis.get_redis_connection` 没有类型注解，我们可以创建：

```python
# typings/django_redis/__init__.pyi
from typing import Any
from redis import Redis

def get_redis_connection(alias: str = "default") -> Redis[Any]: ...
```

### 示例 2：为自定义类型创建存根

如果第三方库返回自定义类型，可以这样定义：

```python
# typings/my_lib/__init__.pyi
from typing import Protocol

class MyCustomType(Protocol):
    def method(self, arg: str) -> int: ...
    property: str
```

## 验证类型存根

创建存根后，运行类型检查器验证：

```bash
uv run python -m basedpyright src/bk_monitor_base/domains/metric_plugin/manager/job/define.py
```

## 最佳实践

1. **最小化原则**：只为实际使用的 API 创建存根，不需要为整个库创建完整的存根
2. **文档化**：在存根文件中添加注释，说明为什么需要这个存根
3. **版本控制**：如果存根对团队有用，应该提交到版本控制；如果是个人临时使用，可以添加到 `.gitignore`
4. **定期更新**：当第三方库更新时，检查是否需要更新存根文件
5. **优先使用官方存根**：如果 PyPI 上有官方的 `types-*` 包，优先使用官方存根

## 常见问题

### Q: 存根文件应该放在哪里？

A: 推荐放在项目根目录的 `typings/` 目录中，并在 `pyproject.toml` 中配置 `stubPath`。

### Q: 存根文件需要提交到版本控制吗？

A: 如果存根对团队有用且相对稳定，应该提交。如果是临时性的或项目特定的，可以添加到 `.gitignore`。

### Q: 如何知道第三方库是否有类型存根？

A: 
1. 检查库的文档
2. 在 PyPI 上搜索 `types-<库名>`
3. 检查库的源码是否包含 `py.typed` 文件（表示库本身支持类型注解）

### Q: 存根文件中的 `...` 是什么意思？

A: `...` 是 Python 的省略号字面量，在存根文件中表示省略的函数体。这是 PEP 484 规定的存根文件语法。

## 参考资源

- [PEP 484 - Type Hints](https://www.python.org/dev/peps/pep-0484/)
- [PEP 561 - Distributing and Packaging Type Information](https://www.python.org/dev/peps/pep-0561/)
- [typeshed - Collection of type stubs](https://github.com/python/typeshed)
- [Basedpyright Documentation](https://github.com/RobertCraigie/basedpyright)
