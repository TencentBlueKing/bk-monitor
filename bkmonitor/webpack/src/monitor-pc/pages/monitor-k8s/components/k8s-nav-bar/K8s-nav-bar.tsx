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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import TemporaryShareNew from '../../../../components/temporary-share/temporary-share';
import { DEFAULT_TIME_RANGE } from '../../../../components/time-range/utils';
import DashboardTools from '../dashboard-tools';
import GotoOldVersion from './goto-old';

import type { TimeRangeType } from '../../../../components/time-range/time-range';

import './K8s-nav-bar.scss';

interface K8sNavBarEvent {
  onImmediateRefresh(): void;
  onRefreshChange(val: number): void;
  onSelected(val: string): void;
  onTimeRangeChange(val: TimeRangeType): void;
  onTimezoneChange(val: string): void;
}

interface K8sNavBarProps {
  refreshInterval?: number;
  timeRange?: TimeRangeType;
  timezone?: string;
  value?: string;
}

@Component
export default class K8sNavBar extends tsc<K8sNavBarProps, K8sNavBarEvent> {
  // 观测对象
  @Prop({ default: 'performance', type: String }) value: string;
  // 数据间隔
  @Prop({ default: () => DEFAULT_TIME_RANGE, type: Array }) timeRange: TimeRangeType;
  // 自动刷新数据间隔
  @Prop({ default: -1 }) readonly refreshInterval: number;
  // 时区
  @Prop({ type: String }) timezone: string;
  routeList = [
    {
      id: 'k8s',
      name: '容器监控',
      subName: '',
    },
  ];

  curTimeRange: TimeRangeType = DEFAULT_TIME_RANGE;

  sceneToggle = false;

  k8sList = [
    { label: window.i18n.tc('性能'), value: 'performance', icon: 'icon-xingneng1', disabled: false },
    { label: window.i18n.tc('网络'), value: 'network', icon: 'icon-wangluo', disabled: false },
    { label: window.i18n.tc('容量'), value: 'capacity', icon: 'icon-rongliang', disabled: false },
    { label: window.i18n.tc('存储'), value: 'storage', icon: 'icon-cunchu', disabled: true },
    { label: window.i18n.tc('事件'), value: 'event', icon: 'icon-shijian2', disabled: true },
    { label: window.i18n.tc('成本'), value: 'cost', icon: 'icon-chengben', disabled: true },
  ];

  get sceneName() {
    return this.k8sList.find(item => item.value === this.value)?.label;
  }

  get selectItem() {
    return this.k8sList.find(item => item.value === this.value);
  }

  handleGotoOld() {
    this.$router.push({
      name: 'k8s',
      query: {},
    });
  }

  @Watch('timeRange', { immediate: true })
  onTimeRangeChange(v: TimeRangeType) {
    this.curTimeRange = v;
  }

  handleSceneToggle(toggle: boolean) {
    this.sceneToggle = toggle;
  }

  @Emit('selected')
  handleSelected(value: string) {
    return value;
  }

  @Emit('timeRangeChange')
  handleTimeRangeChange(val: TimeRangeType) {
    this.curTimeRange = [...val];
    return [...this.curTimeRange];
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

  render() {
    return (
      <div class='k8s-nav-bar'>
        <div class='k8s-nav-title'>
          <span class='title'>{this.$t('容器监控')}</span>
          <bk-select
            class='nav-select'
            clearable={false}
            ext-popover-cls='new-k8s-nav-select-popover'
            searchable={false}
            value={this.value}
            onSelected={this.handleSelected}
            onToggle={this.handleSceneToggle}
          >
            <div
              class='scene-select-trigger'
              slot='trigger'
            >
              <div class='scene-name'>
                <i class={`icon-monitor scene-icon ${this.selectItem.icon}`} />
                <span class='name'>{this.sceneName}</span>
              </div>
              <span class={`icon-monitor icon-mc-arrow-down ${this.sceneToggle ? 'expand' : ''}`} />
            </div>
            {this.k8sList.map(item => (
              <bk-option
                id={item.value}
                key={item.value}
                disabled={item.disabled}
                name={item.label}
              >
                {item.icon && <i class={`icon-monitor ${item.icon}`} />}
                <span class='label'>{item.label}</span>
              </bk-option>
            ))}
          </bk-select>
          <TemporaryShareNew
            icon='icon-mc-share'
            navList={this.routeList}
            navMode='share'
          />
        </div>
        {this.$slots.default}
        <div class='k8s-nav-tools'>
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
          <GotoOldVersion
            tips={this.$tc('新版容器监控尚未完全覆盖旧版功能，如需可切换到旧版查看')}
            onClick={this.handleGotoOld}
          />
        </div>
      </div>
    );
  }
}
