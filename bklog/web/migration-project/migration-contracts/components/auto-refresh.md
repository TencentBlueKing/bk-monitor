# AUTO-REFRESH：组件契约与首轮验证

日期：2026-10-28。状态：行为试验通过；UI 尚待图标与整条工具栏合并复核，不标整体 ACCEPTED。

## 输入与源码链

Vue2 检索路由 → retrieve-hub → retrieve-v3/index → toolbar → retrieve-v2/sub-bar/index.vue → auto-refresh-new.tsx/.scss。

组件内部持有当前周期（默认 off），不接受来自页面的持久化周期。选项为关闭(off)、10s、30s、1m、5m、15m、30m、1h、2h、1d。点击选择立即关弹层、更新周期并重新计时，不立即查询。每次到期更新查询时间并触发 AUTO_REFRESH；关闭或卸载清除定时器。旧版用 store 与事件总线传递，目标通过 refresh emit 通知页面，由页面 search 计算时间并查询。

目标：`packages/web-v3/src/components/RetrieveAutoRefresh.vue`；定时逻辑 `src/features/auto-refresh.mjs`。已从 RetrievePage 移除临时 select 与原有计时器，实际页面已接入组件。

## 逐项场景

- AR-01 默认 off，无周期查询：自动测试验证。
- AR-02 打开菜单，十项顺序/文案与旧版一致：8001/4173 同索引 40676，浏览器核对。
- AR-03 菜单宽80px、内容高174px、32px选项行高、滚动、悬停色：已按源 SCSS 实现，1440×900截图保留；尚未进行像素差异自动验收。
- AR-04 选择10s，触发器显示10s，aria-expanded=false：浏览器通过。
- AR-05 十秒后触发真实查询：浏览器开启后记录用时405毫秒，等待12秒后变为477毫秒，结果仍为0；回到off，最近控制台error为空。此证据证明一次刷新，长期运行及后台窗口节流未测。
- AR-06 切换30s清除旧10s定时：mock timers自动测试通过。
- AR-07 off清除定时、卸载清除定时、销毁后不能重新启动：自动测试通过。
- AR-08 刷新回调内卸载，不会重新产生定时器：自动测试通过。
- AR-09 外部关闭、键盘焦点、快速重复点选及接口失败恢复：待专项浏览器验证。当前事件发射与定时独立，不等待请求完成，按旧版节奏运行。

## 视觉残差与范围边界

触发图标暂用文本 ↻，未复用旧 iconcool 字形，不能声称像素级还原。整条工具栏的布局仍是旧原型，单组件无法证明页面整体还原；UI验收保持待复核。源码还存在监控嵌入编译分支隐藏自动刷新，待嵌入模式初始化模块统一处理。

截图位于 `artifacts/screenshots/auto-refresh/v2-open.png`、`v3-open.png`，同1440×900视口截取顶部340px。40676在本次旧版也无数据，不能拿空态差异当成接口迁移失败，也不能用空数据证明所有查询业务通过。

命令：`pnpm --dir bklog/web/packages/web-v3 --ignore-workspace test`（23通过）；相同目录参数 build（通过）；执行位置仓库根目录。没有提交、推送或改动V2实现。

下一小模块按计划分析完整历史查询（含收藏及场景/联合协议），不是继续给巨型 RetrievePage 添加临时按钮。
