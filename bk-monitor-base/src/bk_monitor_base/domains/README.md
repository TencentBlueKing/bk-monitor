# 领域服务

## 简介

本模块下定义了项目的核心业务逻辑，包括空间管理、数据采集、告警策略等。

每一个目录下都是一个独立的业务模块，模块之间通过接口进行交互。

## 规范

### 目录结构

以 空间管理(space) 为例

```text
bk_monitor_base/
├── domains/
|   ├── space/ # 空间管理模块
|   │   ├── __init__.py
|   │   ├── models.py   # django模型
|   │   ├── define.py   # 核心模型定义
|   │   ├── operations.py   # 核心模型操作
|   │   ├── ... # 其他文件
├── space.py # 空间管理入口
```

在domains/space/ 目录下
- `models.py` 定义了空间管理用到的Django数据模型
- `define.py` 定义了空间管理的核心模型
- `operations.py` 定义了空间管理的核心操作
- `...` 定义了空间管理其他文件

在domains同级目录下的 `space.py` 中定义模块的入口。

### 模块入口

为了让使用者可以方便导入，同时避免对外暴露不必要的API，需要在 `domains`的同级目录下定义模块的入口，在其中只暴露必要的函数/类/变量。

模块入口应当与模块名一致。

以空间管理(space) 为例，在 `bk_monitor_base/space.py` 中定义模块的入口。

```python
# ❌
from bk_monitor_base.domains.space import Space 

# ✅
from bk_monitor_base.space import Space
```

### 模块命名

1. 模块名应当使用小写字母，多个单词之间使用下划线连接。
    ```text
    space ✅
    Space ❌
    spacemanager ❌
    ```
2. 模块名应当简洁明了，能够清晰地表达模块的功能。
    ```text
    space ✅
    space_service ❌
    ```
3. 模块名应当是名词，而不是动词或形容词。
    ```text
    collect ❌
    collector ✅
    ```
4. 模块名应当是单数，而不是复数。
    ```text
    space ✅
    spaces ❌
    ```
    