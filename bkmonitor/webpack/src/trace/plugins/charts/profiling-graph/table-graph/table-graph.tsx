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

import { defineComponent, PropType, ref, shallowRef, Teleport, watch } from 'vue';

import { getHashVal } from '../../../../../monitor-ui/chart-plugins/plugins/profiling-graph/flame-graph/utils';
import { ColorTypes } from '../../../../../monitor-ui/chart-plugins/typings';
import {
  ITableTipsDetail,
  ProfilingTableItem,
  TableColumn
} from '../../../../../monitor-ui/chart-plugins/typings/profiling-graph';
import { getValueFormat } from '../../../../../monitor-ui/monitor-echarts/valueFormats';
import { DirectionType } from '../../../../typings';

// import { ColorTypes } from './../../flame-graph-v2/types';
import './table-graph.scss';

// const valueColumnWidth = 150;

const TABLE_BGCOLOR_COLUMN_WIDTH = 120;

export default defineComponent({
  name: 'ProfilingTableGraph',
  props: {
    textDirection: {
      type: String as PropType<DirectionType>,
      default: 'ltr'
    },
    unit: {
      type: String,
      default: ''
    },
    data: {
      type: Array as PropType<ProfilingTableItem[]>,
      default: () => []
    }
  },
  setup(props) {
    /** 表格数据 */
    const tableData = ref<ProfilingTableItem[]>([]);
    const tableColumns = ref<TableColumn[]>([
      { id: 'Location', name: 'Location', sort: '' },
      { id: 'Self', name: 'Self', mode: 'normal', sort: '' },
      { id: 'Total', name: 'Total', mode: 'normal', sort: '' },
      { id: 'baseline', name: window.i18n.t('查询项'), mode: 'diff', sort: '' },
      { id: 'comparison', name: window.i18n.t('对比项'), mode: 'diff', sort: '' },
      { id: 'diff', name: 'Diff', mode: 'diff', sort: '' }
    ]);
    const maxItem = ref<{ self: number; total: number }>({
      self: 0,
      total: 0
    });
    const tipDetail = shallowRef<ITableTipsDetail>({});
    const diffMode = ref(false);

    watch(
      () => props.data,
      (val: ProfilingTableItem[]) => {
        maxItem.value = {
          self: Math.max(...val.map(item => item.self)),
          total: Math.max(...val.map(item => item.total))
        };
        tableData.value = val.map(item => {
          const palette = Object.values(ColorTypes);
          const colorIndex = getHashVal(item.name) % palette.length;
          const color = palette[colorIndex];
          return {
            ...item,
            color,
            displaySelf: formatColValue(item.self),
            displayTotal: formatColValue(item.total)
          };
        });
      },
      {
        immediate: true,
        deep: true
      }
    );

    // Self 和 Total 值的展示
    const formatColValue = (val: number) => {
      switch (props.unit) {
        case 'nanoseconds': {
          const nsFormat = getValueFormat('ns');
          const { text, suffix } = nsFormat(val);
          return text + suffix;
        }
        default:
          return '';
      }
    };
    const getColStyle = (row: ProfilingTableItem, field: string) => {
      const { color } = row;
      const value = row[field] || 0;
      const percent = (value * TABLE_BGCOLOR_COLUMN_WIDTH) / maxItem.value[field];
      const xPosition = TABLE_BGCOLOR_COLUMN_WIDTH - percent;

      return {
        'background-image': `linear-gradient(${color}, ${color})`,
        'background-position': `-${xPosition}px 0px`,
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
    const handleRowMouseMove = (e: MouseEvent, row: ProfilingTableItem) => {
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

      const { name, displaySelf, displayTotal, self, total } = row;
      const totalItem = tableData.value[0];

      tipDetail.value = {
        left: axisLeft,
        top: axisTop,
        title: name,
        displaySelf,
        displayTotal,
        selfPercent: `${((self / totalItem.self) * 100).toFixed(2)}%`,
        totalPercent: `${((total / totalItem.total) * 100).toFixed(2)}%`
      };
    };
    const handleRowMouseout = () => {
      tipDetail.value = {};
    };

    return {
      tableData,
      tableColumns,
      getColStyle,
      handleSort,
      tipDetail,
      handleRowMouseMove,
      handleRowMouseout,
      diffMode,
      formatColValue
    };
  },
  render() {
    return (
      <div class='profiling-table-graph'>
        <table class={`profiling-table ${this.diffMode ? 'diff-table' : ''}`}>
          <thead>
            <tr>
              {this.tableColumns.map(
                col =>
                  (!col.mode ||
                    (this.diffMode && col.mode === 'diff') ||
                    (!this.diffMode && col.mode === 'normal')) && (
                    <th onClick={() => this.handleSort(col)}>
                      <div class='thead-content'>
                        <span>{col.name}</span>
                        <div class='sort-button'>
                          <i class={`icon-monitor icon-mc-arrow-down asc ${col.sort === 'asc' ? 'active' : ''}`}></i>
                          <i class={`icon-monitor icon-mc-arrow-down desc ${col.sort === 'desc' ? 'active' : ''}`}></i>
                        </div>
                      </div>
                    </th>
                  )
              )}
            </tr>
          </thead>
          <tbody>
            {this.tableData.map(row => (
              <tr
                onMousemove={e => this.handleRowMouseMove(e, row)}
                onMouseout={() => this.handleRowMouseout()}
              >
                <td>
                  <div class='location-info'>
                    <span
                      class='color-reference'
                      style={`background-color: ${row.color}`}
                    ></span>
                    <span class={`text direction-${this.textDirection}`}>{row.name}</span>
                    {/* <div class='trace-mark'>Trace</div> */}
                  </div>
                </td>
                {this.diffMode
                  ? [
                      <td>59%</td>,
                      <td>59%</td>,
                      <td>
                        <span class={`diff-value ${false ? 'is-rise' : 'is-decline'}`}>+45%</span>
                      </td>
                    ]
                  : [
                      <td style={this.getColStyle(row, 'self')}>{row.displaySelf}</td>,
                      <td style={this.getColStyle(row, 'total')}>{row.displayTotal}</td>
                    ]}
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
                  <th>Self (% of total)</th>
                  <th>Total (% of total)</th>
                </thead>
                <tbody>
                  <tr>
                    <td>&nbsp;&nbsp;</td>
                    <td>{`${this.tipDetail.displaySelf}(${this.tipDetail.selfPercent})`}</td>
                    <td>{`${this.tipDetail.displayTotal}(${this.tipDetail.totalPercent})`}</td>
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
