<p align="center">
  <img src="./bk_monitorv3.png" alt="FastAPI" height="80" style="vertical-align: middle;"/>
  <span style="font-size:3rem; font-weight:bold; vertical-align: middle;">蓝鲸监控</span>
</p>
<p align="center">
    <em>蓝鲸监控是蓝鲸智云推出的监控平台</em>
</p>

---

## 开发环境

### 依赖安装与管理

项目使用 [uv](https://docs.astral.sh/uv/getting-started/) 管理项目依赖。

除了默认依赖外，项目依赖有三个额外的分组。

    * aidev是AI相关的依赖（默认分组）
    * test是测试相关的依赖
    * dev是本地开发依赖

#### 创建虚拟环境

创建虚拟环境，如果本地没有对应的 Python 版本，uv 会自动安装。

```bash
# 在项目目录下会创建虚拟环境，默认为 .venv
uv venv --seed

# 也可以指定虚拟环境目录
uv venv venv --seed

# 激活虚拟环境
source .venv/bin/activate
```

在 VS Code 中，可以通过 `[Ctrl/Cmd]+Shift+P` 输入 `Python: Select Interpreter` 选择虚拟环境。

在 Pycharm 中，可以通过 `File` -> `Settings` -> `Project: <project_name>` -> `Python Interpreter` 选择虚拟环境。

#### 安装依赖

```bash
# 安装全部依赖
uv sync --all-groups
```

#### 添加依赖

添加依赖

```bash
# 添加默认依赖
uv add <package>
# 添加到dev分组
uv add --dev <package>
# 添加到test分组
uv add --group test <package>
# 添加到aidev分组
uv add --group aidev <package>
```

#### 删除依赖

```bash
uv remove <package>
```

### 代码检查

#### Ruff

项目使用 [Ruff](https://beta.ruff.rs/docs/configuration/) 进行代码格式化及自动修复。

在本地开发时，可以根据自己使用IDE进行对应的配置

* [VS Code](https://docs.astral.sh/ruff/editors/setup/#vs-code)
* [Pycharm](https://docs.astral.sh/ruff/editors/setup/#pycharm)
* [More](https://docs.astral.sh/ruff/editors/setup/)

#### pre-commit

项目要求在提交代码时，必须使用 pre-commit 进行基础的代码检查，其中包含 Ruff 的检查。

pre-commit 的配置文件在 `.pre-commit-config.yaml` 文件中。

pre-commit 在 dev 分组中，所以需要先完成相关依赖安装。

```bash
pre-commit install
```

执行 pre-commit install 后，会自动安装 pre-commit 的钩子，在提交代码时，会自动进行代码检查。
