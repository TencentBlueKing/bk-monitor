# 折叠管理导航与 ES 空态契约（局部通过）

## 来源和场景

V2 `views/manage/index.vue` 的菜单过滤、getRouteHref、handleClickNavItem；`views/manage-v2/es-cluster/cluster-manage/index.tsx` 的 getTableData、checkCreateAuth 与 empty 插槽；`components/empty-status/index.vue` 的全部展示和操作条件；当前 V2 安装包 bk-magic-vue 2.5.10-beta.15 的 Navigation/Table/Exception 实际实现。

本段具体业务环境与运行记录已移至仓库外本地归档；复验须提供本地授权测试上下文。

固定响应私有目录 bklog-v2-management-CevhCe；V2 自重放报告 runs/pilot/management-self-replay-1794390273596.json。V3 六检查点通过，对照报告按 captureDigest=b1a95e1782dbfbf219dd632fc749bc533fe53abe00f5895cb62837abcb5bcdb3 查找。

## 修复

- TMenuItem 折叠时返回 Tooltip 包装，data-test-id 未落到实际 DOM。标识放到自主 a 链接，路由和修饰键点击处理不变。
- TDesign 默认隐藏折叠分组标题并改为分隔线。按 V2 恢复 keyword、顶部12px、标题40/48px、菜单行40px+上下各2px。
- EmptyStatus 曾移除 Exception 图片，仅留文字。恢复7种原图，SVG payload 从 V2 包原字节提取，记录来源摘要及 License；生产源码不导入原组件库。
- 改为 Vue3 script setup、TDesign Empty、显式 SourceTranslation、类型化 operation。保留原文字映射、scene、showText、默认插槽覆盖、clear-filter 与 refresh。showOperation 在 V2 未参与条件，保留该行为。
- TDesign Empty 将 description 插槽结果放入 computed，默认插槽存在性变化不是其响应式依赖。按 slot presence 调整无状态 Empty 的 key，避免保留旧说明；独立用例覆盖无→有→恢复。
- ES 空态保留源 Table 的60px padding、43px表头；源 BkTable 仅在 data非空且count>0 时显示分页，原生 Table 显式保留该条件。

## 工具修正，不作为产品缺陷

- V2 图标是 span；使用两边真实图标节点点击链接。
- t-table__empty-row 是框架占位，不算业务行。只排除已核实类名，另要求图片真实加载、文字匹配。
- 导航点击后移出悬浮区，等待真实收起及动画稳定，避免把悬浮菜单覆盖误判为丢失列或按钮。
- 命名回退忽略 display:none、visibility:hidden、aria-hidden 后代，保留显式 ARIA 标签。浏览器15项隔离校准通过；该算法不是完整 AX 树，不宣称无障碍全量验收。

## 边界

非空集群、连接状态、ES/Doris切换、配置及写入、权限拒绝、非空分页排序筛选、展开/固定/返回/修饰键导航、其他管理模块、全屏视觉和响应式布局仍待验证。共享空态变更需要回归已验收模块，本报告不表示全业务通过。
