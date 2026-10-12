# IAM 公共框架重构：离线自测报告

日期：2026-10-12。单据：138944425。分支：`feat/iam-v4-support`。
实现基线：`696591016804d4b45a4918dc0aff0d37dc64d756`，对应监控 PR #12734。

## 结论与范围

共同决策/配置/HTTP/双写实现已经落地，BKLog 与监控引用同一公共目录。
已实现范围的离线回归通过；未调用真实 IAM、未注册系统、未部署、未运行真实迁移。
**不能将本报告解释为完整需求验收通过或已具备上线证据。**

尚未完成的开发是任意 V3 策略到 V4 Role/资源分支的产品转换。
已完成迁移预览、冻结、重放、回读机制，但缺少经确认的 Action→Role 映射，不能猜测
单个 Action 可以升级成更大的运维角色。该问题已向提出人询问，不阻塞其他离线工作。
最终真实接入验收与业务验收仍由吴嘉华负责。

## 实际执行结果

下面命令均在仓库根目录执行，`python` 使用对应产品的既有 Python 3.11 环境。
脚本不加载个人 local_settings，不需要真实 IAM 凭据。

| 检查 | 实际结果 | 证据边界 |
| --- | --- | --- |
| 公共层与跨产品适配专项 | 109 passed | 核心策略、HTTP 模拟、实际 SQLite 事务、隔离模块产物 |
| 监控已有 IAM 套件及新增专项 | 570 passed / 39 skipped / 7 deselected | 真实 Django apps、55 Actions、Permission/DRF、mock IAM/DB 边界 |
| BKLog IAM + 管理诊断工具 | 673 tests，OK | IAM 664 + 诊断决策 9，真实 Django models 与内存 fixture 表 |
| 监控原生 MCP 消费者 | 790 passed | 真实 MCP 权限模块；框架边界 mock，部分重型 HTTP 方法由既有 AST 测试执行 |
| Web/API/Worker 装配 | 三种角色均成功加载 V3/V4、55 Actions，并注册 V4 重试任务 | Django 测试 bootstrap；不是完整服务健康或 broker 消费验证 |
| 共同决策/编排静态类型 | 0 errors / 0 warnings | core、provider、dual_write、policy、replay，未全仓类型检查 |
| Ruff / whitespace | 检查和格式化通过，git diff --check 通过 | 仅本次改动文件；正常提交 hook 另行记录 |

执行命令：

```bash
PYTHONPATH=.:bkmonitor python -m pytest -c /dev/null --noconftest \
  -p no:django -p no:cacheprovider iam_engine/tests -q --tb=short
python iam_engine/tests/run_monitor_offline.py tests/iam -m 'not live' --tb=line
python iam_engine/tests/run_bklog_offline.py apps.tests.iam apps.tests.log_admin_resource.test_iam_decision
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:bkmonitor python -m pytest \
  -c /dev/null -p no:cacheprovider bkmonitor/kernel_api/tests/test_native_mcp_permissions.py -q --tb=short
python iam_engine/tests/run_monitor_offline.py --role web --startup-only
python iam_engine/tests/run_monitor_offline.py --role api --startup-only
python iam_engine/tests/run_monitor_offline.py --role worker --startup-only
pyright --pythonpath <monitor-python> iam_engine/core iam_engine/provider \
  iam_engine/migration/dual_write.py iam_engine/migration/policy.py iam_engine/migration/replay.py --level error
```

Monitor 39 跳过项是需要真实 IAM 配置/写授权的既有用例；7 项 live 标记排除，
`test_live*` 模块整体排除，未执行真实环境用例。Monitor 3 条既有 Django 弃用告警，
MCP 7 条依赖弃用告警，不是测试失败。

测试脚本在加载 settings 前拦截外连 socket 和 requests Session，所有 DB alias 为
内存 SQLite、Django cache 为 LocMem。BKLog 关闭测试中的 APIGW 公钥启动获取并
mock 非 IAM Redis 连接；只创建 GlobalConfig、FeatureToggle、SpaceType、Space 表，
不执行迁移/post_migrate。部分 AppConfig 初始化因尚无 fixture 表产生预期日志，
授权重试/指标容错用例也会输出预期异常日志；以上均未改变正式配置。

## 直接覆盖的行为

- V3/V4/Union；允许、拒绝、错误组合；非法模式和非布尔响应 fail closed。
- 动态模式每次请求解析；批量整批只解析一次，Action 策略查询继续走批量入口。
- Union 明确 ALLOW 赢过另一侧 DENY/ERROR；没有 ALLOW 拒绝，保留 degraded 证据。
- 无权限申请/展示优先 V4，既有申请回退路径保留。
- 三个读模式均调用 V3 与 V4 写入，不让读选择影响写目标。
- 首次两侧同步尝试，默认 365 天；实际 transaction.atomic 提交后投递、回滚不投递。
- 重试原样保留租户、主体、角色、资源、expired_at；退避和最终终止不依赖真实 broker。
- 同一 settings loader、endpoint loader、选项归一化；无隐式 V4 网关推导。
- V4 201 空授权响应、HTTP/业务错误、租户头、阶段路径、不完整/重复批量资源结果。
- 持久化 IAM_V1_COMPATIBLE=False 不再双查旧 Action；动态变化不复用旧兼容标志缓存键。
- V4 has_any_permission 不再恒真，零权限不能绕过 Grafana 粗门禁。
- Grafana 实际候选包括当前 org 的 dashboard 和 folder；folder 展开与 View/Edit ACL；
  空期望权限删除现有托管角色 ACL，不影响其他角色，也不创建无用角色。
- MCP 通过统一决策、保留 bypass hook；故障不能触发明确 DENY 的原生权限回退；
  legacy `_v2` Action 归一化，申请保留父链与租户。
- callback 错误响应不回显上游详情，结构化日志转义换行，0 TTL 禁用 token 缓存。
- 最新 model migration 0002 覆盖 55 Actions（含日志采集/提取 MCP），最新 snapshot 无 diff。
- 两平台产物解引用后隔离导入共同模块，公共运行时代码无产品 import。

## 只读自审

目标是本地本次 diff 相对实现基线，而不是把未推送代码当成远端 PR current head。
复核 Permission/DRF→ProviderRouter→SharedMigrationPolicy→ModeRouter→产品 provider 的
实际路径，以及 MCP、Grafana proxy→sync_dashboard_permission、Celery 重试与配置加载。

此前六类高优先风险（V4 任意权限恒真、V3 兼容配置遗漏、非法组合策略回退、Grafana
候选/ACL 回收、MCP 旧 SDK 路径、模型快照遗漏）在本地改动中修复并有回归证据。
callback CodeQL 提示对应位置已在本地处理并直接测试；不代表远端 CodeQL 重新通过。
已实现范围未发现新的可复现 P0/P1；未发布评论、resolve、approve 或创建新 PR。

## 单据验收项状态

| 验收项 | 本轮状态 |
| --- | --- |
| 同一公共源、产物导入 | 本地隔离产物通过；真实部署归档与完整容器待验证 |
| 单向依赖、原 Permission/DRF | 通过 |
| 三种模式、三态组合 | 通过 |
| Union OR、V4 优先申请 | 通过 |
| 动态选择与独立双写 | 通过 |
| 365 天有效期 | 创建者与迁移冻结机制通过；完整转换脚本未完成 |
| 事务/重试/恢复边界 | 离线通过；真实 broker/故障恢复未验证 |
| settings/env 一致 | 共同声明与解析回归通过；未修改 Charts |
| 精确资源/实际消费者 | 当前 IAM、DRF、列表、Grafana、MCP 回归通过；非全平台 E2E |
| 完整策略迁移脚本 | 部分完成，Action→Role 映射与产品转换待确认 |
| 本地测试及证据 | 通过，模拟不冒充真实接入 |
| 真实 IAM 普通用户验收 | 用户指定本阶段 not_run |
| 开发/真实验收分开报告 | 已记录 |
| 吴嘉华最终验收 | 待确认 |

## 真实环境后续清单

监控 system ID 使用 `bk_monitorv3`，目标 V4 gateway 为已确认的 dev 地址，尚未注册。
普通用户 jayjhwu 当前预期 V3 有权/V4 无权。后续在明确操作授权和范围后验证：
V3-only 允许、V4-only 拒绝、Union 允许；再覆盖其余三个授权组合及申请/创建者链路。
核验 callback 路由/Basic token、模型注册、真实资源范围、V4 201 授权、broker 实际投递，
明确云侧 365 天授权有效期与精确实例范围。不要以单测代替真实接口与部署证据。

回退使用配置中心 v3 模式，保留两侧写目标和原 V3 授权。自动化迁移实际执行另行确认。
