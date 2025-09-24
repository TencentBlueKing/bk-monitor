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
import { computed, defineComponent, ref, watch } from 'vue';

import { formatDateTimeField, getRegExp, blobDownload } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import dayjs from 'dayjs';
import { debounce } from 'lodash-es';

import ChartRoot from './chart-root';
import useChartRender from './use-chart-render';

import './index.scss';

export default defineComponent({
  props: {
    chartOptions: {
      type: Object,
      default: () => ({}),
    },
    // 用于触发更新，避免直接监听chartData性能问题
    chartCounter: {
      type: Number,
      default: 0,
    },
  },
  setup(props, { slots }) {
    const refRootElement = ref();
    const refRootContent = ref();
    const searchValue = ref('');
    const { $t } = useLocale();
    const store = useStore();

    const { setChartOptions, destroyInstance, getChartInstance } = useChartRender({
      target: refRootElement,
      type: props.chartOptions.type,
    });

    const showTable = computed(() => props.chartOptions.type === 'table');
    const showNumber = computed(() => props.chartOptions.type === 'number');

    const formatListData = computed(() => {
      const {
        list = [],
        result_schema = [],
        select_fields_order = [],
        total_records = 0,
      } = props.chartOptions.data ?? {};
      const timeFields = result_schema.filter(item => /^date/.test(item.field_type));
      return {
        list: list.map(item => {
          return {
            ...item,
            ...timeFields.reduce((acc, cur) => {
              acc[cur.field_alias] = formatDateTimeField(item[cur.field_alias], cur.field_type);
              return acc;
            }, {}),
          };
        }),
        result_schema,
        select_fields_order,
        total_records,
      };
    });

    let updateTimer: any = null;
    const debounceUpdateChartOptions = (xFields, yFields, dimensions, type) => {
      updateTimer && clearTimeout(updateTimer);
      updateTimer = setTimeout(() => {
        setChartOptions(xFields, yFields, dimensions, formatListData.value, type);
      });
    };

    const tableData = ref([]);

    const getChildNodes = (parent, index) => {
      const field = props.chartOptions.xFields[index];
      if (field) {
        return (formatListData.value?.list ?? []).map(item =>
          getChildNodes({ ...parent, [field]: item[field] }, index + 1),
        );
      }

      return parent;
    };

    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    const setTableData = () => {
      if (showTable.value || showNumber.value) {
        if (props.chartOptions.category === 'table') {
          tableData.value.length = 0;
          tableData.value = [];
          for (const t of formatListData.value?.list ?? []) {
            tableData.value.push(t);
          }
          return;
        }

        const result = (props.chartOptions.yFields ?? []).map(yField => {
          const groups = showNumber.value ? [] : [...props.chartOptions.dimensions, props.chartOptions.xFields[0]];
          return [groups].map(([timeField, xField]) => {
            if (timeField || xField) {
              return (formatListData.value?.list ?? []).map(row => {
                const targetValue = [timeField, xField, yField].reduce((acc, cur) => {
                  if (cur && row[cur]) {
                    acc[cur] = row[cur];
                    return acc;
                  }

                  return acc;
                }, {});
                return getChildNodes(targetValue, 1);
              });
            }

            if (showNumber.value) {
              return (formatListData.value?.list ?? []).map(row => ({ [yField]: row[yField] }));
            }

            return [];
          });
        });

        const length = showNumber.value
          ? (props.chartOptions.yFields ?? []).length
          : [...props.chartOptions.dimensions, ...props.chartOptions.xFields].length *
            props.chartOptions.xFields.length;

        tableData.value.splice(0, tableData.value.length, ...result.flat(length + 1));
        return;
      }

      tableData.value.splice(0, tableData.value.length);
    };

    watch(
      () => props.chartCounter,
      () => {
        const { xFields, yFields, dimensions, type } = props.chartOptions;
        if (showTable.value || showNumber.value) {
          setTableData();
          destroyInstance();
          return;
        }

        debounceUpdateChartOptions(xFields, yFields, dimensions, type);
      },
    );

    const pagination = ref({
      current: 1,
      limit: 20,
    });

    const handlePageChange = newPage => {
      pagination.value.current = newPage;
    };

    const handlePageLimitChange = limit => {
      pagination.value.current = 1;
      pagination.value.limit = limit;
    };

    const columns = computed(() => {
      if (showTable.value) {
        if (props.chartOptions.category === 'table') {
          return (props.chartOptions.data?.select_fields_order ?? []).filter(
            col => !(props.chartOptions.hiddenFields ?? []).includes(col),
          );
        }

        if (props.chartOptions.category === 'number') {
          return props.chartOptions.yFields;
        }

        return [...props.chartOptions.dimensions, ...props.chartOptions.xFields, ...props.chartOptions.yFields];
      }

      return [];
    });

    const filterTableData = computed(() => {
      const reg = getRegExp(searchValue.value);
      const startIndex = (pagination.value.current - 1) * pagination.value.limit;
      const endIndex = startIndex + pagination.value.limit;

      return tableData.value.filter(data => columns.value.some(col => reg.test(data[col]))).slice(startIndex, endIndex);
    });

    const handleChartRootResize = debounce(() => {
      getChartInstance()?.resize();
    });

    const handleSearchClick = value => {
      searchValue.value = value;
    };

    const replacer = (_key, value) => {
      // 处理undefined或null等特殊值，转化为字符串
      return value === null ? '' : value;
    };

    const handleDownloadData = () => {
      const filename = `bklog_${store.state.indexId}_${dayjs(new Date()).format('YYYYMMDD_HHmmss')}.csv`;

      // 如果数据是一个对象数组并且需要提取表头
      if (tableData.value.length === 0) {
        console.error('No data to export');
        return;
      }

      // 提取表头
      const headers = columns.value;

      // 生成 CSV 字符串
      const csvContent = [
        headers.join(','), // 表头行
        ...tableData.value.map(row => headers.map(header => JSON.stringify(row[header], replacer)).join(',')), // 数据行
      ].join('\n');

      blobDownload(csvContent, filename);
    };

    const rendChildNode = () => {
      if (showNumber.value) {
        return (
          <div class='bklog-chart-number-container'>
            {tableData.value.map(row => (
              <div
                key={row}
                class='bklog-chart-number-list'
              >
                {props.chartOptions.yFields?.map(yField => (
                  <div
                    key={yField}
                    class='bklog-chart-number-item'
                  >
                    <div class='bklog-chart-number-label'>{yField}</div>
                    <div class='bklog-chart-number-value'>{row[yField]}</div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        );
      }

      if (showTable.value) {
        if (!tableData.value.length) {
          return '';
        }
        return [
          <div
            key='table-search'
            class='bklog-chart-result-table'
          >
            <bk-input
              style='width: 500px;'
              clearable={true}
              placeholder={$t('搜索')}
              right-icon='bk-icon icon-search'
              value={searchValue.value}
              onChange={handleSearchClick}
            />
            <div>
              {tableData.value.length > 0 ? (
                <span
                  style='font-size: 12px; color: #3A84FF; cursor: pointer;'
                  onClick={handleDownloadData}
                >
                  <i
                    style='font-size: 14px;'
                    class='bklog-icon bklog-download'
                  />
                  {$t('下载')}
                </span>
              ) : null}
              <bk-pagination
                style='display: inline-flex'
                class='top-pagination'
                count={tableData.value.length}
                current={pagination.value.current}
                limit={pagination.value.limit}
                location='right'
                show-total-count={true}
                size='small'
                small={true}
                onChange={handlePageChange}
                onLimit-change={handlePageLimitChange}
              />
            </div>
          </div>,
          <bk-table
            key='table-result'
            data={filterTableData.value}
          >
            <bk-table-column
              width='60'
              label={$t('行号')}
              type='index'
            />
            {columns.value.map(col => (
              <bk-table-column
                key={col}
                label={col}
                prop={col}
                sortable={true}
              />
            ))}
          </bk-table>,
        ];
      }

      return (
        <ChartRoot
          ref={refRootElement}
          class='chart-canvas'
          on-resize={handleChartRootResize}
        />
      );
    };

    const renderContext = () => {
      return (
        <div
          ref={refRootContent}
          class={['bklog-chart-container', { 'is-table': showTable.value }]}
        >
          {rendChildNode()}
          {slots.default?.()}
        </div>
      );
    };
    return {
      renderContext,
    };
  },
  render() {
    return this.renderContext();
  },
});
