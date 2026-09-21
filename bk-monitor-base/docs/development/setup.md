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

### NodeMan 兼容控制面

Base 使用已有 `blueking.api_configs` 分开配置 V2 后台与 V3 提供的 V2 兼容入口：

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

- `nodeman_control` 仅用于 Host/Proxy、IP 选择器主机查询和独立官方插件安装。
- Subscription、插件开发、插件实例查询以及 `auto_deploy_proxy` 的查包/安装链仍走 V2。
- 不配置 `nodeman_control` 时保持原路由；配置存在但缺少 URL 时明确报错，请求失败不回退到 V2。
- 主仓对应配置为 `BKAPP_BKNODEMAN_API_BASE_URL`（V2）与
  `BKAPP_BKNODEMAN_CONTROL_API_BASE_URL`（兼容控制面）。主仓非 COS 上传的
  `BKAPP_NODEMAN_INNER_HOST` 仍指向 V2。Base 与主仓配置独立，部署时应指向同一组服务。
- 这里填写兼容接口入口，不是 V3 原生 Backend URL。配置变更需重启服务；
  回滚路由时移除 Base 的 `nodeman_control` 配置，并清空主仓控制面地址。

本期不新增后端归属字段或数据库迁移，也未实现原生 V3 采集。
独立官方插件安装只提交请求，不新增安装完成轮询。
采集器 Ensure 需要由监控侧保证，本次路由拆分尚未补齐，不应视为空白主机采集已可用。
