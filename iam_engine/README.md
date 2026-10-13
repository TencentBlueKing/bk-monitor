# IAM V3/V4 公共底层

BKLog 与监控实际引用根目录同一份 `iam_engine`；产品目录中的
`iam_engine -> ../iam_engine` 是软链接，不是源码副本。

## 分层与扩展点

- `core/`：协议中立请求、允许/拒绝/错误结果与三种模式。
- `provider/`：ModeRouter、Union 决策/范围合并、能力 Bundle 和执行器协议。
- `migration/`：申请选边、独立双写、注入式事务提交 hook、新建资源授权的冻结请求重试。
- `settings.py`、`v4/`：BKLog 既有环境变量映射、选项归一化、网关、HTTP 和响应校验。
- 产品适配：BKLog `apps.iam.backends`；监控 `bkmonitor.iam.backends` 与 `adapters`。
  Action、资源、角色、codec、租户/资源归属、回调和策略 AST 仍由产品负责。

公共层不 import 任一产品业务模块。两平台保留 Permission/DRF 对外接口，
由 Permission 直接装配公共 ModeRouter。监控不再保留 IAMFramework、ProviderRouter、
SharedMigrationPolicy、框架单例或 IAM_FRAMEWORK 配置目录。产品 backend 只负责
协议、codec、资源解析和 IAM 模型；布尔决策、范围合并与双写编排复用公共实现。

公共 schema/、policy/、model/ 提供不依赖 Django 的模型和策略工具。监控的
Django 信号、模型注册记录及管理命令放在产品侧；模型注册不等于存量权限迁移。

`PairExecutor` 由上层注入。BKLog 继续使用带请求上下文的双路执行器；监控目前顺序
执行两侧，保留租户上下文。不要在公共层读取产品配置中心或另起没有上下文的线程。

## 已确定的运行规则

| 模式 | 实际鉴权 | Union 申请/展示 | 创建者授权 |
| --- | --- | --- | --- |
| v3 | 仅 V3 | 不适用，按 V3 | 已配置的 V3 与 V4 同步尝试 |
| v4 | 仅 V4 | 不适用，优先 V4 | 同上 |
| union | 两侧任一明确允许即通过 | 优先 V4，既有申请回退保留 | 同上 |

Union 无 ALLOW 则拒绝；ERROR 不等于 DENY，决策保留 degraded 与各侧结果。
畸形响应、缺项批量响应和非法模式不能当成允许。MCP 的原生权限回退仅针对明确
拒绝，不能把依赖故障当作无权限；Union 已有另一侧 ALLOW 时仍然放行。

模式来自配置中心，由产品注入；环境变量非空时具有更高优先级。仅支持
`v3`、`v4`、`union`，不支持业务灰度。环境变量覆盖需重启进程；配置中心仍遵循
各产品现有动态配置/缓存机制。Monitor 动态字段名为 `BK_IAM_PERMISSION_MODE`；
BKLog 继续使用 `iam_permission` FeatureToggle 的 `feature_config.mode`。

V4 只在明确配置网关时装配，不从 V3 地址猜测 V4 网关。读模式不决定写目标，也不
决定迁移可用性。监控 V4 system ID 留空时使用 `bk_monitorv3`（V3 ID）。

## 双写与失败恢复

首次 V3、V4 都同步尝试。V4 默认 365 天；冻结主体、角色、资源和 expired_at。
V4 同步失败只在最外层事务提交后投递 Celery；事务回滚不会投递。重放不重算有效期。
V3 的调用结果/失败和产品业务处理继续沿用已有边界，公共化不扩大角色或实例范围。

默认最多尝试 12 次；退避从 30 秒翻倍，最多 600 秒。任务分类处理 4xx 终止、
429/5xx 可重试和传输结果未知；终止或投递失败依靠日志发现与人工处理。
没有 outbox、持久化补偿表或周期扫描；`retry_scheduled` 不是“授权成功”。

人工恢复：确认业务实例仍存在、租户及主体正确，再使用原冻结 task kwargs 重放
`grant_v4_creator_action`；不要重新生成 expired_at。超过有效期的请求不能盲目重放。
真实补授权必须另行确认目标范围，本次离线自测未执行任何 IAM 写入。

## 两平台相同的配置契约

settings 保留 BKLog 的字符串类型默认值；使用时由共同 loader/normalizer 转换。
不要在监控单独增加环境别名或改动单位。凭据值、system ID、网关值可以因产品不同。

| setting | 环境变量 | 默认值 |
| --- | --- | --- |
| BK_IAM_PERMISSION_MODE | BKAPP_IAM_PERMISSION_MODE | 空，动态配置优先参与选择 |
| BK_IAM_V4_SYSTEM_ID | BKAPP_IAM_V4_SYSTEM_ID | 空，回退 V3 ID |
| BK_IAM_V4_APIGATEWAY_URL | BKAPP_IAM_V4_API_BASE_URL | 空，不推导 |
| BK_IAM_V4_CALLBACK_APP_CODE | BKAPP_IAM_V4_CALLBACK_APP_CODE | 空 |
| BK_IAM_V4_CALLBACK_APP_SECRET | BKAPP_IAM_V4_CALLBACK_APP_SECRET | 空 |
| BK_IAM_V4_TIMEOUT | BK_IAM_V4_TIMEOUT | 10 秒 |
| BK_IAM_V4_BATCH_CHUNK_SIZE | BK_IAM_V4_BATCH_CHUNK_SIZE | 100，上限 100 |
| BK_IAM_V4_BATCH_MAX_WORKERS | BK_IAM_V4_BATCH_MAX_WORKERS | 4，上限 8 |
| BK_IAM_V4_AUTH_TOKEN_PATH | BK_IAM_V4_AUTH_TOKEN_PATH | api/v1/open/rbac/model/systems/{system_id}/auth-token/ |
| BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS | BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS | 300 秒，0 关闭缓存 |
| BK_IAM_V4_ADD_AUTHORIZATION_PATH | BKAPP_IAM_V4_ADD_AUTHORIZATION_PATH | api/v1/open/rbac/mgmt/systems/{system_id}/authorizations/ |
| BK_IAM_V4_GRANT_EXPIRE_DAYS | BK_IAM_V4_GRANT_EXPIRE_DAYS | 365 天，上限 365 |
| BK_IAM_GRANT_MAX_ATTEMPTS | BK_IAM_GRANT_MAX_ATTEMPTS | 12 次 |
| BK_IAM_V4_MODEL_BASE_PATH | BKAPP_IAM_V4_MODEL_BASE_PATH | api/v1/open/rbac/model/systems/ |
| BK_IAM_V4_MODEL_MANAGERS | BKAPP_IAM_V4_MODEL_MANAGERS | 空 |
| BK_IAM_V4_CALLBACK_URL | BKAPP_IAM_V4_CALLBACK_URL | 空 |

完整声明以 `settings.IAM_ENVIRONMENT` 为准。四类鉴权/申请路径继续是 settings-level
可覆盖默认值，不增加 BKLog 没有的环境变量声明。callback 凭据必须成对配置；否则
使用全局应用凭据（Monitor 用 SaaS 凭据，非 backend 凭据），与现有产品边界一致。
Charts 应映射同名环境变量；本次未修改 Charts 仓库。

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
保留 IAM 模型注册/更新和新建资源的同步双写及冻结重试，这两者不是存量迁移。

## 自测与真实验收

详见 [离线自测报告](docs/refactor-self-test.md)。测试入口全部使用假凭据，阻断网络，
DB 仅内存 SQLite；不要把 `tests/run_*_offline.py` 的覆盖配置带到部署环境。

真实验收仍需注册监控 V4 系统、授权接入配置/测试用户和资源范围，再验证仅 V3、
仅 V4、两侧有权、两侧无权、申请、创建者授权及重试。用户已决定本阶段不跑真实数据。
回退只把配置中心模式切回 v3；保持 V4 双写及 V3 授权不变，不随回退删除模型或权限。
