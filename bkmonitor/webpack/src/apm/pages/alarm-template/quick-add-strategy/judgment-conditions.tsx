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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AlarmGroup from 'monitor-pc/pages/strategy-config/strategy-config-set-new/components/alarm-group';

import type { IAlarmGroupList } from './typing';

import './judgment-conditions.scss';

interface IProps {
  userList?: IAlarmGroupList[];
}

@Component
export default class JudgmentConditions extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) userList: IAlarmGroupList[];
  detectConfig = {
    checkWindow: 5,
    count: 1,
  };

  userGroups = [];

  isExpand = false;

  emitValueChange() {
    this.$emit('valueChange', this.detectConfig);
  }

  handleUserGroup(data) {
    this.userGroups = data;
  }

  handleExpand() {
    this.isExpand = !this.isExpand;
  }

  render() {
    return (
      <div class='quick-add-strategy-judgment-conditions'>
        <div
          class='expand-btn'
          onClick={this.handleExpand}
        >
          <span>{this.$t('批量修改')}</span>
          <span class={['icon-monitor icon-double-down', { expand: this.isExpand }]} />
        </div>
        {this.isExpand ? (
          <div class='judgment-content'>
            <div class='judgment-content-item'>
              <div class='judgment-content-title'>{this.$t('判断条件')}</div>
              <i18n
                class='i18n-path'
                path='在{0}个周期内累计满足{1}次检测算法'
              >
                <bk-input
                  class='small-input'
                  v-model={this.detectConfig.checkWindow}
                  behavior='simplicity'
                  placeholder={this.$t('输入数字')}
                  show-controls={false}
                  size='small'
                  type='number'
                  on-change={this.emitValueChange}
                />
                <bk-input
                  class='small-input'
                  v-model={this.detectConfig.count}
                  behavior='simplicity'
                  placeholder={this.$t('输入数字')}
                  show-controls={false}
                  size='small'
                  type='number'
                  on-change={this.emitValueChange}
                />
              </i18n>
            </div>
            <div class='judgment-content-item'>
              <div class='judgment-content-title'>{this.$t('告警组')}</div>
              <AlarmGroup
                class='alarm-group'
                list={this.userList}
                readonly={false}
                showAddTip={false}
                value={this.userGroups}
                onChange={data => this.handleUserGroup(data)}
              />
            </div>
          </div>
        ) : undefined}
      </div>
    );
  }
}
