# 代码风格和注释规范

## 代码注释风格

本项目遵循 [Google Python风格指南](https://google.github.io/styleguide/pyguide.html) 的注释规范，使用文档字符串（Docstring）进行代码注释。

## 函数注释示例

```python
def fetch_user_data(user_id: int, include_profile: bool = True) -> dict:
    """获取用户数据。
    
    Args:
        user_id: 用户ID
        include_profile: 是否包含用户资料，默认为True
        
    Returns:
        包含用户信息的字典
        
    Raises:
        UserNotFoundError: 当用户不存在时
        DatabaseConnectionError: 当数据库连接失败时
        
    Example:
        >>> user_data = fetch_user_data(123)
        >>> print(user_data['username'])
        'john_doe'
    """
    pass
```

## 类注释示例

```python
class UserManager:
    """用户管理器，负责用户的增删改查操作。
    
    该类提供了完整的用户生命周期管理功能，包括用户创建、更新、
    删除和查询等操作。支持批量操作和异步处理。
    
    Attributes:
        db_connection: 数据库连接对象
        cache_client: 缓存客户端对象
        
    Example:
        >>> manager = UserManager(db_conn, cache_client)
        >>> user = manager.create_user("john_doe", "john@example.com")
        >>> users = manager.get_users_by_role("admin")
    """
    
    def __init__(self, db_connection, cache_client):
        """初始化用户管理器。
        
        Args:
            db_connection: 数据库连接对象
            cache_client: 缓存客户端对象
        """
        self.db_connection = db_connection
        self.cache_client = cache_client
    
    def create_user(self, username: str, email: str) -> dict:
        """创建新用户。
        
        Args:
            username: 用户名，必须唯一
            email: 用户邮箱地址
            
        Returns:
            新创建的用户信息字典
            
        Raises:
            ValueError: 当用户名或邮箱格式不正确时
            DuplicateUserError: 当用户名已存在时
            
        Example:
            >>> user = manager.create_user("alice", "alice@example.com")
            >>> print(user['id'])
            12345
        """
        pass
```

## 模块注释示例

```python
"""
蓝鲸监控平台基础模块 - 空间管理

此模块提供空间管理的核心功能，包括：
- 空间创建、更新、删除
- 空间权限管理
- 空间数据同步
- 空间配置管理

主要组件：
- SpaceManager: 空间管理器
- SpaceConfig: 空间配置类
- SpacePermission: 空间权限类

使用示例：
    >>> from bk_monitor_base.domains.space import SpaceManager
    >>> manager = SpaceManager()
    >>> space = manager.create_space("prod", "生产环境")
"""

# 模块代码...
```

## 注释规范要点

1. **使用中文注释**：在中文团队中，使用中文注释更容易理解
2. **保持一致性**：在项目中统一使用同一种注释风格
3. **及时更新**：当代码变更时，同步更新相关注释
4. **避免冗余**：不要写显而易见的注释
5. **包含必要信息**：函数注释应包含参数说明、返回值、异常等
6. **使用类型提示**：结合类型注解提高代码可读性

## 代码格式化

### Ruff

项目使用 [Ruff](https://beta.ruff.rs/docs/configuration/) 进行代码格式化及自动修复。

Ruff的相关配置可以在 `pyproject.toml` 文件中进行查看。

在本地开发时，可以根据自己使用IDE进行对应的配置：

* [VS Code](https://docs.astral.sh/ruff/editors/setup/#vs-code)
* [PyCharm](https://docs.astral.sh/ruff/editors/setup/#pycharm)
* [更多编辑器](https://docs.astral.sh/ruff/editors/setup/)

### basedpyright

项目使用 [basedpyright](https://docs.basedpyright.com/v1.29.4/) 进行类型检查。

basedpyright的相关配置可以在 `pyproject.toml` 文件中进行查看。

在本地开发时，可以根据自己使用IDE进行对应的配置，详细说明可以查看 [basedpyright IDEs](https://docs.basedpyright.com/v1.29.4/installation/ides/)。

**忽略类型检查**: 如果需要忽略某些代码的类型检查，可以在代码中使用 `# pyright: ignore`, `# pyright: ignore[reportUnknownVariableType]` 等注释。

**创建类型存根**: 如果因为某些第三方库缺少类型注解或类型注解不准确，可以考虑为该库创建类型存根，详细说明可以查看 [为第三方库补充类型注解指南](./type-stubs.md)。

## 代码检查

### pre-commit

项目要求在提交代码时，必须使用 pre-commit 进行基础的代码检查，其中包含 `Ruff` 和 `basedpyright` 的检查。

pre-commit 的配置文件在 `.pre-commit-config.yaml` 文件中。

```bash
pre-commit install
```

执行 pre-commit install 后，会自动安装 pre-commit 的钩子，在提交代码时，会自动进行代码检查。
