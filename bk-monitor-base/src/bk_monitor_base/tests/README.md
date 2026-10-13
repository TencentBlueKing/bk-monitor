# 测试文档

## 目录结构

示例目录结构：
```
src/bk_monitor_base/tests/
├── __init__.py
├── conftest.py                  # pytest 公共配置
├── cli/                         # CLI 相关测试
│   └── test_cli.py
├── config/                      # 配置相关测试
│   └── test_config.py
├── domains/                     # 领域模块相关测试
│   └── spaces/
│       └── test_define.py
├── infras/                       # 基础设施相关测试
│   └── test_redis.py
└── README.md                    # 测试说明文档
```

* conftest.py 是 pytest 的配置文件，用于设置 pytest 的配置和共享 fixtures。
* 测试文件的命名规则为 test_*.py
* 目录结构与 src 目录结构保持一致，便于组织和寻找测试代码。

## 依赖包

如果需要为测试安装特殊的依赖，如果 `mockredis`等，请添加到 `dev` 分组下。

```bash
uv add xxx --group dev
```

可以使用 uv sync --all-groups 安装所有依赖，包含 `dev` 分组。

```bash
uv sync --all-groups
```

## 运行

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest src/bk_monitor_base/tests/cli/test_cli.py
```

## 覆盖率

项目包含覆盖率报告脚本，位于 `scripts/coverage_report.py`。

```bash
# 生成覆盖率报告
python scripts/coverage_report.py
```

## 配置

主要公共配置在 `pyproject.toml` 和 `src/bk_monitor_base/tests/conftest.py` 中。

- **`pyproject.toml`**: 对pytest进行配置，如测试目录，运行参数等。
- **`src/bk_monitor_base/tests/conftest.py`**: 进行公共配置，如django setup，基础mock，公共fixtures等。

## 要求

1. 测试代码需要与src目录结构保持一致，便于组织和寻找测试代码。
2. 测试应当在默认配置下运行。
3. 单个测试应当可以独立运行，避免出现测试之间互相依赖的情况。
4. 测试对接口/函数的mock应该在测试完成后恢复，避免影响其他测试。
5. 测试中不应该出现sleep等耗时操作，避免影响测试运行速度。
6. 测试过程中产生的数据应当在测试完成后删除，避免影响其他测试，通过添加标识符来区分不同的测试用例生成的数据，避免并行测试时数据冲突。

## 示例

### 使用Class组织测试

```python
import pytest
from bk_monitor_base.domains.space import SpaceManager

class TestSpaceManager:
    """SpaceManager类的测试用例。"""
    
    def test_create_space_success(self):
        """测试成功创建空间。"""
        manager = SpaceManager()
        space = manager.create_space("test", "测试空间")
        
        assert space.name == "test"
        assert space.description == "测试空间"
    
    def test_create_space_duplicate_name(self):
        """测试创建重复名称空间时抛出异常。"""
        manager = SpaceManager()
        manager.create_space("test", "测试空间")
        
        with pytest.raises(ValueError, match="空间名称已存在"):
            manager.create_space("test", "另一个测试空间")

```

### 使用Fixture

```python
import pytest

@pytest.fixture
def space_manager():
    """创建SpaceManager实例的fixture。"""
    return SpaceManager()

@pytest.fixture
def sample_space_data():
    """示例空间数据。"""
    return {
        "name": "test_space",
        "description": "测试空间",
        "type": "development"
    }

def test_create_space_with_fixture(space_manager, sample_space_data):
    """使用fixture测试空间创建。"""
    space = space_manager.create_space(
        sample_space_data["name"],
        sample_space_data["description"]
    )
    
    assert space.name == sample_space_data["name"]
```
