# IAM V3/V4 公共底层

BKLog 与监控实际引用根目录同一份 `iam_engine`；产品目录中的
`iam_engine -> ../iam_engine` 是软链接，不是源码副本。

## 分层与扩展点

- `core/`：协议中立请求、允许/拒绝/错误结果与三种模式。
- `provider/`：ModeRouter、Union 决策/范围合并、能力 Bundle 和执行器协议。
- `migration/`：模式选边、Union 同步双写与授权有效期配置。
- `model/`：公共 V4 模型校验、差异计划与非破坏性收敛；`django.py` 提供可选部署/命令适配。
- `settings.py`、`v4/`：BKLog 既有环境变量映射、选项归一化、网关、HTTP 和响应校验。
- 产品适配：保留各产品原有 Permission/DRF 公开入口，
  `backends/v3/` 与 `backends/v4/` 提供原生能力。回调与同步授权编排共用公共实现，
  产品仅注册原生 ResourceProvider、注入凭据和授权映射。
  Action、资源、角色、codec、租户/资源归属和原 V3 SDK 策略仍由产品负责。

公共层不 import 任一产品业务模块。两平台保留 Permission/DRF 对外接口，
由 Permission 直接装配公共 ModeRouter。监控不再保留 IAMFramework、ProviderRouter、
SharedMigrationPolicy、框架单例或 IAM_FRAMEWORK 配置目录。产品 backend 只负责
协议、codec、资源解析和 IAM 模型；布尔决策、范围合并与双写编排复用公共实现。
监控 Provider 直接实现公共 PermissionProvider，申请和范围能力也由原生 Provider 提供，
不再通过 MonitorAuthAdapter/方言转换层装配；V4 Client 直接引用共同通信底座。
监控的 Action/Resource/Permission/DRF 实现仍位于原有 `bkmonitor.iam` 公开模块；
BKLog 继续使用自身 `apps.iam.handlers` 入口。不强求目录树相同，也不为目录对齐
重写业务 import。两边一致的是职责、能力协议与公共实现，不是文件路径。

公共 schema/ 仅保留元数据记录；没有 Registry、冻结、动态枚举或中间策略 DSL。
原 V3 SDK 策略直接交给 SDK 求值。模型收敛核心不依赖 Django。产品注册 Django 信号和管理命令，
共用 `model.django` 的命令/锁适配；原有 V3 模型历史仍由产品维护，模型注册不是存量权限迁移。

`PairExecutor` 由上层注入。双产品并发和有序分页共用 `concurrency.py`，产品只负责
绑定/恢复本身的请求、租户、时区和 OTel 上下文。不要在公共层读取产品配置中心。
配置 max_workers=1 时仍可串行对照；线程池结果按输入顺序归并。

产品差异限于实际语义：监控的 Action/资源/角色、空间 ID 编码、V3 策略 AST，
Grafana 文件夹覆盖、模型注册命令，以及 SaaS 凭据和本地请求上下文来源。
业务调用方传用户名、业务 ID、仪表盘 UID；不自行拼祖先资源或导入引擎 DTO。
MCP 继续通过产品 Permission 的 `make_request` / `iam_client` 查询和生成申请信息，
双栈客户端由 IAM 内部装配；明确需要 V3 SDK 的模型工具和回调使用 `get_iam_client`。
Grafana 对外保留 `(allowed, role, permissions)` 契约，父文件夹覆盖在权限服务展开；
APM 旧 permission Action key 在 DRF 边界生成，无需逐个视图开启兼容开关。
监控公开 `batch_is_allowed` 继续返回历史 V3 Action 键；默认 V3 直接保留 SDK 的完整资源组、
原始返回值和异常契约。内部 DRF/Router 仍用中立 Action ID，不让调用方承担版本转换。

## 已确定的运行规则

| 模式 | 实际鉴权 | 创建者授权 | 模型同步 | 无权限申请 |
| --- | --- | --- | --- | --- |
| v3（默认） | 仅 V3 | 仅 V3 | 仅 V3 | V3 |
| v4 | 仅 V4 | 仅 V4 | 仅 V4 | V4 |
| union | 两侧任一明确允许即通过 | V3＋V4 | V3＋V4 | 仅 V4 |

Union 无 ALLOW 则拒绝；ERROR 不等于 DENY，决策保留 degraded 与各侧结果。
畸形响应、缺项批量响应和非法模式不能当成允许。MCP 的原生权限回退仅针对明确
拒绝，不能把依赖故障当作无权限；Union 已有另一侧 ALLOW 时仍然放行。

模式来自配置中心，由产品注入；环境变量非空时具有更高优先级。仅支持
`v3`、`v4`、`union`，不支持业务灰度。环境变量覆盖需重启进程；配置中心仍遵循
各产品现有动态配置/缓存机制。Monitor 动态字段名为 `BK_IAM_PERMISSION_MODE`；
BKLog 继续使用 `iam_permission_mode` FeatureToggle 的 `feature_config.mode`。

地址决定请求目的地，模式决定是否调用。能力按需装配，只缓存能力、不缓存模式；
默认 V3 下，即使已推导 V4 URL，也不调用 V4 鉴权/授权/同步/申请。
非法模式拒绝，不自动切到另一协议。监控 V4 system ID 留空时使用 `bk_monitorv3`（V3 ID）。

V4/Union 申请调用 `api/v1/open/application/permission-apply-urls/`，使用返回的页面 URL。
超时、异常、空 URL 或缺少能力返回 `({}, "")`，保持无权限，不回退 V3、
不返回通用 SaaS Host 或网关根地址。沿用后端响应协议；没有修改前端。
V3 保留已有申请逻辑及其失败兜底；“获取申请链接失败”并非 V4 才可能发生。

## 同步授权与失败处理

仅 Union 同时尝试 V3、V4；单栈仅写对应协议。每个选定目标同步写入一次，
不登记事务提交回调、不投递 Celery、不进行异步补偿。V4 默认有效期仍为 365 天。
默认尽力写入并记录失败；仅显式严格调用抛错。Web、API、Worker 不因角色改变
失败契约，默认 V3 的既有失败处理不变。授权调用方仍可按原业务契约捕获异常。
监控结果中的 retry_scheduled 只为兼容保留，始终为 False，不表示后台会补授权。
本地业务事务回滚不撤销已经成功的 IAM 授权，与原 V3 的边界一致。

## 两平台相同的配置契约

settings 保留 BKLog 的字符串类型默认值；使用时由共同 loader/normalizer 转换。
不要在监控单独增加环境别名或改动单位。凭据值、system ID、网关值可以因产品不同。

| setting | 环境变量 | 默认值 |
| --- | --- | --- |
| BK_IAM_PERMISSION_MODE | BKAPP_IAM_PERMISSION_MODE | 空，动态配置优先参与选择 |
| BK_IAM_V4_SYSTEM_ID | BKAPP_IAM_V4_SYSTEM_ID | 空，回退 V3 ID |
| BK_IAM_V4_APIGATEWAY_URL | BKAPP_IAM_V4_API_BASE_URL | 从公共组件地址推导 bkiam 网关 |
| BK_IAM_V4_CALLBACK_APP_CODE | BKAPP_IAM_V4_CALLBACK_APP_CODE | 空 |
| BK_IAM_V4_CALLBACK_APP_SECRET | BKAPP_IAM_V4_CALLBACK_APP_SECRET | 空 |
| BK_IAM_V4_TIMEOUT | BK_IAM_V4_TIMEOUT | 10 秒 |
| BK_IAM_V4_BATCH_CHUNK_SIZE | BK_IAM_V4_BATCH_CHUNK_SIZE | 100，上限 100 |
| BK_IAM_V4_BATCH_MAX_WORKERS | BK_IAM_V4_BATCH_MAX_WORKERS | 4，上限 8 |
| BK_IAM_V4_AUTH_TOKEN_PATH | BK_IAM_V4_AUTH_TOKEN_PATH | api/v1/open/rbac/model/systems/{system_id}/auth-token/ |
| BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS | BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS | 300 秒，0 关闭缓存 |
| BK_IAM_V4_ADD_AUTHORIZATION_PATH | BKAPP_IAM_V4_ADD_AUTHORIZATION_PATH | api/v1/open/rbac/mgmt/systems/{system_id}/authorizations/ |
| BK_IAM_V4_GRANT_EXPIRE_DAYS | BK_IAM_V4_GRANT_EXPIRE_DAYS | 365 天，上限 365 |
| BK_IAM_V4_MODEL_BASE_PATH | BKAPP_IAM_V4_MODEL_BASE_PATH | api/v1/open/rbac/model/systems/ |
| BK_IAM_V4_MODEL_MANAGERS | BKAPP_IAM_V4_MODEL_MANAGERS | 空 |
| BK_IAM_V4_CALLBACK_URL | BKAPP_IAM_V4_CALLBACK_URL | 空 |

完整声明以 `settings.IAM_ENVIRONMENT` 为准。四类鉴权/申请路径继续是 settings-level
可覆盖默认值，不增加 BKLog 没有的环境变量声明。callback 凭据必须成对配置；否则
使用全局应用凭据（Monitor 用 SaaS 凭据，非 backend 凭据），与现有产品边界一致。
Charts 应映射同名环境变量；本次未修改 Charts 仓库。

普通 K8s 环境仅需既有 `BK_COMPONENT_API_URL`：V3 默认
`{BK_COMPONENT_API_URL}/api/bk-iam/prod/`，V4 默认
`{BK_COMPONENT_API_URL}/api/bkiam/prod/`。不要求新增 IAM Helm Values。
显式非空覆盖优先；空字符串/空白无覆盖，统一末尾斜杠。缺少根地址返回空配置，
不拼接 `None`，V4 不回退 V3 网关。两产品沿用 `BKAPP_IAM_API_BASE_URL` 的 V3 覆盖；
监控额外保留既有 `BK_IAM_V3_API_BASE_URL` 最高优先级入口，不把它复制成新的 BKLog 别名。

## 模型同步与运维

两产品 `post_migrate` 与手动 `iam_migrate_model` 共用同一 `ModelSyncService`：

```bash
python manage.py iam_migrate_model          # 预览，不写 IAM
python manage.py iam_migrate_model --apply  # 按进程模式实际同步
python manage.py migrate                   # 部署 post_migrate 自动同步
```

部署模式优先读环境覆盖，否则严格读取产品权威配置表；读配置失败必须报错，
不把迁移进程未装载动态配置误当默认 V3。业务进程遵循产品既有动态配置缓存。
动态切换后不会自动注册新模型；先用相同目标模式部署/同步，再切业务流量。

V3 保留原机制：监控使用 `iam/migrations` 与 `MonitorMigration(app="iam")` 记录，
不会重放已完成文件；BKLog 沿用原 JSON/SDK upsert。V3 预览只列本地文件，
不是远端差异计划，且绝不执行旧写入 Migrator。部署失败向迁移进程传播，手动失败为非零退出。

V4 共用期望模型 → 远端读取 → 校验/差异 → 按依赖应用 → 结果报告。
BKLog 的 JSON 基线与运行时 Action 一致性测试保留；监控从运行时 definitions 派生，
不维护第二份模型快照。模型 ID 与既有 Action 命名不变。
不自动删除远端多余对象/角色动作/客户端；仅报告漂移。Action 换绑、角色授权维度
变化与资源祖先链变化明确阻断，不能自动破坏现有授权。部分失败后重新读取远端并收敛，
远端分页提前结束或 count 畸形时明确失败，不把不完整模型清单作为写入基线。
已收敛不产生模型写请求。MySQL 使用数据库 advisory lock，SQLite 离线仅用进程锁，
不新增或删除历史表。真实 MySQL 锁与部署全链路仍需端到端验证。

旧监控 `iam_engine_migrate`、`iam_engine_makemigrations` 与 Planner/Loader/Recorder 已移除；
BKLog 旧 `iam_v4_migrate_model` 由统一命令替换。原 V3 文件、记录和数据库表不删除。

## 打包

Monitor 的根仓库 Docker 构建显式 COPY `iam_engine/` 到 `/app/iam_engine/`，
满足 `/app/code/iam_engine -> ../iam_engine` 的引用。

BKLog 的 Dockerfile 仍使用 BKLog-only context；制作归档/构建上下文时需像公共
ai_agent 一样解引用软链接，例如 `cp -RL bklog <新建的临时构建目录>` 或 `tar -h`。
不要直接把带外部软链接的 bklog 目录作为不完整上下文。
Dockerfile 在构建时检查模块存在；本地 unit_test 复制也改为解引用。
`test_packaging.py` 实际复制并在隔离目录导入两种产物；未构建完整容器镜像。
部署流水线的实际归档实现仍需按最终部署方式核对。

## 存量权限迁移边界

存量 V3 授权迁移由 IAM 自行完成，不在本次产品开发范围。不提供 Action→Role
转换、批量存量补授权或授权回放脚本，也不将映射规则作为本次开发阻塞项。
保留按模式进行 IAM 模型注册/更新和同步新建资源授权，这些不是存量迁移。

### BKLog 升级前：排空旧创建者授权任务

本次删除旧任务 `apps.iam.tasks.grant.grant_v4_creator_action`。旧版本只要配置
V4 网关，即使处于 V3 模式也可能写 V4，并在失败后投递该任务。升级后，新 Worker
不再注册此任务；尚未完成的消息可能按未注册任务丢弃。

升级前需在实际部署对应的 broker/队列确认该任务的待消费、延迟/重试、reserved
及 active 消息均已处理，并协调滚动发布期间的旧生产者，避免排空后再次入队。
不能仅凭队列长度为零认定没有延迟或正在执行的任务。本次未检查真实队列，
此处是发布风险提示，不代表已经发生授权丢失。

若不能排空，需明确盘点尚未成功的授权意图及其租户、用户、资源，并确认后续处理。
不能假定 IAM 存量授权迁移会覆盖从未写成功的补偿请求；这需要 IAM 单独确认。
升级后保持 V3 不依赖 V4 授权，但这部分遗留请求仍可能影响未来切换 V4/Union。
本次不保留兼容任务、不增加重放脚本，也不自动修改已有授权。

## 自测与真实验收

详见 [离线自测报告](docs/refactor-self-test.md)。测试入口全部使用假凭据，阻断网络，
DB 仅内存 SQLite；不要把 `tests/run_*_offline.py` 的覆盖配置带到部署环境。

真实验收仍需注册监控 V4 系统、授权接入配置/测试用户和资源范围，再验证仅 V3、
仅 V4、两侧有权、两侧无权、申请、同步创建者授权及失败处理。用户已决定本阶段不跑真实数据。
回退到 v3 后，后续操作只用 V3，不再创建 V4 授权或同步请求；不删除已有模型或授权。
不再创建异步授权补偿任务，也不因 Celery eager 模式内联重试。

## 回调与产品公开接口

两产品 V4 路由直接注册共同 `V4ResourceApiDispatcher`，复用 SDK 的 ResourceProvider
分发扩展点，不调用 V3 服务。只支持已核实的 `list_instance`、`fetch_instance_info`；
未知资源/方法返回明确错误，不伪造成功空列表。分页、过滤、属性投影、响应和认证共用。
Basic 用户名固定为 `bk_iam`；Token 由共同客户端获取。缓存键隔离租户、系统、网关、
应用凭据、Token 路径和 TTL；0 关闭缓存，配置/凭据变化不复用旧缓存。
模式校验发生在 Token/凭据/查询之前；两侧 V3 dispatcher 也检查当前模式。

监控公开 ActionMeta/ActionEnum、ResourceMeta/ResourceEnum 继续使用原 V3 SDK 契约，
包含原 Action ID、英文名、依赖动作、选择器、资源构造和批量元数据接口。
内部静态模型从它们派生；业务不改 import，也不接触引擎 DTO。
两产品资源查询由原生 ResourceProvider 承载；构造、回调和 Resolver 没有第二套 catalog ORM。
原 V3 单实例构造和租户回调各自的查询边界不被强行合并：前者保留旧缓存/覆盖属性语义，
后者仍执行租户过滤，由同一产品 Provider 提供相应原生操作。

机制去向、目录及调用链对照见 [架构对齐验收](docs/architecture-alignment.md)。
