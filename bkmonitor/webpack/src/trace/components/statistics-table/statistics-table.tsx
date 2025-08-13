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
import { computed, defineComponent, inject, onMounted, watch, watchEffect } from 'vue';
import { shallowRef } from 'vue';

import {
  type FilterValue,
  type PrimaryTableCol,
  type SortInfo,
  type TableProps,
  PrimaryTable,
} from '@blueking/tdesign-ui';
import { Loading, Message, Popover } from 'bkui-vue';
import { AngleDownFill, AngleUpFill } from 'bkui-vue/lib/icon';
import { traceDiagram, traceStatistics } from 'monitor-api/modules/apm_trace';
import { random } from 'monitor-common/utils';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';

import { statisticDiffTableSetting, statisticTableSetting } from '../../pages/main/inquire-content/table-settings';
import { useTraceStore } from '../../store/modules/trace';
import { updateTemporaryCompareTrace } from '../../utils/compare';
import EmptyStatus from '../empty-status/empty-status';

import './statistics-table.scss';

const IProps = {
  appName: {
    type: String,
    default: true,
  },
  traceId: {
    type: String,
    default: true,
  },
  compareTraceID: {
    type: String,
    default: '',
  },
};

export interface IFilterItem {
  type: string;
  value: '' | number | string;
}

type CustomSortChildField = '' | 'current' | 'difference' | 'refer';

type CustomSortField = '' | 'count' | 'max_duration' | 'min_duration' | 'P95' | 'sum_duration';

interface ICategoryItem {
  icon: string;
  value: string;
}

interface IServiceNameItem {
  icon: string;
  value: string;
}

interface ITableDataItem {
  category: ICategoryItem;
  comparison?: ITableDataItem;
  count: number;
  is_interval: boolean;
  isUseShow?: boolean;
  kind: { icon?: string; text: string; value: string };
  mark: string;
  max_duration: number;
  min_duration: number;
  P95: number;
  'resource.sdk.name': string;
  service_name: IServiceNameItem;
  span_name: string;
  sum_duration: number;
  'resource.service.name': {
    icon: string;
    value: string;
  };
}
interface ITableFilter {
  text: string;
  value: string;
}
type SortType = '' | 'asc' | 'desc';
type StaticTableCol = PrimaryTableCol<ITableDataItem> & {
  isUseShow?: boolean;
};

const transformFilter = (filters: ITableFilter[]) => {
  return filters.map(item => ({
    label: item.text,
    value: item.value,
  }));
};
// table filter 数组对象去重
const deduplicate = (list: ITableFilter[]) => {
  const compareList: any[] = [];
  const result: any[] = [];
  for (const item of list) {
    if (!compareList.includes(item.value)) {
      compareList.push(item.value);
      result.push(item);
    }
  }
  return result;
};
const createCommonTableColumnFilter = (list: ITableFilter[]) => {
  return {
    type: 'multiple',
    showConfirmAndReset: true,
    list: transformFilter(list),
    popupProps: {
      overlayInnerClassName: 'bkui-tdesign-table-custom-popup',
    },
  };
};
export default defineComponent({
  name: 'StatisticsTable',
  props: IProps,
  emits: ['updateCompare', 'update:loading', 'clearKeyword'],
  setup(props, { emit, expose }) {
    const { t } = useI18n();
    const isFullscreen = inject<boolean>('isFullscreen', false);
    const store = useTraceStore();
    let filter: IFilterItem | null = null;
    const reactiveFilter = shallowRef<IFilterItem>();

    // TODO：TS报错：variable used before its declaration。
    const endpointNameFilterList = shallowRef<ITableFilter[]>([]);
    const serviceNameFilterList = shallowRef<ITableFilter[]>([]);
    const sourceList = shallowRef<ITableFilter[]>([]);
    const categoryList = shallowRef<ITableFilter[]>([]);
    /** 是否对比模式 */
    const isCompareView = shallowRef(false);
    // 20230620 勿删

    /** 表格列配置 */
    const tempTableColumns = computed(
      () =>
        [
          {
            isUseShow: true,
            title: t('接口'),
            colKey: 'span_name',
            filter: {
              ...createCommonTableColumnFilter(endpointNameFilterList.value),
            },
            cell: (_, { row }) => (
              <div
                key={random(6)}
                class='link-column'
                onClick={() => handleToEndpoint(row?.['resource.service.name']?.value, row.span_name)}
              >
                <Popover
                  content={row.span_name}
                  popoverDelay={[200, 0]}
                >
                  <span class='link-text'>{row.span_name}</span>
                </Popover>
                <i class='icon-monitor icon-fenxiang' />
              </div>
            ),
          },
          {
            isUseShow: true,
            title: t('服务'),
            colKey: 'resource.service.name',
            filter: {
              ...createCommonTableColumnFilter(serviceNameFilterList.value),
            },
            cell: (_, { row }) => (
              <div
                key={random(6)}
                class='link-column classify-column'
                onClick={() => handleToService(row?.['resource.service.name']?.value)}
              >
                <img
                  alt=''
                  src={row?.['resource.service.name']?.icon}
                />
                <Popover
                  content={row?.['resource.service.name']?.value}
                  popoverDelay={[200, 0]}
                >
                  <span class='link-text'>{row?.['resource.service.name']?.value}</span>
                </Popover>
                <i class='icon-monitor icon-fenxiang' />
              </div>
            ),
          },
          {
            isUseShow: true,
            title: t('数据来源'),
            colKey: 'resource.sdk.name',
            filter: {
              ...createCommonTableColumnFilter(sourceList.value),
            },
          },
          {
            isUseShow: true,
            title: t('Span类型'),
            colKey: 'kind',
            filter: {
              ...createCommonTableColumnFilter(categoryList.value),
            },

            cell: (_, { row }) => (
              <div class='classify-column'>
                <img
                  alt=''
                  src={row.kind?.icon}
                />
                <span class='link-text'>{row.kind?.text}</span>
              </div>
            ),
          },
          {
            title: `${t('最大时间')}（μs）`,
            colKey: 'max_duration',
            sorter: true,
            width: 140,
          },
          {
            title: `${t('最小时间')}（μs）`,
            colKey: 'min_duration',
            sorter: true,
            width: 140,
          },
          {
            title: `${t('总时间')}（μs）`,
            colKey: 'sum_duration',
            sorter: true,
            width: 140,
          },
          {
            title: 'CP95（μs）',
            colKey: 'P95',
            sorter: true,
            width: 140,
          },
          {
            title: t('数量'),
            colKey: 'count',
            sorter: true,
            width: 90,
          },
          {
            title: t('操作'),
            width: 90,
            colKey: 'operation',
            cell: (_, { row }) => (
              <div style='display: flex;'>
                {/* TODO: 这里需要带什么参数去跳转页面 */}
                <div
                  style='width: 70px;'
                  class='link-column'
                  onClick={() => handleToTraceQuery(row)}
                >
                  <span
                    class='link-text'
                    title={t('Span检索')}
                  >
                    {t('Span检索')}
                  </span>
                  <i class='icon-monitor icon-fenxiang' />
                </div>
              </div>
            ),
          },
        ] as StaticTableCol[]
    );
    /** DIFF表格列配置 */
    const tempDiffTableColumns = computed(
      () =>
        [
          {
            isUseShow: true,
            title: t('接口'),
            colKey: 'span_name',
            filter: {
              ...createCommonTableColumnFilter(endpointNameFilterList.value),
            },
            cell: (_, { row }) => (
              <div
                key={random(6)}
                class='link-column'
                onClick={() => handleToEndpoint(row?.['resource.service.name']?.value, row.span_name)}
              >
                <Popover
                  content={row.span_name}
                  popoverDelay={[200, 0]}
                >
                  <span class='link-text'>{row.span_name}</span>
                </Popover>
                <i class='icon-monitor icon-fenxiang' />
              </div>
            ),
          },
          {
            isUseShow: true,
            title: t('服务'),
            colKey: 'resource.service.name',
            filter: {
              ...createCommonTableColumnFilter(serviceNameFilterList.value),
            },
            cell: (_, { row }) => (
              <div
                key={random(6)}
                class='link-column classify-column'
                onClick={() => handleToService(row?.['resource.service.name']?.value)}
              >
                <img
                  alt=''
                  src={row?.['resource.service.name']?.icon}
                />
                <Popover
                  content={row?.['resource.service.name']?.value}
                  popoverDelay={[200, 0]}
                >
                  <span class='link-text'>{row?.['resource.service.name']?.value}</span>
                </Popover>
                <i class='icon-monitor icon-fenxiang' />
              </div>
            ),
          },
          {
            isUseShow: true,
            title: t('数据来源'),
            colKey: 'resource.sdk.name',
            filter: {
              ...createCommonTableColumnFilter(sourceList.value),
            },
          },
          {
            isUseShow: true,
            title: t('Span类型'),
            colKey: 'kind',
            filter: {
              ...createCommonTableColumnFilter(categoryList.value),
            },
            cell: (_, { row }: { row: ITableDataItem }) => (
              <div class='classify-column'>
                <img
                  alt=''
                  src={row.kind?.icon}
                />
                <span class='link-text'>{row.kind?.text}</span>
              </div>
            ),
          },
          {
            title: () => (
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
                        style={
                          selectedField.value === 'max_duration' &&
                          selectedChildField.value === 'current' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('max_duration', 'current', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'max_duration' &&
                          selectedChildField.value === 'current' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
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
                        style={
                          selectedField.value === 'max_duration' &&
                          selectedChildField.value === 'refer' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('max_duration', 'refer', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'max_duration' &&
                          selectedChildField.value === 'refer' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('max_duration', 'refer', 'desc')}
                      />
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
                        style={
                          selectedField.value === 'max_duration' &&
                          selectedChildField.value === 'difference' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('max_duration', 'difference', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'max_duration' &&
                          selectedChildField.value === 'difference' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('max_duration', 'difference', 'desc')}
                      />
                    </span>
                  </div>
                </div>
              </div>
            ),
            colKey: 'max_duration',
            minWidth: 181,
            cell: (_, { row }: { cell: Record<string, string>; row: ITableDataItem }) => (
              <div
                key={random(6)}
                class='custom-cell'
              >
                <div class='custom-cell-child'>{setTextEllipsis(String(row.max_duration))}</div>
                <div class='custom-cell-child'>{setTextEllipsis(String(row.comparison.max_duration))}</div>
                <div class='custom-cell-child'>{getDiffValue(row, 'max_duration')}</div>
              </div>
            ),
          },
          {
            title: () => (
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
                        style={
                          selectedField.value === 'min_duration' &&
                          selectedChildField.value === 'current' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('min_duration', 'current', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'min_duration' &&
                          selectedChildField.value === 'current' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('min_duration', 'current', 'desc')}
                      />
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
                        style={
                          selectedField.value === 'min_duration' &&
                          selectedChildField.value === 'refer' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('min_duration', 'refer', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'min_duration' &&
                          selectedChildField.value === 'refer' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('min_duration', 'refer', 'desc')}
                      />
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
                        style={
                          selectedField.value === 'min_duration' &&
                          selectedChildField.value === 'difference' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('min_duration', 'difference', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'min_duration' &&
                          selectedChildField.value === 'difference' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('min_duration', 'difference', 'desc')}
                      />
                    </span>
                  </div>
                </div>
              </div>
            ),
            colKey: 'min_duration',
            minWidth: 181,
            cell: (_, { row }) => (
              <div
                key={random(6)}
                class='custom-cell'
              >
                <div class='custom-cell-child'>{setTextEllipsis(String(row.min_duration))}</div>
                <div class='custom-cell-child'>{setTextEllipsis(String(row.comparison.min_duration))}</div>
                <div class='custom-cell-child'>{getDiffValue(row, 'min_duration')}</div>
              </div>
            ),
          },
          {
            title: () => (
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
                        style={
                          selectedField.value === 'sum_duration' &&
                          selectedChildField.value === 'current' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('sum_duration', 'current', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'sum_duration' &&
                          selectedChildField.value === 'current' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('sum_duration', 'current', 'desc')}
                      />
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
                        style={
                          selectedField.value === 'sum_duration' &&
                          selectedChildField.value === 'refer' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('sum_duration', 'refer', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'sum_duration' &&
                          selectedChildField.value === 'refer' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('sum_duration', 'refer', 'desc')}
                      />
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
                        style={
                          selectedField.value === 'sum_duration' &&
                          selectedChildField.value === 'difference' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('sum_duration', 'difference', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'sum_duration' &&
                          selectedChildField.value === 'difference' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('sum_duration', 'difference', 'desc')}
                      />
                    </span>
                  </div>
                </div>
              </div>
            ),
            colKey: 'sum_duration',
            minWidth: 181,
            cell: (_, { row }) => (
              <div
                key={random(6)}
                class='custom-cell'
              >
                <div class='custom-cell-child'>{setTextEllipsis(String(row.sum_duration))}</div>
                <div class='custom-cell-child'>{setTextEllipsis(String(row.comparison.sum_duration))}</div>
                <div class='custom-cell-child'>{getDiffValue(row, 'sum_duration')}</div>
              </div>
            ),
          },
          {
            title: () => (
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
                        style={
                          selectedField.value === 'P95' &&
                          selectedChildField.value === 'current' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('P95', 'current', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'P95' &&
                          selectedChildField.value === 'current' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('P95', 'current', 'desc')}
                      />
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
                        style={
                          selectedField.value === 'P95' &&
                          selectedChildField.value === 'refer' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('P95', 'refer', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'P95' &&
                          selectedChildField.value === 'refer' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('P95', 'refer', 'desc')}
                      />
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
                        style={
                          selectedField.value === 'P95' &&
                          selectedChildField.value === 'difference' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('P95', 'difference', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'P95' &&
                          selectedChildField.value === 'difference' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('P95', 'difference', 'desc')}
                      />
                    </span>
                  </div>
                </div>
              </div>
            ),
            colKey: 'P95',
            minWidth: 181,
            cell: (_, { row }) => (
              <div
                key={random(6)}
                class='custom-cell'
              >
                <div class='custom-cell-child'>{setTextEllipsis(String(row.P95))}</div>
                <div class='custom-cell-child'>{setTextEllipsis(String(row.comparison.P95))}</div>
                <div class='custom-cell-child'>{getDiffValue(row, 'P95')}</div>
              </div>
            ),
          },
          {
            title: () => (
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
                        style={
                          selectedField.value === 'count' &&
                          selectedChildField.value === 'current' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('count', 'current', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'count' &&
                          selectedChildField.value === 'current' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('count', 'current', 'desc')}
                      />
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
                        style={
                          selectedField.value === 'count' &&
                          selectedChildField.value === 'refer' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('count', 'refer', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'count' &&
                          selectedChildField.value === 'refer' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('count', 'refer', 'desc')}
                      />
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
                        style={
                          selectedField.value === 'count' &&
                          selectedChildField.value === 'difference' &&
                          selectedSortType.value === 'asc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-up'
                        onClick={() => handleCustomHeaderSort('count', 'difference', 'asc')}
                      />
                      <AngleUpFill
                        style={
                          selectedField.value === 'count' &&
                          selectedChildField.value === 'difference' &&
                          selectedSortType.value === 'desc' &&
                          'color: #3a84ff;'
                        }
                        class='icon-down'
                        onClick={() => handleCustomHeaderSort('count', 'difference', 'desc')}
                      />
                    </span>
                  </div>
                </div>
              </div>
            ),
            colKey: 'count',
            minWidth: 181,
            cell: (_, { row }) => (
              <div
                key={random(6)}
                class='custom-cell'
              >
                <div class='custom-cell-child'>{setTextEllipsis(String(row.count))}</div>
                <div class='custom-cell-child'>{setTextEllipsis(String(row.comparison.count))}</div>
                <div class='custom-cell-child'>{getDiffValue(row, 'count')}</div>
              </div>
            ),
          },
          {
            title: t('操作'),
            cell: (_, { row }) => (
              <div style='display: flex;'>
                {/* TODO: 这里需要带什么参数去跳转页面 */}
                <div
                  style='width: 70px;'
                  class='link-column'
                  onClick={() => handleToTraceQuery(row)}
                >
                  <span
                    class='link-text'
                    title={t('Span检索')}
                  >
                    {t('Span检索')}
                  </span>
                  <i class='icon-monitor icon-fenxiang' />
                </div>
              </div>
            ),
            colKey: 'operation',
            fixed: 'right',
            width: 91,
          },
        ] as StaticTableCol[]
    );

    const tableColumns = computed(() => {
      if (isLoading.value) return [];
      return (isCompareView.value ? tempDiffTableColumns : tempTableColumns).value.filter(item => {
        if (item.isUseShow) {
          return (
            (item.colKey === 'span_name' && store.traceViewFilters.includes('endpoint')) ||
            (item.colKey === 'resource.service.name' && store.traceViewFilters.includes('service')) ||
            (item.colKey === 'resource.sdk.name' && store.traceViewFilters.includes('source')) ||
            (item.colKey === 'kind' && store.traceViewFilters.includes('spanKind'))
          );
        }
        return true;
      });
    });

    // 选中的排序字段。
    const selectedField = shallowRef<CustomSortField>('');
    const selectedChildField = shallowRef<CustomSortChildField>('');
    const selectedSortType = shallowRef<SortType>('');
    const mapOfSortType = ['desc', 'asc', ''];
    // table sort info
    const sortInfo = shallowRef<SortInfo>({ sortBy: '', descending: false });
    const filterValue = shallowRef<TableProps['filterValue']>();
    const isLoading = shallowRef<boolean>(false);

    const originalDiffTableData = shallowRef<ITableDataItem[]>([]);
    const originalBaseTableData = shallowRef<ITableDataItem[]>([]);
    const diffTableData = shallowRef<ITableDataItem[]>([]);
    const baseTableData = shallowRef<ITableDataItem[]>([]);

    /** 表格配置 */
    const tableSettings = shallowRef(statisticTableSetting);
    /** 对比表格配置 */
    const diffTableSettings = shallowRef(statisticDiffTableSetting);
    /** 记录初始化状态 */
    const isInit = shallowRef(false);

    const tableData = computed(() => {
      if (isLoading.value) return [];
      return isCompareView.value ? diffTableData.value : baseTableData.value;
    });

    const originTableData = computed(() => {
      if (isLoading.value) return [];
      return isCompareView.value ? originalDiffTableData.value : originalBaseTableData.value;
    });

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
      console.info('sortField', selectedField.value, selectedSortType.value, selectedChildField.value);
      sortTableData();
    };
    /** 对比模式下的数值排序 */
    const sortTableData = () => {
      if (selectedSortType.value) {
        const list = diffTableData.value.slice();
        list.sort((pre, next) => {
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
              preVal =
                (pre[selectedField.value] - pre.comparison[selectedField.value]) / pre.comparison[selectedField.value];

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
        diffTableData.value = list;
      } else {
        // 没有选择排序就取消排序，改回最初的数据。
        diffTableData.value = originalDiffTableData.value.slice();
      }
    };
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
        spanKind: 'kind',
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
      if (isLoading.value) return;

      const { appName, traceId } = props;
      const group_fields = getGroupFields();
      if (group_fields.length === 0) {
        Message({
          theme: 'error',
          message: `${t('请至少选择一项分组')}`,
          getContainer: isFullscreen ? document.querySelector('.table-wrap.is-show-detail') : '',
        });
        return;
      }
      const params = {
        app_name: appName,
        trace_id: traceId,
        filter,
        group_fields,
      };
      emit('update:loading', true);
      await traceStatistics(params)
        .then(data => {
          originalBaseTableData.value = data;
        })
        .finally(() => {
          emit('update:loading', false);
          isInit.value = true;
        });
    });

    onMounted(() => {
      isCompareView.value = !!props.compareTraceID || false;
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
    watch(originTableData, () => {
      endpointNameFilterList.value.length = 0;
      serviceNameFilterList.value.length = 0;
      sourceList.value.length = 0;
      categoryList.value.length = 0;
      for (const item of originTableData.value) {
        item.span_name &&
          endpointNameFilterList.value.push({
            text: item.span_name,
            value: item.span_name,
          });
        item?.['resource.service.name'] &&
          serviceNameFilterList.value.push({
            text: item?.['resource.service.name'].value,
            value: item?.['resource.service.name'].value,
          });
        item?.['resource.sdk.name'] &&
          sourceList.value.push({
            text: item?.['resource.sdk.name'],
            value: item?.['resource.sdk.name'],
          });
        item?.kind &&
          categoryList.value.push({
            text: item?.kind.text,
            value: item?.kind.value,
          });
      }
      endpointNameFilterList.value = deduplicate(endpointNameFilterList.value);
      serviceNameFilterList.value = deduplicate(serviceNameFilterList.value);
      sourceList.value = deduplicate(sourceList.value);
      categoryList.value = deduplicate(categoryList.value);
    });
    /** 表格搜索过滤 */
    const handleKeywordFilter = (filterDict: IFilterItem | null) => {
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
        const { appName, trace_id: sourceTraceID } = store.traceData;
        const group_fields = getGroupFields();
        if (group_fields.length === 0) {
          Message({
            theme: 'error',
            message: `${t('请至少选择一项分组')}`,
            getContainer: isFullscreen ? document.querySelector('.table-wrap.is-show-detail') : '',
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
          filter,
        };
        emit('update:loading', true);
        await traceDiagram(params)
          .then(data => {
            if (data.diagram_data) {
              isCompareView.value = true;
              originalDiffTableData.value = data.diagram_data;
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
    const getDiffValue = (data: ITableDataItem, field: string) => {
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
    /** 跳转traceId精确查询 */
    function handleToTraceQuery(row: ITableDataItem) {
      // 需要根据分组去拼装查询语句，每选择多一个分组，就多一个查询项。
      const query = [];
      if (store.traceViewFilters.includes('endpoint')) {
        query.push({
          key: 'span_name',
          value: row.span_name,
        });
      }
      if (store.traceViewFilters.includes('service')) {
        query.push({
          key: 'resource.service.name',
          value: row?.['resource.service.name']?.value,
        });
      }
      if (store.traceViewFilters.includes('source')) {
        // 查询值为 opentelemetry 就不参与该查询项
        if ((row?.['resource.sdk.name'] as string).toLowerCase() !== 'opentelemetry') {
          query.push({
            key: 'resource.sdk.name',
            value: row?.['resource.sdk.name'],
          });
        }
      }
      if (store.traceViewFilters.includes('spanKind')) {
        query.push({
          key: 'kind',
          value: row?.kind?.value,
        });
      }
      const where = [{ key: 'trace_id', operator: 'equal', value: [props.traceId] }];

      query.forEach(item => {
        where.push({
          key: item.key,
          operator: 'equal',
          value: [item.value],
        });
      });
      const hash = `#/trace/home?app_name=${props.appName}&sceneMode=span&where=${encodeURIComponent(JSON.stringify(where))}&filterMode=ui`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
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

    function filterValueChange(val: FilterValue) {
      filterValue.value = val;
    }
    /** 原始统计表格排序 */
    function handleColumnSort(info: TableProps['sort']) {
      sortInfo.value = (info as SortInfo) || { sortBy: '', descending: false };
    }
    watchEffect(() => {
      const sortList = isCompareView.value ? originalDiffTableData.value.slice() : originalBaseTableData.value.slice();
      const info = sortInfo.value;
      let sortData = [];
      sortInfo.value = (info as SortInfo) || { sortBy: '', descending: false };
      if (!info) {
        sortData = sortList;
      } else {
        const field = sortInfo.value.sortBy;
        if (sortInfo.value?.descending) {
          sortData = sortList.sort((pre, next) => next[field] - pre[field]);
        } else {
          sortData = sortList.sort((pre, next) => pre[field] - next[field]);
        }
      }
      const entries = Object.entries(filterValue.value || {}).filter(([key, value]) => value.length > 0);
      let list = [];
      if (entries.length > 0) {
        for (const item of sortData) {
          let filterFlag = false;
          if (entries.length > 0) {
            filterFlag = entries.every(([key, filters]) => {
              return filters.includes(item[key]) || filters.includes(item[key]?.value);
            });
          } else {
            filterFlag = true;
          }
          if (filterFlag) {
            list.push(item);
          }
        }
      } else {
        list = sortData;
      }
      if (isCompareView.value) {
        diffTableData.value = list;
        return;
      }
      baseTableData.value = list;
    });

    expose({
      handleKeywordFilter,
      viewCompare,
    });

    return {
      isLoading,
      sortInfo,
      filterValue,
      tableData,
      tableColumns,
      tableSettings,
      diffTableSettings,
      reactiveFilter,
      isCompareView,
      handleColumnSort,
      filterValueChange,
    };
  },

  render() {
    const emptyContent = () => {
      return (
        <EmptyStatus
          type={this.reactiveFilter?.value ? 'search-empty' : 'empty'}
          onOperation={() => this.$emit('clearKeyword')}
        />
      );
    };

    return (
      <Loading
        class='statistics-table-wrap'
        loading={this.isLoading}
      >
        <PrimaryTable
          height='100%'
          class={`statistics-table ${this.isCompareView ? 'statistics-diff-table' : ''}`}
          v-slots={{ empty: () => emptyContent() }}
          bkUiSettings={this.isCompareView ? this.diffTableSettings : this.tableSettings}
          columns={this.tableColumns}
          data={this.tableData.map(item => ({ ...item, id: item.id ?? random(6) }))}
          filterValue={this.filterValue}
          rowKey='id'
          sort={this.sortInfo}
          showSortColumnBgColor
          onFilterChange={this.filterValueChange}
          onSortChange={this.handleColumnSort}
        />
      </Loading>
    );
  },
});
