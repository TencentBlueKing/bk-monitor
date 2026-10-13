# IAM V4 稳定产品边界与公共底层复用：离线自测报告

日期：2026-10-13。单据：138944425。分支：`feat/iam-v4-support`。
本轮纠偏基线：`e33a428ad25a96b2c64c023dec89dbf9b4e19feb`。
已同步 master `ff89f63ff4036b4ff6dad180ba3455eb34ef62ab`；合并提交为
`fda06c588d` 和 `bb52f054f9`。业务兼容同时对照原 V3 及最新 master。
报告只代表本轮最终离线结果，不沿用此前快照的通过数；提交/推送回执另记 TAPD。

## 交付范围与结构

以 V3 稳定产品接口及 BKLog 分层为基础，Monitor Permission 直接装配公共 ModeRouter
和原生 ProviderBundle。V3/V4 Provider 直接实现公共 PermissionProvider；
application/scope 由同一 Provider 提供，writer 通过公共双写编排执行。
Monitor V4 Client 继承公共 V4Client，鉴权、批量、范围、申请和新授权均复用通信底座；
产品只增加模型注册所需方法。删除 MonitorAuthAdapter、独立 grant 装配层及 adapters 目录。

监控的 Permission/Action/Resource/DRF 实现回到原有 `bkmonitor.iam` 公开模块，
不再用根目录转发壳加 handlers 实现；BKLog 保留原有 `apps.iam.handlers` 公开入口。
两者一致的是职责、协议和共同实现，不要求目录树或 import 路径相同。
撤回纯目录对齐造成的上层 import 改动，对照此前改动的 72 个运行时消费者均已恢复。
backends/v3、backends/v4 提供产品协议，callback 和冻结授权重试仍留在产品 IAM 层。
MCP 继续通过 Permission.make_request / iam_client 使用稳定产品入口，
不在业务层实例化双栈客户端；版本装配留在 IAM 内部。
不再因 IAM 内部 resources.py 的错误落点修改全局 ResourceFinder：
删除该落点及配套扫描规则，恢复 master 的资源发现行为。
两平台仍通过软链接引用根目录同一份 iam_engine；并发双路和有序分页也复用同一算法，
产品仅负责绑定及恢复本身的请求、租户、时区和 OTel 上下文。

保留的产品差异是实际的 Action/资源/角色、空间 ID 编码、V3 策略 AST、
Grafana 文件夹覆盖、模型注册与 SaaS 凭据/请求上下文来源，不是旧 V4 框架兼容。
共同 settings/env 契约与已确定的 V3/V4/Union、动态模式、独立双写、365 天规则不变。
**不开发存量授权迁移脚本：该工作由 IAM 完成。**

## 业务兼容复核

- 外部授权创建/更新和列表恢复调用 `get_user_permission` 的三项返回契约；
  原两项 `get_visible_dashboards` 保留为产品权限内部的范围接口。
- 收藏、单仪表盘和目录列表只传用户名、业务 ID、仪表盘 UID；
  本地文件夹候选及覆盖展开集中在 DashboardPermission。
- Grafana 业务消费者不再导入引擎 Subject/Resource 或自己拼祖先资源。
- APM 旧 permission Action key 在 DRF 适配边界从同一授权结果生成，
  删除各业务视图的 include_legacy_action_keys 开关。
- 保留 DRF V3 的 actions/resource_meta 公共属性及真实 MCP Middleware 消费契约。
- master 新增的 MCP 索引目录可见性、资源唯一性和归属空间校验保留，
  不回退到请求业务 ID 代替索引集实际归属空间；冲突路径定向回归 32 passed。
- 沿用 instance_create_func 标准扩展点。APM/RUM 列表元数据保留名字及父空间，
  不再被丢弃后逐条查询。单实例缺少元数据时仍由产品 resolver 解析。
- 装饰器识别实际绑定的 ResourceViewSet，不能把 self 当作 request；
  已增加实际 APM ResourceRoute 的回归。
- 授权范围查询故障不是成功的空范围，不进入 ACL 撤权。

ACL 空期望权限撤销 managed ACL 是此前版本已引入的可观察行为，本轮没有新增或回退
该规则；独立测试撤销范围、非 managed ACL 保留、查询失败不写、写失败及再次同步。
不能将这一行为仅描述为目录重构。

## 已观察到的最终结果

离线入口使用两产品既有 Python 3.11 环境、假凭据、内存 SQLite/LocMem，禁止外连；
不加载个人 local_settings。每套命令独立统计，不相加冒充业务场景数。

| 检查 | 最终结果 | 证据边界 |
| --- | --- | --- |
| Monitor IAM/公共层/DRF/APM/RUM/Grafana/权限 RPC/统一 MCP 合并回归 | 872 passed，39 skipped，13 deselected，退出 0 | 实际 Django 装配和消费者；外部 DB/API 模拟 |
| 独立原生 MCP 套件 | 808 passed，退出 0 | 原生权限模块实际执行；重型 HTTP 方法沿用 AST 隔离测试 |
| 既有产品边界补充回归 | 89 passed，退出 0 | Token、Datalink、NewReport、收藏搜索、FTA、场景/主机视图；ORM 模拟 |
| BKLog IAM 与管理诊断决策 | 673 tests，OK，退出 0 | 实际 Django/产品装配、内存 IAM fixture 表 |
| Monitor Web/API/Worker 冷启动 | 三种角色均退出 0，V3/V4、55 Actions、冻结任务已注册 | 离线 bootstrap，不是在线服务或 broker |
| 公共层 Pyright | 0 errors，0 warnings，退出 0 | core/provider/schema/policy/model、dual_write/policy |
| Ruff / whitespace | 当前 Python 范围通过，git diff --check 通过 | 非全仓静态检查；正常提交 hooks 回执另记 |

39 项因真实 IAM 配置、授权写入开关或迁移目录等门控跳过；13 项明确排除：
10 项 live 用例及 3 项依赖真实数据库迁移的 Profile 集成用例。
test_live* 模块整体不执行，不计入通过数。

此前扩展测试曾暴露并修复上述 DRF 公共属性、元数据扩展点和绑定方法问题；
也更新了已移除 Provider 方言接口的测试替身，保留原鉴权/拒绝断言。
原生 MCP 的极简 settings/模块替身套件必须独立进程执行，不能与完整 Django suite 混用。
统一 MCP 两处既有测试替身按真实职责更新：附加动作规则由实际 legacy 决策函数核验，
时序表范围检查 mock 的是实际 metrics 模块，不再 mock dispatcher 的已移除符号。
本轮没有修改这两处 MCP 产品规则。

本轮新增公开模块实现归属、SDK 请求元数据、V3/V4/Union 经产品入口实际路由、
业务消费者不依赖内部搬迁路径的回归测试。原生 MCP 测试恢复 master 的公开入口替身，
不再让业务夹具装配公共引擎。
补充回归首次出现 10 个失败和 6 个 setup 错误：旧夹具通过 Permission.__new__
注入单栈 SDK、模拟了已不调用的旧内部方法或缺少用户名；全 ORM mock 的 Datalink
用例继承 Django TestCase 后错误启动了全库迁移。按当前调用边界更新替身，
保持原放行/拒绝断言；该无数据库用例使用标准 unittest.TestCase，未改变产品权限规则。
修复后的补充命令为 89 passed，不能将首次失败当作通过或真实数据库验收。

Profile 的 3 项 django_db 用例尝试启动时，既有 MySQL 专用迁移在 SQLite 上语法错误。
这不是用例通过，最终合并命令明确排除并列为未覆盖；未为自测改写产品迁移。
BKLog 启动的应用信息取值被禁网入口阻断，以及故障分支日志/SDK 弃用告警，均如实保留。

## 复现命令

从仓库根目录运行，python 分别使用 Monitor/BKLog 现有环境：

```bash
python iam_engine/tests/run_monitor_offline.py \
  tests/iam ../iam_engine/tests tests/test_iam_business_action_permission.py \
  kernel_api/rpc/tests/test_admin_permission.py kernel_api/rpc/tests/test_admin_permission_v4.py \
  kernel_api/tests/test_unified_mcp.py \
  packages/apm_web/tests/test_application_permissions.py \
  packages/apm_web/tests/test_list_application_permission.py \
  packages/apm_web/tests/llm/test_permissions.py \
  packages/apm_web/tests/profile/test_permissions.py \
  packages/apm_web/tests/trace/test_permissions.py \
  packages/rum_web/tests/test_list_application_permission.py \
  -m 'not live and not django_db' --tb=line --disable-warnings
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:bkmonitor python -m pytest \
  -c /dev/null -p no:cacheprovider bkmonitor/kernel_api/tests/test_native_mcp_permissions.py \
  -q --tb=line --disable-warnings
python iam_engine/tests/run_monitor_offline.py \
  packages/monitor_web/tests/test_permissions.py \
  packages/monitor_web/tests/datalink/test_permissions.py \
  packages/monitor_web/tests/new_report/test_report_view_permissions.py \
  packages/monitor_web/tests/overview/test_service_search.py \
  tests/web/fta_actions/test_action_preview_permissions.py \
  tests/web/performance/test_view_permissions.py \
  tests/web/scene_view/test_view_permissions.py \
  -m 'not live and not django_db' --tb=line --disable-warnings
python iam_engine/tests/run_bklog_offline.py apps.tests.iam apps.tests.log_admin_resource.test_iam_decision
python iam_engine/tests/run_monitor_offline.py --role web --startup-only
python iam_engine/tests/run_monitor_offline.py --role api --startup-only
python iam_engine/tests/run_monitor_offline.py --role worker --startup-only
pyright --pythonpath <monitor-python> iam_engine/core iam_engine/provider \
  iam_engine/schema iam_engine/policy iam_engine/model \
  iam_engine/migration/dual_write.py iam_engine/migration/policy.py --level error
```

## 验收边界与残余风险

没有连接真实 IAM、注册系统、授予权限、部署或修改 Charts；未完成真实 E2E。
真实网关/模型/用户授权、申请页与精确范围、callback、Celery 实际投递与故障恢复，
以及生产 MySQL 上的业务集成测试、镜像构建和归档解引用仍需后续验收。
正常 Git hooks 并不替代这些检查；PreCI 包装脚本若跳过扫描，不表示实际 PreCI 完成。

Union 任一明确 ALLOW 放行，否则拒绝并保留 ERROR/degraded；申请优先 V4。
回退只切读模式到 v3，不删除授权/模型，也不关闭配置好的独立双写。
最终业务验收由提出人负责；存量授权迁移不作为本次产品交付阻塞项。
