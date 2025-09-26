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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils/utils';

import { isVariableName } from '../../variables/template/utils';
import AddVariableOption from '../utils/add-variable-option';
import SelectWrap from '../utils/select-wrap';
import VariableName from '../utils/variable-name';
import AutoWidthInput from '@/components/retrieval-filter/auto-width-input';

import type { IDimensionOptionsItem, IVariablesItem } from '../type/query-config';

import './dimension-creator.scss';

interface IProps {
  allVariables?: { name: string }[];
  options?: IDimensionOptionsItem[];
  showLabel?: boolean;
  showVariables?: boolean;
  value?: string[];
  variables?: IVariablesItem[];
  onChange?: (val: string[]) => void;
  onCreateVariable?: (val: string) => void;
}

@Component
export default class DimensionCreator extends tsc<IProps> {
  /* 是否展示左侧标签 */
  @Prop({ default: true }) showLabel: boolean;
  /* 变量列表 */
  @Prop({ default: () => [] }) variables: IVariablesItem[];
  /* 可选项列表 */
  @Prop({ default: () => [] }) options: IDimensionOptionsItem[];
  /* 是否展示变量 */
  @Prop({ default: false }) showVariables: boolean;
  @Prop({ default: () => [] }) value: string[];
  /* 所有变量，用于校验变量名是否重复 */
  @Prop({ default: () => [] }) allVariables: { name: string }[];

  @Ref('inputRef') inputRef: AutoWidthInput;

  showSelect = false;
  popClickHide = true;

  allOptions: IDimensionOptionsItem[] = [];
  curTags: IDimensionOptionsItem[] = [];

  inputValue = '';
  popOffsetLeft = 0;

  @Watch('options', { immediate: true })
  handleWatchOptions() {
    this.getAllOptions();
  }

  @Watch('variables', { immediate: true })
  handleWatchVariables() {
    this.getAllOptions();
  }
  @Watch('curTags')
  handleWatchCurTags() {
    this.$nextTick(() => {
      this.popOffsetLeft = this.inputRef.$el.offsetLeft;
    });
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    const optionMap = new Map();
    for (const o of this.options) {
      optionMap.set(o.id, o);
    }
    this.curTags = this.value.map(item => ({
      id: item,
      name: optionMap.get(item)?.name || item,
      isVariable: this.showVariables && isVariableName(item),
    }));
  }

  handleOpenChange(v) {
    this.showSelect = v;
    if (v) {
      this.getAllOptions();
    }
  }

  handleAddVar(val) {
    this.popClickHide = true;
    this.handleSelect({
      id: val,
      name: val,
      isVariable: true,
    });
    this.$emit('createVariable', val);
  }
  handleAddVariableOpenChange(val: boolean) {
    this.popClickHide = !val;
  }

  getAllOptions() {
    const curTagsIds = this.curTags.map(item => item.id);
    this.allOptions = [
      ...this.variables.map(item => ({
        ...item,
        id: item.name,
        isVariable: true,
      })),
      ...this.options,
    ].filter(item => {
      const search = this.inputValue.toLocaleLowerCase();
      return (
        !curTagsIds.includes(item.id) &&
        (item.name.toLocaleLowerCase().includes(search) || item.id.toLocaleLowerCase().includes(search))
      );
    });
  }

  handleSelect(item: IDimensionOptionsItem) {
    if (!this.popClickHide) {
      return;
    }
    if (this.curTags.find(t => t.id === item.id)) {
      return;
    }
    this.curTags.push(item);
    this.getAllOptions();
    this.showSelect = false;
    this.$emit(
      'change',
      this.curTags.map(item => item.id)
    );
  }

  handleInputChange(val: string) {
    this.inputValue = val;
    this.getDebounceAllOptions();
  }

  @Debounce(300)
  getDebounceAllOptions() {
    this.getAllOptions();
  }

  handleDelTag(index: number) {
    this.curTags.splice(index, 1);
    this.$emit(
      'change',
      this.curTags.map(item => item.id)
    );
  }

  handleInputEnter() {
    if (this.inputValue) {
      const isVariable = this.showVariables && isVariableName(this.inputValue);
      this.handleSelect({
        id: this.inputValue,
        name: this.inputValue,
        isVariable: isVariable,
      });
      if (isVariable) {
        this.$emit('createVariable', this.inputValue);
      }
      this.inputValue = '';
    }
  }

  handleClear() {
    this.curTags = [];
    this.$emit('change', []);
  }

  handleBlur() {
    this.inputValue = '';
  }

  render() {
    return (
      <div class='template-dimension-creator-component'>
        {this.showLabel && <div class='dimension-label'>{this.$slots?.label || this.$t('聚合维度')}</div>}
        <SelectWrap
          expanded={this.showSelect}
          minWidth={408}
          needClear={!!this.curTags.length}
          needPop={true}
          popClickHide={this.popClickHide}
          popOffset={this.popOffsetLeft}
          onClear={this.handleClear}
          onOpenChange={this.handleOpenChange}
        >
          <div class='tags-wrap'>
            {this.curTags.map((item, index) => (
              <div
                key={index}
                class='tags-item'
                v-bk-tooltips={{
                  placements: ['top'],
                  content: item.id,
                  delay: [300, 0],
                }}
              >
                <span class='tags-item-name'>{item.isVariable ? <VariableName name={item.name} /> : item.name}</span>
                <span
                  class='icon-monitor icon-mc-close'
                  onClick={e => {
                    e.stopPropagation();
                    this.handleDelTag(index, item);
                  }}
                />
              </div>
            ))}
            <AutoWidthInput
              ref='inputRef'
              placeholder={this.$t('请选择') as string}
              value={this.inputValue}
              onBlur={this.handleBlur}
              onEnter={this.handleInputEnter}
              onInput={this.handleInputChange}
            />
          </div>
          <div
            class='template-dimension-creator-component-options-popover'
            slot='popover'
          >
            {this.showVariables && (
              <AddVariableOption
                allVariables={this.allVariables}
                onAdd={this.handleAddVar}
                onOpenChange={this.handleAddVariableOpenChange}
              />
            )}

            {this.allOptions.map((item, index) => (
              <div
                key={index}
                class='options-item'
                v-bk-tooltips={{
                  placements: ['right'],
                  content: item.id,
                  delay: [300, 0],
                }}
                onClick={() => this.handleSelect(item)}
              >
                {item.isVariable ? (
                  <span class='options-item-name'>
                    <VariableName name={item.name} />
                  </span>
                ) : (
                  <span class='options-item-name'>{item.name}</span>
                )}
              </div>
            ))}
          </div>
        </SelectWrap>
      </div>
    );
  }
}
