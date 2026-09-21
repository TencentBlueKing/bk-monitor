# 开发环境搭建

Base 是主仓 `bk-monitor-base/` 下的普通代码模块，不再需要 `git submodule update` 或单独的 Base 分支。
以下命令均在此目录执行；提交、Git hooks 和 PR 使用主仓流程。
监控应用仍通过 `bkmonitor/pyproject.toml` 中的 `../bk-monitor-base` 本地依赖加载，包名与 Docker 路径不变。

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

### NodeMan V2/V3 共存

使用已有 `blueking.api_configs` 分开配置 V2 后台与 V3 的 V2 兼容入口：

```yaml
blueking:
  api_configs:
    nodeman:
      mode: apigw
      custom_api_url: https://v2.example.com/api/bk-nodeman/prod/
    nodeman_control:
      mode: apigw
      custom_api_url: https://control.example.com/api/bk-nodeman/prod/
```

`nodeman_control` 只服务 Host/Proxy、IP 选择器查询及 `official_plugin_operate`。
Subscription、插件开发、`plugin_search` 和 `auto_deploy_proxy` 的 `plugin_operate` 保持 V2。
控制面配置存在时必须提供 `custom_api_url`，失败不回退 V2；删除整个 `nodeman_control` 配置恢复原有路由。

### 共存期间的能力边界

共存是迁移阶段，不是永久双栈。网关地址只影响主机查询和独立官方插件控制，不能改变已有采集资源的归属。

- 主仓以 `get_collect_installer`、Base 以 `get_installer` 选择部署实现；创建、更新、启停、删除、重试及执行结果必须使用同一后端。
- 主仓插件及部署版本的 `nodeman_backend` 字段保存归属；Base 使用 `related_params.nodeman_backend`，当前执行另记 `execution_backend`。历史无标记的 Base 记录固定解释为 V2。
- 主仓须先执行 `monitor_web.0078_nodeman_backend` 数据库迁移，历史记录默认 V2。字段不作为业务接口的可编辑开关；直接修改它不构成资源迁移。
- 主仓列表与数量查询通过安装器的 `statistics` 返回以监控配置 ID 为键的统计；就绪通过 `is_task_ready` 查询。查询缺失不能等价于零实例成功。Base 的执行详情与状态仍由同一个安装器处理。
- 插件管理沿用管理器工厂，按插件归属选择实现；部署必须使用对应后端的插件包。`auto_deploy_proxy` 的查包、查实例、安装仍整体留在 V2。
- 主机查询使用 `host_queries`；独立官方插件安装使用 `official_plugins.install`，兼容实现内部生成接口参数。主仓入口为 `bkmonitor.utils.nodeman`，Base 为 `infras.nodeman_control`。
- 本期只注册 V2 采集实现；V3 控制面兼容入口不等于原生 V3 采集已实现。未知或尚未实现的资源后端明确报错，不回退 V2。

后续按采集模型在现有安装器、插件管理器工厂中注册 V3 实现，并实现统一结果能力，不要求 V3 模拟 Subscription。APM、自定义上报等现有 V2 专用配置模块继续保留各自的业务入口；迁移时在对应入口替换实现，不按底层 API 名称全局切换。本期不增加灰度开关、不执行存量资源迁移。
这里填写提供旧协议的兼容入口，不是 V3 原生 Backend URL；配置变更需重启服务。

与监控主仓一起部署时，主仓仍需配置 `BKAPP_BKNODEMAN_API_BASE_URL`（V2）和
`BKAPP_BKNODEMAN_CONTROL_API_BASE_URL`（兼容控制面）；非 COS 文件上传的 `BKAPP_NODEMAN_INNER_HOST` 仍指向 V2。
Base 的 `api_configs` 与主仓 Django 配置独立，必须指向同一组对应服务。
V2 在 Subscription 内部负责采集器 Ensure；上线前需验证新主机安装及动态新增目标，并准备所需 V2 插件包和模板。
