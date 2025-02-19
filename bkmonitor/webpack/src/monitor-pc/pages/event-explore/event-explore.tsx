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
import { Component, ProvideReactive, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { eventViewConfig } from 'monitor-api/modules/data_explorer';
import { getDataSourceConfig } from 'monitor-api/modules/grafana';
import { random } from 'monitor-common/utils';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import DimensionFilterPanel from './components/dimension-filter-panel';
import EventRetrievalHeader from './components/event-retrieval-header';
import EventRetrievalLayout from './components/event-retrieval-layout';

import type { TimeRangeType } from '../../components/time-range/time-range';
import type { IFormData } from './typing';

import './event-explore.scss';
Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);

@Component
export default class EventRetrievalNew extends tsc<object> {
  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 时区
  @ProvideReactive('timezone') timezone: string = getDefaultTimezone();
  // 刷新间隔
  @ProvideReactive('refleshInterval') refreshInterval = -1;
  // 是否立即刷新
  @ProvideReactive('refleshImmediate') refreshImmediate = '';

  @ProvideReactive('formatTimeRange')
  get formatTimeRange() {
    return handleTransformToTimestamp(this.timeRange);
  }

  @Ref('eventRetrievalLayout') eventRetrievalLayoutRef: EventRetrievalLayout;

  timer = null;

  formData: IFormData = {
    data_source_label: 'custom',
    data_type_label: 'event',
    result_table_id: '',
    query_string: '*',
    where: [],
    group_by: [],
    filter_dict: {},
  };

  dataIdList = [];

  fieldList = [];

  handleDataIdChange(dataId: string) {
    this.formData.result_table_id = dataId;
  }

  handleEventTypeChange(dataType: { data_source_label: string; data_type_label: string }) {
    this.formData.data_source_label = dataType.data_source_label;
    this.formData.data_type_label = dataType.data_type_label;
    this.formData.result_table_id = '';
    this.getDataIdList();
  }

  handleImmediateRefresh() {
    this.refreshImmediate = random(4);
  }

  handleRefreshChange(value: number) {
    this.refreshInterval = value;
    this.timer && clearInterval(this.timer);
    if (value > -1) {
      this.timer = setInterval(() => {
        this.handleImmediateRefresh();
      }, value);
    }
  }

  handleTimeRangeChange(timeRange: TimeRangeType) {
    this.timeRange = timeRange;
  }

  handleTimezoneChange(timezone: string) {
    this.timezone = timezone;
  }

  async getDataIdList(init = true) {
    const list = await getDataSourceConfig({
      data_source_label: this.formData.data_source_label,
      data_type_label: this.formData.data_type_label,
    }).catch(() => []);
    this.dataIdList = list;
    if (init) {
      this.formData.result_table_id = list[0]?.id || '';
    }
  }

  async getViewConfig() {
    const data = await eventViewConfig({
      data_sources: [
        {
          data_source_label: this.formData.data_source_label,
          data_type_label: this.formData.data_type_label,
          table: this.formData.result_table_id,
        },
      ],
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    }).catch(() => ({ display_fields: [], entities: [], fields: [] }));

    this.fieldList = data.fields;
  }

  handleCloseDimensionPanel() {
    this.eventRetrievalLayoutRef.handleClickShrink(false);
  }

  async mounted() {
    await this.getDataIdList(!this.formData.result_table_id);
    await this.getViewConfig();
  }

  render() {
    return (
      <div class='event-explore'>
        <div class='left-favorite-panel' />
        <div class='right-main-panel'>
          <EventRetrievalHeader
            dataIdList={this.dataIdList}
            formData={this.formData}
            onDataIdChange={this.handleDataIdChange}
            onEventTypeChange={this.handleEventTypeChange}
            onImmediateRefresh={this.handleImmediateRefresh}
            onRefreshChange={this.handleRefreshChange}
            onTimeRangeChange={this.handleTimeRangeChange}
            onTimezoneChange={this.handleTimezoneChange}
          />
          <div class='event-retrieval-content'>
            <RetrievalFilter />
            <EventRetrievalLayout
              ref='eventRetrievalLayout'
              class='content-container'
            >
              <div
                class='dimension-filter-panel'
                slot='aside'
              >
                <DimensionFilterPanel
                  formData={this.formData}
                  list={this.fieldList}
                  onClose={this.handleCloseDimensionPanel}
                />
              </div>
              <div class='result-content-panel' />
            </EventRetrievalLayout>
          </div>
        </div>
      </div>
    );
  }
}
