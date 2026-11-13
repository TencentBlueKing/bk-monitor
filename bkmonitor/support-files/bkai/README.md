# 监控 Skill 资源包

使用 `bkai-init 0.1.6` 将六个 Skill 同步到明确指定的 AIDEV 空间。入口是 `package/bkai.yaml`，只包含 Skill 资源。

| Skill | 用途 | 目标环境依赖 |
| --- | --- | --- |
| `bk-grafana-dashboard` | 新建仪表盘、按 panel ID 编辑 | `dashboard-query`、`dashboard-edit`、`metrics-query`、`metadata-query`；Python 3.10+ |
| `bk-log-query` | 索引集、场景日志查询和临时提取 | `log-query`、`log-scene-search`、`log-extract` |
| `bk-log-ingest` | 日志采集及清洗配置 | `log-collector`；主机目标定位额外需要同环境 CMDB MCP |
| `bk-alert-assign` | 分派配置及写入前模拟 | `alarm-handling`、`alarm` |
| `bk-alert-create-verify` | 告警策略创建、更新、回查及历史风险预估 | `alarm-handling`、`alarm`、`metrics-query`、`metadata-query`、`log-query` |
| `bk-data-fetcher` | 直接通过 MCP 拉取观测数据并保存为 JSON | Python 3.10+、requests、PyYAML；目标环境提供的 MCP 配置 |

表中使用 MCP Server 后缀。完整名称由目标网关、发布环境和客户端决定，调用时必须在同一目标环境内发现工具并读取实时 schema。CMDB 依赖为 `open_list_biz_hosts`、`open_search_biz_inst_topo`、`open_search_dynamic_group`、`open_execute_dynamic_group`，不随本包创建。

所有示例均使用合成名称和占位值。Skill 保留业务范围校验、人工确认、写后回查及模拟分派约束。

## 准备运行环境

使用 Python 3.11+，从平台提供的可信包源安装 `bkai-init==0.1.6`。其依赖包含 PyYAML，测试使用 Python 标准库 unittest。包源须实际提供该版本，不假定公共 PyPI 已发布。

```bash
test -f .env || cp .env.example .env
# 填写 .env 中的目标配置后执行：
source .env
: "${BKAI_PIP_INDEX_URL:?请填写平台提供的可信包源}"
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --index-url "$BKAI_PIP_INDEX_URL" 'bkai-init==0.1.6'
make check
make test
make validate
make plan
```

`make check` 检查本地资源、引用和外发内容；`make validate` 使用 bkai-init 校验并尝试打包；两者均不请求目标平台。`make plan` 读取线上状态，预览新增、更新和阻塞项。

`BKAI_SPACE_ID` 必须显式填写。单租户使用 `BKPAAS_MULTI_TENANT_MODE=false`；多租户设为 `true` 并填写目标 `BKAI_TENANT_ID`。`BKAI_USERNAME` 填平台实际 bk_username。应用编码、密钥和网关模板也可由平台已有环境变量注入机制提供，具体优先级见官方协议。

确认 plan 的目标空间及变更内容后执行：

```bash
make sync
make show
```

`make sync` 带 `--confirm`，会创建或更新六个 Skill。按需只同步其中一项：

```bash
python scripts/run_bkai.py plan --resource skill/bk-log-query
python scripts/run_bkai.py sync --resource skill/bk-log-query
```

同步失败时先回读实际状态，已完成项不会自动回滚。平台若返回 Skill 正在构建，bkai-init 可能跳过本项；检查每项结果及平台构建状态，命令退出成功不代表全部新内容已生效。

## 版本、空间与 Agent 关联

`skill.yaml` 和 `SKILL.md` 均不保存目标空间 ID 或发布版本。空间由运行参数传入；Skill 版本由平台根据上传 ZIP 内容决定，包清单版本不作为 Skill 版本兜底。资源默认 `generate_type: space`、`is_public: false`，在选定空间中交付。

需要让现有 Agent 使用时，在 Agent 的 `spec.skills` 中引用相同 code，并配置、发布和授权上述 MCP。资源同步不会创建 MCP、授予权限或自动修改 Agent。

Grafana 的本地脚本需要目标 Skill 沙箱提供 Python 3.10+。如沙箱默认镜像不满足要求，在该 Skill 根目录增加引用平台允许镜像的 Dockerfile，并重新校验、出包和同步。初始化容器与 Skill 沙箱是不同运行环境。

`bk-data-fetcher` 的 `requirements.txt` 声明 requests 与 PyYAML。由平台默认 Skill 镜像流程安装依赖，或在端侧安装该文件。运行时通过 `BK_MCP_CONFIG_PATH` 注入目标 MCP 配置；配置里的地址与凭据由目标环境提供，外发包只含示例。环境别名必须显式选择，无法唯一定位 Server 时停止；自定义 Server 别名使用 `MCPClient.call_tool` 精确调用。

## 随模块交付

镜像仅复制已审阅的 package 和执行脚本，默认进行本地校验。基础镜像必须预装 `bkai-init 0.1.6`：

```bash
make build
docker run --rm \
  -e BKAI_SPACE_ID -e BKAI_APP_CODE -e BKAI_APP_SECRET \
  -e BKAI_USERNAME -e BK_API_URL_TMPL -e BKAI_BASE_URL \
  -e BKPAAS_MULTI_TENANT_MODE -e BKAI_TENANT_ID \
  bk-monitor-skills-init:local plan
```

确认预览后，将命令末尾的 `plan` 改为 `sync` 执行同步。`.env` 使用 shell 的 `export` 语法，先 source 后通过上述环境变量名注入容器。

模块 Chart 可使用 post-install / post-upgrade Job 调用此镜像的 `sync` 命令，复用模块已有的环境变量注入机制。Job 需在目标 AIDEV 服务可访问且应用已有空间权限后运行。连接配置和凭据由部署系统注入，不写入资源包、镜像或提交差异。

## 维护与验收

维护内容时同时更新必要 references 和脚本。`scripts/check_package.py` 默认仅允许公开文档域名、示例域名及协议命名空间，拒绝固定网络地址、身份标识、固定账号样例、文档中的固定业务资源 ID、凭据文件、越界链接和符号链接。账号和业务资源使用占位符，通知组使用明确的合成名称。扫描输出只给文件位置及类别，不回显敏感值；自动检查不能识别所有业务名称，仍需审阅完整差异。

实际上传 ZIP 可用同一检查器再次校验：

```bash
python scripts/check_package.py --archive /path/to/skill.zip
```

测试覆盖六个 Skill 的真实打包、模拟同步到指定空间，以及外发检查的拒绝场景；Grafana 另有脚本回归，数据拉取器另有协议、配置解析、环境隔离和本机 HTTP 往返测试。目标平台验收还需核对 Skill 构建完成、内容版本、Agent 关联和 MCP 授权，并分别验证查询及经确认的写入流程。

协议参考：[bkai-init Package 与资源协议](https://github.com/TencentBlueKing/bk-aidev/blob/develop/src/bkai-init/docs/protocol.md)。
