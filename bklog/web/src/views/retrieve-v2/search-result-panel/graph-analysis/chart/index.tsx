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
import { computed, defineComponent, ref, watch, type Ref } from 'vue';

import { formatDateTimeField, getRegExp } from '@/common/util';
import useFieldAliasRequestParams from '@/hooks/use-field-alias-request-params';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import dayjs from 'dayjs';
import { debounce } from 'lodash-es';
import ChartRoot from './chart-root';
import useChartRender from './use-chart-render';
// import $http from '@/api/index';
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
  emits: ['sql-change'],
  setup(props, { slots }) {
    const refRootElement: Ref<HTMLElement> = ref();
    const sqlContent = computed(() => store.state.indexItem.chart_params.sql);
    const { alias_settings: aliasSettings } = useFieldAliasRequestParams();
    const refRootContent = ref();
    const searchValue = ref('');
    const { $t } = useLocale();
    const store = useStore();
    const indexSetId = computed(() => store.state.indexId);
    const retrieveParams = computed(() => store.getters.retrieveParams);
    const requestAddition = computed(() => store.getters.requestAddition);
    const { setChartOptions, destroyInstance, getChartInstance } = useChartRender({
      target: refRootElement,
      type: props.chartOptions.type,
    });

    const showTable = computed(() => props.chartOptions.type === 'table');
    const showNumber = computed(() => props.chartOptions.type === 'number');

    const formatListData = computed(() => {
      const {
        list = [],
        result_schema: resultSchema = [],
        select_fields_order: selectFieldsOrder = [],
        total_records: totalRecords = 0,
      } = props.chartOptions.data ?? {};
      const timeFields = resultSchema.filter(item => /^date/.test(item.field_type));
      return {
        list: list.map((item) => {
          return {
            ...item,
            ...timeFields.reduce((acc, cur) => {
              acc[cur.field_alias] = formatDateTimeField(item[cur.field_alias], cur.field_type);
              return acc;
            }, {}),
          };
        }),
        result_schema: resultSchema,
        select_fields_order: selectFieldsOrder,
        total_records: totalRecords,
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
        const list = formatListData.value?.list ?? [];
        return list.map(item => getChildNodes({ ...parent, [field]: item[field] }, index + 1));
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

        const result = (props.chartOptions.yFields ?? []).map((yField) => {
          const groups = showNumber.value ? [] : [...props.chartOptions.dimensions, props.chartOptions.xFields[0]];
          return [groups].map(([timeField, xField]) => {
            if (timeField || xField) {
              return (formatListData.value?.list ?? []).map((row) => {
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
          : [...props.chartOptions.dimensions, ...props.chartOptions.xFields].length
          * props.chartOptions.xFields.length;

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

    const handlePageChange = (newPage) => {
      pagination.value.current = newPage;
    };

    const handlePageLimitChange = (limit) => {
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

    const handleSearchClick = (value) => {
      searchValue.value = value;
    };
    /**
    * 检查浏览器是否支持 File System Access API
    */
    function supportsFileSystemAccess() {
      // @ts-ignore - File System Access API 可能不存在于类型定义中
      return 'showSaveFilePicker' in window;
    }
    async function downloadWithBlob(response, filename) {
      const blob = await response.blob();
      // 创建下载链接
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();

      // 清理
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 100);

      return { success: true, message: '文件下载完成' };
    }
    /**
    * 使用现代 File System Access API 下载（内存高效）
    * 使用手动读写方式，确保在 Mac 上正常工作
    */
    async function downloadWithFileSystemAPI(response, filename) {
      try {
        // @ts-ignore - File System Access API 可能不存在于类型定义中
        const fileHandle = await window.showSaveFilePicker({
          suggestedName: filename,
          types: [{
            description: 'CSV 文件',
            accept: {
              'text/csv': ['.csv'],
              'application/vnd.ms-excel': ['.csv'],
            },
          }],
        });

        const writable = await fileHandle.createWritable();
        const reader = response.body.getReader();

        try {
          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              break;
            }

            // 写入数据块
            await writable.write(value);
          }
        } finally {
          // 确保读取器释放
          reader.releaseLock();
        }

        // 重要：必须关闭可写流，否则文件可能不会保存（在 Mac 上尤其重要）
        await writable.close();

        return { success: true, message: '文件保存成功' };
      } catch (error) {
        if (error.name === 'AbortError') {
          return { success: false, message: '用户取消了保存' };
        }
        console.error('File System API 错误:', error);
        throw error;
      }
    }
    // 异步下载
    const handleAsyncDownloadData = async () => {
      const baseUrl = process.env.NODE_ENV === 'development' ? 'api/v1' : window.AJAX_URL_PREFIX.replace(/\/$/, '');
      const searchUrl = `/search/index_set/${indexSetId.value}/export_chart_data/`;
      const fileName = `bklog_${store.state.indexId}_${dayjs(new Date()).format('YYYYMMDD_HHmmss')}.csv`;
      const { start_time, end_time, keyword, sort_list } = retrieveParams.value;

      const requestData = {
        start_time,
        end_time,
        query_mode: 'sql',
        keyword,
        addition: requestAddition.value || '',
        sql: sqlContent.value || '',
        alias_settings: aliasSettings.value || '',
        sort_list,
      };
      try {
        const response = await fetch(`${baseUrl}${searchUrl}`, {
          method: 'POST',
          body: JSON.stringify(requestData),
          headers: {
            'Content-Type': 'application/json', // 明确设置请求类型
          },
        });

        if (!response.ok) {
          throw new Error(`下载失败: ${response.status} ${response.statusText}`);
        }

        // 检查浏览器是否支持 File System Access API
        let result;
        if (supportsFileSystemAccess()) {
          result = await downloadWithFileSystemAPI(response, fileName);
        } else {
          result = await downloadWithBlob(response, fileName);
        }

        if (!result.success) {
          console.warn('下载警告:', result.message);
        }
      } catch (error) {
        console.error('下载出错:', error);
        throw error;
      }
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
                  onClick={handleAsyncDownloadData}
                >
                  <i
                    style='font-size: 14px;'
                    class='bklog-icon bklog-download'
                  />
                  {$t('下载')}
                </span>
              ) : null}
              {/* {tableData.value.length > 0 ? (
                <span
                  style='font-size: 12px; color: #3A84FF; cursor: pointer;margin-left: 5px;'
                  onClick={handleDownloadData}
                >
                  <i
                    style='font-size: 14px;'
                    class='bklog-icon bklog-download'
                  />
                  {$t('下载')}
                </span>
              ) : null} */}

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
