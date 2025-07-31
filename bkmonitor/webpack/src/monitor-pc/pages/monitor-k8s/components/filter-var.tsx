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

import { getVariableValue } from 'monitor-api/modules/grafana';

import CustomSelect from '../../../components/custom-select/custom-select';

import type { IOption, IWhere } from '../typings';
import type { IFilterVarList } from '../typings/filters';

import './filter-var.scss';

export interface IFilterVarEvents {
  onVarChange: IFilterVarList[];
}
export interface IFilterVarProps {
  tabActive: string;
  varOptions: IVarOptions[];
}
export interface IVarOptions {
  checked: boolean;
  id: string;
  name: string;
  value: string[];
  where: IWhere[];
}
@Component
export default class FilterVar extends tsc<IFilterVarProps, IFilterVarEvents> {
  /** 变量的可选数据 */
  @Prop({ default: () => [], type: Array }) varOptions: IVarOptions[];
  /** 页签 */
  @Prop({ default: '', type: String }) tabActive: string;
  /** 选中的变量 */
  selectedVar: string[] = [];
  /** 变量的值 */
  localValue: IFilterVarList[] = [];

  /** 变量可选值的缓存 */
  optionsMap: Map<string, IOption[]> = new Map();

  @Watch('varOptions')
  tabActiveChange() {
    this.selectedVar = [];
    this.varOptions.forEach(item => {
      item.checked && this.selectedVar.push(item.id);
    });
    this.handleAddVar(this.selectedVar);
  }

  /**
   * @description: 变量的增删
   * @param {*} val 变量的key
   */
  handleAddVar(val) {
    this.selectedVar = val;
    const temp = this.selectedVar.map(item => {
      const varOption = this.varOptions.find(opt => opt.id === item);
      return {
        key: item,
        name: varOption.name,
        options: [],
        value: varOption.value || [],
        where: varOption.where,
      };
    });
    this.localValue = temp;
    this.handleVarChange();
    this.handleGetOpotions();
  }

  /**
   * @description: 获取变量的可选值
   */
  handleGetOpotions() {
    return this.localValue.map(async item => {
      if (this.optionsMap.has(item.key)) {
        item.options = this.optionsMap.get(item.key);
      } else {
        const data = await this.getGroupByOptionalValueList(item.key, item.where);
        item.options = data || [];
        this.optionsMap.set(item.key, data);
      }
    });
  }

  /**
   * @description: 获取维度的可选值
   * @param {string} groupBy 维度
   * @param {SettingsVarType} where 条件
   * @return {*}
   */
  getGroupByOptionalValueList(groupBy = '', where: IWhere[] = []): Promise<IOption[]> {
    const metric = {
      metric_field: 'usage',
      result_table_id: 'system.cpu_summary',
      data_source_label: 'bk_monitor',
      data_type_label: 'time_series',
    };
    const params = {
      params: {
        ...metric,
        field: groupBy,
        where,
      },
      type: 'dimension',
    };
    return getVariableValue(params).then(data => data.map(item => ({ id: item.value, name: item.label })));
  }

  /**
   * @description: 过滤条件值更新
   * @return {IFilterVarList[]}
   */
  @Emit('varChange')
  handleVarChange(): IFilterVarList[] {
    return this.localValue;
  }

  render() {
    return (
      <div class='filter-var-wrap'>
        <span class='filter-var-label'>Filters</span>
        {this.localValue.map(item => (
          <span class='filter-var-item'>
            <span class='filter-var-item-label'>{item.name}</span>
            <bk-select
              class='filter-var-item-select'
              vModel={item.value}
              behavior='simplicity'
              popover-width={100}
              multiple
              onClear={this.handleVarChange}
              onSelected={this.handleVarChange}
            >
              {item.options.map(opt => (
                <bk-option
                  id={opt.id}
                  name={opt.name}
                />
              ))}
            </bk-select>
          </span>
        ))}
        <CustomSelect
          class='filter-var-add'
          value={this.selectedVar}
          multiple
          onSelected={this.handleAddVar}
        >
          {this.varOptions.map(opt => (
            <bk-option
              id={opt.id}
              name={opt.name}
            />
          ))}
        </CustomSelect>
      </div>
    );
  }
}
