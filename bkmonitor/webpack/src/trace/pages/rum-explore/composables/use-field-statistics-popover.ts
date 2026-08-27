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
import { shallowRef, useTemplateRef } from 'vue';

import tippy, { type Instance, type Props, type SingleTarget } from 'tippy.js';

import type StatisticsList from '../../trace-explore/components/statistics-list';
import type { IDimensionFieldTreeItem } from '../../trace-explore/typing';

/** 统计分析弹层展示的字段，RUM 检索的字段会额外携带 field_unit */
export type IStatisticsFieldItem = IDimensionFieldTreeItem & { field_unit?: string };

/**
 * 字段统计分析弹层。
 *
 * 左侧维度面板和表格列头都需要点开同一套统计面板，这里统一管理 tippy 生命周期，
 * 调用方只要把 statisticsListRef 挂到 StatisticsList 上，再在点击时调用 openPopover。
 */
export function useFieldStatisticsPopover(placement: Props['placement'] = 'right') {
  const showPopover = shallowRef(false);
  const activeFieldName = shallowRef('');
  const selectField = shallowRef<IStatisticsFieldItem>(null);
  const popoverInstance = shallowRef<Instance | null>(null);
  const statisticsListRef = useTemplateRef<InstanceType<typeof StatisticsList>>('statisticsListRef');

  function destroyPopover() {
    showPopover.value = false;
    activeFieldName.value = '';
    const instance = popoverInstance.value;
    if (instance) {
      popoverInstance.value = null;
      instance.destroy();
    }
  }

  function openPopover(trigger: Element, field: IStatisticsFieldItem) {
    destroyPopover();
    activeFieldName.value = field.name;
    if (!field.is_dimensions) return;
    selectField.value = field;
    const contentEl = statisticsListRef.value?.$refs?.dimensionPopover as HTMLDivElement | undefined;
    if (!contentEl) return;

    const instance = tippy(trigger as SingleTarget, {
      content: contentEl,
      trigger: 'manual',
      placement,
      theme: 'light statistics-dimension-popover-cls',
      arrow: true,
      interactive: true,
      zIndex: 1000,
      offset: [0, 8],
      appendTo: () => document.body,
      popperOptions: {
        modifiers: [{ name: 'preventOverflow', options: { boundary: 'viewport' } }],
      },
      onHidden(hiddenInstance) {
        if (popoverInstance.value !== hiddenInstance) return;
        showPopover.value = false;
        activeFieldName.value = '';
        popoverInstance.value = null;
      },
    });
    popoverInstance.value = instance;
    // 等 StatisticsList 内部完成首次渲染再显示，否则弹层首次定位会偏
    setTimeout(() => {
      if (popoverInstance.value !== instance) return;
      showPopover.value = true;
      instance.show();
    }, 100);
  }

  return {
    activeFieldName,
    selectField,
    showPopover,
    statisticsListRef,
    destroyPopover,
    openPopover,
  };
}
