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

import { NEW_NUMBER_CONDITION_METHOD_LIST, NEW_STRING_CONDITION_METHOD_LIST } from 'monitor-pc/constant/constant';

import UiSelector from '../../../../components/retrieval-filter/ui-selector';
import {
  type IFilterField,
  type IFilterItem,
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  EFieldType,
} from '../../../../components/retrieval-filter/utils';
import CommonItem from '../components/common-form-item';

import type { ICommonItem } from '../typings/index';

import './issue-agg.scss';

/** 告警级别列表 */
const LEVEL_LIST = [
  { id: 1, name: window.i18n.t('致命'), icon: 'icon-danger' },
  { id: 2, name: window.i18n.t('预警'), icon: 'icon-mind-fill' },
  { id: 3, name: window.i18n.t('提醒'), icon: 'icon-tips' },
];

export interface IIssueAggValue {
  /** 聚合维度 */
  agg_dimensions: string[];
  /** 过滤条件 */
  conditions: IFilterItem[];
  /** 生效告警级别 */
  levels: number[];
}

interface IEvents {
  onChange?: IIssueAggValue;
}

interface IProps {
  dimensions?: ICommonItem[];
  readonly?: boolean;
  value?: IIssueAggValue;
}

@Component({
  name: 'IssueAgg',
})
export default class IssueAgg extends tsc<IProps, IEvents> {
  @Prop({ type: Array, default: () => [] }) dimensions: ICommonItem[];
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  @Prop({
    type: Object,
    default: () => ({
      agg_dimensions: [],
      conditions: [],
      levels: [1, 2, 3],
    }),
  })
  value: IIssueAggValue;

  localValue: IIssueAggValue = {
    agg_dimensions: [],
    conditions: [],
    levels: [1, 2, 3],
  };

  @Watch('value', { immediate: true, deep: true })
  handleValueChange(val: IIssueAggValue) {
    this.localValue = { ...val };
  }

  @Emit('change')
  handleChange() {
    return this.localValue;
  }

  /** 聚合维度变更 */
  handleDimensionsChange(val: string[]) {
    this.localValue.agg_dimensions = val;
    this.handleChange();
  }

  /** 条件变更 */
  handleConditionsChange(val: IFilterItem[]) {
    this.localValue.conditions = val;
    this.handleChange();
  }

  /** 告警级别变更 */
  handleLevelsChange(val: number[]) {
    if (val.length === 0) return; // 至少选择一个
    this.localValue.levels = val;
    this.handleChange();
  }

  /** 获取维度字段列表（用于条件选择器） */
  get filterFields(): IFilterField[] {
    return this.dimensions.map(item => ({
      alias: item.name,
      is_option_enabled: true,
      name: item.id,
      type: EFieldType.keyword,
      supported_operations: (item?.type === 'number'
        ? NEW_NUMBER_CONDITION_METHOD_LIST
        : NEW_STRING_CONDITION_METHOD_LIST
      ).map(m => {
        return {
          alias: m.name,
          value: m.id,
        };
      }),
    }));
  }

  /** 获取维度值的方法（需要根据实际情况实现） */
  getValueFn(_params: IGetValueFnParams): Promise<IWhereValueOptionsItem> {
    // TODO: 实现获取维度值的逻辑
    return Promise.resolve({
      count: 0,
      list: [],
    });
  }

  render() {
    return (
      <div class='issue-agg-container'>
        <CommonItem
          title={this.$t('聚合维度')}
          isRequired
        >
          <bk-select
            class='dimension-select'
            v-model={this.localValue.agg_dimensions}
            behavior='simplicity'
            disabled={this.readonly}
            placeholder={this.$t('请选择聚合维度')}
            size='small'
            display-tag
            multiple
            searchable
            onChange={this.handleDimensionsChange}
          >
            {this.dimensions.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.name}
              />
            ))}
          </bk-select>
        </CommonItem>
        <CommonItem title={this.$t('过滤条件')}>
          <UiSelector
            class='condition-select'
            scopedSlots={{
              addBtn: click => {
                return (
                  <div
                    class='cus-add-btn'
                    onClick={click}
                  >
                    <span class='icon-monitor icon-mc-add' />
                  </div>
                );
              },
            }}
            addBtnAlign={'right'}
            fields={this.filterFields}
            getValueFn={this.getValueFn}
            hasConditionChange={true}
            hasInput={false}
            kvTagHasHideBtn={false}
            value={this.localValue.conditions}
            onChange={this.handleConditionsChange}
          />
        </CommonItem>
        <CommonItem
          title={this.$t('生效告警级别')}
          isRequired
        >
          <bk-checkbox-group
            class='levels-checkbox'
            v-model={this.localValue.levels}
            onChange={this.handleLevelsChange}
          >
            {LEVEL_LIST.map(level => (
              <bk-checkbox
                key={level.id}
                value={level.id}
              >
                <i class={`icon-monitor ${level.icon}`} />
                {level.name}
              </bk-checkbox>
            ))}
          </bk-checkbox-group>
        </CommonItem>
      </div>
    );
  }
}
