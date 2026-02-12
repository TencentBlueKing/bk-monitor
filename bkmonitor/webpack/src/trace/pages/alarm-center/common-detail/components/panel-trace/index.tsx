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
import { type PropType, defineComponent, toRef } from 'vue';

import deepmerge from 'deepmerge';

import TraceExploreTable from '../../../../trace-explore/components/trace-explore-table/trace-explore-table';
import { useAlertTraces } from '../../../composables/use-alert-traces';
import { ALERT_TRACE_FIELD_CONFIGS } from './constants';

import type { IDimensionField } from '../../../../trace-explore/typing';

import './index.scss';

export default defineComponent({
  name: 'PanelTrace',
  props: {
    /** 告警ID */
    alertId: String as PropType<string>,
  },
  setup(props) {
    const { traceList, traceQueryConfig, tableLoading, pagination, tableHasMoreData } = useAlertTraces(
      toRef(props, 'alertId')
    );

    const displayFields = [
      'trace_id',
      'trace_duration',
      'min_start_time',
      'root_span_name',
      'root_service',
      'root_service_span_name',
      'error_msg',
    ];

    const handleSliderShow = (openMode: '' | 'span' | 'trace', activeId: string) => {
      const query = deepmerge(traceQueryConfig.value, {
        where: [
          {
            key: openMode === 'span' ? 'span_id' : 'trace_id',
            operator: 'equal',
            value: [activeId],
          },
        ],
      });
      const newQuery = Object.entries(query).reduce((prev, [key, value]) => {
        if (typeof value === 'object') {
          prev[key] = decodeURIComponent(JSON.stringify(value));
        } else {
          prev[key] = value;
        }
        return prev;
      }, {});
      window.open(`#/trace/home/?${new URLSearchParams(newQuery).toString()}`);
    };

    const handleScrollToEnd = () => {
      pagination.offset += pagination.limit;
    };

    return {
      displayFields,
      traceList,
      traceQueryConfig,
      pagination,
      tableLoading,
      tableHasMoreData,
      handleSliderShow,
      handleScrollToEnd,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-trace'>
        <TraceExploreTable
          class='panel-trace-table'
          appName={this.traceQueryConfig?.app_name || ''}
          canSortFieldTypes={[]}
          displayFields={this.displayFields}
          enabledClickMenu={false}
          enabledDisplayFieldSetting={false}
          enableStatistics={false}
          mode='trace'
          scrollContainerSelector='.alarm-center-detail-box'
          showHeaderIcon={false}
          showOperation={false}
          sourceFieldConfigs={ALERT_TRACE_FIELD_CONFIGS as unknown as IDimensionField[]}
          tableData={this.traceList}
          tableHasScrollLoading={this.tableHasMoreData}
          tableLoading={this.tableLoading}
          onScrollToEnd={this.handleScrollToEnd}
          onSliderShow={this.handleSliderShow}
        />
      </div>
    );
  },
});
