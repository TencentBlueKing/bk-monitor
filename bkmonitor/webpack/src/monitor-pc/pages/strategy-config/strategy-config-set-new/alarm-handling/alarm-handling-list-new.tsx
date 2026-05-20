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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import CommonItem from '../components/common-form-item';
import AlarmHandling, { type IValue as IAlarmItem, type IAllDefense } from './alarm-handling';
import IssueAgg from './issue-agg';
import SimpleSelect from './simple-select';
import { type ActionTypeEnum, ACTION_TYPE_OPTIONS, actionType } from './typing';

import type { IGroupItem } from '../components/group-select';
import type { IIssueConfig } from '../type';
import type { ICommonItem, IDetectionConfig, MetricDetail } from '../typings/index';

import './alarm-handling-list.scss';

interface IEvents {
  onAddMeal?: number;
  onChange?: IAlarmItem[];
  onIssueConfigChange?: IIssueConfig;
}

interface ILocalValue {
  //   处理套餐配置
  action: IAlarmItem;
  // tab切换（二选一）
  activeTab: ActionTypeEnum;
  // 是否包含issue/处理套餐的tab
  hasTab: boolean;
  //   issue聚合配置
  issueConfig: IIssueConfig;
  //  能否配置issue聚合配置（已配置则禁用issue tab）
  needIssueConfig: boolean;
  // 告警场景类型
  signal: string[];
}

interface IProps {
  allAction?: IGroupItem[]; // 套餐列表
  allDefense?: IAllDefense[]; // 防御动作列表
  detectionConfig?: IDetectionConfig;
  isSimple?: boolean; // 简易模式（无预览, 无回填）
  issueConfig?: IIssueConfig;
  metricData?: MetricDetail[];
  readonly?: boolean;
  showIssueConfig?: boolean;
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

const defaultActionData = (other = {}) =>
  JSON.parse(
    JSON.stringify({
      config_id: 0,
      signal: [signalOptionType.abnormal],
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
      ...other,
    })
  );
const getHasTab = (signal: string[]) => {
  return signal?.length === 1 && signal?.[0] === signalOptionType.abnormal;
};

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
  //   是否包含issue聚合功能
  @Prop({ type: Boolean, default: true }) showIssueConfig: boolean;

  localValue: ILocalValue[] = [];
  addValue = [];

  errMsg = '';

  get issueConfigDimensions(): ICommonItem[] {
    // 过滤出有聚合维度的指标
    const metricsWithAggDim = this.metricData.filter(m => m.agg_dimension?.length > 0);

    // 如果没有指标有维度，返回空数组
    if (metricsWithAggDim.length === 0) return [];

    // 如果只有一个指标有维度，返回那个指标的已选维度列表
    if (metricsWithAggDim.length === 1) {
      const metric = metricsWithAggDim[0];
      return metric.dimensions?.filter(d => metric.agg_dimension.includes(d.id as string)) || [];
    }

    // 多指标情况，取交集
    // 获取所有指标的 agg_dimension 的交集
    const firstAggDim = metricsWithAggDim[0].agg_dimension;
    const intersectionIds = metricsWithAggDim.reduce(
      (acc, metric) => {
        const ids = new Set(metric.agg_dimension);
        return acc.filter(id => ids.has(id));
      },
      [...firstAggDim]
    );

    // 根据交集 ID 返回对应的维度信息（使用第一个指标的 dimensions 获取维度详情）
    const firstMetric = metricsWithAggDim[0];
    return firstMetric.dimensions?.filter(d => intersectionIds.includes(d.id as string)) || [];
  }

  created() {
    const hasIssueConfig =
      this.issueConfig &&
      (this.issueConfig?.aggregate_dimensions?.length ||
        this.issueConfig?.conditions?.length ||
        this.issueConfig?.alert_levels?.length);
    for (const item of this.value) {
      this.localValue.push({
        activeTab: actionType.action,
        action: item,
        issueConfig: null,
        needIssueConfig: !hasIssueConfig,
        signal: item?.signal || [],
        hasTab: getHasTab(item?.signal || []),
      });
    }
    if (hasIssueConfig) {
      this.localValue.push({
        activeTab: actionType.issueAgg,
        action: defaultActionData(),
        issueConfig: this.issueConfig,
        needIssueConfig: true,
        signal: [signalOptionType.abnormal],
        hasTab: true,
      });
    }
  }

  /** 切换tab */
  handleTabChange(tab: ActionTypeEnum, index: number) {
    if (tab === actionType.issueAgg && !this.localValue[index]?.issueConfig) {
      // 切换到issueConfig需要填充默认值
      const levels = this.detectionConfig?.data?.map(item => item.level).filter(Boolean);
      const localValueItem = this.localValue[index];
      this.localValue.splice(index, 1, {
        ...localValueItem,
        activeTab: tab,
        issueConfig: {
          aggregate_dimensions: this.issueConfigDimensions.map(item => item.id) as string[],
          conditions: [],
          alert_levels: [...new Set(levels)],
        },
      });
    } else {
      this.localValue[index].activeTab = tab;
    }
    this.localValue = this.localValue.map((item, lIndex) => {
      if (lIndex === index) {
        return item;
      }
      return {
        ...item,
        needIssueConfig: item.hasTab ? tab === actionType.action : false,
      };
    });
    this.handleChange();
  }

  @Emit('change')
  handleChange() {
    this.clearError();
    this.handleIssueConfigEmitChange();
    return this.localValue.filter(item => item.activeTab === actionType.action).map(item => item.action);
  }
  @Emit('issueConfigChange')
  handleIssueConfigEmitChange() {
    const issueConfig = this.localValue.find(item => item.activeTab === actionType.issueAgg)?.issueConfig || null;
    return issueConfig?.aggregate_dimensions?.length ||
      issueConfig?.conditions?.length ||
      issueConfig?.alert_levels?.length
      ? issueConfig
      : null;
  }

  /**
   * @description: 新增一个告警处理
   * @param {boolean} v
   * @return {*}
   */
  handleAddBtnToggle(v: boolean) {
    const needIssueConfig = !this.localValue.some(item => item.activeTab === actionType.issueAgg);
    if (!v && this.addValue.length) {
      this.localValue.push({
        activeTab: actionType.action,
        action: defaultActionData({
          signal: this.addValue,
        }),
        issueConfig: null,
        needIssueConfig: needIssueConfig,
        signal: JSON.parse(JSON.stringify(this.addValue)),
        hasTab: getHasTab(this.addValue),
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
    const localValueItem = this.localValue[index];
    const hasTab = getHasTab(v);
    const needIssueConfig =
      hasTab && !this.localValue.some((item, lIndex) => item.activeTab === actionType.issueAgg && index !== lIndex);
    this.localValue[index] = {
      ...localValueItem,
      ...(localValueItem.activeTab === actionType.action
        ? {
            action: {
              ...localValueItem.action,
              signal: v,
            },
          }
        : {}),
      signal: v,
      hasTab: hasTab,
      needIssueConfig: needIssueConfig,
      issueConfig: needIssueConfig ? localValueItem.issueConfig : null,
    };
    this.resetNeedIssueConfig();
    this.handleChange();
  }

  /**
   * @description: 删除一个告警处理
   * @param {number} index
   * @return {*}
   */
  handleDelete(index: number) {
    this.localValue.splice(index, 1);
    this.resetNeedIssueConfig();
    this.handleChange();
  }

  resetNeedIssueConfig() {
    if (this.localValue.filter(item => item.hasTab).every(item => !item.needIssueConfig)) {
      this.localValue = this.localValue.map(item => ({
        ...item,
        needIssueConfig: !!item.hasTab,
      }));
    }
  }

  /**
   * @description: 处理每个item输入的值
   * @param {IAlarmItem} v
   * @param {number} index
   * @return {*}
   */
  handleAlarmChange(v: IAlarmItem, index: number) {
    const localValueItem = this.localValue[index];
    this.localValue.splice(index, 1, {
      ...localValueItem,
      action: {
        ...v,
        signal: localValueItem.signal,
      },
    });

    this.handleChange();
  }

  validate() {
    return new Promise((resolve, reject) => {
      const validate = this.localValue.some(item => !item.signal?.length);
      const configValidate = this.localValue.every(item =>
        item.activeTab === actionType.action ? !!item.action?.config_id : true
      );
      const skipDelayValidate = this.localValue.some(item =>
        item.activeTab === actionType.action ? item.action?.options.skip_delay === -1 : false
      );
      const issueAggLevelsValidate = this.localValue.some(item =>
        item.activeTab === actionType.issueAgg ? !item.issueConfig?.alert_levels?.length : false
      );
      const issueAggDimensionsValidate = this.localValue.some(item =>
        item.activeTab === actionType.issueAgg ? !item.issueConfig?.aggregate_dimensions?.length : false
      );
      if (validate) {
        this.errMsg = window.i18n.tc('输入告警场景');
        reject();
      } else if (!configValidate) {
        this.errMsg = window.i18n.tc('选择处理套餐');
        reject();
      } else if (issueAggDimensionsValidate) {
        this.errMsg = window.i18n.tc('请选择Issue聚合维度');
        reject();
      } else if (issueAggLevelsValidate) {
        this.errMsg = window.i18n.tc('请选择Issue聚合生效告警级别');
        reject();
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

  handleIssueConfigChange(config: IIssueConfig, index: number) {
    this.localValue[index].issueConfig = config;
    this.handleChange();
  }

  /**
   * @description 告警策略，可配置issue聚合的条件：
    1. 仅且只有“告警触发时”，可以配置issue聚合
    2. 多个“告警触发时”，只能配置一个issue聚合，其他“issue聚合”tab禁用样式，tips：已配置issue聚合
   * @param item 
   * @param index 
   * @returns 
   */
  actionTabRender(item: ILocalValue, index: number) {
    if (item.signal.length === 1 && item.signal[0] === signalOptionType.abnormal && this.showIssueConfig) {
      return [
        <CommonItem
          key={`${index}_tab`}
          class='action-tab-form-item'
          title={this.$t('动作')}
          isRequired
          show-semicolon
        >
          <bk-select
            style='flex: 1; max-width: 180px;'
            behavior='simplicity'
            clearable={false}
            searchable={false}
            size={'small'}
            value={item.activeTab}
            onChange={val => {
              if (item.needIssueConfig) {
                this.handleTabChange(val, index);
              }
            }}
          >
            {ACTION_TYPE_OPTIONS.map(action => (
              <bk-option
                id={action.id}
                key={action.id}
                v-bk-tooltips={{
                  content: this.$t('已配置issue聚合'),
                  placements: ['right'],
                  disabled: action.id === actionType.issueAgg ? item.needIssueConfig : true,
                }}
                disabled={action.id === actionType.issueAgg ? !item.needIssueConfig : false}
                name={action.name}
              />
            ))}
          </bk-select>
          {/* <div class='bk-button-group'>
            {ACTION_TYPE_OPTIONS.map(action => (
              <span
                key={action.id}
                style={'display: inline-block'}
                v-bk-tooltips={{
                  content: this.$t('已配置issue聚合'),
                  placements: ['top'],
                  disabled: action.id === actionType.issueAgg ? item.needIssueConfig : true,
                }}
              >
                <bk-button
                  key={action.id}
                  class={item.activeTab === action.id ? 'is-selected' : ''}
                  disabled={action.id === actionType.issueAgg ? !item.needIssueConfig : false}
                  size='small'
                  onClick={() => {
                    if (item.needIssueConfig) {
                      this.handleTabChange(action.id, index);
                    }
                  }}
                >
                  {action.name}
                </bk-button>
              </span>
            ))}
          </div> */}
        </CommonItem>,
        item.activeTab === actionType.issueAgg ? (
          <IssueAgg
            key={`${index}_IssueAgg`}
            class='alarm-handling-item'
            dimensions={this.issueConfigDimensions}
            metricData={this.metricData}
            readonly={this.readonly}
            value={item.issueConfig}
            onChange={val => this.handleIssueConfigChange(val, index)}
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
            value={item.action}
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
        value={item.action}
        onAddMeal={() => this.handleAddMeal(index)}
        onChange={v => this.handleAlarmChange(v, index)}
      />
    );
  }

  render() {
    return (
      <div class='alarm-handling-list-content'>
        <div class='items-wrap'>
          {this.localValue.map((item, index) => (
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
        {this.readonly && !this.localValue.length ? <div class='no-data'>{this.$t('无')}</div> : undefined}
        {this.errMsg ? <span class='error-msg'>{this.errMsg}</span> : undefined}
      </div>
    );
  }
}
