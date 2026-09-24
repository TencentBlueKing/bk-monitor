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
import { type PropType, defineAsyncComponent, defineComponent, shallowRef, toRef } from 'vue';

import { storeToRefs } from 'pinia';

import TraceExploreTable from '../../../../trace-explore/components/trace-explore-table/trace-explore-table';
import { useAlertTraces } from '../../../composables/use-alert-traces';
import { ALERT_TRACE_FIELD_CONFIGS } from './constants';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { IDimensionField } from '../../../../trace-explore/typing';

import './index.scss';

const TraceSlider = defineAsyncComponent(
  () => import(/* webpackChunkName: "trace-slider" */ '@/components/trace-slider/trace-slider')
);

export default defineComponent({
  name: 'PanelTrace',
  props: {
    /** 告警ID */
    alertId: String as PropType<string>,
  },
  setup(props) {
    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    const { bizId } = storeToRefs(alarmCenterDetailStore);
    const { traceList, traceQueryConfig, tableLoading, pagination, tableHasMoreData } = useAlertTraces(
      toRef(props, 'alertId')
    );
    const sliderShow = shallowRef(false);
    const activeTraceId = shallowRef('');

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
      if (openMode === 'trace' && activeId) {
        activeTraceId.value = activeId;
        sliderShow.value = true;
        return;
      }
      sliderShow.value = false;
    };

    const handleSliderClose = () => {
      sliderShow.value = false;
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
      sliderShow,
      activeTraceId,
      bizId,
      handleSliderShow,
      handleSliderClose,
      handleScrollToEnd,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-trace'>
        <div class='alarm-center-detail-panel-trace-wrapper'>
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
        <TraceSlider
          appName={this.traceQueryConfig?.app_name || ''}
          bizId={this.bizId}
          isShow={this.sliderShow}
          traceId={this.activeTraceId}
          onSliderClose={this.handleSliderClose}
        />
      </div>
    );
  },
});
