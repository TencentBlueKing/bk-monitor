# V2基准重建执行目录

最新审查：[迁移对齐丢失根因与方案修订](reports/alignment-audit-20261112/迁移对齐丢失根因与方案修订.md)。以日志聚类追溯旧名适配的插槽、实例方法、表单与关闭契约缺口；跨模块 104 处候选仍需按真实路由验证。本批只分析，未修复业务。

后续实施：[实施记录 01：Pinia 采集、全局域与聚类交互](reports/alignment-audit-20261112/实施记录-01-Pinia采集全局域与聚类交互.md)。历史审查保持不变；新记录单独说明代码、验证、截图与剩余差异，当前尚未完成两个方案的全部实施。

历史实施：[实施记录 02：检索域原生 Pinia 与聚类切换](reports/alignment-audit-20261112/实施记录-02-检索域原生Pinia与聚类切换.md)。检索域及调用方迁移、模式确认细节修复；补充两版共有列宽行为的核对结论。根状态和旧调用清理仍未完成。

历史实施：[实施记录 03：根状态原生 Pinia 与 Monitor、聚类验证](reports/alignment-audit-20261112/实施记录-03-根状态原生Pinia与Monitor聚类验证.md)。完成根状态拥有者及内部调用清理，保留独立 Monitor 发布边界；聚类筛选、解绑确认继续对齐。全量测试 364/388、严格类型仍有 1574 条错误，整体验收尚未通过。证据和可重复状态审计见本批记录。

历史实施：[实施记录 04：图表交互与采集、管理样式](reports/alignment-audit-20261112/实施记录-04-图表交互与采集管理样式.md)。修复采集步骤圆点/连线、管理导航滚动条、采集空白滚动、实时/上下文拖拽条及图表状态与选择控件；402 项测试中 395 通过，严格类型仍有 1567 条错误。局部证据及重复验证步骤见本批记录，整体验收仍未通过。

历史实施：[实施记录 05：聚类策略菜单与批量别名入口](reports/alignment-audit-20261112/实施记录-05-聚类策略菜单与别名入口.md)。修复弹层 Teleport 样式丢失和懒加载事件接收者缺失，保留原业务操作；局部尺寸及首次入口浏览器证据见本批记录。

历史实施：[实施记录 06：采集搜索首次聚焦](reports/alignment-audit-20261112/实施记录-06-采集搜索首次聚焦.md)。修复 focus/click 弹层竞态、边缘点击、光标前缀位置和失焦样式；两版首击及真实采集名查询已验证。

历史实施：[实施记录 07：标签过滤样式与外部关闭](reports/alignment-audit-20261112/实施记录-07-标签过滤样式与外部关闭.md)。对齐搜索区、列表和按钮；补回受控 Popup 关闭回写，验证外部关闭恢复草稿及两版筛选结果一致。

历史实施：[实施记录 08：场景化检索布局与空态](reports/alignment-audit-20261112/实施记录-08-场景化检索布局与空态.md)。修复原生下拉定位、标签提示/边框及空态图片排版；截图和运行数据仅保存在仓库外的本地归档。

最新实施：[实施记录 09：场景联想 loading 滚动闪动](reports/alignment-audit-20261112/实施记录-09-场景联想Loading滚动闪动.md)。复现 1px 动画溢出并局部裁剪，持续 loading 与长列表滚动已验证；证据和临时复现源码仅保存在仓库外。

后续开发的快速入口：[回归使用指南](回归使用指南.md)。基准清单位于 `baselines/ui-alignment/2026-11-12-r1/manifest.json`，支持证据校验、按改动文件选组和 63 条去重快速回归；尚未完成的真实业务与视觉验收不会自动标为通过。

```sh
# 从 bklog/web 执行
node analyze-info/harness/run-regression-baseline.mjs --all
```

这是2026-11-11按用户已评审方案重新建立的分析工程。旧344个结果文件已清除，仅保留两份原始export输入。没有导入旧PASS/FAIL、覆盖率、Mock或问题清单。

## 当前材料

- `source/source-manifest.json`：冻结的源码/配置摘要和既有差异记录。
- `runs/p0/discard-manifest.json`：已清理文件与保留输入摘要。
- `source/entry-graph.json`、`routes.json`、`capability-candidates.json`：AST发现，全部仍为候选，不能当作业务覆盖。
- `spec/execution-state.json`：阶段状态；baselineAccepted和v3Accepted保持false。
- `harness/verify-calibration.mjs`：要求指定用例实际通过，空测试文件/退出码0不足以过关。
- `harness/run-browser-calibration.mjs`：隔离页面校准，不能替代真实V2/V3验收。

## 执行命令

从bklog/web执行：

```sh
node analyze-info/harness/source-inventory.mjs
node analyze-info/harness/verify-calibration.mjs
node analyze-info/harness/run-browser-calibration.mjs
```

浏览器访问只使用appdev.woa.com和实际监听端口。登录失败停止依赖真实页面的采集，等待用户本地更新.cookie。业务写入按端点语义阻止，不返回伪造成功响应。

源码图保留不能静态解析的入口和旧语法警告。源摘要、数据或工具变化后，应重建相关证据，不修改旧结果为通过。
