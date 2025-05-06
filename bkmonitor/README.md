<p align="center">
  <img src="docs/logo.png" alt="BkMonitor" style="vertical-align: middle;"/>
</p>

<p align="center">
<a href="https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2FTencentBlueKing%2Fbk-monitor%2Frefs%2Fheads%2Fmaster%2Fbkmonitor%2Fversion.yaml&query=version&label=version" target="_blank">
  <img src="https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2FTencentBlueKing%2Fbk-monitor%2Frefs%2Fheads%2Fmaster%2Fbkmonitor%2Fversion.yaml&query=version&label=version" alt="Version"/>
</a>
<a href="https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FTencentBlueKing%2Fbk-monitor%2Frefs%2Fheads%2Fmaster%2Fbkmonitor%2Fpyproject.toml" target="_blank">
  <img src="https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FTencentBlueKing%2Fbk-monitor%2Frefs%2Fheads%2Fmaster%2Fbkmonitor%2Fpyproject.toml" alt="Python Version from PEP 621 TOML"/>
</a>
<a href="https://github.com/TencentBlueKing/bk-monitor/blob/master/LICENSE.txt" target="_blank">
  <img src="https://img.shields.io/badge/license-mit-brightgreen.svg?style=flat" alt="license"/>
</a>
</p>

---

蓝鲸监控平台(BLUEKING-MONITOR)是蓝鲸智云官方推出的一款监控平台产品，除了具有丰富的数据采集能力，大规模的数据处理能力，简单易用，还提供更多的平台扩展能力。依托于蓝鲸 PaaS，有别于传统的 CS 结构，在整个蓝鲸生态中可以形成监控的闭环能力。

致力于满足不同的监控场景需求和能力，提高监控的及时性、准确性、智能化，为在线业务保驾护航。

---

## 开发环境

### 依赖管理

项目使用 <a href="https://docs.astral.sh/uv/getting-started/" target="_blank">uv</a> 管理项目依赖。

除了默认依赖外，项目依赖有三个额外的分组。

    * aidev是AI相关的依赖（默认分组）
    * test是测试相关的依赖
    * dev是本地开发依赖

#### 创建虚拟环境

如果本地没有对应的 Python 版本，uv 会根据 `.python-version` 自动安装。

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

项目使用 <a href="https://beta.ruff.rs/docs/configuration/" target="_blank">Ruff</a> 进行代码格式化及自动修复。

在本地开发时，可以根据自己使用IDE进行对应的配置

* <a href="https://docs.astral.sh/ruff/editors/setup/#vs-code" target="_blank">VS Code</a>
* <a href="https://docs.astral.sh/ruff/editors/setup/#pycharm" target="_blank">Pycharm</a>
* <a href="https://docs.astral.sh/ruff/editors/setup/" target="_blank">More</a>

#### pre-commit

项目要求在提交代码时，必须使用 pre-commit 进行基础的代码检查，其中包含 Ruff 的检查。

pre-commit 的配置文件在 `.pre-commit-config.yaml` 文件中。

pre-commit 在 dev 分组中，所以需要先完成相关依赖安装。

```bash
pre-commit install
```

执行 pre-commit install 后，会自动安装 pre-commit 的钩子，在提交代码时，会自动进行代码检查。

### 单元测试

项目使用 <a href="https://docs.pytest.org/" target="_blank">pytest</a> 进行单元测试。
