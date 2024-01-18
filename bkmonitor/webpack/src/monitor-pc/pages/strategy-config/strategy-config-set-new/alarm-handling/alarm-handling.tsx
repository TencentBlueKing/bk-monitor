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
import { Component, Emit, Inject, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SetMealDeail from '../../../../../fta-solutions/pages/setting/set-meal-detail/set-meal-detail';
import { deepClone } from '../../../../../monitor-common/utils/utils';
import * as ruleAuth from '../../authority-map';
import CommonItem from '../components/common-form-item';
import GroupSelect, { IGroupItem } from '../components/group-select';
import { IActionConfig } from '../type';
import { strategyType } from '../typings/index';

import './alarm-handling.scss';

/**
 * @description: 转换为分组列表
 * @param {IActionConfig} actionConfigList
 * @return {*}
 */
export const actionConfigGroupList = (actionConfigList: IActionConfig[]): IGroupItem[] => {
  const groupMap = {};
  const groupList = [];
  actionConfigList.forEach(item => {
    if (groupMap?.[item.plugin_type]?.list.length) {
      groupMap[item.plugin_type].list.push({ id: item.id, name: item.name });
    } else {
      groupMap[item.plugin_type] = { groupName: item.plugin_name, list: [{ id: item.id, name: item.name }] };
    }
  });
  Object.keys(groupMap).forEach(key => {
    const obj = groupMap[key];
    groupList.push({ id: key, name: obj.groupName, children: obj.list });
  });
  return groupList;
};

export interface IValue {
  config_id?: number;
  user_groups?: number[];
  options: {
    converge_config: {
      converge_func: string; // 防御动作
      timedelta: number; // 防御窗口大小（秒），默认设置为 60
      count: number; // 执行次数，默认设置为 1
      is_enabled?: boolean; // 是否启用
    };
  };
  signal?: string[];
}

export interface IAllDefense {
  key: string;
  name: string;
  description?: string;
}
interface IAlarmHandlingNewProps {
  value?: IValue;
  allDefense?: IAllDefense[]; // 防御动作列表
  allAction?: IGroupItem[]; // 套餐列表
  readonly?: boolean;
  strategyId?: number | string;
  extCls?: string;
  isSimple?: boolean; // 简洁模式(无预览，无回填)
}

interface IAlarmHandlingNewEvent {
  onChange?: IValue;
  onAddMeal?: void;
}

@Component({
  name: 'AlarmHandlingNew'
})
export default class AlarmHandlingNew extends tsc<IAlarmHandlingNewProps, IAlarmHandlingNewEvent> {
  @Prop({
    type: Object,
    default: () => ({
      config_id: 0,
      user_groups: [],
      options: {
        converge_config: {
          converge_func: 'skip_when_success', // 防御动作
          timedelta: 1, // 防御窗口大小（秒），默认设置为 60
          count: 1, // 执行次数，默认设置为 1
          is_enabled: true
        }
      }
    })
  })
  value: IAlarmHandlingNewProps['value'];
  @Prop({ type: Array, default: () => [] }) allDefense: IAlarmHandlingNewProps['allDefense'];
  @Prop({ type: Array, default: () => [] }) allAction: IGroupItem[];
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  @Prop({ default: '', type: [Number, String] }) strategyId: number;
  @Prop({ default: '', type: String }) extCls: string;
  @Prop({ default: false, type: Boolean }) isSimple: boolean;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  @Inject() strategyType: strategyType;

  @Ref('selectMeal') selectMealRef: GroupSelect;

  get defenseTips() {
    const tips = {};
    this.allDefense.forEach(item => {
      tips[item.key] = item.description;
    });
    return tips;
  }
  get noNoticeActionConfigList() {
    return this.allAction.filter(item => item.id !== 'notice');
  }

  data: IValue = {
    config_id: 0,
    user_groups: [],
    options: {
      converge_config: {
        converge_func: 'skip_when_success', // 防御动作
        timedelta: 1, // 防御窗口大小（秒），默认设置为 60
        count: 1, // 执行次数，默认设置为 1
        is_enabled: true
      }
    }
  };
  isShowDetail = false;

  @Watch('value', { immediate: true, deep: true })
  handleValue(data: IAlarmHandlingNewProps['value']) {
    this.data = deepClone(data);
  }
  @Emit('change')
  handleChange() {
    return this.data;
  }

  // 切换套餐
  handleChangeConfigId(v: number | string) {
    this.data.config_id = Number(v);
    if (!this.isSimple) {
      this.handleShowMealDetail();
    }
    this.handleChange();
  }
  handleClearConfigId() {
    this.data.config_id = 0;
    this.handleChange();
  }

  handleToAddSetMeal() {
    this.handleAddMeal();
    this.selectMealRef?.destroyPopoverInstance();
    setTimeout(() => {
      this.$router.push({
        name: 'set-meal-add',
        params: {
          strategyId: !this.isSimple ? `${this.strategyId}` : undefined
        }
      });
    }, 300);
  }

  @Emit('addMeal')
  handleAddMeal() {}

  handleShowMealDetail() {
    this.isShowDetail = true;
  }

  render() {
    return (
      <div class={['alarm-handling-new-component', this.extCls, { readonly: this.readonly }]}>
        <CommonItem
          title={this.$t('处理套餐')}
          show-semicolon
        >
          <span>{this.$t('当告警触发时执行')}</span>
          <GroupSelect
            ref='selectMeal'
            value={this.data.config_id}
            list={this.noNoticeActionConfigList}
            class='select-warp'
            readonly={this.readonly}
            placeholder={this.$tc('选择套餐')}
            onChange={data => this.handleChangeConfigId(data)}
            onClear={() => this.handleClearConfigId()}
          >
            <div
              style={{ width: '100%', height: '100%', display: 'flex', 'align-items': 'center' }}
              slot='extension'
              v-authority={{ active: !this.authority.MANAGE_ACTION_CONFIG }}
              onClick={() =>
                this.authority.MANAGE_ACTION_CONFIG
                  ? this.handleToAddSetMeal()
                  : this.handleShowAuthorityDetail(ruleAuth.MANAGE_ACTION_CONFIG)
              }
            >
              <i
                class='icon-monitor icon-jia'
                style='margin: 4px 4px 0 0;'
              ></i>
              <span
                class='add-text'
                v-bk-tooltips={{
                  content: this.$t('进入新增页，新增完可直接返回不会丢失数据'),
                  disabled: this.isSimple
                }}
              >
                {this.$t('新建套餐')}
                {!this.isSimple ? (
                  <span style={{ marginLeft: '10px', color: '#ea3636' }}>{`(${this.$t('新增后会进行回填')})`}</span>
                ) : undefined}
              </span>
            </div>
          </GroupSelect>
          {!this.isSimple ? (
            <bk-button
              text
              title='primary'
              size='small'
              disabled={this.data.config_id === 0}
              style={{ padding: 0 }}
              on-click={this.handleShowMealDetail}
            >
              {this.$t('button-预览')}
            </bk-button>
          ) : undefined}
        </CommonItem>
        <CommonItem
          title={this.$t('防御规则')}
          show-semicolon
        >
          <bk-switcher
            style={{ marginRight: '8px' }}
            v-model={this.data.options.converge_config.is_enabled}
            theme='primary'
            size='small'
            disabled={this.readonly}
            on-change={this.handleChange}
          ></bk-switcher>
          {this.data.options.converge_config.is_enabled && (
            <i18n
              path='当{0}分钟内执行{1}次时，防御动作{2}'
              class={`defense-wrap ${this.isSimple ? 'simple' : ''}`}
            >
              {!this.readonly ? (
                <bk-input
                  type='number'
                  size='small'
                  class='small-input'
                  behavior='simplicity'
                  showControls={false}
                  readonly={this.readonly}
                  v-model={this.data.options.converge_config.timedelta}
                  on-change={this.handleChange}
                ></bk-input>
              ) : (
                <span>{this.data.options.converge_config.timedelta}</span>
              )}
              {!this.readonly ? (
                <bk-input
                  type='number'
                  size='small'
                  class='small-input'
                  behavior='simplicity'
                  showControls={false}
                  readonly={this.readonly}
                  v-model={this.data.options.converge_config.count}
                  on-change={this.handleChange}
                ></bk-input>
              ) : (
                <span>{this.data.options.converge_config.count}</span>
              )}
              <bk-select
                class='select-inline'
                popover-min-width={140}
                v-model={this.data.options.converge_config.converge_func}
                behavior={'simplicity'}
                size='small'
                clearable={false}
                searchable
                readonly={this.readonly}
                on-change={this.handleChange}
              >
                {this.allDefense.map(option => (
                  <bk-option
                    key={option.key}
                    id={option.key}
                    name={option.name}
                  ></bk-option>
                ))}
              </bk-select>
            </i18n>
          )}
        </CommonItem>
        {this.data.options.converge_config.is_enabled && (
          <div class='tips-key1'>
            <i class='icon-monitor icon-hint'></i>{' '}
            <span class='tip-text'>
              {this.defenseTips[this.data.options.converge_config.converge_func] ||
                this.allDefense[0]?.description ||
                ''}
            </span>
          </div>
        )}
        <SetMealDeail
          id={this.data.config_id}
          v-model={this.isShowDetail}
          strategyType={this.strategyType}
          strategyId={this.strategyId}
          needEditTips={!this.readonly}
        ></SetMealDeail>
      </div>
    );
  }
}
