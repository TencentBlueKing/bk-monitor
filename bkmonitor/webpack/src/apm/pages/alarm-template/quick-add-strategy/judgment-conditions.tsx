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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AlarmGroup from 'monitor-pc/pages/strategy-config/strategy-config-set-new/components/alarm-group';

import type { IAlarmGroupList } from './typing';

import './judgment-conditions.scss';

interface IConfig {
  detect: IDetectConfig;
  user_group_list: {
    id: string;
    name: string;
  }[];
}
interface IDetectConfig {
  recovery_check_window: number;
  trigger_check_window: number;
  trigger_count: number;
}

interface IProps {
  userList?: IAlarmGroupList[];
  onChange?: (v: IConfig) => void;
}

@Component
export default class JudgmentConditions extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) userList: IAlarmGroupList[];
  detectConfig = {
    checkWindow: 5,
    count: 1,
  };

  userGroups = [];
  userParams = [];

  userListMap = new Map();

  isExpand = false;

  @Watch('userList', { immediate: true })
  handleUserGroupChange() {
    if (this.userList.length) {
      for (const item of this.userList) {
        this.userListMap.set(item.id, item);
      }
    }
  }

  handleChange() {
    const params = {
      detect: {
        type: 'default',
        config: {
          trigger_check_window: Number(this.detectConfig.checkWindow),
          trigger_count: Number(this.detectConfig.count),
        },
      },
      user_group_list: this.userParams,
    };
    this.$emit('change', params);
  }

  handleUserGroup(data) {
    this.userParams = data.map(id => {
      const name = this.userListMap.get(id)?.name || '';
      return {
        id: id,
        name: name,
      };
    });
    this.userGroups = data;
    this.handleChange();
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
                  on-change={this.handleChange}
                />
                <bk-input
                  class='small-input'
                  v-model={this.detectConfig.count}
                  behavior='simplicity'
                  placeholder={this.$t('输入数字')}
                  show-controls={false}
                  size='small'
                  type='number'
                  on-change={this.handleChange}
                />
              </i18n>
            </div>
            <div class='judgment-content-item'>
              <div class='judgment-content-title'>{this.$t('告警组')}</div>
              <AlarmGroup
                class='alarm-group'
                isOpenNewPage={true}
                isSimple={true}
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
