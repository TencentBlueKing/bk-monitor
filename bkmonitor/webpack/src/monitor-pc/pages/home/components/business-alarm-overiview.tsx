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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { alarmDetailChartData } from 'monitor-api/modules/event_center';

import Os from '../business-alarm-overview/os.vue';
import Process from '../business-alarm-overview/process.vue';
import Service from '../business-alarm-overview/service.vue';
import Uptimecheck from '../business-alarm-overview/uptimecheck.vue';
import BusinessAlarmPanel from './business-alarm-panel/business-alarm-panel.vue';
import BusinessAlarmAquare from './business-alarm-square';
import PanelCard from './panel-card/panel-card.vue';

import './business-alarm-overview.scss';

export interface IBusinessAlarm {
  has_monitor?: boolean;
  has_more: boolean;
  high_risk?: { content: string; event_id: string; type: string }[];
  high_risk_count?: number;
  name: string;
  no_monitor_target?: boolean;
  other?: any[];
  other_count?: number;
  status: string;
  step?: number;
}

interface IBusinessAlarmProps {
  businessAlarm: IBusinessAlarm[];
  homeDays?: number;
}

@Component({
  name: 'BusinessAlarmOverview',
})
export default class BusinessAlarmOverview extends tsc<IBusinessAlarmProps> {
  @Prop({ type: Array, default: () => [] }) businessAlarm: IBusinessAlarm[];
  @Prop({ type: Number, default: 7 }) homeDays: number;

  selectedIndex = 0;
  isAllNormal = false;
  alarmMap = {
    uptimecheck: 'uptimecheck',
    service: 'service',
    process: 'process',
    os: 'os',
  };
  titleMap = {
    uptimecheck: {
      serious: window.i18n.tc('拨测监控异常报告'),
      slight: window.i18n.tc('拨测监控异常报告'),
      normal: window.i18n.tc('拨测监控很健康'),
      unset: window.i18n.tc('综合拨测 - 未配置'),
    },
    service: {
      serious: window.i18n.tc('服务监控异常报告'),
      slight: window.i18n.tc('服务监控异常报告'),
      normal: window.i18n.tc('服务监控很健康'),
      unset: window.i18n.tc('服务监控 - 未配置'),
    },

    process: {
      serious: window.i18n.tc('进程监控异常报告'),
      slight: window.i18n.tc('进程监控异常报告'),
      normal: window.i18n.tc('进程监控很健康'),
      unset: window.i18n.tc('进程监控 - 未配置'),
    },
    os: {
      serious: window.i18n.tc('主机监控异常报告'),
      slight: window.i18n.tc('主机监控异常报告'),
      normal: window.i18n.tc('主机监控很健康'),
      unset: window.i18n.tc('主机监控 - 未配置'),
    },
  };

  get selectAlarm(): any {
    return this.businessAlarm[this.selectedIndex];
  }
  get selectTitle() {
    return this.titleMap?.[this.selectAlarm.name]?.[this.selectAlarm.status];
  }
  get selectLogs() {
    return this.selectAlarm.operate_records ? this.selectAlarm.operate_records[0].operate_desc : '';
  }

  created() {
    if (this.businessAlarm.length) {
      this.handleSetIndex();
    }
  }

  @Watch('businessAlarm', { deep: true })
  handleBusinessAlarm() {
    this.handleSetIndex();
  }

  getCustomAlarmChartData() {
    alarmDetailChartData({
      alarm_id: 5838598, // 告警实例ID
      monitor_id: 364, // 监控项ID
      chart_type: 'main', // 固定值
    });
  }
  findIndexByStatus(status) {
    return this.businessAlarm.findIndex(item => item.status === status);
  }
  handleSetIndex() {
    let selectIndex = this.findIndexByStatus('serious');
    if (selectIndex === -1) {
      selectIndex = this.findIndexByStatus('slight');
      if (selectIndex === -1) {
        selectIndex = this.findIndexByStatus('unset');
      }
    }
    this.selectedIndex = selectIndex === -1 ? 0 : selectIndex;
  }

  render() {
    return this.selectAlarm ? (
      <section class='business-alarm-component'>
        <PanelCard
          class='left'
          title={this.$t('监控对象总览')}
        >
          <div
            class={['wall-border', `wall-border-${this.selectAlarm.status}`]}
            slot='custom'
          />
          <BusinessAlarmAquare
            class='content'
            is-all-normal={this.isAllNormal}
            selected-index={this.selectedIndex}
            squares={this.businessAlarm}
            status={this.selectAlarm.status}
            onIsAllNormal={v => (this.isAllNormal = v)}
            onSelectedIndex={v => (this.selectedIndex = v)}
          />
        </PanelCard>
        <div class='right'>
          <BusinessAlarmPanel
            style={{ display: !this.isAllNormal ? 'block' : 'none' }}
            icon={this.selectAlarm.status}
            title={this.selectTitle}
          >
            <keep-alive>
              {this.selectAlarm.name === this.alarmMap.uptimecheck ? (
                <Uptimecheck
                  alarm={this.selectAlarm}
                  homeDays={this.homeDays}
                />
              ) : undefined}
              {this.selectAlarm.name === this.alarmMap.service ? (
                <Service
                  alarm={this.selectAlarm}
                  homeDays={this.homeDays}
                />
              ) : undefined}
              {this.selectAlarm.name === this.alarmMap.process ? (
                <Process
                  alarm={this.selectAlarm}
                  homeDays={this.homeDays}
                />
              ) : undefined}
              {this.selectAlarm.name === this.alarmMap.os ? (
                <Os
                  alarm={this.selectAlarm}
                  homeDays={this.homeDays}
                />
              ) : undefined}
            </keep-alive>
          </BusinessAlarmPanel>
        </div>
      </section>
    ) : undefined;
  }
}
