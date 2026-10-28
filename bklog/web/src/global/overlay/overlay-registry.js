/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

'use strict';

const FALLBACK_ZINDEX_START = 2000;

/**
 * 检索页弹出统一契约。业务实现必须满足这些规则，而不是各自 new tippy / 自管 visible。
 */
const OVERLAY_RULES = Object.freeze({
  R1_REGISTER: 'open 前必须 register(id, { type, group, parentId, anchor })',
  R2_STACK: '关外层必须先关 children；同 group 互斥，同时只开一个',
  R3_ANCHOR: '锚点 unmount / 尺寸变 0 / 输入框被替换成 tag 时，先 hide 再改 DOM',
  R4_OUTSIDE: 'click-outside 一律 closest(rootSelector | ignoreSelector)，禁止 classList.contains',
  R5_VISIBLE: 'Dialog / Slider 的 visible 必须双向：内部 Esc / 遮罩 / 关闭回写父状态',
  R6_POSITION: "appendTo body + strategy: 'fixed'；矩形无效时不准把 (0,0) 交给 popper",
  R7_ZINDEX: '只从 __bk_zIndex_manager 或 Registry 取下一层，禁止业务写死 99999 / 100000',
  R8_DISPOSE: '组件 onUnmounted 必须 dispose，不能只 hide',
});

const createRecord = (id, options = {}) => ({
  id,
  type: options.type || 'popover',
  group: options.group,
  parentId: options.parentId,
  anchor: options.anchor ?? null,
  rootSelector: options.rootSelector,
  ignoreSelector: options.ignoreSelector,
  hide: options.hide,
  zIndex: 0,
  visible: false,
  children: new Set(),
});

const assignRecord = (record, options = {}) => {
  if (options.type) record.type = options.type;
  if (options.group !== undefined) record.group = options.group;
  if (options.parentId !== undefined) record.parentId = options.parentId;
  if (options.anchor !== undefined) record.anchor = options.anchor;
  if (options.rootSelector !== undefined) record.rootSelector = options.rootSelector;
  if (options.ignoreSelector !== undefined) record.ignoreSelector = options.ignoreSelector;
  if (typeof options.hide === 'function') record.hide = options.hide;
  return record;
};

const isEscapeEvent = event => {
  return event?.key === 'Escape' || event?.key === 'Esc' || event?.keyCode === 27;
};

const stopEscapeEvent = event => {
  event?.preventDefault?.();
  event?.stopPropagation?.();
  event?.stopImmediatePropagation?.();
};

const installEscapeListener = registry => {
  if (typeof document === 'undefined' || registry.escapeBound) {
    return;
  }

  const handler = event => {
    registry.handleEscape(event);
  };

  document.addEventListener('keydown', handler, true);
  document.addEventListener('keyup', handler, true);
  registry.escapeBound = true;
  registry.escapeHandler = handler;
};

const isClickInsideClosest = (event, selectors = []) => {
  const target = event?.target;
  if (!target || typeof target.closest !== 'function') {
    return false;
  }

  return selectors.filter(Boolean).some(selector => Boolean(target.closest(selector)));
};

const shouldHideOnOutsideClick = (event, { rootSelector, ignoreSelector } = {}) => {
  return !isClickInsideClosest(event, [rootSelector, ignoreSelector]);
};

const isValidAnchorRect = rect => {
  if (!rect) {
    return false;
  }

  const width = Number(rect.width) || 0;
  const height = Number(rect.height) || 0;
  return width > 0 && height > 0;
};

const resolvePopperPlacementRect = rect => {
  if (!isValidAnchorRect(rect)) {
    return null;
  }

  return rect;
};

/**
 * bk-dialog 单向 value 的纯状态机：内部 Esc / 遮罩关闭必须回写成 false，
 * 否则父级再次赋 true 不会触发打开。
 */
const createDialogVisibleState = (initial = false, hooks = {}) => {
  let visible = Boolean(initial);

  const apply = next => {
    const value = Boolean(next);
    if (visible === value) {
      return visible;
    }

    visible = value;
    if (value) {
      hooks.onOpen?.();
    } else {
      hooks.onHide?.();
    }

    return visible;
  };

  return {
    getVisible: () => visible,
    setVisible: apply,
    onValueChange: apply,
  };
};

class OverlayRegistry {
  constructor() {
    this.reset();
  }

  reset() {
    this.records = new Map();
    this.stack = [];
    this.hiding = new Set();
    this.fallbackZIndex = FALLBACK_ZINDEX_START;
    this.escapeConsumed = false;
  }

  nextZIndex() {
    const manager = (typeof globalThis !== 'undefined' ? globalThis.window : undefined)?.__bk_zIndex_manager;
    if (manager && typeof manager.nextZIndex === 'function') {
      return manager.nextZIndex();
    }

    this.fallbackZIndex += 1;
    return this.fallbackZIndex;
  }

  get(id) {
    return this.records.get(id) ?? null;
  }

  isOpen(id) {
    return Boolean(this.get(id)?.visible);
  }

  getStack() {
    return [...this.stack];
  }

  collectAncestors(id) {
    const ids = [];
    let current = this.get(id);
    while (current?.parentId) {
      ids.push(current.parentId);
      current = this.get(current.parentId);
    }
    return ids;
  }

  linkParent(id, parentId) {
    if (!parentId) {
      return;
    }

    const parent = this.get(parentId);
    parent?.children.add(id);
  }

  unlinkParent(id, parentId) {
    if (!parentId) {
      return;
    }

    this.get(parentId)?.children.delete(id);
  }

  register(id, options = {}) {
    if (!id) {
      throw new Error('[overlay-registry] id is required');
    }

    const current = this.get(id);
    if (current) {
      const previousParentId = current.parentId;
      assignRecord(current, options);
      if (previousParentId !== current.parentId) {
        this.unlinkParent(id, previousParentId);
        this.linkParent(id, current.parentId);
      }
      return current;
    }

    const record = createRecord(id, options);
    this.records.set(id, record);
    this.linkParent(id, record.parentId);
    return record;
  }

  open(id, extra = {}) {
    const record = this.get(id) || this.register(id, extra);
    const previousParentId = record.parentId;
    assignRecord(record, extra);
    if (previousParentId !== record.parentId) {
      this.unlinkParent(id, previousParentId);
      this.linkParent(id, record.parentId);
    }

    if (record.group) {
      this.hideGroup(record.group, id);
    }

    record.zIndex = this.nextZIndex();
    record.visible = true;
    if (!this.stack.includes(id)) {
      this.stack.push(id);
    }

    extra.onOpen?.(record);
    return record;
  }

  hideChildren(id) {
    const record = this.get(id);
    if (!record) {
      return;
    }

    [...record.children].forEach(childId => {
      this.hide(childId);
    });
  }

  hide(id) {
    const record = this.get(id);
    if (!record || this.hiding.has(id)) {
      return;
    }

    this.hiding.add(id);
    try {
      this.hideChildren(id);
      const wasVisible = record.visible;
      record.visible = false;
      this.stack = this.stack.filter(itemId => itemId !== id);
      if (wasVisible) {
        record.hide?.();
      }
    } finally {
      this.hiding.delete(id);
    }
  }

  hideTop() {
    const topId = this.stack[this.stack.length - 1];
    if (!topId) {
      return false;
    }

    this.hide(topId);
    return true;
  }

  handleEscape(event) {
    if (!isEscapeEvent(event)) {
      return false;
    }

    if (event?.type === 'keyup' && this.escapeConsumed) {
      this.escapeConsumed = false;
      stopEscapeEvent(event);
      return true;
    }

    if (this.stack.length <= 1) {
      return false;
    }

    this.hideTop();
    this.escapeConsumed = true;
    stopEscapeEvent(event);
    return true;
  }

  hideGroup(group, exceptId) {
    if (!group) {
      return;
    }

    const protectedIds = new Set([exceptId, ...this.collectAncestors(exceptId)]);
    [...this.records.values()].forEach(record => {
      if (record.group === group && record.visible && !protectedIds.has(record.id)) {
        this.hide(record.id);
      }
    });
  }

  notifyAnchorLost(id) {
    this.hide(id);
  }

  findParentIdByElement(el) {
    if (!el || typeof el.closest !== 'function') {
      return null;
    }

    const records = [...this.records.values()];
    for (let index = records.length - 1; index >= 0; index -= 1) {
      const record = records[index];
      if (!record.visible || !record.rootSelector) {
        continue;
      }

      try {
        if (el.closest(record.rootSelector)) {
          return record.id;
        }
      } catch {
        // invalid selector should not break open()
      }
    }

    return null;
  }

  isClickInsideRecord(event, id) {
    const record = this.get(id);
    if (!record) {
      return false;
    }

    if (isClickInsideClosest(event, [record.rootSelector, record.ignoreSelector])) {
      return true;
    }

    return [...record.children].some(childId => this.isClickInsideRecord(event, childId));
  }

  dispose(id) {
    const record = this.get(id);
    this.hide(id);
    if (!record) {
      return;
    }

    this.unlinkParent(id, record.parentId);
    this.records.delete(id);
  }
}

const overlayRegistry = new OverlayRegistry();
installEscapeListener(overlayRegistry);

/**
 * 给检索目录里仍直接 tippy() 的调用点提供统一生命周期。
 * 业务继续拿 tippy instance 调 show/hide/destroy，Registry 负责关栈、锚点丢失和 z-index。
 */
const createRawTippyLifecycle = (id, options = {}, registry = overlayRegistry) => {
  if (!id) {
    throw new Error('[overlay-registry] id is required');
  }

  let instance = null;

  const hideInstance = () => {
    if (Array.isArray(instance)) {
      instance.forEach(item => item?.hide?.());
      return;
    }
    instance?.hide?.();
  };

  registry.register(id, {
    ...options,
    type: options.type || 'popover',
    hide: hideInstance,
  });

  return {
    setInstance(next) {
      instance = next;
    },
    nextZIndex: () => registry.nextZIndex(),
    onShow(reference) {
      const rect = reference?.getBoundingClientRect?.();
      if (rect && !isValidAnchorRect(rect)) {
        hideInstance();
        registry.notifyAnchorLost(id);
        return false;
      }
      const parentId = options.parentId || registry.findParentIdByElement(reference);
      registry.open(id, {
        anchor: reference ?? null,
        parentId: parentId || undefined,
      });
      return true;
    },
    onHidden() {
      registry.hide(id);
    },
    onDestroy() {
      registry.dispose(id);
    },
  };
};

export {
  FALLBACK_ZINDEX_START,
  OVERLAY_RULES,
  OverlayRegistry,
  overlayRegistry,
  isClickInsideClosest,
  isEscapeEvent,
  shouldHideOnOutsideClick,
  isValidAnchorRect,
  resolvePopperPlacementRect,
  createDialogVisibleState,
  createRawTippyLifecycle,
};
