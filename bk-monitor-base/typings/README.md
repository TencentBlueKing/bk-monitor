# 类型存根文件目录

此目录用于存放第三方库的类型存根（Type Stubs）文件，为缺少类型注解的第三方库补充类型信息。

## 目录结构

```
typings/
├── django_redis/
│   └── __init__.pyi          # django_redis 的类型存根
└── README.md                  # 本文件
```

## 使用说明

1. **创建存根文件**：当需要使用缺少类型注解的第三方库时，在此目录下创建对应的 `.pyi` 文件
2. **目录结构**：存根文件的目录结构应该与第三方库的包结构保持一致
3. **命名规范**：存根文件使用 `.pyi` 扩展名，文件名与对应的 Python 模块名相同

## 示例

### 为 `django_redis` 创建存根

如果 `django_redis.get_redis_connection` 没有类型注解，创建：

```
typings/django_redis/__init__.pyi
```

内容示例：

```python
from typing import Any
from redis import Redis

def get_redis_connection(alias: str = "default") -> Redis: ...
```

## 配置

类型检查器（basedpyright）的配置在 `pyproject.toml` 中：

```toml
[tool.basedpyright]
stubPath = "typings"  # 指定存根文件目录
```

## 注意事项

1. **最小化原则**：只为实际使用的 API 创建存根，不需要为整个库创建完整的存根
2. **文档化**：在存根文件中添加注释，说明为什么需要这个存根
3. **版本控制**：存根文件应该提交到版本控制，以便团队成员共享
4. **定期更新**：当第三方库更新时，检查是否需要更新存根文件

## 更多信息

详细的使用指南请参考：`docs/development/type-stubs.md`
