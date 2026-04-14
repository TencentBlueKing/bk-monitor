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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import CommonItem from '../components/common-form-item';
import AlarmHandling, { type IValue as IAlarmItem, type IAllDefense } from './alarm-handling';
import IssueAgg from './issue-agg';
import SimpleSelect from './simple-select';
import { type ActionTypeEnum, ACTION_TYPE_OPTIONS, actionType } from './typing';

import type { IGroupItem } from '../components/group-select';
import type { IIssueConfig } from '../type';
import type { IDetectionConfig, MetricDetail } from '../typings/index';

import './alarm-handling-list.scss';

interface IEvents {
  onAddMeal?: number;
  onChange?: IAlarmItem[];
  onIssueConfigChange?: IIssueConfig;
}

interface IProps {
  allAction?: IGroupItem[]; // 套餐列表
  allDefense?: IAllDefense[]; // 防御动作列表
  detectionConfig?: IDetectionConfig;
  isSimple?: boolean; // 简易模式（无预览, 无回填）
  issueConfig?: IIssueConfig;
  metricData?: MetricDetail[];
  readonly?: boolean;
  strategyId?: number | string;
  value?: IAlarmItem[];
}

const signalOptionType = {
  abnormal: 'abnormal',
  recovered: 'recovered',
  closed: 'closed',
  no_data: 'no_data',
  incident: 'incident',
} as const;
export const signalNames = {
  [signalOptionType.abnormal]: window.i18n.tc('告警触发时'),
  [signalOptionType.recovered]: window.i18n.tc('告警恢复时'),
  [signalOptionType.closed]: window.i18n.tc('告警关闭时'),
  [signalOptionType.no_data]: window.i18n.tc('无数据时'),
  [signalOptionType.incident]: window.i18n.tc('故障生成时'),
};

const signalOptions: { id: string; name: string }[] = [
  { id: signalOptionType.abnormal, name: signalNames.abnormal },
  { id: signalOptionType.recovered, name: signalNames.recovered },
  { id: signalOptionType.closed, name: signalNames.closed },
  { id: signalOptionType.no_data, name: signalNames.no_data },
  { id: signalOptionType.incident, name: signalNames.incident },
];

@Component
export default class AlarmHandlingList extends tsc<IProps, IEvents> {
  @Prop({ default: () => [], type: Array }) value: IAlarmItem[];
  @Prop({ type: Array, default: () => [] }) allAction: IGroupItem[];
  @Prop({ type: Array, default: () => [] }) allDefense: IAllDefense[];
  @Prop({ type: Object, default: () => ({}) }) detectionConfig: IDetectionConfig;
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  @Prop({ default: '', type: [Number, String] }) strategyId: number;
  @Prop({ default: false, type: Boolean }) isSimple: boolean;
  @Prop({ type: Array, default: () => [] }) metricData: MetricDetail[];
  @Prop({ type: Object, default: () => null }) issueConfig: IIssueConfig;

  data: IAlarmItem[] = [];
  addValue = [];
  /** 当前选中的tab: action(处理套餐) | issueAgg(Issue聚合) */
  activeTab: ActionTypeEnum = actionType.action;

  errMsg = '';

  get needIssueConfigIndex() {
    return this.data.findIndex(item => {
      return item.signal.length === 1 && item.signal[0] === signalOptionType.abnormal;
    });
  }

  /** 切换tab */
  handleTabChange(tab: ActionTypeEnum) {
    this.activeTab = tab;
  }

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
    if (index === this.needIssueConfigIndex) {
      this.handleIssueConfigChange(null);
      this.activeTab = actionType.action;
    }
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

  @Emit('issueConfigChange')
  handleIssueConfigChange(config: IIssueConfig) {
    return config;
  }

  /**
   * @description 告警策略，可配置issue聚合的条件：
    1. 仅且只有“告警触发时”，可以配置issue聚合
    2. 多个“告警触发时”，只能配置一个issue聚合，其他“issue聚合”tab禁用样式，tips：已配置issue聚合
   * @param item 
   * @param index 
   * @returns 
   */
  actionTabRender(item: IAlarmItem, index: number) {
    if (item.signal.length === 1 && item.signal[0] === signalOptionType.abnormal) {
      return [
        <CommonItem
          key={`${index}_tab`}
          class='action-tab-form-item'
          title={this.$t('动作')}
        >
          <div class='bk-button-group'>
            {ACTION_TYPE_OPTIONS.map(action => (
              <span
                key={action.id}
                style={'display: inline-block'}
                v-bk-tooltips={{
                  content: this.$t('已配置issue聚合'),
                  placements: ['top'],
                  disabled: index === this.needIssueConfigIndex || action.id === actionType.action,
                }}
              >
                <bk-button
                  key={action.id}
                  class={
                    (
                      index === this.needIssueConfigIndex
                        ? this.activeTab === action.id
                        : action.id === actionType.action
                    )
                      ? 'is-selected'
                      : ''
                  }
                  disabled={index !== this.needIssueConfigIndex && action.id === actionType.issueAgg}
                  size='small'
                  onClick={() => {
                    if (index === this.needIssueConfigIndex) {
                      this.handleTabChange(action.id);
                    }
                  }}
                >
                  {action.name}
                </bk-button>
              </span>
            ))}
          </div>
        </CommonItem>,
        this.activeTab === actionType.issueAgg && this.needIssueConfigIndex === index ? (
          <IssueAgg
            key={`${index}_IssueAgg`}
            class='alarm-handling-item'
            detectionConfig={this.detectionConfig}
            metricData={this.metricData}
            readonly={this.readonly}
            value={this.issueConfig}
            onChange={this.handleIssueConfigChange}
          />
        ) : (
          <AlarmHandling
            key={`${index}_AlarmHandling`}
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
        ),
      ];
    }
    return (
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
    );
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
              {this.actionTabRender(item, index)}
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
