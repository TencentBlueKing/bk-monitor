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
import { Exception } from 'bkui-vue';
import { getHashVal } from 'monitor-ui/chart-plugins/plugins/profiling-graph/flame-graph/utils';
import { ColorTypes } from 'monitor-ui/chart-plugins/typings';
import { ITableTipsDetail, ProfilingTableItem, TableColumn } from 'monitor-ui/chart-plugins/typings/profiling-graph';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

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
    },
    highlightId: {
      type: Number,
      default: -1
    },
    filterKeyword: {
      type: String,
      default: ''
    },
    // 对比模式
    isCompared: {
      type: Boolean,
      default: false
    },
    // 数据类型
    dataType: {
      type: String,
      default: ''
    }
  },
  emits: ['updateHighlightId', 'sortChange'],
  setup(props, { emit }) {
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
    const localIsCompared = ref(false);

    watch(
      () => props.data,
      (val: ProfilingTableItem[]) => {
        maxItem.value = {
          self: Math.max(...val.map(item => item.self)),
          total: Math.max(...val.map(item => item.total))
        };
        getTableData();
      },
      {
        immediate: true,
        deep: true
      }
    );
    watch(
      () => props.filterKeyword,
      () => {
        getTableData();
      }
    );

    function getTableData() {
      tableData.value = props.data
        .filter(item => (!!props.filterKeyword ? item.name.includes(props.filterKeyword) : true))
        .map(item => {
          const palette = Object.values(ColorTypes);
          const colorIndex = getHashVal(item.name) % palette.length;
          const color = palette[colorIndex];
          return {
            ...item,
            color
          };
        });
      localIsCompared.value = props.isCompared;
    }
    // Self 和 Total 值的展示
    function formatColValue(val: number) {
      switch (props.unit) {
        case 'nanoseconds': {
          const nsFormat = getValueFormat('ns');
          const { text, suffix } = nsFormat(val);
          return text + suffix;
        }
        default:
          return '';
      }
    }
    function getColStyle(row: ProfilingTableItem, field: string) {
      const { color } = row;
      const value = row[field] || 0;
      const percent = (value * TABLE_BGCOLOR_COLUMN_WIDTH) / maxItem.value[field];
      let xPosition = TABLE_BGCOLOR_COLUMN_WIDTH - percent;
      if (TABLE_BGCOLOR_COLUMN_WIDTH - 2 < xPosition && xPosition < TABLE_BGCOLOR_COLUMN_WIDTH) {
        xPosition = TABLE_BGCOLOR_COLUMN_WIDTH - 2; // 保留 2px 最小宽度可见
      }

      return {
        'background-image': `linear-gradient(${color}, ${color})`,
        'background-position': `-${xPosition}px 0px`,
        'background-repeat': 'no-repeat'
      };
    }
    /** 列字段排序 */
    function handleSort(col: TableColumn) {
      let sortKey;
      switch (col.sort) {
        case 'asc':
          col.sort = 'desc';
          sortKey = `-${col.id}`;
          break;
        case 'desc':
          col.sort = '';
          sortKey = undefined;
          break;
        default:
          col.sort = 'asc';
          sortKey = col.id;
      }
      emit('sortChange', sortKey);
      tableColumns.value = tableColumns.value.map(item => {
        return {
          ...item,
          sort: col.id === item.id ? col.sort : ''
        };
      });
    }
    function handleRowMouseMove(e: MouseEvent, row: ProfilingTableItem) {
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

      const { name, self, total, baseline, comparison, mark = '' } = row;
      const totalItem = tableData.value[0];

      tipDetail.value = {
        left: axisLeft,
        top: axisTop,
        title: name,
        self,
        total,
        baseline,
        comparison,
        mark,
        selfPercent: `${((self / totalItem.self) * 100).toFixed(2)}%`,
        totalPercent: `${((total / totalItem.total) * 100).toFixed(2)}%`
      };
    }
    function handleRowMouseout() {
      tipDetail.value = {};
    }
    function handleHighlightClick(id) {
      let hightlightId = -1;
      if (props.highlightId !== id) {
        hightlightId = id;
      }
      return emit('updateHighlightId', hightlightId);
    }

    return {
      tableData,
      tableColumns,
      getColStyle,
      handleSort,
      tipDetail,
      localIsCompared,
      formatColValue,
      handleRowMouseMove,
      handleRowMouseout,
      handleHighlightClick
    };
  },
  render() {
    const getDiffTpl = row => {
      if (['removed', 'added'].includes(row.mark)) {
        return <span style={`color: ${row.mark === 'removed' ? '#ff5656' : '#2dcb56'}`}>{row.mark}</span>;
      }

      const { baseline, comparison } = row;
      const diffVal = (baseline - comparison) / comparison;

      if (diffVal === 0) return <span style='color:#dddfe3'>0%</span>;

      return <span style={`color:${diffVal > 0 ? '#ff5656' : '#2dcb56'}`}>{`${(diffVal * 100).toFixed(0)}%`}</span>;
    };

    return (
      <div class='profiling-table-graph'>
        <table class={`profiling-table ${this.localIsCompared ? 'diff-table' : ''}`}>
          <thead>
            <tr>
              {this.tableColumns.map(
                col =>
                  (!col.mode ||
                    (this.localIsCompared && col.mode === 'diff') ||
                    (!this.localIsCompared && col.mode === 'normal')) && (
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
            {this.tableData.length ? (
              <>
                {this.tableData.map(row => (
                  <tr
                    class={row.id === this.highlightId ? 'hightlight' : ''}
                    onMousemove={e => this.handleRowMouseMove(e, row)}
                    onMouseout={() => this.handleRowMouseout()}
                    onClick={() => this.handleHighlightClick(row.id)}
                  >
                    <td>
                      <div class='location-info'>
                        <span
                          class='color-reference'
                          style={`background-color: ${!this.localIsCompared ? row.color : '#dcdee5'}`}
                        ></span>
                        <span class={`text direction-${this.textDirection}`}>{row.name}</span>
                        {/* <div class='trace-mark'>Trace</div> */}
                      </div>
                    </td>
                    {this.localIsCompared
                      ? [
                          <td>{this.formatColValue(row.baseline)}</td>,
                          <td>{this.formatColValue(row.comparison)}</td>,
                          <td>{getDiffTpl(row)}</td>
                        ]
                      : [
                          <td style={this.getColStyle(row, 'self')}>{this.formatColValue(row.self)}</td>,
                          <td style={this.getColStyle(row, 'total')}>{this.formatColValue(row.total)}</td>
                        ]}
                  </tr>
                ))}
              </>
            ) : (
              <tr>
                <td colspan='3'>
                  <Exception
                    class='empty-table-exception'
                    type='search-empty'
                    scene='part'
                    description={this.$t('搜索为空')}
                  />
                </td>
              </tr>
            )}
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
                {this.localIsCompared
                  ? [
                      <thead>
                        <th></th>
                        <th>Baseline</th>
                        <th>Comparison</th>
                        <th>Diff</th>
                      </thead>
                    ]
                  : [
                      <thead>
                        <th></th>
                        <th>Self (% of total)</th>
                        <th>Total (% of total)</th>
                      </thead>
                    ]}
                {this.localIsCompared ? (
                  <tbody>
                    <tr>
                      <td>{this.dataType}</td>
                      <td>{this.formatColValue(this.tipDetail.baseline)}</td>
                      <td>{this.formatColValue(this.tipDetail.comparison)}</td>
                      <td>{getDiffTpl(this.tipDetail)}</td>
                    </tr>
                  </tbody>
                ) : (
                  <tbody>
                    <tr>
                      <td>{this.dataType}</td>
                      <td>{`${this.formatColValue(this.tipDetail.self)}(${this.tipDetail.selfPercent})`}</td>
                      <td>{`${this.formatColValue(this.tipDetail.total)}(${this.tipDetail.totalPercent})`}</td>
                    </tr>
                  </tbody>
                )}
              </table>
            ]}
          </div>
        </Teleport>
      </div>
    );
  }
});
