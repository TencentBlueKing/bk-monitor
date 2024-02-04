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

import { alertStatus, updateAlertUserGroups } from '../../../../../monitor-api/modules/datalink';
import { Debounce } from '../../../../../monitor-common/utils';
// import { isEnFn } from '../../../../utils/index';
import { TCollectorAlertStage } from '../typings/detail';

import AlarmGroup, { IAlarmGroupList } from './alarm-group';
import AlertHistogram from './alert-histogram';

import './alert-topic.scss';

interface IProps {
  alarmGroupList?: IAlarmGroupList[];
  stage: TCollectorAlertStage;
  updateKey?: string;
  alarmGroupListLoading?: boolean;
  onAlarmGroupListRefresh?: () => void;
}

@Component
export default class AlertTopic extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) alarmGroupList: IAlarmGroupList[];
  @Prop({ type: String, default: '' }) stage: TCollectorAlertStage;
  @Prop({ type: [String, Number], default: '' }) id: number | string;
  @Prop({ type: String, default: '' }) updateKey: string;
  @Prop({ type: Boolean, default: false }) alarmGroupListLoading: boolean;

  strategies = [];
  userGroupList = [];
  alertHistogram = [];
  hasAlert = 0;

  alertQuery = '';

  show = false;

  @Watch('updateKey')
  handleWatchKey() {
    if (!!this.stage && !!this.id) {
      alertStatus({
        collect_config_id: this.id,
        stage: this.stage
      }).then(data => {
        if (data?.has_strategies === false) {
          return;
        }
        this.show = true;
        this.strategies = data.alert_config?.strategies || [];
        this.userGroupList = data.alert_config?.user_group_list?.map(item => item.id) || [];
        this.alertHistogram = data?.alert_histogram || [];
        this.hasAlert = data.has_alert;
        this.alertQuery = data.alert_query;
      });
    }
  }

  handleToEvent() {
    // const strategyIds = this.strategies.map(item => item.id);
    // const isEn = isEnFn();
    // const strategyKey = isEn ? 'strategy_id' : this.$t('策略ID');
    // const query = `queryString=${strategyIds.map(id => `${strategyKey} : ${id}`).join(' OR ')}`;
    const timeRange = 'from=now-30d&to=now';
    // window.open(`${location.origin}${location.pathname}${location.search}#/event-center?${query}&${timeRange}`);
    window.open(
      `${location.origin}${location.pathname}${location.search}#/event-center?queryString=${this.alertQuery}&${timeRange}`
    );
  }

  @Debounce(1000)
  handleAlarmGroupChange(value) {
    updateAlertUserGroups({
      collect_config_id: this.id,
      stage: this.stage,
      notice_group_list: value
    });
  }

  @Emit('alarmGroupListRefresh')
  handleAlarmGroupListRefresh() {}

  render() {
    return (
      this.show && (
        <div class='alert-topic-component'>
          <span class='left-wrap'>
            <span class='cur-alert'>
              {this.hasAlert
                ? [<span class='icon-monitor icon-danger'></span>, <span class='ml-8'>{this.$t('当前有告警')}</span>]
                : [
                    <span class='icon-monitor icon-mc-check-fill'></span>,
                    <span class='ml-8'>{this.$t('当前暂无告警')}</span>
                  ]}
            </span>
            <span class='split-line'></span>
            <span class='alert-histogram'>
              <span class='alert-msg mr-8'>
                <span>{this.$t('总告警')}</span>
                <span class='sub-msg'>({this.$t('近1小时')})</span>
              </span>
              <span
                class='alert-link'
                onClick={() => this.handleToEvent()}
              >
                <AlertHistogram
                  value={this.alertHistogram}
                  defaultInterval={2}
                ></AlertHistogram>
              </span>
            </span>
          </span>
          <span class='right-wrap'>
            <span class='receive-msg'>
              <span class='icon-monitor icon-mc-alarm-create mr-6'></span>
              <bk-popover
                theme='light'
                ext-cls='alert-topic-component-pop-alert'
              >
                <span class='dash-text'>{this.$t('可接收告警')}</span>
                <div
                  slot='content'
                  class='alert-topic-component-alert-name'
                >
                  {this.strategies.map(item => (
                    <div class='alert-name-item'>
                      <div class='item-name'>{item.name}</div>
                      <div class='item-description'>{item.description}</div>
                    </div>
                  ))}
                </div>
              </bk-popover>
            </span>
            <span class='split-line'></span>
            <span class='group-wrap'>
              <span class='group-title mr-8'>
                <span class='icon-monitor icon-mc-add-strategy mr-6'></span>
                <span>{this.$t('告警组')}: </span>
              </span>
              <AlarmGroup
                value={this.userGroupList}
                list={this.alarmGroupList}
                isRefresh={true}
                isOpenNewPage={true}
                loading={this.alarmGroupListLoading}
                onRefresh={this.handleAlarmGroupListRefresh}
                onChange={this.handleAlarmGroupChange}
              ></AlarmGroup>
            </span>
          </span>
        </div>
      )
    );
  }
}
