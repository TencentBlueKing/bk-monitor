/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, defineComponent, KeepAlive, nextTick, shallowRef, useTemplateRef } from 'vue';

import { Tab } from 'bkui-vue';

import AlarmRecords from './alarm-records';
import DimensionAnalysis from './dimension-analysis';
import AlarmCharts from './echarts/alarm-charts';
import { useDiagnosticNavigate } from '@/pages/alarm-center/composables/use-diagnostic-navigate';
import { ALARM_CENTER_PANEL_TAB_MAP, ALARM_CENTER_VIEW_TAB_MAP } from '@/pages/alarm-center/utils/constant';

import type { AlarmDetail } from '../../../typings/detail';
import type { DateValue } from '@blueking/date-picker';

import './alarm-view.scss';
export default defineComponent({
  name: 'AlarmView',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => null,
    },
    /** 业务ID */
    bizId: {
      type: Number,
    },
    /** 默认时间范围 */
    defaultTimeRange: {
      type: Array as unknown as PropType<DateValue>,
    },
  },
  emits: {
    relatedEventsTimeRange: (_val: string[]) => true,
  },
  setup(_props, { emit }) {
    const activeTab = shallowRef<string>(ALARM_CENTER_VIEW_TAB_MAP.DIMENSION);
    const tabWrapRef = useTemplateRef<HTMLDivElement>('tabWrap');
    /** 右侧 AI 诊断要求选中的维度，交给维度分析按已加载的维度列表匹配 */
    const navigateDimensions = shallowRef<string[]>([]);

    const handleTabChange = (v: string) => {
      activeTab.value = v;
    };
    const handleRelatedEventsTimeRange = (timeRange: string[]) => {
      emit('relatedEventsTimeRange', timeRange);
    };

    useDiagnosticNavigate(ALARM_CENTER_PANEL_TAB_MAP.VIEW, async filter => {
      if (filter.viewAnchor !== 'dimension-analysis') return;
      activeTab.value = ALARM_CENTER_VIEW_TAB_MAP.DIMENSION;
      navigateDimensions.value = filter.dimensions || [];
      await nextTick();
      tabWrapRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    return {
      activeTab,
      navigateDimensions,
      handleTabChange,
      handleRelatedEventsTimeRange,
    };
  },
  render() {
    return (
      <div class='alarm-view'>
        <div class='alarm-view-chart-wrapper'>
          <AlarmCharts
            bizId={this.bizId}
            defaultTimeRange={this.defaultTimeRange}
            detail={this.detail}
          />
        </div>
        <div
          ref='tabWrap'
          class='alarm-view-tab'
        >
          <Tab
            active={this.activeTab}
            type='unborder-card'
            onUpdate:active={this.handleTabChange}
          >
            <Tab.TabPanel
              label={this.$t('维度分析')}
              name={ALARM_CENTER_VIEW_TAB_MAP.DIMENSION}
            />
            <Tab.TabPanel
              label={this.$t('告警流转记录')}
              name={ALARM_CENTER_VIEW_TAB_MAP.ALARM_RECORDS}
            />
          </Tab>
          <KeepAlive>
            {this.activeTab === ALARM_CENTER_VIEW_TAB_MAP.DIMENSION && (
              <DimensionAnalysis
                alertId={this.detail?.id}
                bizId={this.bizId}
                defaultTimeRange={this.defaultTimeRange}
                detail={this.detail}
                graphPanel={this.detail?.graph_panel}
                navigateDimensions={this.navigateDimensions}
              />
            )}
            {this.activeTab === ALARM_CENTER_VIEW_TAB_MAP.ALARM_RECORDS && (
              <AlarmRecords
                detail={this.detail}
                onRelatedEventsTimeRange={this.handleRelatedEventsTimeRange}
              />
            )}
          </KeepAlive>
        </div>
      </div>
    );
  },
});
