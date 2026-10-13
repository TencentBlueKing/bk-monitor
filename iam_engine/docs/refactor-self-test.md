# IAM 结构收敛：离线自测报告

日期：2026-10-13。单据：138944425。分支：`feat/iam-v4-support`。
本轮基线：`c5b7054b3cd02a2c59080b3012283bb9c62ab180`，对应 PR #12734 已推送版本。

## 结论与范围

监控保留 Permission/DRF 对外接口，直接装配 BKLog 使用的公共 ModeRouter；
删除监控私有 iam_engine、IAMFramework、ProviderRouter、SharedMigrationPolicy、
框架单例和 IAM_FRAMEWORK 配置目录，不通过兼容外壳间接复用公共层。
两平台仍引用根目录同一份 iam_engine。

产品协议适配统一放在 backends/v3、backends/v4；监控的 Action、Resource、Role、
codec、资源解析、回调和租户边界保持产品所有权。纯 Python schema、policy、model
工具移至公共目录；Django AppConfig、注册记录、信号和命令留在产品侧。
模型注册文件明确排除在 Django 数据库 migrations 之外。

**存量授权迁移由 IAM 完成，不在本次产品开发范围。** 未被产品调用的存量回放
工具及其测试已移除；保留模型注册/更新、新建资源授权双写和冻结请求重试。
此前报告中 Action→Role 存量转换待确认、脚本未完成的说明作废。

本轮开发离线自测通过；真实 IAM 接入验收为 not_run，不宣称已可上线。
未连接真实 IAM、未注册系统、未真实授权、未部署，未修改 Charts。
最终业务验收仍由提出人负责。

## 实际执行结果

Python 使用两产品既有 Python 3.11 环境；离线入口不加载个人 local_settings，
使用显式假 SaaS 凭据、内存 SQLite 和 LocMem，阻断 socket/requests 外连。
API/Worker 正式环境的 SaaS 凭据仍沿用 settings/GlobalConfig，未改变其来源。

| 检查 | 实际结果 | 证据边界 |
| --- | --- | --- |
| 监控 IAM、公共层、管理权限 RPC、告警消费者合并回归 | 785 passed / 39 skipped / 10 deselected | 实际 Permission/DRF、55 Actions、模拟 IAM、内存 DB |
| BKLog IAM 与管理诊断决策 | 673 tests，OK | 实际 Django 装配与产品适配；外部依赖模拟 |
| 监控原生 MCP 消费者 | 790 passed | 实际 MCP 权限模块；部分重型方法采用既有 AST 测试 |
| 重构前后同输入对照 | 195 passed | 基线 c5b7054b 的实际决策与范围算法，对照当前 Permission |
| Web/API/Worker 装配 | 三种角色加载 V3/V4、55 Actions、冻结授权重试任务 | 离线 Django bootstrap，不是完整服务或真实 broker |
| 公共层类型检查 | 0 errors / 0 warnings | core、provider、schema、policy、model、dual_write、migration policy |
| Ruff / whitespace | 检查、格式化和 git diff --check 通过 | 本次 Python 改动范围，不是全仓检查 |

上述套件结果分别统计，不用相加后的总数冒充互不重复的业务场景数。
39 个跳过项需真实 IAM 配置/写授权；10 个 live 用例明确排除，
test_live* 模块整体不运行。Django/SDK 弃用告警不是测试失败。
BKLog 启动取应用信息被离线入口阻断，以及故障分支的异常日志，属于预期输出。

执行命令均从仓库根目录运行，python 使用表中对应产品环境：

```bash
PYTHONPATH=.:bkmonitor python iam_engine/tests/run_monitor_offline.py \
  tests/iam ../iam_engine/tests \
  kernel_api/rpc/tests/test_admin_permission.py \
  kernel_api/rpc/tests/test_admin_permission_v4.py \
  packages/fta_web/tests/alert/test_biz_condition.py -m 'not live' --tb=line
python iam_engine/tests/run_bklog_offline.py \
  apps.tests.iam apps.tests.log_admin_resource.test_iam_decision
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:bkmonitor python -m pytest \
  -c /dev/null -p no:cacheprovider \
  bkmonitor/kernel_api/tests/test_native_mcp_permissions.py -q --tb=line
python iam_engine/tests/run_monitor_offline.py --role web --startup-only
python iam_engine/tests/run_monitor_offline.py --role api --startup-only
python iam_engine/tests/run_monitor_offline.py --role worker --startup-only
pyright --pythonpath <monitor-python> iam_engine/core iam_engine/provider \
  iam_engine/schema iam_engine/policy iam_engine/model \
  iam_engine/migration/dual_write.py iam_engine/migration/policy.py --level error
```

同输入对照为本轮临时只读验证：从 Git 读取固定基线的 SharedMigrationPolicy 和其
契约，使用等价值对象加载；147 个模式/允许/拒绝/异常/畸形结果组合，
48 个资源范围组合，全部与当前结果一致。临时验证脚本不加入产品产物。
持续回归由仓库里的契约测试维护，不让 CI 依赖本地临时文件或 Git 历史。
类型检查不覆盖全仓产品代码。正常提交 hooks 与推送回执另记于单据。

## 直接覆盖的验收项

- 公共模块无产品业务 import；双产品软链接指向同一源；隔离产物可以导入。
- 监控没有私有引擎或新增框架外壳，Permission 实际持有公共 ModeRouter。
- V3/V4/Union；Union 任一明确允许即通过，无允许则拒绝；异常保留 degraded。
- 动态模式每次解析，批量模式快照；非法模式、非布尔值、批量缺项不放行。
- Union 无权限申请优先 V4，原申请回退保持；精确资源范围不退化为空间级授权。
- 三个读模式均独立调用两侧写目标；默认 V4 365 天。
- 实际 transaction.atomic 提交后投递、回滚不投递；冻结主体、租户、资源、角色、
  expired_at 不在重试时重算；没有 outbox/持久化补偿。
- 两平台共同 settings/endpoint loader、选项归一化；不从 V3 推导 V4 网关。
- Permission/DRF 的 Action 兼容、token/skip_check、申请协议、列表范围与租户边界。
- MCP 明确拒绝/错误的回退边界；Grafana 粗门禁、dashboard/folder 候选与 ACL 回收。
- callback 路由、凭据与 token 缓存，V4 HTTP/业务异常和批量响应契约。
- 模型注册命令使用实际 Permission 和只读 recorder；最新 snapshot 覆盖 55 Actions。
- Web/API/Worker 的产品 IAMConfig 与重试任务注册，模型注册/数据库迁移分离。

## 本地只读自审

针对本轮相对 c5b7054b 的本地 diff，核对真实 Permission/DRF → 公共 ModeRouter
→ 产品 backend，以及 MCP、Grafana、RPC、callback、授权重试和模型注册调用链。
删除的测试是已移除框架配置/外壳的过时契约；业务行为测试改为实际 Permission
边界，没有增加仅为旧测试服务的兼容框架。

自审发现的命令 settings 导入遮蔽、旧消费者 mock 和离线角色凭据缺口已修复，
重新运行相关测试。当前范围未发现新的可复现 P0/P1。
未发布 GitHub 评论、resolve、approve 或创建新 PR；远端 CI 未以本地结果代替。

## 未覆盖与残余风险

真实 IAM 普通用户/精确资源/申请页/模型注册/新增授权，以及 Celery broker 投递
与故障恢复未验证；未构建完整镜像、未验证真实部署流水线解引用归档。
公共目录的隔离导入不等于完整容器或正式部署验收。

后续需在明确操作范围后验证监控 system ID bk_monitorv3、仅 V3/仅 V4/Union，
四种授权组合、callback 和创建者授权及重试。本阶段按提出人要求不运行真实数据。
配置中心切回 v3 是读侧回退，不删除 V3/V4 模型、授权或关闭独立双写。
存量权限迁移不作为本次交付阻塞项，由 IAM 负责。
