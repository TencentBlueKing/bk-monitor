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

import {
  type IFilterItem,
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  ECondition,
  EMethod,
} from '../../../../components/retrieval-filter/utils';
import VariableName from '../utils/variable-name';
import ConditionCreatorOptions from './condition-creator-options';
import KvTag from './kv-tag';

import type { IFilterField } from './typing';

import './condition-creator-selector.scss';

interface IProps {
  allVariables?: { name: string }[];
  clearKey?: string;
  dimensionValueVariables?: { name: string }[];
  fields?: IFilterField[];
  hasVariableOperate?: boolean;
  value?: IFilterItem[];
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onAddVariableOpenChange?: (val: boolean) => void;
  onChange?: (v: IFilterItem[]) => void;
  onCreateValueVariable?: (val: { name: string; related_tag: string }) => void;
  onCreateVariable?: (variableName: string) => void;
  onPopoverShowChange?: (val: boolean) => void;
}

@Component
export default class ConditionCreatorSelector extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  @Prop({ type: Array, default: () => [] }) value: IFilterItem[];
  @Prop({ type: String, default: '' }) clearKey: string;
  @Prop({ type: Boolean, default: true }) hasVariableOperate: boolean;
  @Prop({ type: Array, default: () => [] }) dimensionValueVariables: { name: string }[];
  /* 所有变量，用于校验变量名是否重复 */
  @Prop({ default: () => [] }) allVariables: { name: string }[];
  @Ref('selector') selectorRef: HTMLDivElement;

  /* 是否显示弹出层 */
  showSelector = false;
  /* tag列表 */
  localValue: IFilterItem[] = [];
  /* 弹层实例 */
  popoverInstance = null;
  /* 当亲编辑项 */
  updateActive = -1;
  isHover = false;

  showCreateVariablePop = false;

  @Watch('value', { immediate: true })
  handleWatchValue() {
    const valueStr = JSON.stringify(this.value);
    const localValueStr = JSON.stringify(this.localValue);
    if (valueStr !== localValueStr) {
      this.localValue = JSON.parse(valueStr);
    }
  }

  async handleShowSelect(event: MouseEvent) {
    if (this.popoverInstance) {
      this.destroyPopoverInstance();
      return;
    }
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.selectorRef,
      trigger: 'click',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: false,
      interactive: true,
      boundary: 'window',
      distance: 17,
      zIndex: 998,
      animation: 'slide-toggle',
      followCursor: false,
      onHide: () => {
        return !this.showCreateVariablePop;
      },
      onHidden: () => {
        this.destroyPopoverInstance();
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show();
    this.handlePopoverShowChange(true);
    this.showSelector = true;
  }
  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.showSelector = false;
    this.handlePopoverShowChange(false);
  }

  handleAdd(event: MouseEvent) {
    event.stopPropagation();
    this.updateActive = -1;
    const customEvent = {
      ...event,
      target: event.currentTarget,
    };
    this.handleShowSelect(customEvent);
  }

  /**
   * @description 点击弹层取消
   */
  handleCancel() {
    this.destroyPopoverInstance();
  }
  /**
   * @description 点击弹层确认
   */
  handleConfirm(value: IFilterItem) {
    const localValue = JSON.parse(JSON.stringify(this.localValue));
    if (value) {
      if (this.updateActive > -1) {
        localValue.splice(this.updateActive, 1, value);
      } else {
        localValue.push(value);
      }
    }
    this.localValue = localValue;
    this.destroyPopoverInstance();
    this.handleChange();
  }

  /**
   * @description 删除tag
   * @param index
   */
  handleDeleteTag(index: number) {
    this.localValue.splice(index, 1);
    this.handleChange();
    this.handleCancel();
  }

  /**
   * @description 编辑tag
   * @param event
   * @param index
   */
  handleUpdateTag(event: MouseEvent, index: number) {
    event.stopPropagation();
    this.updateActive = index;
    const customEvent = {
      ...event,
      target: event.currentTarget,
    };
    this.handleShowSelect(customEvent);
  }

  handleChange() {
    this.$emit('change', this.localValue);
  }

  handlePopoverShowChange(show: boolean) {
    this.$emit('popoverShowChange', show);
  }

  handleMouseEnter() {
    this.isHover = true;
  }
  handleMouseLeave() {
    this.isHover = false;
  }

  handleCreateVariable(val) {
    this.$emit('createVariable', val);
    this.localValue.push({
      key: { id: val, name: val },
      method: { id: EMethod.eq, name: '' },
      value: [],
      condition: { id: ECondition.and, name: 'AND' },
      options: {
        isVariable: true,
      },
    });
    this.destroyPopoverInstance();
    this.handleChange();
  }

  handleAddVariableOpenChange(val: boolean) {
    this.showCreateVariablePop = val;
    this.$emit('addVariableOpenChange', val);
  }

  handleCreateValueVariable(val) {
    this.$emit('createValueVariable', val);
  }

  render() {
    return (
      <div
        class='template-config-ui-selector-component'
        onMouseenter={this.handleMouseEnter}
        onMouseleave={this.handleMouseLeave}
      >
        {this.localValue.map((item, index) =>
          item?.options?.isVariable ? (
            <div
              key={`${index}_kv`}
              class='variable-tag'
              onClick={event => this.handleUpdateTag(event, index)}
            >
              <VariableName name={item.key.name} />
              <span
                class='icon-monitor icon-mc-close'
                onClick={(e: MouseEvent) => {
                  e.stopPropagation();
                  this.handleDeleteTag(index);
                }}
              />
            </div>
          ) : (
            <KvTag
              key={`${index}_kv`}
              hasHideBtn={false}
              value={item}
              onDelete={() => this.handleDeleteTag(index)}
              onUpdate={event => this.handleUpdateTag(event, index)}
            />
          )
        )}

        <div
          class='add-btn'
          onClick={this.handleAdd}
        >
          <span class='icon-monitor icon-mc-add' />
        </div>

        <div style='display: none;'>
          <div ref='selector'>
            <ConditionCreatorOptions
              allVariables={this.allVariables}
              dimensionValueVariables={this.dimensionValueVariables}
              fields={this.fields}
              getValueFn={this.getValueFn}
              hasVariableOperate={this.hasVariableOperate}
              isEnterSelect={true}
              show={this.showSelector}
              value={this.localValue?.[this.updateActive]}
              onAddVariableOpenChange={this.handleAddVariableOpenChange}
              onCancel={this.handleCancel}
              onConfirm={this.handleConfirm}
              onCreateValueVariable={this.handleCreateValueVariable}
              onCreateVariable={this.handleCreateVariable}
            />
          </div>
        </div>
      </div>
    );
  }
}
