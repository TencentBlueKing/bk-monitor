# 原始日志固定时间列迁移修复

日期：2026-10-29。

## 定位

V2 `src/views/retrieve-v2/search-result-panel/log-result/log-rows.tsx` 的 `originalColumns` 使用 Vue2 `h('span', { attrs, domProps })` 展示时间。V3 迁移后导入 Vue3 `h`，但保留了这段参数结构：浏览器将 `domProps` 渲染成 `[object Object]` 属性，时间文本为空，`data-field-name` 也未落到元素上。

当前问题发生在渲染层，时间值仍存在于日志行中。本次未修改请求协议、返回数据、字段过滤或缓存逻辑。

## 修复

将时间列的 `data-field-name`、`innerHTML` 改为 Vue3 平铺 props。保留原时区格式化、纳秒精度、格式化开关、mark 解析、高亮生成、HTML 转义和空值回退。

## 验证

- 真实只读页面 `/retrieve/40678?spaceUid=bkcc__5000140&bizId=5000140`：50 个已加载时间单元格全部有文本及真实字段名属性，空单元格和缺失属性均为 0。
- 新增 `tests/original-log-time-cell.test.mjs`：从真实组件 AST 读取列渲染函数，用 Vue3 SSR 验证最终文本及 DOM 属性，与冻结 V2 参数语义对照。覆盖纳秒、时区调用、高亮、原始值 0、null/undefined/空串及 HTML 转义。
- 全部 157 项测试通过，AI 来源与依赖检查通过；主应用、APM、Trace 构建与 Monitor 产物校验通过，两个本地 Monitor 交付目录已同步，未发布。
- 截图仅保留固定列区域，不保存真实日志正文：[修复截图](../evidence/20261029-original-log-time/fixed-time-column.png)。

未对已有业务数据进行编辑或删除。本批验证结论只覆盖本次时间列缺失问题，不替代其他检索场景的全量验收。
