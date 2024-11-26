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

import { formatDateTimeField } from '@/common/util';

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
    const { setChartOptions, destroyInstance } = useChartRender({
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
      const timeFieldList = result_schema.filter(item => /^date/.test(item.field_type));
      return {
        list: list.map(item => {
          const timeFields = timeFieldList.reduce((obj, field) => {
            const value = item[field.field_name];
            return Object.assign(obj, {
              [field.field_name]: formatDateTimeField(value, field.field_type),
              [`__origin_${field.field_name}`]: value,
            });
          }, {});
          return Object.assign(item, timeFields);
        }),
        result_schema,
        select_fields_order,
        total_records,
      };
    });

    watch(
      () => props.chartCounter,
      () => {
        const { xFields, yFields, dimensions, type } = props.chartOptions;
        if (!showTable.value) {
          setTimeout(() => {
            setChartOptions(xFields, yFields, dimensions, formatListData.value, type);
          });
        } else {
          destroyInstance();
        }
      },
    );

    const tableData = computed(() => formatListData.value?.list ?? []);
    const columns = computed(() => {
      if (props.chartOptions.category === 'table') {
        return (props.chartOptions.data?.select_fields_order ?? []).filter(
          col => !(props.chartOptions.hiddenFields ?? []).includes(col),
        );
      }

      return props.chartOptions.data?.select_fields_order ?? [];
    });
    const rendChildNode = () => {
      if (showTable.value) {
        return (
          <bk-table data={tableData.value}>
            {columns.value.map(col => (
              <bk-table-column
                key={col}
                label={col}
                prop={col}
              ></bk-table-column>
            ))}
          </bk-table>
        );
      }

      return (
        <div
          ref={refRootElement}
          class='chart-canvas'
        ></div>
      );
    };

    const renderContext = () => {
      return (
        <div class='bklog-chart-container'>
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
