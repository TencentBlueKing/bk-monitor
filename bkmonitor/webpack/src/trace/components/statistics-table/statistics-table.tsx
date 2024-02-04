/* eslint-disable codecc/comment-ratio */
/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable codecc/comment-ratio */
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

import { computed, defineComponent, inject, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Loading, Message, Popover, Table } from 'bkui-vue';
import { AngleDownFill, AngleUpFill } from 'bkui-vue/lib/icon';
import { debounce } from 'throttle-debounce';

import { traceDiagram, traceStatistics } from '../../../monitor-api/modules/apm_trace';
import { deepClone, random } from '../../../monitor-common/utils';
import { statisticDiffTableSetting, statisticTableSetting } from '../../pages/main/inquire-content/table-settings';
import { useTraceStore } from '../../store/modules/trace';
import { updateTemporaryCompareTrace } from '../../utils/compare';
import EmptyStatus from '../empty-status/empty-status';

import './statistics-table.scss';

const IProps = {
  appName: {
    type: String,
    default: true
  },
  traceId: {
    type: String,
    default: true
  },
  compareTraceID: {
    type: String,
    default: ''
  }
};

export interface IFilterItem {
  type: string;
  value: string | number | '';
}

interface IServiceNameItem {
  icon: string;
  value: string;
}

interface ICategoryItem {
  icon: string;
  value: string;
}

interface ItableDataItem {
  span_name: string;
  service_name: IServiceNameItem;
  max_duration: number;
  min_duration: number;
  sum_duration: number;
  P95: number;
  count: number;
  category: ICategoryItem;
  'resource.sdk.name': string;
  kind: { text: string; value: string; icon?: string };
  mark: string;
  comparison?: ItableDataItem;
  'resource.service.name': {
    value: string;
    icon: string;
  };
  is_interval: boolean;
}

interface ITableFilter {
  text: string;
  value: string;
}

type CustomSortField = 'max_duration' | 'min_duration' | 'sum_duration' | 'P95' | 'count' | '';
type CustomSortChildField = 'current' | 'refer' | 'difference' | '';
type SortType = 'desc' | 'asc' | '';

export default defineComponent({
  name: 'StatisticsTable',
  props: IProps,
  emits: ['updateCompare', 'update:loading'],
  setup(props, { emit, expose }) {
    const { t } = useI18n();
    const isFullscreen = inject<boolean>('isFullscreen', false);
    const store = useTraceStore();
    let filter: IFilterItem | null = null;
    const reactiveFilter = ref({});
    // table filter 数组对象去重
    function deduplicate(list: ITableFilter[]) {
      const compareList: any[] = [];
      const result: any[] = [];
      list.forEach(item => {
        if (!compareList.includes(item.value)) {
          compareList.push(item.value);
          result.push(item);
        }
      });
      return result;
    }
    // TODO：TS报错：variable used before its declaration。
    const endpointNameFilterList = ref<ITableFilter[]>([]);
    const serviceNameFilterList = ref<ITableFilter[]>([]);
    const sourceList = ref<ITableFilter[]>([]);
    const categoryList = ref<ITableFilter[]>([]);
    /** 是否对比模式 */
    const isCompareView = ref(false);
    // 20230620 勿删
    /** 表格列配置 */
    const tempTableColumns = [
      {
        isUseShow: true,
        label: t('接口'),
        field: 'span_name',
        filter: {
          list: endpointNameFilterList,
          filterFn: (selected, row, column) => {
            return selected.length ? selected.includes(row[column.field]) : true;
          }
        },
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div
            class='link-column'
            key={random(6)}
            onClick={() => handleToEndpoint(row?.['resource.service.name']?.value, row.span_name)}
          >
            <Popover
              content={row.span_name}
              popoverDelay={[200, 0]}
            >
              <span class='link-text'>{row.span_name}</span>
            </Popover>
            <i class='icon-monitor icon-fenxiang'></i>
          </div>
        )
      },
      {
        isUseShow: true,
        label: t('服务'),
        field: 'resource.service.name',
        filter: {
          list: serviceNameFilterList,
          filterFn: (selected, row, column) => {
            return selected.length ? selected.includes(row[column.field].value) : true;
          }
        },
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div
            class='link-column classify-column'
            key={random(6)}
            onClick={() => handleToService(row?.['resource.service.name']?.value)}
          >
            <img
              src={row?.['resource.service.name']?.icon}
              alt=''
            />
            <Popover
              content={row?.['resource.service.name']?.value}
              popoverDelay={[200, 0]}
            >
              <span class='link-text'>{row?.['resource.service.name']?.value}</span>
            </Popover>
            <i class='icon-monitor icon-fenxiang'></i>
          </div>
        )
      },
      {
        isUseShow: true,
        label: t('数据来源'),
        field: 'resource.sdk.name',
        filter: {
          list: sourceList
        }
      },
      {
        isUseShow: true,
        label: t('Span类型'),
        field: 'kind',
        filter: {
          list: categoryList,
          filterFn: (selected, row, column) => {
            return selected.length ? selected.includes(row[column.field].value) : true;
          }
        },
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div class='classify-column'>
            <img
              src={row.kind?.icon}
              alt=''
            />
            <span class='link-text'>{row.kind?.text}</span>
          </div>
        )
      },
      {
        label: `${t('最大时间')}（μs）`,
        field: 'max_duration',
        sort: true,
        width: 140
      },
      {
        label: `${t('最小时间')}（μs）`,
        field: 'min_duration',
        sort: true,
        width: 140
      },
      {
        label: `${t('总时间')}（μs）`,
        field: 'sum_duration',
        sort: true,
        width: 140
      },
      {
        label: 'CP95（μs）',
        field: 'P95',
        sort: true,
        width: 140
      },
      {
        label: t('数量'),
        field: 'count',
        sort: true,
        width: 90
      },
      {
        label: t('操作'),
        width: 160,
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div style='display: flex;'>
            {/* TODO: 这里需要带什么参数去跳转页面 */}
            <div
              class='link-column'
              onClick={() => handleToTraceQuery(row)}
              style='width: 70px;'
            >
              <span
                class='link-text'
                title={t('Span检索')}
              >
                {t('Span检索')}
              </span>
              <i class='icon-monitor icon-fenxiang'></i>
            </div>

            {/* TODO: 这里需要带什么参数去跳转页面 */}
            <Popover
              content={t('该数据是internal类型，没有对应的观测场景。')}
              popoverDelay={[200, 0]}
              disabled={!row.is_interval}
            >
              <div
                class='link-column'
                onClick={() => !row.is_interval && handleToObserve(row)}
                style={{
                  marginLeft: '10px',
                  color: row.is_interval ? '#dcdee5 !important' : '#3a84ff',
                  cursor: row.is_interval ? 'not-allowed !important' : 'pointer'
                }}
              >
                <span
                  class='link-text'
                  style={{
                    color: row.is_interval ? '#dcdee5 !important' : '#3a84ff',
                    cursor: row.is_interval ? 'not-allowed !important' : 'pointer'
                  }}
                >
                  {t('观测')}
                </span>
                <i class='icon-monitor icon-fenxiang'></i>
              </div>
            </Popover>
          </div>
        )
      }
    ];
    /** 表格列配置 */
    const tempDiffTableColumns = [
      {
        isUseShow: true,
        label: t('接口'),
        field: 'span_name',
        filter: {
          list: endpointNameFilterList,
          filterFn: (selected, row, column) => {
            return selected.length ? selected.includes(row[column.field]) : true;
          }
        },
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div
            class='link-column'
            key={random(6)}
            onClick={() => handleToEndpoint(row?.['resource.service.name']?.value, row.span_name)}
          >
            <Popover
              content={row.span_name}
              popoverDelay={[200, 0]}
            >
              <span class='link-text'>{row.span_name}</span>
            </Popover>
            <i class='icon-monitor icon-fenxiang'></i>
          </div>
        )
      },
      {
        isUseShow: true,
        label: t('服务'),
        field: 'resource.service.name',
        filter: {
          list: serviceNameFilterList,
          filterFn: (selected, row, column) => {
            return selected.length ? selected.includes(row[column.field].value) : true;
          }
        },
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div
            class='link-column classify-column'
            key={random(6)}
            onClick={() => handleToService(row?.['resource.service.name']?.value)}
          >
            <img
              src={row?.['resource.service.name']?.icon}
              alt=''
            />
            <Popover
              content={row?.['resource.service.name']?.value}
              popoverDelay={[200, 0]}
            >
              <span class='link-text'>{row?.['resource.service.name']?.value}</span>
            </Popover>
            <i class='icon-monitor icon-fenxiang'></i>
          </div>
        )
      },
      {
        isUseShow: true,
        label: t('数据来源'),
        field: 'resource.sdk.name',
        filter: {
          list: sourceList
        }
      },
      {
        isUseShow: true,
        label: t('Span类型'),
        field: 'kind',
        filter: {
          list: categoryList,
          filterFn: (selected, row, column) => {
            return selected.length ? selected.includes(row[column.field].value) : true;
          }
        },
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div class='classify-column'>
            <img
              src={row.kind?.icon}
              alt=''
            />
            <span class='link-text'>{row.kind?.text}</span>
          </div>
        )
      },
      {
        label: () => (
          <div style='width: 100%;'>
            <div class='custom-header-row-top'>{`${t('最大时间')}（μs）`}</div>
            <div class='custom-header-row-bottom'>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('max_duration', 'current')}
                >
                  {`${t('当前')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'max_duration' &&
                      selectedChildField.value === 'current' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('max_duration', 'current', 'asc')}
                  />
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'max_duration' &&
                      selectedChildField.value === 'current' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('max_duration', 'current', 'desc')}
                  />
                </span>
              </div>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('max_duration', 'refer')}
                >
                  {`${t('参照')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'max_duration' &&
                      selectedChildField.value === 'refer' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('max_duration', 'refer', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'max_duration' &&
                      selectedChildField.value === 'refer' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('max_duration', 'refer', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('max_duration', 'difference')}
                >
                  {`${t('差异值')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'max_duration' &&
                      selectedChildField.value === 'difference' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('max_duration', 'difference', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'max_duration' &&
                      selectedChildField.value === 'difference' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('max_duration', 'difference', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
            </div>
          </div>
        ),
        field: 'max_duration',
        width: 181,
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div
            class='custom-cell'
            key={random(6)}
          >
            <div class='custom-cell-child'>{setTextEllipsis(String(row.max_duration))}</div>
            <div class='custom-cell-child'>{setTextEllipsis(String(row.comparison.max_duration))}</div>
            <div class='custom-cell-child'>{getDiffValue(row, 'max_duration')}</div>
          </div>
        )
      },
      {
        label: () => (
          <div style='width: 100%;'>
            <div class='custom-header-row-top'>{`${t('最小时间')}（μs）`}</div>
            <div class='custom-header-row-bottom'>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('min_duration', 'current')}
                >
                  {`${t('当前')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'min_duration' &&
                      selectedChildField.value === 'current' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('min_duration', 'current', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'min_duration' &&
                      selectedChildField.value === 'current' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('min_duration', 'current', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('min_duration', 'refer')}
                >
                  {`${t('参照')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'min_duration' &&
                      selectedChildField.value === 'refer' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('min_duration', 'refer', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'min_duration' &&
                      selectedChildField.value === 'refer' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('min_duration', 'refer', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('min_duration', 'difference')}
                >
                  {`${t('差异值')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'min_duration' &&
                      selectedChildField.value === 'difference' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('min_duration', 'difference', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'min_duration' &&
                      selectedChildField.value === 'difference' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('min_duration', 'difference', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
            </div>
          </div>
        ),
        field: 'min_duration',
        width: 181,
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div
            class='custom-cell'
            key={random(6)}
          >
            <div class='custom-cell-child'>{setTextEllipsis(String(row.min_duration))}</div>
            <div class='custom-cell-child'>{setTextEllipsis(String(row.comparison.min_duration))}</div>
            <div class='custom-cell-child'>{getDiffValue(row, 'min_duration')}</div>
          </div>
        )
      },
      {
        label: () => (
          <div style='width: 100%;'>
            <div class='custom-header-row-top'>{`${t('总时间')}（ms）`}</div>
            <div class='custom-header-row-bottom'>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('sum_duration', 'current')}
                >
                  {`${t('当前')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'sum_duration' &&
                      selectedChildField.value === 'current' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('sum_duration', 'current', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'sum_duration' &&
                      selectedChildField.value === 'current' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('sum_duration', 'current', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('sum_duration', 'refer')}
                >
                  {`${t('参照')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'sum_duration' &&
                      selectedChildField.value === 'refer' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('sum_duration', 'refer', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'sum_duration' &&
                      selectedChildField.value === 'refer' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('sum_duration', 'refer', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('sum_duration', 'difference')}
                >
                  {`${t('差异值')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'sum_duration' &&
                      selectedChildField.value === 'difference' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('sum_duration', 'difference', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'sum_duration' &&
                      selectedChildField.value === 'difference' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('sum_duration', 'difference', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
            </div>
          </div>
        ),
        field: 'sum_duration',
        width: 181,
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div
            class='custom-cell'
            key={random(6)}
          >
            <div class='custom-cell-child'>{setTextEllipsis(String(row.sum_duration))}</div>
            <div class='custom-cell-child'>{setTextEllipsis(String(row.comparison.sum_duration))}</div>
            <div class='custom-cell-child'>{getDiffValue(row, 'sum_duration')}</div>
          </div>
        )
      },
      {
        label: () => (
          <div style='width: 100%;'>
            <div class='custom-header-row-top'>{`${t('CP95')}（ms）`}</div>
            <div class='custom-header-row-bottom'>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('P95', 'current')}
                >
                  {`${t('当前')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'P95' &&
                      selectedChildField.value === 'current' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('P95', 'current', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'P95' &&
                      selectedChildField.value === 'current' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('P95', 'current', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('P95', 'refer')}
                >
                  {`${t('参照')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'P95' &&
                      selectedChildField.value === 'refer' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('P95', 'refer', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'P95' &&
                      selectedChildField.value === 'refer' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('P95', 'refer', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('P95', 'difference')}
                >
                  {`${t('差异值')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'P95' &&
                      selectedChildField.value === 'difference' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('P95', 'difference', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'P95' &&
                      selectedChildField.value === 'difference' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('P95', 'difference', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
            </div>
          </div>
        ),
        field: 'P95',
        width: 181,
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div
            class='custom-cell'
            key={random(6)}
          >
            <div class='custom-cell-child'>{setTextEllipsis(String(row.P95))}</div>
            <div class='custom-cell-child'>{setTextEllipsis(String(row.comparison.P95))}</div>
            <div class='custom-cell-child'>{getDiffValue(row, 'P95')}</div>
          </div>
        )
      },
      {
        label: () => (
          <div style='width: 100%;'>
            <div class='custom-header-row-top'>{`${t('总数')}（ms）`}</div>
            <div class='custom-header-row-bottom'>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('count', 'current')}
                >
                  {`${t('当前')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'count' &&
                      selectedChildField.value === 'current' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('count', 'current', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'count' &&
                      selectedChildField.value === 'current' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('count', 'current', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('count', 'refer')}
                >
                  {`${t('参照')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'count' &&
                      selectedChildField.value === 'refer' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('count', 'refer', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'count' &&
                      selectedChildField.value === 'refer' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('count', 'refer', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
              <div class='custom-header-row-bottom-child'>
                <span
                  class='custom-label-text'
                  onClick={() => handleCustomHeaderSort('count', 'difference')}
                >
                  {`${t('差异值')}`}
                </span>
                <span class='sort-icon'>
                  <AngleDownFill
                    class='icon-up'
                    style={
                      selectedField.value === 'count' &&
                      selectedChildField.value === 'difference' &&
                      selectedSortType.value === 'asc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('count', 'difference', 'asc')}
                  ></AngleDownFill>
                  <AngleUpFill
                    class='icon-down'
                    style={
                      selectedField.value === 'count' &&
                      selectedChildField.value === 'difference' &&
                      selectedSortType.value === 'desc' &&
                      'color: #3a84ff;'
                    }
                    onClick={() => handleCustomHeaderSort('count', 'difference', 'desc')}
                  ></AngleUpFill>
                </span>
              </div>
            </div>
          </div>
        ),
        field: 'count',
        width: 181,
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div
            class='custom-cell'
            key={random(6)}
          >
            <div class='custom-cell-child'>{setTextEllipsis(String(row.count))}</div>
            <div class='custom-cell-child'>{setTextEllipsis(String(row.comparison.count))}</div>
            <div class='custom-cell-child'>{getDiffValue(row, 'count')}</div>
          </div>
        )
      },
      {
        label: t('操作'),
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell, row }: { cell: Record<string, string>; row: ItableDataItem }) => (
          <div style='display: flex;'>
            {/* TODO: 这里需要带什么参数去跳转页面 */}
            <div
              class='link-column'
              onClick={() => handleToTraceQuery(row)}
              style='width: 70px;'
            >
              <span
                class='link-text'
                title={t('Span检索')}
              >
                {t('Span检索')}
              </span>
              <i class='icon-monitor icon-fenxiang'></i>
            </div>

            {/* TODO: 这里需要带什么参数去跳转页面 */}
            <Popover
              content={t('该数据是internal类型，没有对应的观测场景。')}
              popoverDelay={[200, 0]}
              disabled={!row.is_interval}
            >
              <div
                class='link-column'
                onClick={() => !row.is_interval && handleToObserve(row)}
                style={{
                  marginLeft: '10px',
                  color: row.is_interval ? '#dcdee5 !important' : '#3a84ff',
                  cursor: row.is_interval ? 'not-allowed !important' : 'pointer'
                }}
              >
                <span
                  class='link-text'
                  style={{
                    color: row.is_interval ? '#dcdee5 !important' : '#3a84ff',
                    cursor: row.is_interval ? 'not-allowed !important' : 'pointer'
                  }}
                >
                  {t('观测')}
                </span>
                <i class='icon-monitor icon-fenxiang'></i>
              </div>
            </Popover>
          </div>
        ),
        fixed: 'right',
        width: 151
      }
    ];
    /** 默认表格列配置 */
    const tableColumns = ref([]);
    /** 对比表格列配置 */
    const diffTableColumns = ref([]);
    // 选中的排序字段。
    const selectedField = ref<CustomSortField>('');
    const selectedChildField = ref<CustomSortChildField>('');
    const selectedSortType = ref<SortType>('');
    const mapOfSortType = ['desc', 'asc', ''];
    /** 表格自定义排序 */
    const handleCustomHeaderSort = (
      sortField: CustomSortField,
      sortChildField: CustomSortChildField,
      sortType?: SortType
    ) => {
      if (sortField === selectedField.value && sortChildField === selectedChildField.value) {
        const currentIndex = mapOfSortType.findIndex(type => type === selectedSortType.value);
        // 如果有 sortType 说明是通过按 上下 箭头，没有则为按 标签 进行排序。
        if (sortType) {
          // 这里需要判断重复点击同一个排序按钮的情况。
          if (sortType === selectedSortType.value) {
            // 为空则为取消排序。
            selectedSortType.value = '';
          } else {
            selectedSortType.value = sortType;
          }
        } else {
          selectedSortType.value = mapOfSortType[(currentIndex + 1) % mapOfSortType.length] as SortType;
        }
      } else {
        selectedSortType.value = 'desc';
        selectedField.value = sortField;
        selectedChildField.value = sortChildField;
      }
      sortTableData();
    };
    /** 对比模式下的数值排序 */
    const sortTableData = () => {
      if (selectedSortType.value) {
        tableData.value.sort((pre, next) => {
          let preVal = 0;
          let nextVal = 0;
          switch (selectedChildField.value) {
            case 'current':
              preVal = pre[selectedField.value];
              nextVal = next[selectedField.value];
              break;
            case 'refer':
              preVal = pre.comparison[selectedField.value];
              nextVal = next.comparison[selectedField.value];
              break;
            case 'difference':
              // eslint-disable-next-line max-len
              preVal =
                (pre[selectedField.value] - pre.comparison[selectedField.value]) / pre.comparison[selectedField.value];
              // eslint-disable-next-line max-len
              nextVal =
                (next[selectedField.value] - next.comparison[selectedField.value]) /
                next.comparison[selectedField.value];
              break;
            default:
              break;
          }
          if (selectedSortType.value === 'asc') {
            return preVal - nextVal;
          }
          return nextVal - preVal;
        });
      } else {
        // 没有选择排序就取消排序，改回最初的数据。
        tableData.value = deepClone(originalDiffTableData);
      }
    };

    const isLoading = ref<boolean>(false);
    /** 表格数据 */
    const tableData = ref<ItableDataItem[]>([]);
    /** 表格排序数据 */
    const originalSortTableData = ref<ItableDataItem[]>([]);
    /** 对比表格的原始数据 */
    let originalDiffTableData: ItableDataItem[] = [];
    /** 表格配置 */
    const tableSettings = ref(statisticTableSetting);
    /** 对比表格配置 */
    const diffTableSettings = ref(statisticDiffTableSetting);
    /** 记录初始化状态 */
    const isInit = ref(false);

    watch(
      () => props.traceId,
      () => {
        getTableData();
      }
    );
    /** 获取分组参数 */
    const getGroupFields = () => {
      const keyMap = {
        endpoint: 'span_name',
        service: 'resource.service.name',
        source: 'resource.sdk.name',
        spanKind: 'kind'
      };
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const group_fields = store.traceViewFilters.map(key => keyMap[key]);
      if (!isInit.value && group_fields.every(val => !val)) {
        // 兼容面板切换异步重新赋值工具栏初始值为空
        group_fields.splice(0, group_fields.length, ...['span_name', 'resource.service.name']);
      }
      return group_fields;
    };
    /** 获取表格数据 */
    const getTableData = debounce(300, async () => {
      tableColumns.value = tempTableColumns.filter(item => {
        if (item.isUseShow && item.field === 'span_name' && store.traceViewFilters.includes('endpoint')) return item;
        if (item.isUseShow && item.field === 'resource.service.name' && store.traceViewFilters.includes('service'))
          return item;
        if (item.isUseShow && item.field === 'resource.sdk.name' && store.traceViewFilters.includes('source'))
          return item;
        if (item.isUseShow && item.field === 'kind' && store.traceViewFilters.includes('spanKind')) return item;
        if (!item.isUseShow) return item;
      });
      if (isLoading.value) return;

      const { appName, traceId } = props;
      const group_fields = getGroupFields();
      if (group_fields.length === 0) {
        Message({
          theme: 'error',
          message: `${t('请至少选择一项分组')}`,
          getContainer: isFullscreen ? document.querySelector('.table-wrap.is-show-detail') : ''
        });
        return;
      }
      const params = {
        app_name: appName,
        trace_id: traceId,
        filter,
        group_fields
      };
      emit('update:loading', true);
      await traceStatistics(params)
        .then(data => {
          tableData.value = data;
          originalSortTableData.value = data;
          originalDiffTableData = data;
        })
        .finally(() => {
          emit('update:loading', false);
          isInit.value = true;
        });
    });

    onMounted(() => {
      isCompareView.value = !!props.compareTraceID ?? false;
    });

    watch(
      () => store.traceViewFilters,
      () => {
        // 切换到 trace 详情的其它 tab 时会触发 traceViewFilters 更新导致意料之外的请求，这里做一层判断。
        if (store.selectedTraceViewFilterTab === 'statistics') {
          if (isCompareView.value) {
            viewCompare(props.compareTraceID);
          } else {
            getTableData();
          }
        }
      }
    );

    // 收集 table filter 并对其内容去重。
    watch(tableData, () => {
      endpointNameFilterList.value.length = 0;
      serviceNameFilterList.value.length = 0;
      sourceList.value.length = 0;
      categoryList.value.length = 0;
      tableData.value.forEach(item => {
        item.span_name &&
          endpointNameFilterList.value.push({
            text: item.span_name,
            value: item.span_name
          });
        item?.['resource.service.name'] &&
          serviceNameFilterList.value.push({
            text: item?.['resource.service.name'].value,
            value: item?.['resource.service.name'].value
          });
        item?.['resource.sdk.name'] &&
          sourceList.value.push({
            text: item?.['resource.sdk.name'],
            value: item?.['resource.sdk.name']
          });
        item?.kind &&
          categoryList.value.push({
            text: item?.kind.value,
            value: item?.kind.value
          });
      });
      endpointNameFilterList.value = deduplicate(endpointNameFilterList.value);
      serviceNameFilterList.value = deduplicate(serviceNameFilterList.value);
      sourceList.value = deduplicate(sourceList.value);
      categoryList.value = deduplicate(categoryList.value);
    });
    /** 表格搜索过滤 */
    const handleKeywordFliter = (filterDict: IFilterItem | null) => {
      filter = filterDict;
      reactiveFilter.value = filterDict;
      if (isCompareView.value) {
        viewCompare(props.compareTraceID);
      } else {
        getTableData();
      }
    };
    /** 跳转服务 */
    const handleToService = (serviceName: string) => {
      const hash = `#/apm/service?filter-service_name=${serviceName}&filter-app_name=${props.appName}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };
    /** 跳转接口 */
    const handleToEndpoint = (serviceName: string, endpointName: string) => {
      const filters = store.traceViewFilters;
      // 单独点击 接口 链接也要考虑是否选择 服务 分组。
      if (filters.includes('service')) {
        const hash = `#/apm/service?filter-app_name=${props.appName}&filter-service_name=${serviceName}&sceneType=detail&sceneId=apm_service&dashboardId=service-default-endpoint&filter-endpoint_name=${endpointName}`;
        const url = location.href.replace(location.hash, hash);
        window.open(url, '_blank');
      } else {
        handleToEndpointPreview();
      }
    };
    /** 跳转接口概览页面，是因为某些数据不带有 服务 名称 */
    const handleToEndpointPreview = () => {
      const hash = `#/apm/application?filter-app_name=${props.appName}&sceneType=overview&sceneId=apm_application&dashboardId=endpoint`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };
    /** 对比 */
    const viewCompare = debounce(300, async (traceID: string) => {
      if (traceID) {
        diffTableColumns.value = tempDiffTableColumns.filter(item => {
          if (item.isUseShow && item.field === 'span_name' && store.traceViewFilters.includes('endpoint')) return item;
          if (item.isUseShow && item.field === 'resource.service.name' && store.traceViewFilters.includes('service'))
            return item;
          if (item.isUseShow && item.field === 'resource.sdk.name' && store.traceViewFilters.includes('source'))
            return item;
          if (item.isUseShow && item.field === 'kind' && store.traceViewFilters.includes('spanKind')) return item;
          if (!item.isUseShow) return item;
        });

        const { appName, trace_id: sourceTraceID } = store.traceData;
        const group_fields = getGroupFields();
        if (group_fields.length === 0) {
          Message({
            theme: 'error',
            message: `${t('请至少选择一项分组')}`,
            getContainer: isFullscreen ? document.querySelector('.table-wrap.is-show-detail') : ''
          });
          return;
        }
        const params = {
          bk_biz_id: window.bk_biz_id,
          app_name: appName,
          trace_id: sourceTraceID,
          diff_trace_id: traceID,
          diagram_type: 'statistics',
          group_fields,
          filter
        };
        emit('update:loading', true);
        await traceDiagram(params)
          .then(data => {
            if (data.diagram_data) {
              isCompareView.value = true;
              originalDiffTableData = deepClone(data.diagram_data);
              tableData.value = data.diagram_data;
              updateTemporaryCompareTrace(traceID);
              emit('updateCompare', true);
            }
          })
          // .catch((err) => {
          //   showCompareErrorMessage(err.message);
          // })
          .finally(() => emit('update:loading', false));
      } else {
        // 取消对比
        if (isCompareView.value) {
          isCompareView.value = false;
          emit('updateCompare', false);
          getTableData();
        }
      }
    });
    /** 获取对比差异值显示 */
    const getDiffValue = (data: ItableDataItem, field: string) => {
      if (['removed', 'added'].includes(data.mark)) {
        return <span style={`color: ${data.mark === 'removed' ? '#FF5656' : '#2DCB56'}`}>{data.mark}</span>;
      }
      const current = data[field];
      const comparison = data.comparison[field];
      const diffValue = (current - comparison) / comparison;
      if (diffValue === 0) return <span style='color:#dddfe3'>0%</span>;
      const textColor = diffValue > 0 ? '#2DCB56' : '#FF5656';
      const resultText = `${(diffValue * 100).toFixed(2)}%`;
      if (resultText.length > 5) {
        const tempStr = resultText;
        return (
          <Popover
            content={resultText}
            popoverDelay={[200, 0]}
          >
            <span style={`color: ${textColor}`}>{`${tempStr.substring(0, 5)}...`}</span>
          </Popover>
        );
      }
      return <span style={`color: ${textColor}`}>{resultText}</span>;
    };
    /** 原始统计表格排序 */
    const handleColumnSort = ({ column, index, type }) => {
      const sortList = deepClone(tableData.value);
      switch (type) {
        case 'asc':
          originalSortTableData.value = sortList.sort((pre, next) => pre[column.field] - next[column.field]);
          return;
        case 'desc':
          originalSortTableData.value = sortList.sort((pre, next) => next[column.field] - pre[column.field]);
          return;
        default:
          originalSortTableData.value = sortList;
      }
    };
    /** 跳转traceId精确查询 */
    function handleToTraceQuery(row: ItableDataItem) {
      // 需要根据分组去拼装查询语句，每选择多一个分组，就多一个查询项。
      const query = [];
      if (store.traceViewFilters.includes('endpoint')) {
        query.push({
          key: 'span_name',
          value: row.span_name
        });
      }
      if (store.traceViewFilters.includes('service')) {
        query.push({
          key: 'resource.service.name',
          value: row?.['resource.service.name']?.value
        });
      }
      if (store.traceViewFilters.includes('source')) {
        // 查询值为 opentelemetry 就不参与该查询项
        if ((row?.['resource.sdk.name'] as string).toLowerCase() !== 'opentelemetry') {
          query.push({
            key: 'resource.sdk.name',
            value: row?.['resource.sdk.name']
          });
        }
      }
      if (store.traceViewFilters.includes('spanKind')) {
        query.push({
          key: 'kind',
          value: row?.kind?.value
        });
      }
      let queryString = '';
      query.forEach((item, index) => {
        queryString += `${item.key}: "${item.value}"`;
        if (index < query.length - 1) queryString += ' AND ';
      });
      // eslint-disable-next-line no-useless-escape
      const hash = `#/trace/home?app_name=${props.appName}&search_type=scope&listType=span&trace_id=${props.traceId}&query=${queryString}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    function handleToObserve(data: ItableDataItem) {
      const filters = store.traceViewFilters;
      if (filters.includes('endpoint') && filters.includes('service')) {
        handleToEndpoint(data?.['resource.service.name']?.value, data.span_name);
      } else if (filters.includes('endpoint')) {
        handleToEndpointPreview();
      } else if (filters.includes('service')) {
        handleToService(data?.['resource.service.name']?.value);
      } else {
        handleToEndpointPreview();
      }
    }
    /**
     * 这个函数用于将文本截断并添加省略号
     */
    function setTextEllipsis(str: string) {
      // 避免直接操作原响应式对象属性导致无法排序
      const tempStr = str;
      // 如果字符串长度大于5
      if (str.length > 5) {
        const result = tempStr.substring(0, 5);

        // 返回前个字符并在末尾添加省略号
        return (
          <Popover
            content={tempStr}
            popoverDelay={[200, 0]}
          >
            <span>{`${result}...`}</span>
          </Popover>
        );
      }
      return <span>{tempStr}</span>;
    }

    expose({
      handleKeywordFliter,
      viewCompare
    });

    return {
      isLoading,
      tableColumns,
      diffTableColumns,
      tableData,
      originalSortTableData,
      tableSettings,
      diffTableSettings,
      reactiveFilter,
      isCompareView,
      handleColumnSort
    };
  },

  render() {
    const emptyContent = () => {
      const status = computed(() => {
        if (this.tableData.length === 0 && this.reactiveFilter?.value?.length > 0) return 'search-empty';
        return 'empty';
      });
      return (
        <EmptyStatus type={status.value}>
          <span></span>
        </EmptyStatus>
      );
    };

    return (
      <Loading
        class='statistics-table-wrap'
        loading={this.isLoading}
      >
        {!this.isCompareView ? (
          <Table
            height='100%'
            class='statistics-table'
            rowHeight={42}
            settings={this.tableSettings}
            columns={this.tableColumns}
            data={this.originalSortTableData}
            onColumnSort={this.handleColumnSort}
            v-slots={{ empty: () => emptyContent() }}
          />
        ) : (
          <Table
            height='100%'
            class='statistics-table statistics-diff-table'
            rowHeight={42}
            settings={this.diffTableSettings}
            columns={this.diffTableColumns}
            data={this.tableData}
            v-slots={{ empty: () => emptyContent() }}
            thead={{
              height: 84
            }}
            border={['row', 'col']}
            cell-class={(option: any) => option.field}
          />
        )}
      </Loading>
    );
  }
});
