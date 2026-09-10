/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type Ref, onBeforeUnmount, onMounted, shallowRef } from 'vue';

import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

/** 引用文本超出这个长度就截断，避免把整段日志灌进输入框 */
const MAX_CONTEXT_TEXT_LENGTH = 300;

const MENU_OFFSET_Y = 6;

/** 指针位移达到这个像素才算划选，用来排除单击已选文本 */
const MIN_DRAG_SIZE = 4;

/**
 * 语义单元：一段文本所属的最小完整对象。划选不完整时补全到这里，
 * 键值对和表格单元格能顺带把「这是什么」一起带出来。
 */
const UNIT_SELECTORS = ['.dimensions-item', '.item-col', 'td', 'th', '.alert-problem-content'];

/** 各类单元里键与值的取法 */
const UNIT_PAIR_RULES = [
  { unit: '.dimensions-item', label: '.name', value: '.content' },
  { unit: '.item-col', label: '.item-label', value: '.item-content' },
];

/** 词边界：没有语义单元时补到这些符号之间 */
const WORD_BOUNDARY_REG = /[\s,;|'"`(){}[\]，；、。：！？]/;

interface ISelectionMenuState {
  category: string;
  label: string;
  text: string;
  x: number;
  y: number;
}

const getElement = (node: Node | null): Element | null => {
  if (!node) return null;
  return node instanceof Element ? node : node.parentElement;
};

/**
 * 取当前选区。微前端下详情页挂在 shadow DOM 里，Chrome 的 document.getSelection() 拿不到
 * shadow 内的选区，需要优先问 ShadowRoot 要。
 */
const getActiveSelection = (container: HTMLElement): null | Selection => {
  const root = container.getRootNode() as Document | ShadowRoot;
  const shadowSelection = (root as ShadowRoot & { getSelection?: () => null | Selection }).getSelection?.();
  if (shadowSelection?.toString()) return shadowSelection;
  return window.getSelection();
};

const normalizeText = (text: null | string) => (text ?? '').replace(/\s+/g, ' ').trim();

const trimLabel = (text: null | string) => normalizeText(text).replace(/[:：=]$/, '').trim();

/** 这段文本落在哪个语义单元里 */
const resolveUnit = (node: Node | null, container: HTMLElement): Element | null => {
  const element = getElement(node);
  if (!element || !container.contains(element)) return null;
  for (const selector of UNIT_SELECTORS) {
    const unit = element.closest(selector);
    if (unit && container.contains(unit)) return unit;
  }
  return null;
};

/** 表格单元格的「对象」：优先同列表头，没有表头时用同行首列 */
const resolveCellLabel = (cell: Element): string => {
  const row = cell.parentElement;
  if (!row) return '';
  const index = Array.prototype.indexOf.call(row.children, cell);
  const headerCell = cell.closest('table')?.querySelector('thead tr')?.children?.[index];
  if (headerCell && headerCell !== cell) {
    const header = trimLabel(headerCell.textContent);
    if (header) return header;
  }
  const firstCell = row.children[0];
  return firstCell && firstCell !== cell ? trimLabel(firstCell.textContent) : '';
};

/** 从单元里读出键值对，读不出键值结构时返回 null */
const readUnitPair = (unit: Element): null | { label: string; text: string } => {
  for (const rule of UNIT_PAIR_RULES) {
    if (!unit.matches(rule.unit)) continue;
    const value = normalizeText(unit.querySelector(rule.value)?.textContent);
    if (value) return { label: trimLabel(unit.querySelector(rule.label)?.textContent), text: value };
  }
  if (unit.matches('td, th')) {
    const value = normalizeText(unit.textContent);
    if (value) return { label: resolveCellLabel(unit), text: value };
  }
  return null;
};

/** 兜底的「对象」：所在板块标题 */
const resolveSectionLabel = (node: Node | null): string => {
  const element = getElement(node);
  const section = element?.closest('.alert-problem, .dimension-info, .basic-info');
  return trimLabel(
    section?.querySelector('.block-title')?.textContent || section?.previousElementSibling?.textContent
  );
};

/**
 * 划词所在区域，用来把引用归类：上方信息区取板块标题（告警问题 / 维度信息 / 基础信息），
 * 下方内容区取当前激活的 tab 名（视图 / 日志 等）。
 */
const resolveCategory = (node: Node | null, container: HTMLElement): string => {
  const sectionLabel = resolveSectionLabel(node);
  if (sectionLabel) return sectionLabel;

  const element = getElement(node);
  if (element?.closest('.alarm-center-detail-alarm-alert')) return window.i18n.t('告警状态') as string;

  const activeTab = container.querySelector('.panel-tab .bk-tab-header--active');
  return trimLabel(activeTab?.textContent);
};

/** 起点补到词边界 */
const expandStartToWord = (range: Range) => {
  const { startContainer } = range;
  if (startContainer.nodeType !== Node.TEXT_NODE) return;
  const text = startContainer.textContent ?? '';
  let start = range.startOffset;
  while (start > 0 && !WORD_BOUNDARY_REG.test(text[start - 1])) start -= 1;
  range.setStart(startContainer, start);
};

/** 终点补到词边界 */
const expandEndToWord = (range: Range) => {
  const { endContainer } = range;
  if (endContainer.nodeType !== Node.TEXT_NODE) return;
  const text = endContainer.textContent ?? '';
  let end = range.endOffset;
  while (end < text.length && !WORD_BOUNDARY_REG.test(text[end])) end += 1;
  range.setEnd(endContainer, end);
};

/**
 * 把划选补全：两端各自补到所在语义单元的边界，没有单元时补到词边界。
 * 跨多个单元时按首尾两个单元各补一边，不会把用户已选的范围缩回去。
 */
const expandRange = (range: Range, container: HTMLElement) => {
  const startUnit = resolveUnit(range.startContainer, container);
  const endUnit = resolveUnit(range.endContainer, container);
  const expanded = range.cloneRange();

  if (startUnit) {
    const unitRange = range.cloneRange();
    unitRange.selectNodeContents(startUnit);
    expanded.setStart(unitRange.startContainer, unitRange.startOffset);
  } else {
    expandStartToWord(expanded);
  }

  if (endUnit) {
    const unitRange = range.cloneRange();
    unitRange.selectNodeContents(endUnit);
    expanded.setEnd(unitRange.endContainer, unitRange.endOffset);
  } else {
    expandEndToWord(expanded);
  }

  return { expanded, startUnit, endUnit };
};

/**
 * 左侧详情划词后弹出「添加至聊天」，点击把这段文本作为引用交给右侧 AI 会话输入框。
 */
export function useSelectionToChat(containerRef: Ref<HTMLElement | null>) {
  const store = useAlarmCenterDetailStore();
  const selectionMenu = shallowRef<ISelectionMenuState | null>(null);

  const hideSelectionMenu = () => {
    selectionMenu.value = null;
  };

  /**
   * 自己记录按下位置来判断划选，而不是复用 selection-decoder 的实现：
   * 那边的监听注册在 document 上，微前端沙箱会代理 document，拿不准能不能收到子应用里的事件。
   */
  let pointerDownPoint: null | { x: number; y: number } = null;

  const handlePointerdown = (event: PointerEvent) => {
    if (event.button !== 0) return;
    pointerDownPoint = { x: event.clientX, y: event.clientY };
  };

  /** 有位移的划选，或双击 / 三击产生的选区，才弹菜单 */
  const isSelectionTrigger = (event: MouseEvent) => {
    if (event.detail >= 2) return true;
    if (!pointerDownPoint) return false;
    return (
      Math.abs(event.clientX - pointerDownPoint.x) >= MIN_DRAG_SIZE ||
      Math.abs(event.clientY - pointerDownPoint.y) >= MIN_DRAG_SIZE
    );
  };

  const handleMouseup = (event: MouseEvent) => {
    const container = containerRef.value;
    if (!container) return;

    const selection = getActiveSelection(container);
    const text = selection?.toString() ?? '';
    if (!selection || !text.trim() || !selection.rangeCount) {
      hideSelectionMenu();
      return;
    }
    // 纯单击已选文本时选区仍在，靠这个判断只认划选与双击
    if (!isSelectionTrigger(event)) return;
    if (!container.contains(selection.anchorNode)) {
      hideSelectionMenu();
      return;
    }

    // 划得不完整就补全，并把补全后的范围回写，让用户看到实际取了哪一段
    const { expanded, startUnit, endUnit } = expandRange(selection.getRangeAt(0), container);
    selection.removeAllRanges();
    selection.addRange(expanded);

    // 落在同一个单元里时按键值对取，跨单元或无单元时整段带上
    const pair = startUnit && startUnit === endUnit ? readUnitPair(startUnit) : null;
    const resolved = pair ?? {
      label: resolveSectionLabel(expanded.startContainer),
      text: normalizeText(expanded.toString()),
    };
    if (!resolved.text) {
      hideSelectionMenu();
      return;
    }

    const rect = expanded.getBoundingClientRect();
    selectionMenu.value = {
      text: resolved.text.slice(0, MAX_CONTEXT_TEXT_LENGTH),
      label: resolved.label,
      category: resolveCategory(expanded.startContainer, container),
      x: rect.left + rect.width / 2,
      y: rect.bottom + MENU_OFFSET_Y,
    };
  };

  const handleAddToChat = () => {
    const menu = selectionMenu.value;
    if (!menu) return;
    store.addChatContext({ text: menu.text, label: menu.label, category: menu.category });
    if (containerRef.value) getActiveSelection(containerRef.value)?.removeAllRanges();
    hideSelectionMenu();
  };

  const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') hideSelectionMenu();
  };

  /** 容器所在根节点：微前端下是 shadow root，独立页是 document，容器内的事件必经此处 */
  let eventRoot: Document | ShadowRoot = document;

  onMounted(() => {
    eventRoot = (containerRef.value?.getRootNode() as Document | ShadowRoot) || document;
    eventRoot.addEventListener('pointerdown', handlePointerdown, true);
    eventRoot.addEventListener('mouseup', handleMouseup);
    eventRoot.addEventListener('keydown', handleKeydown);
    eventRoot.addEventListener('scroll', hideSelectionMenu, true);
  });

  onBeforeUnmount(() => {
    eventRoot.removeEventListener('pointerdown', handlePointerdown, true);
    eventRoot.removeEventListener('mouseup', handleMouseup);
    eventRoot.removeEventListener('keydown', handleKeydown);
    eventRoot.removeEventListener('scroll', hideSelectionMenu, true);
  });

  return {
    selectionMenu,
    handleAddToChat,
    hideSelectionMenu,
  };
}
