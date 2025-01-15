/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { defineComponent, ref, watch } from 'vue';

import { commonLegendEmits, commonLegendProps, useCommonLegend } from './common-legend';

import type { ILegendItem, TableLegendHeadType } from '../typings';

import './table-legend.scss';

export default defineComponent({
  name: 'TableLegend',
  props: {
    ...commonLegendProps,
  },
  emits: [...commonLegendEmits],
  setup(props, { emit }) {
    // 表格图例 表头
    const headList: TableLegendHeadType[] = ['Min', 'Max', 'Avg'];
    // 图例数据
    const list = ref<ILegendItem[]>([]);
    // 排序 0 不排序 1 向上 2 向下
    const sort = ref(0);
    const sortTitle = ref('');
    function handleSortChange(title?: TableLegendHeadType, sortVal?: number) {
      sortTitle.value = title || '';
      if (title) {
        if (typeof sortVal === 'number') {
          sort.value = sortVal;
        } else {
          sort.value = (sort.value + 1) % 3;
        }
      }
      if (sort.value === 0 || !title) {
        list.value = props.legendData!;
        return;
      }
      const sortId = `${title.toLocaleLowerCase()}Source`;
      list.value = props.legendData!.slice().sort((a, b) => {
        const aVal = (a as any)[sortId] || 0;
        const bVal = (b as any)[sortId] || 0;
        if (sort.value === 1) {
          return +aVal - +bVal;
        }
        return +bVal - +aVal;
      });
    }
    watch(
      () => props.legendData,
      () => handleSortChange(),
      { immediate: true }
    );
    const { handleLegendEvent } = useCommonLegend(emit);
    return {
      headList,
      list,
      sort,
      sortTitle,
      handleSortChange,
      handleLegendEvent,
    };
  },
  render() {
    return (
      <table class='table-legend'>
        <colgroup>
          <col style='width: 100%' />
        </colgroup>
        <thead>
          <tr>
            {this.headList.map(title => (
              <th
                key={title}
                style='text-align: right'
                onClick={() => this.handleSortChange(title)}
              >
                {title}
                <span class='caret-wrapper'>
                  <i
                    class={{ 'sort-caret is-asc': true, active: this.sortTitle === title && this.sort === 1 }}
                    onClick={() => this.handleSortChange(title, 1)}
                  />
                  <i
                    class={{ 'sort-caret is-desc': true, active: this.sortTitle === title && this.sort === 2 }}
                    onClick={() => this.handleSortChange(title, 2)}
                  />
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {this.list.map((item, index) => {
            if (item.hidden) return undefined;
            return (
              <tr key={index}>
                {this.headList.map(title => (
                  <td key={title}>
                    <div class='content-wrapper'>
                      {title === 'Min' && (
                        <div
                          class='legend-metric'
                          onClick={e => this.handleLegendEvent(e, 'click', item)}
                          // onMouseenter={e => this.handleLegendEvent(e, 'highlight', item) }
                          // onMouseleave={e => this.handleLegendEvent(e, 'downplay', item) }
                        >
                          <span
                            style={{ backgroundColor: item.show ? item.color : '#ccc' }}
                            class='metric-label'
                          />
                          <span
                            style={{ color: item.show ? '#63656e' : '#ccc' }}
                            class='metric-name'
                            v-bk-overflow-tips={{ placement: 'top', offset: '100, 0' }}
                          >
                            {item.name}
                          </span>
                        </div>
                      )}
                      <div class='legend-value'>{(item as any)[title.toLocaleLowerCase()]}</div>
                    </div>
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  },
});
