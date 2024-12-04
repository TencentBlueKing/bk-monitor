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

import { formatDateTimeField, getRegExp } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import { debounce } from 'lodash';

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

    const { setChartOptions, destroyInstance, getChartInstance } = useChartRender({
      target: refRootElement,
      type: props.chartOptions.type,
    });

    const showTable = computed(() => props.chartOptions.type === 'table');

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
          return Object.assign(
            {},
            item,
            timeFields.reduce((acc, cur) => {
              return Object.assign(acc, { [cur.field_alias]: formatDateTimeField(item[cur.field_alias]) });
            }, {}),
          );
        }),
        result_schema,
        select_fields_order,
        total_records,
      };
    });

    let updateTimer = null;
    const debounceUpdateChartOptions = (xFields, yFields, dimensions, type) => {
      updateTimer && clearTimeout(updateTimer);
      updateTimer = setTimeout(() => {
        setChartOptions(xFields, yFields, dimensions, formatListData.value, type);
      });
    };

    watch(
      () => props.chartCounter,
      () => {
        const { xFields, yFields, dimensions, type } = props.chartOptions;
        if (!showTable.value) {
          debounceUpdateChartOptions(xFields, yFields, dimensions, type);
        } else {
          destroyInstance();
        }
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
      if (props.chartOptions.category === 'table') {
        return (props.chartOptions.data?.select_fields_order ?? []).filter(
          col => !(props.chartOptions.hiddenFields ?? []).includes(col),
        );
      }

      return props.chartOptions.data?.select_fields_order ?? [];
    });

    const tableData = computed(() => formatListData.value?.list ?? []);

    const filterTableData = computed(() => {
      const reg = getRegExp(searchValue.value);
      const startIndex = (pagination.value.current - 1) * pagination.value.limit;
      const endIndex = startIndex + pagination.value.limit;

      return tableData.value.filter(data => columns.value.some(col => reg.test(data[col]))).slice(startIndex, endIndex);
    });

    const handleChartRootResize = debounce(() => {
      console.log('resize');
      getChartInstance()?.resize();
    });

    const handleSearchClick = value => {
      searchValue.value = value;
    };

    const rendChildNode = () => {
      if (showTable.value) {
        if (!tableData.value.length) {
          return '';
        }
        return [
          <div class='bklog-chart-result-table'>
            <bk-input
              style='width: 500px;'
              clearable={true}
              placeholder={$t('搜索')}
              right-icon='bk-icon icon-search'
              value={searchValue.value}
              onChange={handleSearchClick}
            ></bk-input>
            <bk-pagination
              style='display: inline-flex'
              class='top-pagination'
              count={tableData.value.length}
              current={pagination.value.current}
              limit={pagination.value.limit}
              location='right'
              show-total-count={true}
              size='small'
              onChange={handlePageChange}
              onLimit-change={handlePageLimitChange}
            ></bk-pagination>
          </div>,
          <bk-table data={filterTableData.value}>
            <bk-table-column
              width='60'
              label={$t('行号')}
              type='index'
            ></bk-table-column>
            {columns.value.map(col => (
              <bk-table-column
                key={col}
                label={col}
                prop={col}
                sortable={true}
              ></bk-table-column>
            ))}
          </bk-table>,
        ];
      }

      return (
        <ChartRoot
          ref={refRootElement}
          class='chart-canvas'
          on-resize={handleChartRootResize}
        ></ChartRoot>
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
