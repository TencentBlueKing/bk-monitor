---
name: log-search-overlay
description: 日志检索弹出统一管理。新增或修改 popover、tippy、bk-dialog、划词层、收藏/聚类浮层时必须走 Overlay Registry，禁止业务裸 tippy()、自管 visible 或写死 z-index。Use when the task mentions overlay, popover, tippy, BklogPopover, Dialog, 弹出, 浮层, 左上角, 关后再打不开, click-outside, or retrieve-v2/v3 popup lifecycle.
---

# 日志检索弹出统一管理

检索页浮层必须走 `src/global/overlay/`，不要再各自 `new tippy()` / 自管 `visible` / 写死 `99999`。

代码入口：`src/global/overlay/index.ts`  
单测：`src/global/overlay/overlay-registry.test.cjs`

实现示例见 [examples.md](examples.md)。

## 何时加载

任务涉及以下任一情况时，先读本技能再改代码：

- 检索页 popover / menu / dialog / sideslider
- `tippy()`、`PopInstanceUtil`、`BklogPopover`、`bk-dialog`
- 浮层飞到左上角、关后再打不开、点内层误关外层
- 锚点卸载、输入框收成 tag、虚拟列表滚动后层还在

## 选型（只选一条）

| 场景 | API | 禁止 |
| --- | --- | --- |
| Vue 模板点击/悬停层 | `BklogPopover`（已接 Registry） | 业务里再包一层 tippy |
| 已有 `PopInstanceUtil` | `createOverlayTippy` | `new PopInstanceUtil` |
| 检索目录仍直接 `tippy()` | `createRawTippyOverlay` | `import tippy from 'tippy.js'` 后裸调用 |
| `bk-dialog` / 确认框 | `useDialogVisible` | 只绑 `:value` / `:visible`，不接 `on-value-change` |
| 自定义层、只需登记 | `useOverlay` | 自己维护 stack / z-index |

`import { createOverlayTippy, createRawTippyOverlay, useDialogVisible, useOverlay } from '@/global/overlay'`

## 八条契约

业务实现必须满足这些规则，而不是各自 new tippy / 自管 visible。

| ID | 规则 | 做法 |
| --- | --- | --- |
| R1 | 打开前登记 | `register(id, { type, group, parentId, anchor })`；适配器会代登记 |
| R2 | 关栈 | 关外层先关 children；同 `group` 互斥；父子同组时不关祖先 |
| R3 | 锚点丢失先 hide | 锚点 unmount / 宽高为 0 / 输入框收成 tag：**先 hide 再改 DOM** |
| R4 | 点外用 closest | `closest(rootSelector \| ignoreSelector)`，禁止 `classList.contains` |
| R5 | Dialog 双向 visible | Esc / 遮罩 / 右上角关闭必须 `onValueChange(false)`，再 `setVisible(true)` 才是有效打开 |
| R6 | 定位 | `appendTo: body` + `strategy: 'fixed'`；无效矩形返回 `null`，不准把 `(0,0)` 交给 popper |
| R7 | 层级 | 只从 `__bk_zIndex_manager` 或 Registry `nextZIndex()` 取；禁止 `99999` / `100000` |
| R8 | 销毁 | `onUnmounted` 必须 `dispose` / `destroy`，不能只 `hide` |

## 必填字段

```ts
{
  id: string;                 // 稳定可读，如 retrieve-context-log-dialog
  type?: 'popover' | 'dialog' | 'slider' | 'menu';
  group?: string;             // 同组互斥
  parentId?: string;          // 嵌套层；关父先关子
  rootSelector?: string;      // 点外判定的层根
  ignoreSelector?: string;    // 点这里不关外层，如 .bklog-popover-stop
}
```

锚点将消失或尺寸变 0 时调用：

```ts
overlayTippy.notifyAnchorLost();
// 或 overlayRegistry.notifyAnchorLost(id)
```

## 已接入调用点（改这些时保持契约）

| 能力 | 文件 |
| --- | --- |
| 搜索栏 UI 联想 | `src/views/retrieve-v2/search-bar/utils/use-focus-input.ts` |
| 快捷键加条件先 hide | `src/views/retrieve-v2/search-bar/ui-mode/ui-input.vue` |
| 划词 | `src/views/retrieve-v2/search-result-panel/log-result/log-rows.tsx` |
| 划词实例 | `src/global/utils/segment-pop-instance.ts` |
| 收藏删除 Dialog | `src/views/retrieve-v3/favorite/components/collect-list/collect-list.tsx` |
| 批量菜单内 Dialog | `src/views/retrieve-v2/collect/batch-operation-menu.vue` |
| 收藏管理 Dialog | `src/views/retrieve-v2/collect/favorite-manage-dialog.vue` |
| 上下文 / 实时日志 | `src/views/retrieve-v3/search-result/original-log/context-log/index.tsx`、`real-time-log/index.tsx` |
| 聚类 popover / 正则 | `.../cluster-popover/index.tsx`、`regex-match/index.tsx`、`content-table/index.tsx` |
| 字段过滤 | `.../original-log/components/data-filter/index.tsx` |
| 模板编辑删除 | `.../template-item/index.tsx` |
| 通用封装 | `src/components/bklog-popover/index.tsx` |

## 禁止

- 检索目录新增裸 `tippy()` 或 `new PopInstanceUtil`
- 业务写死 `z-index: 99999` / `100000` 盖住上一层
- `bk-dialog` 只写 `:value="show"`，不绑 `@value-change` / `on-value-change`
- 点外用 `event.target.classList.contains`
- 输入框替换成 tag / 锚点卸载之后再 hide
- 无效矩形仍把 `{ top:0, left:0, width:0, height:0 }` 交给 popper
- 把管理页筛选、收藏列表状态机、URL 索引集同步塞进 Overlay

## 改动检查清单

- [ ] 选了上表中的适配器，而不是裸 tippy
- [ ] 有稳定 `id`；嵌套层有 `parentId`；互斥层有 `group`
- [ ] 点外走 `rootSelector` / `ignoreSelector` + `closest`
- [ ] Dialog 使用 `visible` + `setVisible` + `onValueChange`
- [ ] 锚点会变时，先 `notifyAnchorLost`
- [ ] 卸载路径调用 `dispose` / `destroy` / `uninstall`
- [ ] 无写死 z-index
- [ ] 跑 `node --test src/global/overlay/overlay-registry.test.cjs`

## 回归（相关页面至少覆盖触及的路径）

1. 收藏删除：Esc / 遮罩 / 取消后再点，必须能打开
2. 移动至分组：关外层后子菜单不得留在左上角
3. UI 快捷键加条件：联想先 hide，再把输入框收成 tag
4. 分级展示：点字段下拉不关外层
5. 划词：滚动跟手；Monitor 宿主不飞 (0,0)
6. 上下文 / 实时 / 收藏管理 / 正则 Dialog：关后再开
7. 组件卸载后面层消失，无残留 tippy
