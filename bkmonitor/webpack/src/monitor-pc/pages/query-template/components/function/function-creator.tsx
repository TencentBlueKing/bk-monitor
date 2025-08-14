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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SelectWrap from '../utils/select-wrap';
import VariableName from '../utils/variable-name';
import FunctionCreatorPop from './function-creator-pop';
import FunctionCreatorTag from './function-creator-tag';

import type { IFunctionOptionsItem, IVariablesItem } from '../type/query-config';

import './function-creator.scss';

interface IProps {
  hasCreateVariable?: boolean;
  isExpSupport?: boolean;
  options?: IFunctionOptionsItem[];
  showLabel?: boolean;
  showVariables?: boolean;
  variables?: IVariablesItem[];
  onCreateVariable?: (val: string) => void;
}

interface IValue {
  id: string;
  params: {
    id: string;
    value: string;
  }[];
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
  /** 是否有创建变量功能 */
  @Prop({ default: true }) hasCreateVariable: boolean;
  /** 只展示支持表达式的函数 */
  @Prop({ default: false, type: Boolean }) readonly isExpSupport: boolean;
  @Prop({ default: () => [] }) value: IValue[];

  showSelect = false;
  popClickHide = true;

  curTags: IFunctionOptionsItem[] = [];

  handleOpenChange(v) {
    this.showSelect = v;
  }

  handleAddVar(val: string) {
    this.$emit('createVariable', val);
  }

  handleSelect(item: IFunctionOptionsItem) {
    if (!this.curTags.map(item => item.id).includes(item.id)) {
      this.curTags.push(item);
    }
  }

  handleSelectVar(item: IFunctionOptionsItem) {
    if (!this.curTags.map(item => item.id).includes(item.id)) {
      this.curTags.push({
        ...item,
        isVariable: true,
      });
    }
  }

  handleDelTag(index: number) {
    this.curTags.splice(index, 1);
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
  }

  render() {
    return (
      <div class='template-function-creator-component'>
        {this.showLabel && <div class='function-label'>{this.$slots?.label || this.$t('函数')}</div>}
        <SelectWrap
          expanded={this.showSelect}
          minWidth={357}
          needPop={true}
          popClickHide={this.popClickHide}
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
            hasCreateVariable={this.hasCreateVariable}
            isExpSupport={this.isExpSupport}
            options={this.options}
            variables={this.variables}
            onAddVar={this.handleAddVar}
            onSelect={this.handleSelect}
            onSelectVar={this.handleSelectVar}
          />
        </SelectWrap>
      </div>
    );
  }
}
