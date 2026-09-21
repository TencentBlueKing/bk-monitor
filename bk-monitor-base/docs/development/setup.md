# 开发环境搭建

## 依赖管理

项目使用 [uv](https://docs.astral.sh/uv/getting-started/) 管理项目依赖。

除了默认依赖外，项目依赖有两个额外的分组：

* `dev` 是本地开发依赖，包含代码检查和测试相关的依赖
* `cli` 是命令行工具相关的依赖

### 创建虚拟环境

如果本地没有对应的 Python 版本，uv 会根据 `.python-version` 自动安装。

```bash
# 在项目目录下会创建虚拟环境，默认为 .venv
uv venv --seed

# 也可以指定虚拟环境目录
uv venv venv --seed

# 激活虚拟环境
source .venv/bin/activate
```

### IDE配置

#### VS Code
在 VS Code 中，可以通过 `[Ctrl/Cmd]+Shift+P` 输入 `Python: Select Interpreter` 选择虚拟环境。

#### PyCharm
在 Pycharm 中，可以通过 `File` -> `Settings` -> `Project: <project_name>` -> `Python Interpreter` 选择虚拟环境。

### 安装依赖

```bash
# 安装全部依赖
uv sync --all-groups
```

### 添加依赖

```bash
# 添加默认依赖
uv add <package>
# 添加到dev分组
uv add --dev <package>
# 添加到cli分组
uv add --group cli <package>
```

### 删除依赖

```bash
uv remove <package>
```

## 环境变量

项目支持 .env 和环境变量两种方式进行配置。
