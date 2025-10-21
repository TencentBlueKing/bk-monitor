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

import { NUMBER_CONDITION_METHOD_LIST, STRING_CONDITION_METHOD_LIST } from '../../../../constant/constant';
import { isEn } from '../../../../i18n/lang';
import { fetchMetricDimensionValueList } from '../../service/dimension';
import { isVariableName } from '../../variables/template/utils';
import { CONDITIONS } from './condition-condition-tag';
import ConditionCreatorSelector from './condition-creator-selector';
import { EFieldType } from './typing';

import type { IFilterItem, IGetValueFnParams } from '../../../../components/retrieval-filter/utils';
import type { MetricDetailV2 } from '../../typings/metric';
import type { AggCondition } from '../../typings/query-config';
import type { IConditionOptionsItem, IVariablesItem } from '../type/query-config';
import type { IFilterField } from './typing';

import './condition-creator.scss';

const methodNameMap = {
  include: '包含',
  exclude: '不包含',
  reg: '正则等于',
  nreg: '正则不等于',
};

interface IProps {
  allVariables?: { name: string }[];
  dimensionValueVariables?: { name: string }[];
  hasVariableOperate?: boolean;
  metricDetail?: MetricDetailV2;
  options?: IConditionOptionsItem[];
  showConditionTag?: boolean;
  showLabel?: boolean;
  value?: AggCondition[];
  variables?: IVariablesItem[];
  onChange?: (val: AggCondition[]) => void;
  onCreateValueVariable?: (val: { name: string; related_tag: string }) => void;
  onCreateVariable?: (val: string) => void;
  onPopoverShowChange?: (val: boolean) => void;
}

@Component
export default class ConditionCreator extends tsc<IProps> {
  /* 是否展示左侧标签 */
  @Prop({ default: true }) showLabel: boolean;
  /* 变量列表 */
  @Prop({ default: () => [] }) variables: IVariablesItem[];
  /* 可选项列表 */
  @Prop({ default: () => [] }) options: IConditionOptionsItem[];
  /* 是否展示变量 */
  @Prop({ default: true }) hasVariableOperate: boolean;
  @Prop({ default: () => [] }) value: AggCondition[];
  @Prop({ default: () => null }) metricDetail: MetricDetailV2;
  @Prop({ default: () => [], type: Array }) dimensionValueVariables: { name: string }[];
  /* 所有变量，用于校验变量名是否重复 */
  @Prop({ default: () => [] }) allVariables: { name: string }[];
  /** 是否展示条件标签 */
  @Prop({ default: false, type: Boolean }) showConditionTag: boolean;

  cacheDimensionValues = new Map();

  localValue: IFilterItem[] = [];

  @Watch('value', { immediate: true })
  handleWatchValue() {
    this.localValue = this.value.map(item => {
      const curField = this.fields.find(f => f.name === item.key);
      const keyName = curField?.alias || item.key;
      const methodName = curField?.supported_operations?.find(s => s.value === item.method)?.alias || item.method;
      return {
        condition: { id: item.condition, name: CONDITIONS.find(c => c.id === item.condition)?.name || item.condition },
        key: { id: item.key, name: keyName },
        method: { id: item.method, name: methodName },
        value: item.value.map(v => ({ id: v, name: v, isVariable: this.hasVariableOperate && isVariableName(v) })),
        options: this.hasVariableOperate
          ? {
              isVariable: isVariableName(item.key),
            }
          : undefined,
      };
    }) as IFilterItem[];
  }

  get fields() {
    return [
      ...(this.hasVariableOperate
        ? [
            {
              alias: '',
              name: '创建变量 ${}',
              type: EFieldType.custom_operator,
              is_option_enabled: false,
              supported_operations: [],
            },
          ]
        : []),
      ...this.variables.map(item => ({
        alias: item.name,
        name: item.name,
        type: EFieldType.variable,
        is_option_enabled: false,
        supported_operations: [],
      })),
      ...this.options.map(item => ({
        alias: item.name,
        name: item.id,
        type: EFieldType.text,
        is_option_enabled: true,
        supported_operations: this.handleGetMethodList(item?.dimensionType || 'string').map(item => ({
          alias: isEn ? item.name : methodNameMap?.[item.id] || item.name,
          value: item.id,
        })),
      })),
    ];
  }

  handleGetMethodList(type: 'number' | 'string') {
    if (type === 'number') {
      return NUMBER_CONDITION_METHOD_LIST;
    }
    return STRING_CONDITION_METHOD_LIST;
  }

  handleCreateVariable(val) {
    this.$emit('createVariable', val);
  }
  handleCreateValueVariable(val) {
    this.$emit('createValueVariable', val);
  }

  handlePopoverShowChange(show: boolean) {
    this.$emit('popoverShowChange', show);
  }

  handleChange(val: IFilterItem[]) {
    this.$emit(
      'change',
      val.map(item => {
        return {
          condition: item.condition.id,
          key: item.key.id,
          method: item.method.id,
          value: item.value.map(v => v.id),
        };
      })
    );
  }

  getValueFn(params: IGetValueFnParams): any {
    return new Promise(resolve => {
      const searchList = (search: string, list) => {
        if (!search) {
          return list;
        }
        const searchLower = search.toLocaleLowerCase();
        return list.filter(
          item =>
            item.name.toLocaleLowerCase().includes(searchLower) || item.id.toLocaleLowerCase().includes(searchLower)
        );
      };
      const searchValue = params?.where?.[0]?.value?.[0];
      const dimensionKey = params.fields[0];
      const list = this.cacheDimensionValues.get(dimensionKey);
      if (Array.isArray(list)) {
        const allOptions = [
          ...this.dimensionValueVariables.map(item => ({ name: item.name, id: item.name, isVariable: true })),
          ...list,
        ];
        const filterList = searchList(searchValue, allOptions);
        resolve({
          count: filterList.length,
          list: filterList,
        });
      } else {
        fetchMetricDimensionValueList(dimensionKey, {
          data_source_label: this.metricDetail?.data_source_label,
          data_type_label: this.metricDetail?.data_type_label,
          result_table_id: this.metricDetail?.result_table_id,
          metric_field: this.metricDetail?.metric_field,
        }).then(data => {
          const result = Array.isArray(data) ? data.map(item => ({ name: item.label, id: item.value })) : [];
          const allOptions = [
            ...this.dimensionValueVariables.map(item => ({ name: item.name, id: item.name, isVariable: true })),
            ...result,
          ];
          this.cacheDimensionValues.set(dimensionKey, result);
          const filterList = searchList(searchValue, allOptions);
          resolve({
            count: filterList.length,
            list: filterList,
          });
        });
      }
    });
  }

  render() {
    return (
      <div class='template-condition-creator-component'>
        {this.showLabel && <div class='condition-label'>{this.$slots?.label || this.$t('过滤条件')}</div>}
        <ConditionCreatorSelector
          allVariables={this.allVariables}
          dimensionValueVariables={this.dimensionValueVariables}
          fields={this.fields as IFilterField[]}
          getValueFn={this.getValueFn}
          hasVariableOperate={this.hasVariableOperate}
          showConditionTag={this.showConditionTag}
          value={this.localValue}
          onChange={this.handleChange}
          onCreateValueVariable={this.handleCreateValueVariable}
          onCreateVariable={this.handleCreateVariable}
          onPopoverShowChange={this.handlePopoverShowChange}
        />
      </div>
    );
  }
}
