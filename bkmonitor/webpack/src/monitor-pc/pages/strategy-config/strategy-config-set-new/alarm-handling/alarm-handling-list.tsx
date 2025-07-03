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

import AlarmHandling, { type IAllDefense, type IValue as IAlarmItem } from './alarm-handling';
import SimpleSelect from './simple-select';

import type { IGroupItem } from '../components/group-select';

import './alarm-handling-list.scss';

interface IProps {
  value?: IAlarmItem[];
  allAction?: IGroupItem[]; // 套餐列表
  allDefense?: IAllDefense[]; // 防御动作列表
  readonly?: boolean;
  strategyId?: number | string;
  isSimple?: boolean; // 简易模式（无预览, 无回填）
}

interface IEvents {
  onChange?: IAlarmItem[];
  onAddMeal?: number;
}

export const signalNames = {
  abnormal: window.i18n.tc('告警触发时'),
  recovered: window.i18n.tc('告警恢复时'),
  closed: window.i18n.tc('告警关闭时'),
  no_data: window.i18n.tc('无数据时'),
  incident: window.i18n.tc('故障生成时'),
};

const signalOptions: { id: string; name: string }[] = [
  { id: 'abnormal', name: signalNames.abnormal },
  { id: 'recovered', name: signalNames.recovered },
  { id: 'closed', name: signalNames.closed },
  { id: 'no_data', name: signalNames.no_data },
  { id: 'incident', name: signalNames.incident },
];

@Component
export default class AlarmHandlingList extends tsc<IProps, IEvents> {
  @Prop({ default: () => [], type: Array }) value: IAlarmItem[];
  @Prop({ type: Array, default: () => [] }) allAction: IGroupItem[];
  @Prop({ type: Array, default: () => [] }) allDefense: IAllDefense[];
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  @Prop({ default: '', type: [Number, String] }) strategyId: number;
  @Prop({ default: false, type: Boolean }) isSimple: boolean;

  data: IAlarmItem[] = [];
  addValue = [];

  errMsg = '';

  @Watch('value', { immediate: true, deep: true })
  handleValue(v) {
    this.data = v;
  }

  @Emit('change')
  handleChange() {
    this.clearError();
    return this.data;
  }

  /**
   * @description: 新增一个告警处理
   * @param {boolean} v
   * @return {*}
   */
  handleAddBtnToggle(v: boolean) {
    if (!v && this.addValue.length) {
      this.data.push({
        config_id: 0,
        signal: JSON.parse(JSON.stringify(this.addValue)),
        user_groups: [],
        options: {
          converge_config: {
            is_enabled: true,
            converge_func: 'skip_when_success',
            timedelta: 1,
            count: 1,
          },
          skip_delay: 0,
        },
      });
      this.addValue = [];
    }
  }
  /**
   * @description: 新增告警类型值
   * @param {string} v
   * @return {*}
   */
  handleAddBtnChange(v: string[]) {
    this.addValue = v;
  }

  /**
   * @description: 告警类型输入
   * @param {string} v
   * @param {number} index
   * @return {*}
   */
  handleSignalChange(v: string[], index: number) {
    this.data[index].signal = v;
    this.handleChange();
  }

  /**
   * @description: 删除一个告警处理
   * @param {number} index
   * @return {*}
   */
  handleDelete(index: number) {
    this.data.splice(index, 1);
    this.handleChange();
  }

  /**
   * @description: 处理每个item输入的值
   * @param {IAlarmItem} v
   * @param {number} index
   * @return {*}
   */
  handleAlarmChange(v: IAlarmItem, index: number) {
    this.$set(this.data, index, {
      ...v,
      signal: this.data[index].signal,
    });
    this.handleChange();
  }

  validate() {
    return new Promise((resolve, reject) => {
      const validate = this.data.some(item => !item.signal?.length);
      const configValidate = this.data.every(item => !!item.config_id);
      const skipDelayValidate = this.data.some(item => item.options.skip_delay === -1);
      if (validate) {
        this.errMsg = window.i18n.tc('输入告警场景');
        reject();
      } else if (!configValidate) {
        this.errMsg = window.i18n.tc('选择处理套餐');
      } else if (skipDelayValidate) {
        // 后端只存储延迟时间，不记录开关状态。 -1：switch状态开但时间设置不正确
        reject();
      } else {
        resolve(true);
      }
    });
  }

  clearError() {
    this.errMsg = '';
  }

  @Emit('addMeal')
  handleAddMeal(index: number) {
    return index;
  }

  render() {
    return (
      <div class='alarm-handling-list-content'>
        <div class='items-wrap'>
          {this.data.map((item, index) => (
            <div
              key={index}
              class='alarm-item'
            >
              {!this.readonly ? (
                <i
                  class='icon-monitor icon-mc-delete-line'
                  onClick={() => this.handleDelete(index)}
                />
              ) : undefined}
              <SimpleSelect
                disabled={this.readonly}
                list={signalOptions}
                multiple={true}
                popoverMinWidth={130}
                value={item.signal}
                onChange={v => this.handleSignalChange(v as string[], index)}
              >
                <span class='signal-select-wrap'>
                  {item.signal?.length ? (
                    <span class='signal-name'>{item.signal.map(key => signalNames[key] || key).join(',')}</span>
                  ) : (
                    <span class='add-placeholder'>{this.$t('选择添加告警场景')}</span>
                  )}
                  <span class='icon-monitor icon-arrow-down' />
                </span>
              </SimpleSelect>
              <AlarmHandling
                extCls={'alarm-handling-item'}
                allAction={this.allAction}
                allDefense={this.allDefense}
                isSimple={this.isSimple}
                list={signalOptions}
                readonly={this.readonly}
                strategyId={this.strategyId}
                value={item}
                onAddMeal={() => this.handleAddMeal(index)}
                onChange={v => this.handleAlarmChange(v, index)}
              />
            </div>
          ))}
        </div>
        {!this.readonly && (
          <div class='add-wrap'>
            <SimpleSelect
              list={signalOptions}
              multiple={true}
              popoverMinWidth={130}
              value={this.addValue}
              onChange={v => this.handleAddBtnChange(v as string[])}
              onToggle={v => this.handleAddBtnToggle(v)}
            >
              <span class='signal-select-wrap'>
                <span class='add-placeholder'>{this.$t('选择添加告警场景')}</span>
                <span class='icon-monitor icon-arrow-down' />
              </span>
            </SimpleSelect>
          </div>
        )}
        {this.readonly && !this.data.length ? <div class='no-data'>{this.$t('无')}</div> : undefined}
        {this.errMsg ? <span class='error-msg'>{this.errMsg}</span> : undefined}
      </div>
    );
  }
}
