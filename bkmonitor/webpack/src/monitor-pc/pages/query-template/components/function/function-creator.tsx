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

import { isVariableName } from '../../variables/template/utils';
import SelectWrap from '../utils/select-wrap';
import VariableName from '../utils/variable-name';
import FunctionCreatorPop from './function-creator-pop';
import FunctionCreatorTag from './function-creator-tag';

import type { AggFunction } from '../../typings';
import type { IFunctionOptionsItem, IVariablesItem } from '../type/query-config';

import './function-creator.scss';

interface IProps {
  allVariables?: { name: string }[];
  isExpSupport?: boolean;
  needClear?: boolean;
  options?: IFunctionOptionsItem[];
  showLabel?: boolean;
  showVariables?: boolean;
  value?: AggFunction[];
  variables?: IVariablesItem[];
  onChange?: (val: AggFunction[]) => void;
  onCreateVariable?: (val: string) => void;
  onOpenChange?: (val: boolean) => void;
}

@Component
export default class FunctionCreator extends tsc<IProps> {
  /* 是否展示左侧标签 */
  @Prop({ default: true }) showLabel: boolean;
  /* 变量列表 */
  @Prop({ default: () => [] }) variables: IVariablesItem[];
  /* 可选项列表 */
  @Prop({ default: () => [] }) options: IFunctionOptionsItem[];
  /* 是否展示变量 */
  @Prop({ default: false }) showVariables: boolean;
  /** 只展示支持表达式的函数 */
  @Prop({ default: false, type: Boolean }) readonly isExpSupport: boolean;
  @Prop({ default: () => [] }) value: AggFunction[];
  /* 所有变量，用于校验变量名是否重复 */
  @Prop({ default: () => [] }) allVariables: { name: string }[];
  @Prop({ default: true }) needClear: boolean;

  showSelect = false;
  popClickHide = true;

  curTags: IFunctionOptionsItem[] = [];

  @Watch('value', { immediate: true })
  handleValueChange(val: AggFunction[]) {
    if (!val?.length) {
      return;
    }
    const optionMap = new Map();
    for (const option of this.options) {
      for (const child of option?.children || []) {
        optionMap.set(child.id, child);
      }
    }
    this.curTags = val.map(item => {
      const option = optionMap.get(item.id);
      const isVariable = isVariableName(item.id);
      return {
        ...(isVariable
          ? {
              id: item.id,
              name: item.id,
            }
          : option),
        isVariable,
        params: isVariable
          ? []
          : item?.params?.map(p => {
              const optionP = option?.params?.find(param => param.id === p.id);
              if (optionP) {
                return {
                  ...optionP,
                  value: p.value,
                };
              }
              return {
                ...p,
              };
            }) || [],
      };
    });
  }

  handleOpenChange(v) {
    this.showSelect = v;
    this.$emit('openChange', v);
  }

  handleAddVar(val: string) {
    this.handleSelectVar({
      id: val,
      name: val,
      isVariable: true,
      params: [],
    });
    this.showSelect = false;
    this.$emit('createVariable', val);
  }

  handleSelect(item: IFunctionOptionsItem) {
    if (!this.curTags.map(item => item.id).includes(item.id)) {
      this.curTags.push(item);
      this.handleChange();
    }
    this.showSelect = false;
  }

  handleSelectVar(item: IFunctionOptionsItem) {
    if (!this.curTags.map(item => item.id).includes(item.id)) {
      this.curTags.push({
        ...item,
        isVariable: true,
      });
      this.handleChange();
    }
    this.showSelect = false;
  }

  handleDelTag(index: number) {
    this.curTags.splice(index, 1);
    this.handleChange();
  }

  /**
   * @description 处理函数参数改变
   * @param val
   * @param index
   */
  handleFunctionParamsChange(val, index: number) {
    this.curTags[index].params = this.curTags[index].params.map(item => {
      const param = val.find(param => param.id === item.id);
      if (param) {
        return {
          ...item,
          value: param.value,
        };
      }
      return item;
    });
    this.handleChange();
  }

  handleClear() {
    this.curTags = [];
    this.handleChange();
  }

  handleChange() {
    this.$emit(
      'change',
      this.curTags.map(item => ({
        id: item.id,
        params: item?.isVariable
          ? []
          : item.params?.map(p => ({
              id: p.id,
              value: p?.value || p?.default,
            })),
      }))
    );
  }

  handleCancel() {
    this.showSelect = false;
  }

  render() {
    return (
      <div class='template-function-creator-component'>
        {this.showLabel && <div class='function-label'>{this.$slots?.label || this.$t('函数')}</div>}
        <SelectWrap
          expanded={this.showSelect}
          minWidth={357}
          needClear={this.needClear && !!this.curTags.length}
          needPop={true}
          popClickHide={this.popClickHide}
          onClear={this.handleClear}
          onOpenChange={this.handleOpenChange}
        >
          {this.curTags.length ? (
            <div class='tags-wrap'>
              {this.curTags.map((item, index) => (
                <div
                  key={index}
                  class='tags-item'
                >
                  <span class='tags-item-name'>
                    {item.isVariable ? (
                      <VariableName name={item.name} />
                    ) : (
                      <FunctionCreatorTag
                        value={item}
                        onChange={val => this.handleFunctionParamsChange(val, index)}
                      />
                    )}
                  </span>
                  <span
                    class='icon-monitor icon-mc-close'
                    onClick={e => {
                      e.stopPropagation();
                      this.handleDelTag(index);
                    }}
                  />
                </div>
              ))}
            </div>
          ) : (
            <p class='placeholder'>{this.$t('请选择')}</p>
          )}
          <FunctionCreatorPop
            slot='popover'
            allVariables={this.allVariables}
            hasCreateVariable={this.showVariables}
            isExpSupport={this.isExpSupport}
            options={this.options}
            selected={this.curTags}
            variables={this.variables}
            onAddVar={this.handleAddVar}
            onCancel={this.handleCancel}
            onSelect={this.handleSelect}
            onSelectVar={this.handleSelectVar}
          />
        </SelectWrap>
      </div>
    );
  }
}
