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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { DEFAULT_TIME_RANGE } from '../../../../components/time-range/utils';
import DashboardTools from '../../../monitor-k8s/components/dashboard-tools';

import type { TimeRangeType } from '../../../../components/time-range/time-range';

import './event-retrieval-header.scss';
interface EventRetrievalNavBarEvents {
  onDataIdChange(val: string): void;
  onEventTypeChange(eventType: EventRetrievalNavBarProps['eventType']): void;
  onImmediateRefresh(): void;
  onRefreshChange(val: number): void;
  onTimeRangeChange(val: TimeRangeType): void;
  onTimezoneChange(val: string): void;
}

interface EventRetrievalNavBarProps {
  dataId?: string;
  eventType?: { data_source_label: string; data_type_label: string };
  refreshInterval?: number;
  timeRange?: TimeRangeType;
  timezone?: string;
}

@Component
export default class EventRetrievalHeader extends tsc<EventRetrievalNavBarProps, EventRetrievalNavBarEvents> {
  @Prop({ default: () => ({ data_source_label: 'custom', data_type_label: 'event' }) })
  eventType: EventRetrievalNavBarProps['eventType'];

  @Prop({ default: () => '' }) dataId: string;
  // 数据间隔
  @Prop({ default: () => DEFAULT_TIME_RANGE, type: Array }) timeRange: TimeRangeType;
  // 自动刷新数据间隔
  @Prop({ default: -1 }) readonly refreshInterval: number;
  // 时区
  @Prop({ type: String }) timezone: string;

  dataIdList = [];

  dataIdToggle = false;

  get selectDataIdName() {
    return this.dataIdList.find(item => item.id === this.dataId)?.name || '';
  }

  @Emit('dataIdChange')
  // 处理dataId变化
  handleDataIdChange(dataId: string) {
    return dataId;
  }

  handleDataIdToggle(toggle: boolean) {
    this.dataIdToggle = toggle;
  }

  @Emit('timeRangeChange')
  handleTimeRangeChange(val: TimeRangeType) {
    return val;
  }

  @Emit('timezoneChange')
  handleTimezoneChange(v: string) {
    return v;
  }

  @Emit('immediateRefresh')
  handleImmediateRefresh() {}

  @Emit('refreshChange')
  handleRefreshChange(v: number) {
    return v;
  }

  @Emit('eventTypeChange')
  handleEventTypeChange(type: 'custom' | 'log') {
    if (type === 'custom') return { data_source_label: 'custom', data_type_label: 'event' };
    return { data_source_label: 'bk_monitor', data_type_label: 'log' };
  }

  render() {
    return (
      <div class='event-retrieval-header'>
        <div class='header-left'>
          <div class='favorite-btn'>
            <i class='icon-monitor icon-back-right' />
            <span class='text'>{this.$t('收藏夹')}</span>
          </div>
          <div class='event-type-select'>
            <div
              class={{ item: true, active: this.eventType.data_source_label === 'custom' }}
              onClick={() => this.handleEventTypeChange('custom')}
            >
              {this.$t('自定义上报事件')}
            </div>
            <div
              class={{ item: true, active: this.eventType.data_source_label === 'bk_monitor' }}
              onClick={() => this.handleEventTypeChange('log')}
            >
              {this.$t('日志关键字')}
            </div>
          </div>
          <bk-select
            class='data-id-select'
            clearable={false}
            value={this.dataId}
            searchable
            onChange={this.handleDataIdChange}
            onToggle={this.handleDataIdToggle}
          >
            <div
              class='data-id-select-trigger'
              slot='trigger'
            >
              <span>
                <span class='prefix'>{this.$t('数据ID')}:</span>
                <span class='name'>{this.selectDataIdName}</span>
              </span>
              <span class={`icon-monitor icon-mc-arrow-down ${this.dataIdToggle ? 'expand' : ''}`} />
            </div>
            {this.dataIdList.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.name}
              />
            ))}
          </bk-select>
        </div>
        <div class='header-tools'>
          <DashboardTools
            isSplitPanel={false}
            menuList={[]}
            refreshInterval={this.refreshInterval}
            showDownSampleRange={false}
            showFullscreen={false}
            showListMenu={false}
            showSplitPanel={false}
            timeRange={this.timeRange}
            timezone={this.timezone}
            onImmediateRefresh={this.handleImmediateRefresh}
            onRefreshChange={this.handleRefreshChange}
            onTimeRangeChange={this.handleTimeRangeChange}
            onTimezoneChange={this.handleTimezoneChange}
          >
            {this.$slots.dashboardTools}
          </DashboardTools>
        </div>
      </div>
    );
  }
}
