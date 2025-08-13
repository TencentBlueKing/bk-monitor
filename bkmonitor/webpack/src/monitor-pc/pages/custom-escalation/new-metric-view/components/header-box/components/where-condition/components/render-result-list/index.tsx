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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';

import { formatTipsContent } from '../../../../../../metric-chart-view/utils';
import EditPanel, { type IMetrics, type IValue, methodMap } from './components/edit-panel/index';
import customEscalationViewStore from '@store/modules/custom-escalation-view';

import './index.scss';

interface IEmit {
  onChange: (value: IValue[]) => void;
}

interface IProps {
  value: IValue[];
}

@Component
export default class ValueTag extends tsc<IProps, IEmit> {
  @Prop({ type: Array, default: () => [] }) readonly value: IProps['value'];

  @Ref('editPanelRef') editPanelRef: EditPanel;

  localValue: Readonly<IProps['value']> = [];
  currentEditDimension: IValue;
  latestMetricsList: Readonly<IMetrics[]> = [];

  get currentSelectedMetricList() {
    return customEscalationViewStore.currentSelectedMetricList;
  }

  get dimensionAliasNameMap() {
    return customEscalationViewStore.dimensionAliasNameMap;
  }

  get isAddBtnDisabled() {
    return _.every(this.latestMetricsList, metricItem => metricItem.dimensions.length < 1);
  }

  @Watch('currentSelectedMetricList', { immediate: true })
  metricsListChange() {
    this.calcLatestMetricsList();
  }

  @Watch('value', { immediate: true })
  valueChange() {
    this.localValue = Object.freeze(this.value);
    this.editPanelRef?.hide();
  }

  calcLatestMetricsList() {
    const dimensionCountMap: Record<string, number> = {};

    for (const metricItem of this.currentSelectedMetricList) {
      for (const dimensionItem of metricItem.dimensions) {
        dimensionCountMap[dimensionItem.name] = (dimensionCountMap[dimensionItem.name] || 0) + 1;
      }
    }

    const commonDimensionList: IMetrics['dimensions'] = [];
    const otherDimensionList: IMetrics['dimensions'] = [];
    for (const metricsItem of this.currentSelectedMetricList) {
      for (const dimensionItem of metricsItem.dimensions) {
        if (dimensionCountMap[dimensionItem.name] > 1) {
          commonDimensionList.push(dimensionItem);
          continue;
        }
        otherDimensionList.push(dimensionItem);
      }
    }

    const nextMetricsList: IMetrics[] = [];

    // 选择指标数至少有 2 个时一定会显示共有维度分组
    if (this.currentSelectedMetricList.length >= 2) {
      nextMetricsList.push({
        alias: this.$t('共用维度') as string,
        metric_name: this.$t('共用维度') as string,
        dimensions: _.uniqBy(commonDimensionList, item => item.name),
      });
    }

    if (otherDimensionList.length > 0) {
      nextMetricsList.push({
        alias: this.$t('其它维度') as string,
        metric_name: this.$t('其它维度') as string,
        dimensions: otherDimensionList,
      });
    }

    this.latestMetricsList = Object.freeze(nextMetricsList);
  }

  triggerChange() {
    this.$emit('change', [...this.localValue]);
  }

  handleShowEditPanel(payload: IValue, event: Event) {
    this.currentEditDimension = payload;
    this.editPanelRef.show(event.target as HTMLElement);
    this.calcLatestMetricsList();
  }

  handleShowAppendPanel(event: Event) {
    if (this.isAddBtnDisabled) {
      return;
    }
    this.currentEditDimension = undefined;
    this.editPanelRef.show(event.target as HTMLElement);
    this.calcLatestMetricsList();
  }

  handleEditPanelChange(value: IValue) {
    if (this.currentEditDimension) {
      const localValue = [...this.localValue];
      const index = _.findIndex(localValue, item => item.key === value.key);
      localValue.splice(index, 1, value);
      this.localValue = Object.freeze(localValue);
    } else {
      this.localValue = Object.freeze([...this.localValue, value]);
    }
    this.triggerChange();
  }

  handleConditionChange(payload: IValue) {
    const localValue = [...this.localValue];
    const index = _.findIndex(localValue, item => item === payload);
    localValue.splice(index, 1, {
      ...payload,
      condition: payload.condition === 'and' ? 'or' : 'and',
    });
    this.localValue = Object.freeze(localValue);
    this.triggerChange();
  }

  handleRemoveTag(index: number) {
    const localValue = [...this.localValue];
    localValue.splice(index, 1);
    this.localValue = Object.freeze(localValue);
    this.triggerChange();
  }

  handleClear() {
    this.localValue = [];
    this.triggerChange();
  }

  created() {
    this.localValue = Object.freeze([...this.value]);
  }

  render() {
    return (
      <div>
        <div class='metric-view-filter-conditions-demension-list'>
          {this.localValue.map((item, index) => {
            return (
              <div
                key={index}
                class='dimension-tag-box'
                v-bk-tooltips={{ content: formatTipsContent(item.key, this.dimensionAliasNameMap[item.key]) }}
              >
                {index > 0 && (
                  <div
                    class='dimension-condition'
                    onClick={() => this.handleConditionChange(item)}
                  >
                    {item.condition.toLocaleUpperCase()}
                  </div>
                )}
                <div
                  class='tag-wrapper'
                  onClick={(event: Event) => this.handleShowEditPanel(item, event)}
                >
                  <div class='dimension-header'>
                    <div class='dimension-key'>
                      {this.dimensionAliasNameMap[item.key] || item.key}
                      {/* {this.dimensionAliasNameMap[item.key]
                        ? `${this.dimensionAliasNameMap[item.key]} (${item.key})`
                        : item.key} */}
                    </div>
                    <div class='dimension-method'>{methodMap[item.method]}</div>
                  </div>
                  <div class='dimension-value-wrapper'>
                    {item.value.slice(0, 3).map((valueText, index) => (
                      <div
                        key={`${valueText}#${index}`}
                        class='dimension-value'
                      >
                        {index > 0 && <span style='color: #F59500; padding: 0 2px; font-weight: bold'>,</span>}
                        {valueText}
                      </div>
                    ))}
                    {item.value.length > 3 && (
                      <span class='dimension-value'>
                        <span style='color: #F59500; padding: 0 2px; font-weight: bold'>+{item.value.length - 3}</span>
                      </span>
                    )}
                  </div>
                </div>
                <div
                  class='tag-remove'
                  onClick={() => this.handleRemoveTag(index)}
                >
                  <i
                    style='font-size: 12px;'
                    class='icon-monitor icon-mc-close-fill'
                  />
                </div>
              </div>
            );
          })}
          <div class='more-action-box'>
            <div
              key='add'
              class={{
                'add-btn': true,
                'is-disabled': this.isAddBtnDisabled,
              }}
              v-bk-tooltips={{
                content: this.$t('没有可选维度'),
                disabled: !this.isAddBtnDisabled,
              }}
              onClick={this.handleShowAppendPanel}
            >
              <i class='icon-monitor icon-a-1jiahao' />
            </div>
            {this.localValue.length > 0 && (
              <div
                key='clear'
                class='clear-btn'
                v-bk-tooltips={this.$t('清空')}
                onClick={this.handleClear}
              >
                <i class='icon-monitor icon-a-Clearqingkong' />
              </div>
            )}
          </div>
        </div>
        <EditPanel
          ref='editPanelRef'
          metricsList={this.latestMetricsList as IMetrics[]}
          value={this.currentEditDimension}
          onChange={this.handleEditPanelChange}
        />
      </div>
    );
  }
}
