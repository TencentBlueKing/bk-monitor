# V2基准重建执行目录

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
