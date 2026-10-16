# IAM V4 稳定产品边界与公共底层复用：离线自测报告

> 下文前几节是已交付快照的历史记录。“始终双写”“显式 V4 URL 才启用”“申请回退 V3”
> 已由文末新版模式/模型同步验收替代；当前行为以 README 和文末最新范围为准。
> SchemaRegistry、动态枚举、中间策略 DSL、产品回调框架等描述也仅属于历史快照；
> 它们已在最新架构对齐中删除，不能作为当前实现说明。

日期：2026-10-13。单据：138944425。分支：`feat/iam-v4-support`。
本轮纠偏基线：`e33a428ad25a96b2c64c023dec89dbf9b4e19feb`。
已同步 master `ff89f63ff4036b4ff6dad180ba3455eb34ef62ab`；合并提交为
`fda06c588d` 和 `bb52f054f9`。业务兼容同时对照原 V3 及最新 master。
报告包含同日 `a7a0440743` 之后的 PR diff 清理；以下最终结果已在清理后重新运行，
不沿用此前快照的通过数；提交/推送及正常 hooks 回执另记 TAPD。

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

复审确认：空期望权限撤销 ACL 不属于本次需求，已恢复为 V3 基线的直接返回、不操作 ACL。
非空权限的 managed ACL 对账仍保留，测试覆盖非 managed ACL 保留、查询失败不写、
写失败及再次同步。不能把未授权的业务行为变化混入 IAM 重构。

## 已观察到的最终结果

离线入口使用两产品既有 Python 3.11 环境、假凭据、内存 SQLite/LocMem，禁止外连；
不加载个人 local_settings。每套命令独立统计，不相加冒充业务场景数。

| 检查 | 最终结果 | 证据边界 |
| --- | --- | --- |
| Monitor IAM/公共层/DRF/APM/RUM/Grafana/权限 RPC/统一 MCP 合并回归 | 915 passed，36 skipped，13 deselected，退出 0 | 实际 Django 装配和消费者；外部 DB/API 模拟 |
| 独立原生 MCP 套件 | 808 passed，退出 0 | 原生权限模块实际执行；重型 HTTP 方法沿用 AST 隔离测试 |
| 既有产品边界补充回归 | 89 passed，退出 0 | Token、Datalink、NewReport、收藏搜索、FTA、场景/主机视图；ORM 模拟 |
| BKLog IAM 与管理诊断决策 | 673 tests，OK，退出 0 | 实际 Django/产品装配、内存 IAM fixture 表 |
| Monitor Web/API/Worker 冷启动 | 三种角色均退出 0，V3/V4、55 Actions、冻结任务已注册 | 离线 bootstrap，不是在线服务或 broker |
| 公共层 Pyright | 0 errors，0 warnings，退出 0 | core/provider/schema/policy/model、dual_write/policy |
| Ruff correctness / whitespace | 本轮现有文件无新增 E4/E7/E9/F；新增目录树用例通过；git diff --check 通过 | 与 master 对照既有告警；未执行全文件自动格式化，正常 hooks 回执另记 |

36 项因真实 IAM 配置、授权写入开关或迁移目录等门控跳过；13 项明确排除：
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

## PR diff 范围清理（2026-10-13）

清理基线为 `a7a0440743`，对照已同步的 master `ff89f63ff4`，
检查范围是整个 PR，不只本轮提交的文件。

- 22 个文件恢复为 master 原文，完全退出 PR diff：16 个业务视图/工具文件，
  healthz、ResourceFinder、搜索 handler、旧 IAM migrate、原生 MCP 测试及目录树调用方。
- 混合文件保留必要 IAM 配置、SDK/公共层引用及测试替身；撤回无关注释删改、
  字符串/类型现代化和行宽变化。异常处理框架只保留 IAM PermissionDenied 转换。
- 目录树重新统一调用已有 request-aware 产品权限入口；内部和外部用户各一项
  实际消费者回归，证明业务层不必新增版本/身份分支。
- 按 Git 的 rename-aware 口径，PR 涉及路径从 272 缩减为 250。
  其余改动归属产品 IAM、公共引擎、配置/打包/回调/任务，以及必要消费者和回归测试。
  仍有新的 IAM 文件和公共模块抽取，不能把路径总数当成上层业务改动数量。
- 当前相对 master 不再有整文件 AST 相同的 Python diff；恢复原文的文件逐一字节核对。
  本轮现有文件的 correctness 静态告警从 master 11 项到当前 2 项，未新增；
  master 的既有格式/现代化告警不是本需求的修复范围。

不修改 Ruff/PreCI 的仓库规则，不接受 hook 重新引入无关变更后直接暂存提交。
正常提交 hook 的实际执行结果及处置另记 TAPD，不能以本报告替代提交回执。

## PR #12734 新增问题修复与 V3 基线复核

本轮修改起点为 `be94662bb66e6bf5bb0b0e2ac986c00079712546`；
V3 对照使用 PR 当前目标基线 `ff89f63ff4036b4ff6dad180ba3455eb34ef62ab`。
以下结论针对本轮工作区修复，不把旧远端 head 的 CI 结果当作修复后验收。

此前 review 的十项问题已处理：

1. Grafana 门禁恢复当前业务与 request-aware 入口，不按全局任意仪表盘授权放行。
2. V3 策略转换不再丢弃无法识别的 AND 子条件；本地判定沿用 SDK 求值器，
   保留数组、类型、负向条件、比较及 `_bk_iam_path_` 的历史语义。
3. Grafana V3 策略范围解析收回 V3 backend，保留裸 UID、嵌套 AND/OR、
   文件夹和不依赖本地候选存在性的授权范围；文件夹展开仍在产品权限层。
4. space_uid 在统一 resolver 中归一化；批量响应按编码后的 ID 查找，
   再用调用方原始 ID 回填，覆盖 V3/V4 两条路径。
5. `is_allowed_by_biz` 恢复完整 Token/skip_check 前置豁免。
6. 收藏与 Grafana 门禁恢复原 request.skip_check/超级用户和角色合并规则；
   外部授权撤掉重复范围查询，沿用原角色/实例权限映射。
7. 默认 V3 动作元数据原样返回远端 model.actions；V4/Union 投影稳定的
   前端历史 Action ID、依赖 ID 及资源选择字段，不要求 V3 在线。
8. V3 申请数据初始化 SDK 元数据，冷启动返回正确的系统、动作及资源名称。
9. DRF 拒绝分支沿用 SaaS 空间 26 Action 申请包，覆盖三种读模式。
10. 空期望 ACL 恢复基线 no-op，`bk_dataview/api.py` 与 PR 基线字节一致。

进一步复审补齐默认 V3 的完整关联资源请求与显式实例属性，不再新增混合类型限制，
不将原 SDK 请求改成逐实例鉴权；非空间资源的拒绝信息不再误构造为空间资源。
V4/Union 多实例批量入口维持既有逐项决策，公共 OR 规则、V4 优先申请、
配置中心模式、独立双写及 365 天有效期未改变。

删除没有运行时引用的 CodecPermissionProvider/Dialect DTO/ProviderFeatures
中间模板及其专用测试；实际 V3/V4 Provider 和公共 Router、通信、双写测试保留。
旧断言中“丢弃 attribute”和“空权限撤销 ACL”被更新为 V3 基线契约；
业务测试替身补齐真实 Permission 的 SaaS 申请接口，没有修改业务放行/拒绝断言。

新增 `test_v3_compatibility.py` 为持久回归；另用同组输入执行实际基线源码的
20 项差异对照，全部通过。该对照为方法/消费者隔离复现，不是完整 HTTP 或真实 IAM。
本轮主回归、业务补充、BKLog、独立 MCP、三角色冷启动与公共层 Pyright 均重新执行；
结果见上表。只读 Ruff correctness 与 `git diff --check` 通过。
正常提交 hook 首次因整理本轮新增代码失败；逐 hunk 确认只涉及新代码及删除后的类间距，
没有对原有无关代码进行全文件格式化或现代化改写；未跳过 hooks。
完整 PR 的现存 Python diff 没有整文件 AST 相同的纯格式/注释改动；
上层仅保留必要的权限接口适配，收藏与 ACL 同步退出 PR diff。

远端仍有四条 CodeQL 日志注入线程未解决；本轮未发布 review 或 resolve。
Code Review MCP 未连接 GitHub，未读取修复后 CI；不将本地通过扩大为 CI/部署通过。
真实 IAM、申请页面、MySQL 迁移及线上 E2E 仍未执行。

## 新版模式、网关与模型同步（2026-10-13）

本轮修改基线 `b925ce99f`。最新用户 Plan 替换历史“所有模式始终双写”及“URL 非空启用 V4”。
单一模式统一控制鉴权、创建者授权、模型同步与申请；默认 V3 仅调用 V3，V4 仅调用 V4，
Union 两套鉴权取 OR、授权和模型都执行两套，申请仅走 V4。不新增启用开关、业务灰度、
`all_of` 或 `primary`。原有 Token/skip_check、产品角色/资源边界与 365 天冻结重试保留。

两产品共用 `resolve_iam_gateway_url`，从组件根地址独立推导 `bk-iam` / `bkiam` 网关；
保留既有合法覆盖入口及优先级，处理空白、斜杠和缺失值。测试 mock 实际 HTTP 请求 URL，
不是只断言 settings。V3 默认不装配 V4；能力缓存不缓存模式，一次鉴权/申请共用快照。
V4/Union 申请使用 API 返回的页面 URL，失败保持拒绝并返回空申请数据/链接，无 V3 回退。
**仅 IAM 后端和必要配置/生命周期/测试改动，没有新增前端改动。**

V4 期望模型、远端 API、校验、diff、依赖执行、漂移/阻塞报告与锁进入共同 `model/`。
BKLog 保留 JSON 权威基线和运行时一致性检查；Monitor 从运行时 definitions 派生，
保留既有 Action ID，系统 ID 默认 `bk_monitorv3`。不删除远端额外对象/客户端/角色动作，
Action 换绑、角色维度和祖先链改变阻断。状态型假客户端验证部分失败后重跑收敛及最终 no-op。

部署 post_migrate 与两平台 `iam_migrate_model [--apply]` 共用 `ModelSyncService`。
部署严格读取权威模式，配置查询失败不假装默认 V3；同步失败会传播，命令失败为 CommandError。
Monitor V3 使用原 `Migrator` 和 `MonitorMigration(app="iam")`：不重放历史，
预览只列待执行文件、不调用写入口，apply 用新的原 Migrator 实例，防止重复加载破坏依赖图；
完成后核对历史记录，不能把旧引擎的静默退出当成功。BKLog 保留原 JSON/SDK upsert，
预览明确不是远端 diff。仅动态切模式不会自动注册目标模型，必须先以目标模式部署或同步。

删除旧 Monitor 迁移命令、Planner/Loader/Recorder、V4 快照及专用测试；
移除重复模型 HTTP 接口和孤儿迁移 DTO/可见性 helper；BKLog 旧 V4 命令由统一命令替换。
**原 Monitor V3 迁移文件、历史模型/数据库表均未删除；不实施存量授权迁移。**
删除的源码与测试可从 Git 恢复，不执行数据库结构清理。

本轮实际结果（分别统计，不相加冒充场景数）：

| 检查 | 结果 | 边界 |
| --- | --- | --- |
| Monitor IAM/公共层/DRF/APM/RUM/Grafana/RPC/MCP 主回归 | 906 passed、9 skipped、21 deselected，退出 0 | 实际 Django 与业务调用链，外部依赖 mock |
| 既有业务补充 | 89 passed，退出 0 | ORM/API 模拟 |
| 原生 MCP 独立进程 | 808 passed，退出 0 | 独立原生权限与消费者 |
| BKLog IAM/管理诊断 | 661 tests，OK，退出 0 | 实际 Django、内存 fixture 表 |
| 实际 V3 基线源码差异对照 | 20 passed，退出 0 | `ff89f63ff4` 方法/消费者隔离，不是 HTTP E2E |
| Web/API/Worker 冷启动 | 均退出 0，只装配 v3、55 Actions、冻结任务已注册 | 假配置、禁网 |
| 公共层 Pyright | 0 errors、0 warnings，退出 0 | 包含新公共模型服务/命令适配 |
| 新模型/模式测试 Ruff | 通过 | 只读检查；新增文件排版通过 apply_patch 应用 |

主回归 9 项为真实 IAM 门控；21 项明确排除 live 或真实 DB 迁移用例。
SQLite 未运行全库迁移，MySQL advisory lock 仅做游标/故障模拟；未验证真实部署锁。
测试入口仍阻断 socket/HTTP；BKLog 启动应用信息和故障分支日志如实保留。
首次失败来自旧规则断言、旧依赖注入和测试清理残留，已修正后重新执行上述命令。

没有调用真实 IAM、注册/授权、部署或修改 Charts。真实模型 API/回调可达、V4 页面点击、
Celery/broker、生产 MySQL 与镜像部署仍待授权后的 E2E，不以离线通过代替。
CI 工具返回“Connect your GitHub account to continue”，未确认修复后远端 CI。
最新 master 已获取为 `59249477c`；提交、合并及合并后复测回执另记本报告与 TAPD。

最后一轮自审修复两个边界：公共 V4 模型读取拒绝提前空页/非法 count，避免基于不完整清单写入；
监控公开批量鉴权恢复原 V3 SDK 的完整资源组、历史 Action 键、原始返回与异常契约，
V4/Union 整批使用同一模式快照并保留同样的公开键。新增 14 项模型清单及 5 项批量契约测试。
针对后者的定向回归为 101 passed、9 skipped、7 deselected，退出 0；旧“公开接口返回内部 ID”
及旧 Provider 调用次数断言已按稳定接口契约更新，不要求业务调用方改键。
一次定向命令漏写离线筛选参数，尝试运行 SQLite 全库迁移后在 MySQL 专用 SQL 处失败；
没有真实 IAM/数据库写入。补回 `not live and not django_db` 后定向回归通过。
正常提交首次由 ruff-format 改写 18 个文件而中断，不是代码测试失败；逐项审阅后撤回一处
原 V3 的无关换行。用户授权本轮仅跳过 ruff-format，其余 hooks 保留；不修改仓库规则。

### 最终提交与合并后验收

实现提交为 `9e42bcd46`，随后将最新 master `59249477c` 合入，合并提交为 `0d595efcc`。
合并无冲突、没有改变 IAM 内容；两次提交的 GPG 签名均实际验证为 Good signature。
本节替代上面合并前的测试统计与待合并状态，不把重复执行的测试相加。

| 合并后实际检查 | 结果 |
| --- | --- |
| Monitor 主回归、业务补充与 V3 基线对照合并执行 | 1034 passed、9 skipped、21 deselected，退出 0 |
| 原生 MCP 独立进程 | 808 passed，退出 0 |
| BKLog IAM/管理诊断 | 661 tests、OK，退出 0 |
| Web/API/Worker 冷启动 | 三项退出 0，仅装配 V3、55 Actions；冻结重试任务注册不等于调用 V4 |
| 公共层 Pyright | 0 errors、0 warnings，退出 0 |
| IAM 范围只读 Ruff correctness、完整 PR `git diff --check` | 均通过 |

Monitor 使用产品虚拟环境解释器，执行命令如下；临时 V3 对照脚本隔离运行实际基线方法，
不是仓库测试入口或完整业务 E2E。临时脚本的 20 项已经包含在 1034 项中。

```bash
python iam_engine/tests/run_monitor_offline.py \
  tests/iam ../iam_engine/tests tests/test_iam_business_action_permission.py \
  kernel_api/rpc/tests/test_admin_permission.py kernel_api/rpc/tests/test_admin_permission_v4.py \
  kernel_api/tests/test_unified_mcp.py \
  packages/apm_web/tests/test_application_permissions.py \
  packages/apm_web/tests/test_list_application_permission.py \
  packages/apm_web/tests/llm/test_permissions.py packages/apm_web/tests/profile/test_permissions.py \
  packages/apm_web/tests/trace/test_permissions.py packages/rum_web/tests/test_list_application_permission.py \
  packages/monitor_web/tests/test_permissions.py packages/monitor_web/tests/datalink/test_permissions.py \
  packages/monitor_web/tests/new_report/test_report_view_permissions.py \
  packages/monitor_web/tests/overview/test_service_search.py \
  tests/web/fta_actions/test_action_preview_permissions.py tests/web/performance/test_view_permissions.py \
  tests/web/scene_view/test_view_permissions.py /private/tmp/test_pr12734_v3_review.py \
  -m 'not live and not django_db' --tb=short --disable-warnings

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:bkmonitor python -m pytest \
  -c /dev/null -p no:cacheprovider bkmonitor/kernel_api/tests/test_native_mcp_permissions.py \
  -q --tb=line --disable-warnings

python iam_engine/tests/run_bklog_offline.py apps.tests.iam apps.tests.log_admin_resource.test_iam_decision
python iam_engine/tests/run_monitor_offline.py --role web --startup-only
python iam_engine/tests/run_monitor_offline.py --role api --startup-only
python iam_engine/tests/run_monitor_offline.py --role worker --startup-only

pyright --pythonpath <monitor-python> iam_engine/core iam_engine/provider iam_engine/schema \
  iam_engine/policy iam_engine/model iam_engine/migration/dual_write.py \
  iam_engine/migration/policy.py --level error
ruff check --no-cache --select E4,E7,E9,F --ignore E402 iam_engine bkmonitor/bkmonitor/iam \
  bkmonitor/tests/iam bklog/apps/iam bklog/apps/tests/iam
git diff --check 59249477c...HEAD
```

再次检查整个 PR，而非只检查本轮提交：相对最新 master，前端与原 Monitor
`iam/migrations` 没有 diff；没有整文件 Python AST 相同的纯格式/注释变更。
上层改动限制在必要配置、注册/任务/打包、IAM 错误与产品权限入口适配及相关回归。
公开批量鉴权、文件夹覆盖、外部授权返回值、APM permission 与原 ACL 空权限 no-op
均纳入回归；不为目录一致而修改业务 import，不夹带 typo、类型现代化或无关优化。

实现提交仅跳过用户明确授权的 `ruff-format`；Ruff、冲突、私钥、IP 与提交信息 hooks
照常执行。master 合并走正常 Git 流程；没有修改 hook 配置或使用 `--no-verify`。
PreCI 包装提示系统未安装 PreCI 并跳过，不能计为实际 PreCI 扫描通过。
修复后的远端 CI 无法通过当前未连接的 GitHub MCP 核验，状态仍未确认。
上述全部是离线结果；真实 IAM、MySQL 部署迁移、回调和申请页面仍未验收。

## 最新：从 V3 基线出发的架构对齐验收

本节替代前面历史快照的实现说明和测试统计。盘点起点为 `89182eaa4`；
已将最新 master `864722982` 无冲突合入，合并提交为 `a0cba2225`。
完整机制去向、目录和调用链见 [架构对齐清单](architecture-alignment.md)。

本轮实际收敛内容：

- 两平台 V4 回调使用同一个 SDK Dispatcher 扩展和 ResourceProvider 协议适配；
  Monitor 的 Registry/Service/View/Auth 链及两产品重复回调/Token 缓存已删除。
- 每产品只有原生 ResourceProvider 拥有 ORM 查询，供回调、Resolver、构造和批量元数据
  共用。Monitor catalog 不再查询 ORM，BKLog 资源构造不再另写 ORM 查询。
- Monitor 公开 ActionMeta/ResourceMeta、静态枚举、字段、辅助方法、原 SDK Resource
  和原 `_v2` Action ID 保留；中立模型从这些定义派生，不维护第二份可编辑模型。
  `BK_IAM_APP_CODE`、`BK_IAM_SYSTEM_NAME` 恢复原 V3 配置契约。
- 删除 SchemaRegistry 注册/冻结/加载/快照/可见性、动态枚举和无消费者框架；
  删除 SDK dict → 中间 PolicyExpression → SDK dict，V3 原策略直接交 SDK 求值。
- Monitor 删除额外 V4 config dataclass/TokenProvider/客户端模型包装；
  直接使用共同 V4Options、通信、Token、缓存和租户/凭据隔离规则。
- 最新授权规则：公共编排仅同步调用选定 Writer，各尝试一次；已删除 Celery 补偿、
  冻结重试、退避及提交回调。所有角色仅显式严格调用抛错；默认 V3 契约不变。
  产品只负责真实授权映射，默认有效期仍为 365 天。后文历史运行数量不代表本轮结果。
- 原全局异常处理器恢复 master 原文；实际 IAM DRF → 原处理器测试确认三模式拒绝
  及 V4/Union 申请失败均为已处理的无权限响应，不误跳 V3、不产生未处理的 500。
- 权限诊断 RPC 补齐共同模式目标检查：指定被禁用的协议或非法模式时，装配 Provider
  前即拒绝；没有绕过主模式的 IAM 查询旁路。

模式同时控制鉴权/范围、创建者授权、模型同步和申请：默认 V3 仅 V3；V4 仅 V4；
Union 前三项执行两套、任一明确允许放行、申请固定 V4。URL 不启用协议。
网关推导、统一配置 loader、非破坏性 V4 模型收敛、自动 post_migrate 和
`iam_migrate_model` 入口保持新版规则；没有存量授权迁移，没有前端改动。

### 最后稳定工作区的实际结果

| 检查 | 结果与边界 |
| --- | --- |
| Monitor IAM/公共层/真实 DRF 处理器/APM/RUM/Grafana/RPC/MCP + V3 基线隔离对照 | 1025 passed、21 deselected、7 warnings，退出 0；包含 20 项基线方法对照 |
| 原生 MCP 独立进程 | 808 passed、7 warnings，退出 0；208.75 秒 |
| BKLog IAM/管理诊断 | 634 tests、OK，退出 0 |
| 原 V3 CompatibleIAM 与当前 V3Client 策略和请求的只读隔离对照 | 18 passed，退出 0；覆盖旧 Action 兼容开/关、成功空策略/ANY/EQ，不运行真实 IAM |
| Web/API/Worker 冷启动 | 三项退出 0；仅装配 V3、55 Actions，历史 V4 任务注册但不执行 |
| 公共层 Pyright | 0 errors、0 warnings，退出 0；core/provider/schema/model、dual_write/policy |
| IAM correctness Ruff、修改/新增 IAM 文件完整 Ruff、git diff --check | 均通过；恢复 master 原文的全局异常文件另有基线 UP 现代化告警，不改写无关代码 |

测试删除的是被替换框架及过时/不运行的断言；以原公开接口、真实消费者和 SDK 原语义
补充回归，不能把旧框架的测试数量作为本轮通过数。21 项为明确排除的 live/真实 DB 用例。
所有测试均禁用出站 HTTP/socket；BKLog 冷启动应用信息请求被阻断的日志如实保留。

Monitor 复现命令沿用前节完整业务集合，增加
`kernel_api/rpc/tests/test_permission_mode_boundary.py`；Pyright 不再传已删除的
`iam_engine/policy`。原生 MCP、BKLog 与冷启动命令保持前节入口。
临时 V3 对照脚本只用于基线方法隔离核验，不冒充完整 HTTP 端到端或仓库内测试。

再次检查完整 PR 相对 `864722982` 的 diff：前端、原 Monitor V3 migrations、全局异常
处理器均无 diff；Python diff 中没有整文件 AST 相同的纯格式/注释变更。
不批量调整业务 import、不夹带 typo、类型现代化或业务优化。
原 V3 模型迁移历史/数据库表保留；没有新增旧 Action 升级或存量授权迁移工具。

Git 提交及推送 hooks 的实际结果另记交付回执，不用单测替代 hooks。
仍未验收真实 IAM、MySQL 锁/部署 migrate、真实 Celery/broker、镜像和 Charts、
回调可达性及 V4 申请页面；当前 GitHub MCP 未连接，远端 CI 未核实。

### 最新提交及交付前同步回执

- `9951c5751`：架构对齐实现，正常 Ruff 通过；只跳过用户授权的 ruff-format。
- `7a9edad77`：单文件删除全局异常处理器新增分支，恢复 master 原文。
  正常尝试时 Ruff 自动改写该文件的基线类型/格式，且仍报两处 UP031；
  改写已撤回。经用户另行明确授权，仅此单文件提交额外跳过 Ruff。
  冲突、私钥、IP 和提交信息检查均正常通过，没有 --no-verify 或规则修改。
- `95c47bc94`：交付前再合入最新 master `4ffa88c7e`，无冲突、正常 hook。
  该上游增量仅包含两处前端变化；逐目录比对确认 IAM/配置/消费者与
  `7a9edad77` 相同。完整 PR 相对最新 master 仍无前端/原 V3 migrations/全局异常 diff。
- 上述实现、单文件恢复和两次 master 合并均实际验证 GPG Good signature。
  PreCI 包装返回成功，但提示未安装 PreCI 并跳过，不能描述为实际 PreCI 扫描通过。

提交后 Monitor 主回归 1025 passed、21 deselected，BKLog 634 tests/OK，
原生 MCP 808 passed（206.46 秒），均退出 0。最后纯前端 master 合并后，
Monitor 再次为 1025 passed（10.08 秒），Web/API/Worker 冷启动均退出 0。
MCP 的 808 项针对合并前的同一 IAM 代码，没有将重复运行数量相加。
2026-10-13 交付前再次读取 PR CI 仍返回 GitHub account 未连接，未确认远端 CI。
最终推送 head 与正式自测评论回读另记 TAPD；真实环境验收边界不变。
