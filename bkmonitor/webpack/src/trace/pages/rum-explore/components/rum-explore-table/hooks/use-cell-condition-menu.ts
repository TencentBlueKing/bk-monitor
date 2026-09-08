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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */
import { type Ref, nextTick, onBeforeUnmount, onMounted, reactive } from 'vue';
import type { MaybeRef } from 'vue';

import { get } from '@vueuse/core';

import { useTablePopover } from '../../../../../hooks/use-table-popover';
import { isEllipsisActiveSingleLine } from '../../../../../utils/dom-helper';
import { ENABLED_TABLE_CONDITION_MENU_CLASS_NAME } from '../../../../trace-explore/components/trace-explore-table/constants';
import { useExploreDataCache } from '../../../../trace-explore/components/trace-explore-table/hooks/use-explore-data-cache';

import type { ActiveConditionMenuTarget } from '../../../../trace-explore/components/trace-explore-table/typing';

/**
 * CLICK 类型列的文本节点选择器。
 *
 * RUM 的 span_name 等列左键已用于「点击直接加为检索条件」，与 trace 的 CLICK 列（打开详情抽屉）一样不参与左键菜单，
 * 这里改用右键唤起同一个条件菜单，从而同时保留两种入口。
 */
const CLICK_CELL_TEXT_SELECTOR = '.explore-click-text';

export interface UseCellConditionMenuOptions {
  /** 事件委托根节点：CommonTable 组件实例（内部取 $el）或原生 DOM */
  delegationRoot: DelegationRoot;
  /** 条件菜单组件实例 ref，其 $el 作为 popover 内容 */
  menuRef: ConditionMenuRef;
  /** 表格行唯一键字段名 */
  rowKey: MaybeRef<string>;
}

/** 条件菜单组件实例 ref，其 $el 作为 popover 内容 */
type ConditionMenuRef = Ref<null | { $el: HTMLElement }>;

/** 事件委托根节点：组件实例（内部取 $el）或原生 DOM */
type DelegationRoot = MaybeRef<HTMLElement | null | { $el: HTMLElement }>;

/**
 * @description RUM 检索表格单元格「点击弹出检索条件菜单」。
 * 交互与 trace 检索保持一致：带 explore-table-condition-menu 标记的单元格左键点击弹出菜单，
 * CLICK 类型列左键被「直接加为检索条件」占用，改由右键弹出同一个菜单。
 * @param {UseCellConditionMenuOptions} options 配置
 */
export const useCellConditionMenu = ({ delegationRoot, menuRef, rowKey }: UseCellConditionMenuOptions) => {
  /** 当前激活的条件菜单目标 */
  const activeConditionMenuTarget = reactive<ActiveConditionMenuTarget>({
    rowId: '',
    colId: '',
    conditionValue: '',
  });
  /** 行数据缓存：事件委托只能拿到 rowId/colId，需据此回源取单元格原始值（含 tag 的 index 取值） */
  const { cacheRows, getCellComplexValue, clearCache } = useExploreDataCache(rowKey);
  /** 右键监听所在的根 DOM，组件卸载时解绑 */
  let contextMenuRoot: HTMLElement = null;

  /**
   * @description 重置/设置条件菜单目标
   * @param {Partial<ActiveConditionMenuTarget>} item 目标信息，不传即重置
   */
  function setActiveConditionMenu(item: Partial<ActiveConditionMenuTarget> = {}) {
    activeConditionMenuTarget.rowId = item.rowId || '';
    activeConditionMenuTarget.colId = item.colId || '';
    activeConditionMenuTarget.conditionValue = item.conditionValue || '';
  }

  /**
   * @description 解析菜单 popover 的内容与挂载目标
   * @param {HTMLElement} triggerDom 命中的单元格文本节点
   * @returns 再次点击同一单元格时返回空（表现为收起），否则返回菜单内容与挂载目标
   */
  function getContentOptions(triggerDom: HTMLElement) {
    const oldRowId = activeConditionMenuTarget.rowId;
    const oldColId = activeConditionMenuTarget.colId;
    setActiveConditionMenu();
    if (triggerDom.dataset.rowId === oldRowId && triggerDom.dataset.colId === oldColId) {
      return;
    }
    const sourceValue = getCellComplexValue(triggerDom.dataset.rowId, triggerDom.dataset.colId, {
      index: triggerDom.dataset.index ? Number(triggerDom.dataset.index) : null,
    });
    setActiveConditionMenu({
      rowId: triggerDom.dataset.rowId,
      colId: triggerDom.dataset.colId,
      conditionValue: Array.isArray(sourceValue) ? JSON.stringify(sourceValue) : String(sourceValue),
    });
    const { isEllipsisActive } = isEllipsisActiveSingleLine(triggerDom.parentElement);
    return {
      content: menuRef.value?.$el,
      popoverTarget: isEllipsisActive ? triggerDom.parentElement : triggerDom,
    };
  }

  const { handlePopoverHide, handlePopoverShow, initListeners } = useTablePopover(
    delegationRoot as Parameters<typeof useTablePopover>[0],
    {
      trigger: { selector: `.${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`, eventType: 'click', delay: 0 },
      getContentOptions,
      onHide: () => setActiveConditionMenu(),
      popoverOptions: {
        theme: 'light padding-0',
        placement: 'bottom',
        interactive: true,
        duration: [50, null],
      },
    }
  );

  /**
   * @description 解析事件委托根 DOM（兼容组件实例与原生 DOM）
   */
  function getRootDom(): HTMLElement {
    const root = get(delegationRoot) as HTMLElement | { $el?: HTMLElement };
    return (root as { $el?: HTMLElement })?.$el ?? (root as HTMLElement);
  }

  /**
   * @description CLICK 类型列右键唤起条件菜单（左键保持「直接加为检索条件」）
   * @param {MouseEvent} event 右键事件
   */
  function handleContextMenu(event: MouseEvent) {
    const triggerDom = (event.target as HTMLElement)?.closest?.<HTMLElement>(CLICK_CELL_TEXT_SELECTOR);
    if (!triggerDom) return;
    event.preventDefault();
    const options = getContentOptions(triggerDom);
    if (options?.content == null) {
      handlePopoverHide();
      return;
    }
    handlePopoverShow(options.popoverTarget || triggerDom, options.content);
  }

  /**
   * @description 菜单项点击后收起菜单并重置目标
   */
  function closeMenu() {
    setActiveConditionMenu();
    handlePopoverHide();
  }

  onMounted(() => {
    nextTick(() => {
      initListeners();
      contextMenuRoot = getRootDom();
      contextMenuRoot?.addEventListener('contextmenu', handleContextMenu, true);
    });
  });

  onBeforeUnmount(() => {
    contextMenuRoot?.removeEventListener('contextmenu', handleContextMenu, true);
    contextMenuRoot = null;
  });

  return {
    /** 当前激活的条件菜单目标 */
    activeConditionMenuTarget,
    /** 批量缓存行数据（数据追加时调用） */
    cacheRows,
    /** 清空行数据缓存（新查询时调用） */
    clearCache,
    /** 收起菜单并重置目标 */
    closeMenu,
    /** 收起菜单（滚动等场景） */
    hideMenu: handlePopoverHide,
  };
};
