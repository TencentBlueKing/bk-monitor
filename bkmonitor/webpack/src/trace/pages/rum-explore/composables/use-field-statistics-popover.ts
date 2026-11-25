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
import { nextTick, shallowRef, useTemplateRef } from 'vue';

import tippy, { type Instance, type Props, type SingleTarget } from 'tippy.js';

import type StatisticsList from '../../trace-explore/components/statistics-list/statistics-list';
import type { IDimensionFieldTreeItem } from '../../trace-explore/typing';
import type { IRumField } from '../typings';

/** 统计弹层字段入参：数组时由 StatisticsList 展示字段 Tab，首项为初始激活字段 */
export type IStatisticsFieldInput = IStatisticsFieldItem | IStatisticsFieldItem[];

/** 统计分析弹层展示的字段，RUM 检索的字段会额外携带 field_unit */
export type IStatisticsFieldItem = {
  /** 是否耗时字段，由调用方按检索语义判定 */
  isDuration?: boolean;
  /** 是否数值字段，由调用方按检索语义判定 */
  isInteger?: boolean;
} & IDimensionFieldTreeItem &
  Pick<IRumField, 'field_display_type' | 'field_unit'>;

/**
 * 字段统计分析弹层。
 *
 * 左侧维度面板和表格列头都需要点开同一套统计面板，这里统一管理 tippy 生命周期，
 * 调用方只要把 statisticsListRef 挂到 StatisticsList 上，再在点击时调用 openPopover。
 */
export const useFieldStatisticsPopover = (placement: Props['placement'] = 'right') => {
  const showPopover = shallowRef(false);
  const activeFieldName = shallowRef('');
  const selectField = shallowRef<IStatisticsFieldInput>(null);
  const popoverInstance = shallowRef<Instance | null>(null);
  const statisticsListRef = useTemplateRef<InstanceType<typeof StatisticsList>>('statisticsListRef');

  /** 清空激活字段并释放当前的浮层实例。 */
  const destroyPopover = () => {
    showPopover.value = false;
    activeFieldName.value = '';
    const instance = popoverInstance.value;
    if (instance) {
      popoverInstance.value = null;
      instance.destroy();
    }
  };

  /** 归一化字段：聚合结果可能混合 CLS 与耗时指标，不能把 vital 作为固定时间单位。 */
  const normalizeField = (field: IStatisticsFieldItem): IStatisticsFieldItem => {
    const normalizedField =
      field.field_unit === 'vital' ? { ...field, field_unit: '', field_display_type: undefined } : field;
    return {
      ...normalizedField,
      isDuration: normalizedField.field_display_type === 'duration' || normalizedField.field_unit === 'bytes',
      isInteger: ['double', 'long', 'integer', 'float'].includes(normalizedField.type),
    };
  };

  /** 更新分析字段，需要时通过显隐周期重启统计请求；数组时首项为初始激活字段。 */
  const selectPopoverField = (field: IStatisticsFieldInput) => {
    const fields = Array.isArray(field) ? field : [field];
    const [initialField] = fields;
    if (!initialField?.is_dimensions) return;
    const instance = popoverInstance.value;
    if (showPopover.value && instance) {
      // 统计组件通过显隐周期取消旧字段请求并加载新字段。
      showPopover.value = false;
      nextTick(() => {
        if (popoverInstance.value === instance) showPopover.value = true;
      });
    }
    activeFieldName.value = initialField.name;
    const normalizedFields = fields.map(normalizeField);
    selectField.value = Array.isArray(field) ? normalizedFields : normalizedFields[0];
  };

  /** 创建分析浮层，以点击位置为锚点并加载初始字段。 */
  const openPopover = (trigger: Element, field: IStatisticsFieldInput) => {
    destroyPopover();
    const [initialField] = Array.isArray(field) ? field : [field];
    if (!initialField?.is_dimensions) return;
    const contentEl = statisticsListRef.value?.$refs?.dimensionPopover as HTMLDivElement | undefined;
    if (!contentEl) return;
    selectPopoverField(field);

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
      onHidden: hiddenInstance => {
        if (popoverInstance.value !== hiddenInstance) return;
        showPopover.value = false;
        activeFieldName.value = '';
        popoverInstance.value = null;
        hiddenInstance.destroy();
      },
    });
    popoverInstance.value = instance;
    // 等 StatisticsList 内部完成首次渲染再显示，否则弹层首次定位会偏
    setTimeout(() => {
      if (popoverInstance.value !== instance) return;
      showPopover.value = true;
      instance.show();
    }, 100);
  };

  /**
   * 弹层内容渲染完成后重新定向。
   * openPopover 时内容尚未加载数据，初始定位基于较低的高度；数据加载完成后内容撑高，
   * 需要重新计算定位，否则底部内容会被视口裁掉。
   */
  const updatePopoverPosition = () => {
    popoverInstance.value?.popperInstance?.forceUpdate();
  };

  return {
    activeFieldName,
    selectField,
    showPopover,
    statisticsListRef,
    destroyPopover,
    openPopover,
    selectPopoverField,
    updatePopoverPosition,
  };
};
