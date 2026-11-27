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
import { type PropType, computed, defineComponent, useTemplateRef } from 'vue';

import { useI18n } from 'vue-i18n';

import FieldTypeIcon from '../../../../../trace-explore/components/field-type-icon';
import RumHoverInfo from '../../../../detail/components/hover-info/hover-info';
import { useHoverInfo } from '../../../../detail/composables/use-hover-info';
import RumColumnSort, { type RumSortOption, type RumSortOrder } from '../column-sort/column-sort';

import type { IRumField } from '../../../../typings';

import './column-header.scss';

/** 点击列头分析入口时打开的字段及其可切换范围。 */
export interface FieldAnalysisSelection {
  /** 复合列中支持分析的字段，按布局顺序排列。 */
  candidates: IRumField[];
  /** 初始分析字段，优先使用复合列的 primary。 */
  field: IRumField;
}

export default defineComponent({
  name: 'RumColumnHeader',
  props: {
    /** 展示列的字段键，接口缺少别名时用于显示。 */
    colKey: { type: String, required: true },
    /** 展示列的字段元信息，包括单位说明和复合布局。 */
    field: { type: Object as PropType<IRumField>, default: undefined },
    /** 列头分析入口的默认字段和候选，缺省时隐藏入口。 */
    analysis: { type: Object as PropType<FieldAnalysisSelection>, default: undefined },
    /** 复合列当前的排序方向，未排序时为空串。 */
    sort: { type: String as PropType<RumSortOrder>, default: '' },
    /** 复合列当前生效排序的分类字段。 */
    sortField: { type: String, default: '' },
  },
  emits: {
    /** 打开字段分析浮层，并用按钮作为定位锚点。 */
    fieldAnalysis: (_trigger: Element, _selection: FieldAnalysisSelection) => true,
    /** 复合列分类排序变更：order 为方向，field 为选中的分类字段。 */
    sortChange: (_order: RumSortOrder, _field?: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const label = computed(() => props.field?.alias ?? props.colKey);
    const hoverInfoRef = useTemplateRef<HTMLDivElement>('hoverInfo');
    /** hover 字段说明时展示 hover-info 卡片，无 hover 数据的列头不加事件 */
    const { hoverBindings, hoverData } = useHoverInfo();
    /** 复合列才有分类排序：候选与字段分析弹层的 tab 分类一致。 */
    const sortOptions = computed<RumSortOption[]>(() => {
      if (!props.field?.composite || !props.analysis) return [];
      return props.analysis.candidates.map(item => ({ label: item.alias ?? item.name, value: item.name }));
    });

    /** 打开分析浮层，避免点击同时触发表头排序。 */
    const handleAnalysis = (event: MouseEvent) => {
      event.stopPropagation();
      if (props.analysis) emit('fieldAnalysis', event.currentTarget as Element, props.analysis);
    };

    /** 转发分类排序结果，由表格统一转成查询排序。 */
    const handleSortChange = (order: RumSortOrder, field?: string) => {
      emit('sortChange', order, field);
    };

    return { t, label, hoverInfoRef, hoverBindings, hoverData, sortOptions, handleAnalysis, handleSortChange };
  },
  render() {
    const hover = this.field?.hover;
    const label = (
      <span
        class={['th-label', { 'has-hover-info': hover }]}
        {...this.hoverBindings(this.hoverInfoRef, hover)}
      >
        {this.label}
      </span>
    );
    return (
      <div class='rum-table-header-cell'>
        {!this.field?.composite && (
          <FieldTypeIcon
            class='field-type-icon'
            type={this.field?.type}
          />
        )}
        <div
          class='header-title'
          v-overflow-tips={{ placement: 'top', theme: 'dark text-wrap' }}
        >
          {label}
        </div>
        {this.analysis && (
          <button
            class='header-analysis-icon'
            aria-label={this.t('字段分析')}
            type='button'
            onClick={this.handleAnalysis}
          >
            <i
              class='icon-monitor icon-Chart'
              aria-hidden='true'
            />
          </button>
        )}
        {!!this.sortOptions.length && (
          <RumColumnSort
            sort={this.sort}
            sortField={this.sortField}
            sortOptions={this.sortOptions}
            onSortChange={this.handleSortChange}
          />
        )}
        <div style='display: none'>
          <div ref='hoverInfo'>
            <RumHoverInfo data={this.hoverData} />
          </div>
        </div>
      </div>
    );
  },
});
