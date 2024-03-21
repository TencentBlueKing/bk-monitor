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
import { Component, Watch } from 'vue-property-decorator';

import { ILegendItem, TableLegendHeadType } from '../../typings';

import CommonLegend from './common-legend';

import './table-legend.scss';

@Component
export default class TableLegend extends CommonLegend {
  // 表格图例 表头
  headList: TableLegendHeadType[] = ['Min', 'Max', 'Avg'];
  // 图例数据
  list: ILegendItem[] = [];
  // 排序 0 不排序 1 向上 2 向下
  sort = 0;
  sortTitle = '';

  @Watch('legendData', { immediate: true })
  handleLegendDataChange() {
    this.handleSortChange();
  }
  handleSortChange(title?: TableLegendHeadType, sort?) {
    this.sortTitle = title || '';
    if (title) {
      if (typeof sort === 'number') {
        this.sort = sort;
      } else {
        this.sort = (this.sort + 1) % 3;
      }
    }
    if (this.sort === 0 || !title) {
      this.list = this.legendData;
      return;
    }
    const sortId = `${title.toLocaleLowerCase()}Source`;
    this.list = this.legendData.slice().sort((a, b) => {
      const aVal = a[sortId] || 0;
      const bVal = b[sortId] || 0;
      if (this.sort === 1) {
        return +aVal - +bVal;
      }
      return +bVal - +aVal;
    });
  }

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
                    onClick={() => this.handleSortChange(title, 1)}
                    class={{ 'sort-caret is-asc': true, active: this.sortTitle === title && this.sort === 1 }}
                  ></i>
                  <i
                    onClick={() => this.handleSortChange(title, 2)}
                    class={{ 'sort-caret is-desc': true, active: this.sortTitle === title && this.sort === 2 }}
                  ></i>
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
                          onMousedown={e => this.handleLegendMouseEvent(e, 'mousedown')}
                          onMousemove={e => this.handleLegendMouseEvent(e, 'mousemove')}
                          onMouseup={e => this.handleLegendMouseEvent(e, 'mouseup', item)}
                          onMouseenter={e => this.handleLegendEvent(e, 'highlight', item)}
                          onMouseleave={e => this.handleLegendEvent(e, 'downplay', item)}
                        >
                          <span
                            class='metric-label'
                            style={{ backgroundColor: item.show ? item.color : '#ccc' }}
                          ></span>
                          <span
                            v-bk-overflow-tips={{ placement: 'top', offset: '100, 0' }}
                            class='metric-name'
                            style={{ color: item.show ? '#63656e' : '#ccc' }}
                          >
                            {item.name}
                          </span>
                        </div>
                      )}
                      <div class='legend-value'>{item[title.toLocaleLowerCase()]}</div>
                    </div>
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }
}
