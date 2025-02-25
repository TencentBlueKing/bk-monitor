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
import { Component, Provide, ProvideReactive, Ref, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { eventViewConfig } from 'monitor-api/modules/data_explorer';
import { getDataSourceConfig } from 'monitor-api/modules/grafana';
import { random } from 'monitor-common/utils';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import { APIType, getEventTopK } from './api-utils';
import DimensionFilterPanel from './components/dimension-filter-panel';
import EventExploreView from './components/event-explore-view';
import EventRetrievalHeader from './components/event-retrieval-header';
import EventRetrievalLayout from './components/event-retrieval-layout';

import type { IGetValueFnParams } from '../../components/retrieval-filter/utils';
import type { TimeRangeType } from '../../components/time-range/time-range';
import type { IFormData } from './typing';

import './event-explore.scss';
Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);

@Component
export default class EventRetrievalNew extends tsc<{ source: APIType }> {
  /** 来源 */
  @Prop({ default: APIType.MONITOR }) source: APIType;
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
  loading = false;

  formData: IFormData = {
    data_source_label: 'custom',
    data_type_label: 'event',
    table: '',
    query_string: '*',
    where: [],
    group_by: [],
    filter_dict: {},
  };

  dataIdList = [];

  fieldList = [];

  /** 公共参数 */
  @ProvideReactive('commonParams')
  get commonParams() {
    return {
      query_configs: [
        {
          ...this.formData,
        },
      ],
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    };
  }

  @Provide('handleTimeRangeChange')
  handleTimeRangeChange(timeRange: TimeRangeType) {
    this.timeRange = timeRange;
    this.getViewConfig();
  }

  handleDataIdChange(dataId: string) {
    this.formData.table = dataId;
    this.getViewConfig();
  }

  async handleEventTypeChange(dataType: { data_source_label: string; data_type_label: string }) {
    this.formData.data_source_label = dataType.data_source_label;
    this.formData.data_type_label = dataType.data_type_label;
    await this.getDataIdList();
    await this.getViewConfig();
  }

  handleImmediateRefresh() {
    this.refreshImmediate = random(4);
    this.getViewConfig();
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
      this.formData.table = list[0]?.id || '';
    }
  }

  async getViewConfig() {
    if (!this.formData.table) {
      this.fieldList = [];
      return;
    }
    this.loading = true;
    const data = await eventViewConfig({
      data_sources: [
        {
          data_source_label: this.formData.data_source_label,
          data_type_label: this.formData.data_type_label,
          table: this.formData.table,
        },
      ],
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    }).catch(() => ({ display_fields: [], entities: [], fields: [] }));
    this.loading = false;
    this.fieldList = data.fields || data.field;
    this.setRouteParams();
  }

  handleCloseDimensionPanel() {
    this.eventRetrievalLayoutRef.handleClickShrink(false);
  }

  async mounted() {
    this.getRouteParams();
    await this.getDataIdList(!this.formData.table);
    await this.getViewConfig();
  }

  async getRetrievalFilterValueData(params: IGetValueFnParams = {}) {
    return getEventTopK({
      limit: params?.limit || 5,
      query_configs: [
        {
          data_source_label: this.formData.data_source_label,
          data_type_label: this.formData.data_type_label,
          table: this.formData.table,
          filter_dict: {},
          where: params?.where || [],
          query_string: params?.queryString || '*',
        },
      ],
      fields: params?.fields || [],
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    });
  }

  /** 兼容以前的事件检索URL格式 */
  getRouteParams() {
    const { targets, from, to, timezone, refreshInterval } = this.$route.query;
    if (targets) {
      try {
        const targetsList = JSON.parse(decodeURIComponent(targets as string));
        const [
          {
            data: {
              query_configs: [
                {
                  data_type_label,
                  data_source_label,
                  result_table_id,
                  where,
                  query_string: queryString,
                  group_by: groupBy,
                  filter_dict: filterDict,
                },
              ],
            },
          },
        ] = targetsList;
        this.formData = {
          data_type_label,
          data_source_label,
          table: result_table_id,
          where: where || [],
          query_string: queryString || '',
          group_by: groupBy || [],
          filter_dict: filterDict || {},
        };

        this.timeRange = from ? [from as string, to as string] : DEFAULT_TIME_RANGE;
        this.timezone = (timezone as string) || getDefaultTimezone();
        this.refreshInterval = Number(refreshInterval) || -1;
      } catch (error) {
        console.log('route query:', error);
      }
    }
  }

  setRouteParams() {
    const { table: result_table_id, ...other } = this.formData;
    const query = {
      ...this.$route.query,
      from: this.timeRange[0],
      to: this.timeRange[1],
      timezone: this.timezone,
      refreshInterval: String(this.refreshInterval),
      targets: JSON.stringify([
        {
          data: {
            query_configs: [
              {
                ...other,
                result_table_id,
              },
            ],
          },
        },
      ]),
    };

    const targetRoute = this.$router.resolve({
      query,
    });

    /** 防止出现跳转当前地址导致报错 */
    if (targetRoute.resolved.fullPath !== this.$route.fullPath) {
      this.$router.replace({
        query,
      });
    }
  }

  render() {
    return (
      <div class='event-explore'>
        <div class='left-favorite-panel' />
        <div class='right-main-panel'>
          <EventRetrievalHeader
            dataIdList={this.dataIdList}
            formData={this.formData}
            refreshInterval={this.refreshInterval}
            timeRange={this.timeRange}
            timezone={this.timezone}
            onDataIdChange={this.handleDataIdChange}
            onEventTypeChange={this.handleEventTypeChange}
            onImmediateRefresh={this.handleImmediateRefresh}
            onRefreshChange={this.handleRefreshChange}
            onTimeRangeChange={this.handleTimeRangeChange}
            onTimezoneChange={this.handleTimezoneChange}
          />
          <div class='event-retrieval-content'>
            <RetrievalFilter
              fields={this.fieldList}
              getValueFn={this.getRetrievalFilterValueData}
            />
            <EventRetrievalLayout
              ref='eventRetrievalLayout'
              class='content-container'
            >
              <div
                class='dimension-filter-panel'
                slot='aside'
              >
                <DimensionFilterPanel
                  list={this.fieldList}
                  listLoading={this.loading}
                  onClose={this.handleCloseDimensionPanel}
                />
              </div>
              <div class='result-content-panel'>
                <EventExploreView commonParams={this.commonParams} />
              </div>
            </EventRetrievalLayout>
          </div>
        </div>
      </div>
    );
  }
}
