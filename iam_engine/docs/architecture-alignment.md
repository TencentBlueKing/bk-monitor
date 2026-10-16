# IAM 架构对齐验收

盘点起点 `89182eaa4`；原 V3 对照 `ff89f63` / `8ba164e28`。
以真实调用链而非目录外观判断共享。完整配置与运行规则见 [公共入口](../README.md)，
实际结果见 [离线自测](refactor-self-test.md)。

## 机制去向

| 原机制 | 处置与目标 | 保留/删除理由 |
| --- | --- | --- |
| 原 Permission/DRF、Token/skip_check | 保留公开路径，内部直接接 ModeRouter | 产品既有权限语义，不向业务泄漏版本与 DTO |
| ActionMeta/ResourceMeta、静态枚举、查询接口 | 恢复原 SDK ID、字段及方法；中立模型派生 | V3 公开协议不能因 V4 改变；不是旧 V4 包装 |
| IAMFramework/ProviderRouter/框架单例及私有引擎 | 删除，根 iam_engine + 两个软链接 | 不继续维护另一套编排 |
| Monitor callback Registry/Service/View/Authentication | 删除；两产品原生 ResourceProvider 注册同一 V4ResourceApiDispatcher | SDK 分发扩展点足够；V4 协议转换在公共层 |
| 独立 TokenProvider / 两套回调缓存 | 共同 V4CallbackIAM + V4Client | Token 生命周期、Basic、缓存和隔离统一 |
| catalog 独立 ORM | 删除；catalog 仅解析 ID/path 和转发原生 Provider | 查询实现属于产品，回调/Resolver/构造共用所有者 |
| Monitor V4 credentials/system/options dataclass | 删除；直接共同 V4Options | 模型元数据只在产品 expected_model；通信无二次包装 |
| SchemaRegistry 注册/冻结/loaders/snapshot/visibility | 删除，静态只读索引 | 没有运行时注册需求；模型由公开定义派生 |
| 动态 ActionEnum / 第二份 Action 定义 | 删除；原生静态 ActionEnum 为权威源 | V3 SDK 的英文名、依赖/选择器和辅助接口保留 |
| SDK dict → PolicyExpression → SDK dict | 删除；原 dict 直接交 SDK | 原 V3 数组、path、operator、异常语义不可替换 |
| 双产品同步授权编排 | common migration/dual_write；产品提供 Writer | 按模式各写一次、逐侧成功/失败；无异步补偿 |
| 原 Monitor V4 Planner/Loader/Recorder/旧命令 | 删除，共同 model/convergence 与 iam_migrate_model | 同一 V4 期望态和生命周期，不迁就旧引擎 |
| 原 V3 Migrator/MonitorMigration 与 BKLog SDK upsert | 保留产品适配，统一 ModelSyncService | 已有历史和执行语义不同，不重放或清表 |

删除证据由 `tests/test_architecture.py` 直接检查文件、类和导入不存在；
两个 V4 路由模块均无自定义 View 类或 ORM，catalog 无 ORM，公共层无产品 import。
原 Monitor V3 migrations、数据库表与历史记录未删除，前端不在重构 diff 中。
`iam_generate_config` 是旧框架快照导出，实际消费者只有旧测试，已一并删除。

## 目录与调用链对照

| 职责 | BKLog（apps.iam） | Monitor（bkmonitor.iam） | 同一公共实现 |
| --- | --- | --- | --- |
| 公开入口 | handlers/permission.py、drf.py | permission.py、drf.py、action.py、resource.py | provider/router、migration/policy |
| 协议能力 | backends/v3、backends/v4 | backends/v3、backends/v4 | provider 协议、v4/config、client、并发 |
| 资源查询 | views/resources.py | monitor_web/iam/views.py | 原 SDK ResourceProvider；无公共 ORM |
| V4 回调 | views/resources_v4.py、callback_client | views/resources_v4.py、callback_client | v4/callback、v4/resource |
| 新建授权 | 产品角色映射、Writer | 产品角色映射、Writer | migration/dual_write |
| 模型/运维 | JSON 模型及 V3 SDK adapter | 原 Action/Resource + 角色派生、V3 history adapter | model/convergence、sync、django |
| 实际源码 | iam_engine → ../iam_engine | iam_engine → ../iam_engine | 仓库根 iam_engine，不是副本 |

真实链路：

- 业务 → 原 Permission/DRF → 操作模式快照 → LazyProviderBundles → ModeRouter → 原生 V3/V4 能力。
- V4 回调 URL → 共同 SDK Dispatcher → 模式/Basic/Token/租户 → 共同协议适配 →
  产品原生 ResourceProvider → 原生查询；V3 回调继续原 SDK 流程，前置模式检查。
- 创建者入口 → 产品映射 → 共同按模式执行 → 失败请求冻结 → 事务提交后投递 →
  共同检查当前模式 → 产品 writer → 共同客户端。
- migrate/post_migrate 或 iam_migrate_model → 同一 ModelSyncService → 模式快照与锁 →
  V3 原历史机制 / V4 共同非破坏性收敛。
- 权限诊断 RPC → 同一模式目标检查 → 对应产品 Provider；显式指定被禁用的协议
  也不能装配 Provider 或查询 IAM，非法模式返回已处理的错误。

地址只决定请求目的地，不决定装配或启用。默认 V3 在 V4 默认 URL 存在时仍不访问 V4，
包括回调、历史任务和权限诊断 RPC；模式切换后新操作不使用旧模式缓存。

## 剩余差异及具体理由

1. Action、资源、角色及版本 ID 映射：两产品权限模型真实不同；监控旧 Action `_v2`
   是 Action 方言，不是 IAM 版本。V4 ID 沿用已经确认的映射，不重新命名。
2. BKLog Space 使用本地缓存，监控 APM/RUM/Grafana 查询本身模型。
   Monitor APM/RUM 共用查询扩展点，仅 queryset 不同。目录覆盖仪表盘在产品权限服务展开。
3. 原 V3 单实例构造存在缓存、属性覆盖、空间 UID 转换、裸 Grafana UID/title 等契约，
   回调则按租户列举并使用回调展示名；同一原生 Provider 保留这些不同操作，不私改查询边界。
4. Monitor V3 迁移按 MonitorMigration 历史执行，BKLog JSON/SDK upsert 幂等执行。
   共用的是生命周期/V4 收敛；不是强行重写已有 V3 历史。
5. Monitor SaaS 凭据来源和 BKLog 应用凭据来源不同，Celery/请求上下文框架也不同。
   仅薄注入保留，Token/缓存算法不复制；授权不再绑定 Celery 或重试任务。
6. 产品现有动态配置来源不同；公共选边/类型/默认值相同，部署严格读取各自权威配置表。

## 验证边界

覆盖公共规则及产品真实入口：三模式、禁用协议隔离、配置实际请求 URL、
分页/过滤/未知方法、Token 隔离/TTL/缓存错误、创建者事务与历史任务、
V3 SDK 原策略、资源/Action 公开契约、Grafana/APM/MCP 与模型同步失败传播。
移除旧框架测试，但保留并增强业务契约测试；测试数降低不能用历史统计冒充本轮覆盖。

尚未执行真实 IAM、MySQL advisory lock、Celery broker、真实 migrate 部署、
回调可达性、真实 V4 模型注册及申请页点击；不宣称端到端通过。
没有存量授权迁移，也没有真实 IAM 写入或擅自部署。
