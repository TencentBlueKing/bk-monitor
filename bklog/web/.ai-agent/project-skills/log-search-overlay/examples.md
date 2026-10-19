# Overlay 接入示例

从已落地调用点摘出的最小写法。路径相对 `bklog/web/`。

## 1. 裸 tippy → `createRawTippyOverlay`

原：`popoverInstance = tippy(el, { ... })`  
现：`cluster-popover/index.tsx`

```ts
import { createRawTippyOverlay } from '@/global/overlay';

popoverInstance = createRawTippyOverlay(
  e.target as Element,
  {
    content: eventTippyRef.value,
    arrow: true,
    trigger: 'click',
    theme: 'light',
    placement: 'bottom',
    interactive: true,
    allowHTML: true,
    onShow: handlePopoverShow,
    onHidden: handlePopoverHide,
  },
  {
    id: patternMenuId,
    type: 'menu',
    group: 'cluster-pattern-menu',
    rootSelector: '.pattern-event-tippy',
  },
);
popoverInstance.show(500);
```

返回值仍是 tippy instance，可继续 `show` / `hide` / `destroy`。无效锚点会先 hide 再 `notifyAnchorLost`。

## 2. `PopInstanceUtil` → `createOverlayTippy`

现：`search-bar/utils/use-focus-input.ts`

```ts
import { createOverlayTippy } from '@/global/overlay';

const overlayTippy = createOverlayTippy({
  id: `retrieve-search-suggest-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  group: 'retrieve-search-suggest',
  tippy: { refContent, onShowFn, onHiddenFn, arrow, newInstance, tippyOptions },
});

const popInstanceUtil = overlayTippy.instance;

// 输入框即将收成 tag / 锚点卸载之前：
overlayTippy.notifyAnchorLost();

// 卸载：
overlayTippy.uninstall();
```

`ui-input.vue` 在快捷键加条件、提交前先调 `hideTippyInstanceImmediate()`（内部即 `notifyAnchorLost`）。

## 3. Dialog → `useDialogVisible`

现：`original-log/context-log/index.tsx`

```ts
import { useDialogVisible } from '@/global/overlay';

const { visible, setVisible, onValueChange } = useDialogVisible(false, {
  id: 'retrieve-context-log-dialog',
  type: 'dialog',
  group: 'retrieve-related-log',
});

// 父级 props 打开
setVisible(true);

return () => (
  <bk-dialog
    value={visible.value}
    on-value-change={onValueChange}
    on-after-leave={handleAfterLeave}
  />
);
```

Vue SFC 同样：`:value` + `@value-change="onValueChange"`，打开走 `setVisible(true)`。见 `favorite-manage-dialog.vue`。

## 4. 嵌套层

外层登记 `id`，内层传 `parentId`。关外层会先 `hideChildren`。

同组互斥用同一个 `group`。父子同组时，开子不会把祖先关掉。

点内层控件不关外层：外层设 `ignoreSelector: '.bklog-popover-stop'`，内层根节点加上该类名。点外判定一律 `closest`，不要 `classList.contains`。

## 5. 划词 / 虚拟列表

`log-rows.tsx` + `segment-pop-instance.ts`：滚动只 `update`；锚点矩形无效时 `notifyAnchorLost`，不要把 `(0,0)` 交给 popper。Monitor / Trace 宿主保持 `appendTo: body` + `fixed`。
