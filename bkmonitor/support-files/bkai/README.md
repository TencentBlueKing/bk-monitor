# 监控 Skill 资源包

由官方 `bkai-init 0.1.6` 将 `package/bkai.yaml` 声明的六个 Skill 同步到 AIDEV 系统空间 `system-bkaidev`。资源声明为 `generate_type: global`、`is_public: true`，供所有租户使用；多租户部署使用系统租户 `system` 的应用凭据。资源目录随监控模块外发，连接信息和凭据由部署环境注入。

| Skill | 用途 | 目标环境依赖 |
| --- | --- | --- |
| `bkm-grafana-dashboard` | 新建仪表盘、按 panel ID 编辑 | `dashboard-query`、`dashboard-edit`、`metrics-query`、`metadata-query`；Python 3.10+ |
| `bklog-query` | 索引集、场景日志查询和临时提取 | `log-query`、`log-scene-search`、`log-extract` |
| `bklog-ingest` | 日志采集及清洗配置 | `log-collector`；主机目标定位另需同环境 CMDB MCP |
| `bkm-alert-assign` | 分派配置及写入前模拟 | `alarm-handling`、`alarm` |
| `bkm-alert-create-verify` | 告警策略创建、更新、回查及历史风险预估 | `alarm-handling`、`alarm`、`metrics-query`、`metadata-query`、`log-query` |
| `bkm-data-fetcher` | 通过 MCP 拉取观测数据并保存为 JSON | Python 3.10+、requests、PyYAML；目标环境 MCP 配置 |

表中列出 MCP Server 后缀，完整名称和实时 schema 从目标环境发现。CMDB 使用 `open_list_biz_hosts`、`open_search_biz_inst_topo`、`open_search_dynamic_group`、`open_execute_dynamic_group`。MCP 创建、发布、授权和 Agent 的 `spec.skills` 关联由目标环境配置。

## 资源出包

监控现有 Dockerfile 已将本目录复制到模块镜像的 `/app/code/support-files/bkai/`。同步 Job 的 initContainer 使用同一版本监控镜像，把 `package/` 复制到共享卷；主容器直接使用平台提供、内置 `bkai-init 0.1.6` 的官方初始化镜像。无需为六个 Skill 单独维护初始化程序或构建另一份模块镜像。

```bash
python scripts/check_package.py
```

部署前确认监控镜像包含资源包，官方初始化镜像在目标环境可拉取。初始化镜像与 Skill 沙箱镜像各自独立；目标沙箱需满足表中的 Python 和依赖要求。`bkm-data-fetcher` 通过 `BK_MCP_CONFIG_PATH` 读取目标 MCP 配置，仓库仅提供占位示例。

## 安装和升级自动同步

监控 Chart 的 `monitor.bkai` 控制同步 Job。启用后，每次安装和升级通过 `post-install` / `post-upgrade` Hook 直接执行：

```bash
bkai-init sync --confirm -f /app/package/bkai.yaml --space system-bkaidev --tenant-id system
```

Chart 配置示例：

```yaml
monitor:
  bkai:
    enabled: true
    image:
      repository: registry.example.com/platform/bkai-init
      tag: "0.1.6"  # 使用平台实际提供的配套镜像版本
    space: system-bkaidev
    tenantId: system
    packagePath: /app/package/bkai.yaml
    excludeResources: []  # 如 skill/bklog-query，保留平台手工维护项
```

`monitor.config.enableMultipleTenant` 决定多租户模式；开启时 Job 还传入 `--tenant-id system`。Chart 和官方 SDK 在同步前校验系统空间；Chart 拒绝以其他租户执行本包的全局资源同步。默认关闭同步以兼容尚未接入 AIDEV 的部署。

Job 复用监控应用的 `appCode` / `appSecret`，通过官方别名 `BKPAAS_APP_ID` / `BKPAAS_APP_SECRET` 注入；连接配置复用 `monitor.extraEnvVars`、`monitor.extraEnvVarsCM` 和 `monitor.extraEnvVarsSecret`，并注入 `BKPAAS_MULTI_TENANT_MODE`。需要核对：

| 环境变量 | 配置要求 |
| --- | --- |
| `BKAI_BASE_URL` | 当前部署的 AIDEV 网关完整地址，包含网关环境；不能沿用其他部署的地址 |
| `BKAI_APP_CODE` / `BKAI_APP_SECRET` | 可覆盖默认监控应用，使用已获系统空间管理权限的系统租户应用；密钥从既有 Secret 引用 |
| `BKAI_USERNAME` | 可选，实际蓝鲸用户名；省略时须配置 `BK_USER_BASE_URL` 或 `BK_API_URL_TMPL`，官方工具通过 BK User 解析默认管理员，并需要相应接口权限 |

启用 KMS 时，Job 不读取监控加密凭据，须通过既有环境变量机制另行提供同步凭据。官方工具也支持 `BK_API_URL_TMPL`。空间 ID 和租户通过 Job 参数显式指定，不依赖环境变量默认值。真实地址、账号、业务数据和凭据不得进入资源目录或公开示例。空间管理授权与 API 网关权限分别核对；`plan` 可读不代表可以写入。

Hook 失败会使本次安装或升级失败，日志保留到下一次运行或 Job 到期清理。此前成功同步的资源不会自动回滚；重试前使用 `show` / `plan` 检查实际状态。平台返回 Skill 构建中时可能跳过本项，还需确认六个 Skill 的最终版本和构建结果。

## 手工预览和维护

本地安装官方 `bkai-init==0.1.6` 后，在环境中注入上述配置。以下示例用于多租户部署；单租户不需要 `--tenant-id`。

```bash
bkai-init validate -f package/bkai.yaml --space system-bkaidev
bkai-init plan -f package/bkai.yaml --space system-bkaidev --tenant-id system
# 确认预览后执行同步，再回查：
bkai-init sync --confirm -f package/bkai.yaml --space system-bkaidev --tenant-id system
bkai-init show -f package/bkai.yaml --space system-bkaidev --tenant-id system
```

`skill.yaml` 中的 code 使用 `bkm-`（监控平台）或 `bklog-`（日志平台）前缀，中文展示名称使用“产品名称-资源名称”。全局范围在创建后不能通过更新在全局与普通空间资源之间切换；已有同名资源须先核对归属。同步到系统空间不替 Agent 关联 Skill，也不授予各租户业务数据权限。所有示例使用合成名称和占位值，保留业务范围校验、人工确认、模拟分派和写后回查约束。

`scripts/check_package.py` 检查外发内容、路径边界和引用；也可通过 `--archive /path/to/skill.zip` 检查实际 ZIP。测试放在 `tests/`，不进入上传包。使用已安装官方依赖的 Python 执行 `python -B -m unittest discover -s tests -v`；自动检查之外还需审阅业务名称和示例来源。

协议参考：[bkai-init Package 与资源协议](https://github.com/TencentBlueKing/bk-aidev/blob/develop/src/bkai-init/docs/protocol.md)；[Helm Hook 生命周期](https://helm.sh/docs/topics/charts_hooks/)。
