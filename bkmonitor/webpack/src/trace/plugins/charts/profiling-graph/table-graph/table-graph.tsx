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

import { defineComponent, ref, shallowRef, Teleport } from 'vue';

import {
  ITableTipsDetail,
  ProfilingTableItem,
  TableColumn
} from '../../../../../monitor-ui/chart-plugins/typings/profiling-graph';
import { PROFILING_TABLE_DATA } from '../mock';

// import { ColorTypes } from './../../flame-graph-v2/types';
import './table-graph.scss';

// const valueColumnWidth = 150;

export default defineComponent({
  name: 'ProfilingTableGraph',
  setup() {
    /** 表格数据 */
    const tableData = ref<ProfilingTableItem[]>(PROFILING_TABLE_DATA);
    const tableColumns = ref<TableColumn[]>([
      { id: 'Location', sort: '' },
      { id: 'Self', sort: '' },
      { id: 'Total', sort: '' }
    ]);
    const tipDetail = shallowRef<ITableTipsDetail>({});

    const getColStyle = (row: ProfilingTableItem) => {
      const { color } = row;
      return {
        'background-image': `linear-gradient(${color}, ${color})`,
        // 'background-position': `-${Math.round(Math.random() * valueColumnWidth)}px 0px`,
        'background-position': `-80px 0px`,
        'background-repeat': 'no-repeat'
      };
    };
    /** 列字段排序 */
    const handleSort = (col: TableColumn) => {
      col.sort = col.sort === 'desc' ? 'asc' : 'desc';
      tableColumns.value = tableColumns.value.map(item => {
        return {
          ...item,
          sort: col.id === item.id ? col.sort : ''
        };
      });
    };
    const handleRowMouseMove = (e: MouseEvent) => {
      let axisLeft = e.pageX;
      let axisTop = e.pageY;
      if (axisLeft + 394 > window.innerWidth) {
        axisLeft = axisLeft - 394 - 20;
      } else {
        axisLeft = axisLeft + 20;
      }
      if (axisTop + 120 > window.innerHeight) {
        axisTop = axisTop - 120;
      } else {
        axisTop = axisTop;
      }
      tipDetail.value = {
        left: axisLeft,
        top: axisTop,
        title: 'sync.(*Mutex).Unlock'
      };
    };
    const handleRowMouseout = () => {
      tipDetail.value = {};
    };

    return {
      tableColumns,
      tableData,
      getColStyle,
      handleSort,
      tipDetail,
      handleRowMouseMove,
      handleRowMouseout
    };
  },
  render() {
    return (
      <div class='profiling-table-graph'>
        <table class='profiling-table'>
          <thead>
            <tr>
              {this.tableColumns.map(col => (
                <th onClick={() => this.handleSort(col)}>
                  <div class='thead-content'>
                    <span>{col.id}</span>
                    <div class='sort-button'>
                      <i class={`icon-monitor icon-mc-arrow-down asc ${col.sort === 'asc' ? 'active' : ''}`}></i>
                      <i class={`icon-monitor icon-mc-arrow-down desc ${col.sort === 'desc' ? 'active' : ''}`}></i>
                    </div>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {this.tableData.map(row => (
              <tr
                onMousemove={e => this.handleRowMouseMove(e)}
                onMouseout={() => this.handleRowMouseout()}
              >
                <td>
                  <div class='location-info'>
                    <span
                      class='color-reference'
                      style={`background-color: ${row.color}`}
                    ></span>
                    <span>{row.location}</span>
                    {/* <div class='trace-mark'>Trace</div> */}
                  </div>
                </td>
                <td style={this.getColStyle(row)}>{row.self}</td>
                <td style={this.getColStyle(row)}>{row.Total}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <Teleport to='body'>
          <div
            class='table-graph-row-tips'
            style={{
              left: `${this.tipDetail.left || 0}px`,
              top: `${this.tipDetail.top || 0}px`,
              display: this.tipDetail.title ? 'block' : 'none'
            }}
          >
            {this.tipDetail.title && [
              <div class='funtion-name'>{this.tipDetail.title}</div>,
              <table class='tips-table'>
                <thead>
                  <th></th>
                  <th>Self (% of total CPU)</th>
                  <th>Total (% of total CPU)</th>
                </thead>
                <tbody>
                  <tr>
                    <td>CPU Time</td>
                    <td>4.32 minutes(9.33%)</td>
                    <td>5.33 minutes(11.52%)</td>
                  </tr>
                </tbody>
              </table>
            ]}
          </div>
        </Teleport>
      </div>
    );
  }
});
