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

import {
  type PropType,
  defineComponent,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  Teleport,
  watch,
} from 'vue';

import { Exception } from 'bkui-vue';
import { sortTableGraph } from 'monitor-ui/chart-plugins/plugins/profiling-graph/table-graph/utils';
import {
  type ProfileDataUnit,
  parseProfileDataTypeValue,
} from 'monitor-ui/chart-plugins/plugins/profiling-graph/utils';
import { getSpanColorByName } from 'monitor-ui/chart-plugins/typings';
import { useI18n } from 'vue-i18n';

import type { DirectionType } from '../../../../typings';
import type {
  ITableTipsDetail,
  ProfilingTableItem,
  TableColumn,
} from 'monitor-ui/chart-plugins/typings/profiling-graph';

import './table-graph.scss';

const TABLE_BGCOLOR_COLUMN_WIDTH = 120;
const TABLE_PAGE_SIZE = 30;
export default defineComponent({
  name: 'ProfilingTableGraph',
  props: {
    textDirection: {
      type: String as PropType<DirectionType>,
      default: 'ltr',
    },
    unit: {
      type: String as () => ProfileDataUnit,
      default: '',
    },
    data: {
      type: Array as PropType<ProfilingTableItem[]>,
      default: () => [],
    },
    highlightId: {
      type: Number,
      default: -1,
    },
    highlightName: {
      type: String,
      default: '',
    },
    filterKeyword: {
      type: String,
      default: '',
    },
    // 对比模式
    isCompared: {
      type: Boolean,
      default: false,
    },
    // 数据类型
    dataType: {
      type: String,
      default: '',
    },
  },
  emits: ['sortChange', 'updateHighlightName'],
  setup(props, { emit }) {
    /** 表格数据 */
    const tableData = ref<ProfilingTableItem[]>([]);
    const tableColumns = ref<TableColumn[]>([
      { id: 'name', name: 'Location', sort: '' },
      { id: 'self', name: 'Self', mode: 'normal', sort: '' },
      { id: 'total', name: 'Total', mode: 'normal', sort: '' },
      { id: 'baseline', name: window.i18n.t('查询项'), mode: 'diff', sort: '' },
      { id: 'comparison', name: window.i18n.t('对比项'), mode: 'diff', sort: '' },
      { id: 'diff', name: 'Diff', mode: 'diff', sort: '' },
    ]);
    const tabelLoadingRef = ref<HTMLDivElement>();
    const maxItem = ref<{ self: number; total: number }>({
      self: 0,
      total: 0,
    });
    const tipDetail = shallowRef<ITableTipsDetail>({});
    const localIsCompared = ref(false);
    const sortKey = ref('');
    const sortType = ref('');
    let intersectionObserver: IntersectionObserver = null;
    const renderTableData = shallowRef([]);
    const hiddenLoading = ref(false);
    const { t } = useI18n();
    watch(
      () => props.data,
      (val: ProfilingTableItem[]) => {
        maxItem.value = {
          self: Math.max(...val.map(item => item.self)),
          total: Math.max(...val.map(item => item.total)),
        };
        sortKey.value = '';
        getTableData();
        tableColumns.value = tableColumns.value.map(item => ({ ...item, sort: '' }));
      },
      {
        immediate: true,
        // deep: true,
      }
    );
    watch(
      () => props.filterKeyword,
      () => {
        getTableData();
      }
    );

    function getTableData() {
      const filterList = JSON.parse(
        JSON.stringify(
          (props.data || [])
            .filter(item =>
              props.filterKeyword
                ? item.name.toLocaleLowerCase().includes(props.filterKeyword.toLocaleLowerCase())
                : true
            )
            .map(item => {
              const color = getSpanColorByName(item.name);
              return {
                ...item,
                color,
              };
            })
        )
      );
      tableData.value = sortTableGraph(filterList, sortKey.value, sortType.value);
      nextTick(() => {
        renderTableData.value = tableData.value.slice(0, TABLE_PAGE_SIZE);
      });
      localIsCompared.value = props.isCompared;
    }
    // Self 和 Total 值的展示
    function formatColValue(val: number) {
      const { value } = parseProfileDataTypeValue(val, props.unit);
      return value;
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
        'background-repeat': 'no-repeat',
      };
    }
    /** 列字段排序 */
    function handleSort(col: TableColumn) {
      switch (col.sort) {
        case 'asc':
          col.sort = 'desc';
          sortType.value = 'desc';
          sortKey.value = col.id;
          break;
        case 'desc':
          col.sort = '';
          sortType.value = '';
          sortKey.value = undefined;
          break;
        default:
          col.sort = 'asc';
          sortType.value = 'asc';
          sortKey.value = col.id;
      }
      emit('sortChange', sortKey.value);
      getTableData();
      tableColumns.value = tableColumns.value.map(item => {
        return {
          ...item,
          sort: col.id === item.id ? col.sort : '',
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
      }

      const { name, self, total, baseline, comparison, mark = '', diff = 0 } = row;
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
        diff,
        selfPercent: `${((self / totalItem.self) * 100).toFixed(2)}%`,
        totalPercent: `${((total / totalItem.total) * 100).toFixed(2)}%`,
      };
    }
    function handleRowMouseout() {
      tipDetail.value = {};
    }
    function handleHighlightClick(name) {
      let hightlightName = '';
      if (props.highlightName !== name) {
        hightlightName = name;
      }
      return emit('updateHighlightName', hightlightName);
    }
    function isInViewport(element: Element) {
      const rect = element.getBoundingClientRect();
      return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
      );
    }
    function handleTriggerObserver() {
      hiddenLoading.value = true;
      window.requestIdleCallback(() => {
        hiddenLoading.value = false;
      });
    }

    function observerTableLoading() {
      intersectionObserver = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (entry.intersectionRatio <= 0) return;
          if (renderTableData.value.length >= tableData.value.length) return;
          renderTableData.value.push(
            ...tableData.value.slice(renderTableData.value.length, renderTableData.value.length + TABLE_PAGE_SIZE)
          );
          nextTick(() => {
            if (isInViewport(tabelLoadingRef.value) && renderTableData.value.length < tableData.value.length) {
              handleTriggerObserver();
            }
          });
        }
      });
      intersectionObserver.observe(tabelLoadingRef.value);
    }
    onMounted(() => {
      observerTableLoading();
    });
    onBeforeUnmount(() => {
      intersectionObserver?.unobserve(tabelLoadingRef.value);
    });
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
      handleHighlightClick,
      tabelLoadingRef,
      hiddenLoading,
      renderTableData,
      t,
    };
  },
  render() {
    const getDiffTpl = row => {
      if (['removed', 'added'].includes(row.mark)) {
        return <span style={`color: ${row.mark === 'removed' ? '#ff5656' : '#2dcb56'}`}>{row.mark}</span>;
      }

      const { diff } = row;

      if (diff === 0) return <span style='color:#dddfe3'>0%</span>;

      return <span style={`color:${diff > 0 ? '#ff5656' : '#2dcb56'}`}>{`${(diff * 100).toFixed(2)}%`}</span>;
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
                          <i class={`icon-monitor icon-mc-arrow-down asc ${col.sort === 'asc' ? 'active' : ''}`} />
                          <i class={`icon-monitor icon-mc-arrow-down desc ${col.sort === 'desc' ? 'active' : ''}`} />
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
                {this.renderTableData.map(row => (
                  <tr
                    key={row.id}
                    class={row.name === this.highlightName ? 'hightlight' : ''}
                    onClick={() => this.handleHighlightClick(row.name)}
                    onMousemove={e => this.handleRowMouseMove(e, row)}
                    onMouseout={() => this.handleRowMouseout()}
                  >
                    <td>
                      <div class='location-info'>
                        <span
                          style={`background-color: ${!this.localIsCompared ? row.color : '#dcdee5'}`}
                          class='color-reference'
                        />
                        <span class={`text direction-${this.textDirection}`}>{row.name}</span>
                        {/* <div class='trace-mark'>Trace</div> */}
                      </div>
                    </td>
                    {this.localIsCompared
                      ? [
                          <td key={1}>{this.formatColValue(row.baseline)}</td>,
                          <td key={2}>{this.formatColValue(row.comparison)}</td>,
                          <td key={3}>{getDiffTpl(row)}</td>,
                        ]
                      : [
                          <td
                            key={4}
                            style={this.getColStyle(row, 'self')}
                          >
                            {this.formatColValue(row.self)}
                          </td>,
                          <td
                            key={5}
                            style={this.getColStyle(row, 'total')}
                          >
                            {this.formatColValue(row.total)}
                          </td>,
                        ]}
                  </tr>
                ))}
              </>
            ) : (
              <tr>
                <td colspan='3'>
                  <Exception
                    class='empty-table-exception'
                    description={this.t('搜索为空')}
                    scene='part'
                    type='search-empty'
                  />
                </td>
              </tr>
            )}
            <tr key='tabelLoadingRef'>
              <td colspan={3}>
                <div
                  ref='tabelLoadingRef'
                  style={{
                    display:
                      this.hiddenLoading || this.tableData.length <= this.renderTableData.length ? 'none' : 'flex',
                  }}
                  class='table-loading'
                >
                  {this.t('加载中...')}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <Teleport to='body'>
          <div
            style={{
              left: `${this.tipDetail.left || 0}px`,
              top: `${this.tipDetail.top || 0}px`,
              display: this.tipDetail.title ? 'block' : 'none',
            }}
            class='table-graph-row-tips'
          >
            {this.tipDetail.title && [
              <div
                key={1}
                class='funtion-name'
              >
                {this.tipDetail.title}
              </div>,
              <table
                key={2}
                class='tips-table'
              >
                {this.localIsCompared
                  ? [
                      <thead key={1}>
                        <th />
                        <th>{this.t('当前')}</th>
                        <th>{this.t('参照')}</th>
                        <th>{this.t('差异')}</th>
                      </thead>,
                    ]
                  : [
                      <thead key={2}>
                        <th />
                        <th>Self (% of total)</th>
                        <th>Total (% of total)</th>
                      </thead>,
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
              </table>,
            ]}
          </div>
        </Teleport>
      </div>
    );
  },
});
