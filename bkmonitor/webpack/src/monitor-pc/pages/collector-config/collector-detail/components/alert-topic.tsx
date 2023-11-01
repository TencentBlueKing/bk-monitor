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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AlarmGroup, { IAlarmGroupList } from './alarm-group';
import AlertHistogram from './alert-histogram';

import './alert-topic.scss';

interface IProps {
  alarmGroupList?: IAlarmGroupList[];
}

@Component
export default class AlertTopic extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) alarmGroupList: IAlarmGroupList[];

  render() {
    return (
      <div class='alert-topic-component'>
        <span class='left-wrap'>
          <span class='cur-alert'>
            <span class='icon-monitor icon-mc-check-fill'></span>
            <span class='ml-8'>{this.$t('当前暂无告警')}</span>
          </span>
          <span class='split-line'></span>
          <span class='alert-histogram'>
            <span class='alert-msg mr-8'>
              <span>{this.$t('总告警')}</span>
              <span class='sub-msg'>({this.$t('近1小时')})</span>
            </span>
            <AlertHistogram></AlertHistogram>
          </span>
        </span>
        <span class='right-wrap'>
          <span class='receive-msg'>
            <span class='icon-monitor icon-mc-alarm-create mr-6'></span>
            <span class='dash-text'>{this.$t('可接收告警')}</span>
          </span>
          <span class='split-line'></span>
          <span class='group-wrap'>
            <span class='group-title mr-8'>
              <span class='icon-monitor icon-mc-add-strategy mr-6'></span>
              <span>{this.$t('告警组')}: </span>
            </span>
            <AlarmGroup list={this.alarmGroupList}></AlarmGroup>
          </span>
        </span>
      </div>
    );
  }
}
