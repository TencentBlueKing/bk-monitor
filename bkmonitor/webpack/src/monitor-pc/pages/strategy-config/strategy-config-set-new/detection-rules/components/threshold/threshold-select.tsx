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

import SelectMenu from '../../../components/select-menu';

import './threshold-select.scss';

export interface IItem {
  id: string | number;
  name: string | number;
}

export interface ILocalValueItem {
  method: string;
  value: number;
  condition: string;
}
export type IThresholdSelectValue = Array<Array<{ method: string; threshold: number }>>;
interface IThresholdSelect {
  value?: IThresholdSelectValue;
  methodList?: IItem[];
  readonly?: boolean;
  unit: string;
  label?: string;
  autoAdd?: boolean;
}

interface IEvent {
  onChange?: any;
}

@Component({ name: 'ThresholdSelect' })
export default class ThresholdSelect extends tsc<IThresholdSelect, IEvent> {
  @Prop({ default: () => [], type: Array }) readonly value: IThresholdSelectValue;
  @Prop({ default: () => [], type: Array }) readonly methodList: IItem[];
  @Prop({ default: false, type: Boolean }) readonly readonly: boolean;
  @Prop({ default: '', type: String }) readonly unit: string;
  @Prop({ type: Boolean, default: true }) readonly autoAdd: boolean;
  @Prop({
    default: () => [
      { id: 'or', name: 'OR' },
      { id: 'and', name: 'AND' }
    ],
    type: Array
  })
  readonly conditionList: IItem[];
  @Prop({ type: String, default: window.i18n.tc('（当前值）') }) label: string;

  /** 下拉数据 */
  showSelectMenu = false;
  curSelectTarget: any = null;
  menuList: IItem[] = [];
  curIndex: number = null;
  curValueIndex: number = null;
  curType: 'condition' | 'method' = null;
  needDelete = false;

  localValue: ILocalValueItem[] = [];
  localValueRenderList = [];

  get isChinese(): boolean {
    return this.$store.getters.lang !== 'en';
  }

  @Watch('value', { immediate: true, deep: true })
  updateLocalValue(value: IThresholdSelectValue) {
    if (!Array.isArray(value)) return;
    if (!value.length && this.autoAdd) this.handleAdd();
    this.localValue = [];
    value.forEach((item, index) => {
      item.forEach((child, i) => {
        const isAnd = index === 0 || i !== 0;
        this.localValue.push({
          method: child.method,
          value: child.threshold,
          condition: isAnd ? 'and' : 'or'
        });
      });
    });
    this.handleLocalValueRenderList();
  }

  @Emit('change')
  emitLocalChange(): IThresholdSelectValue {
    const value = [];
    this.localValue.forEach((item, index) => {
      if (index === 0 || item.condition === 'or') {
        value.push([
          {
            method: item.method,
            threshold: item.value
          }
        ]);
      } else {
        const lastChild = value[value.length - 1];
        lastChild?.push({
          method: item.method,
          threshold: item.value
        });
      }
    });
    return value;
  }

  isActive(index: number, type: 'condition' | 'method') {
    return this.curIndex === index && this.showSelectMenu === true && this.curType === type;
  }

  handleLocalValueRenderList() {
    this.localValueRenderList = [];
    this.localValue.forEach((item, index) => {
      const condition = { condition: item, index };
      const method = { method: item };
      const value = { value: item };
      this.localValueRenderList.push(condition);
      this.localValueRenderList.push(method);
      this.localValueRenderList.push(value);
    });
  }

  methodNameDisplsy(id) {
    const res = this.methodList.find(item => item.id === id);
    return res ? res.name : id;
  }

  conditionNameDisplsy(id) {
    const res = this.conditionList.find(item => item.id === id);
    return res ? res.name : id;
  }

  handleAdd() {
    this.localValue.push({
      method: 'gte',
      value: 0,
      condition: 'and'
    });
    this.emitLocalChange();
  }

  handleShowSelect(ref: string, index: number, valueIndex?: number) {
    if (this.readonly) return;
    if (this.showSelectMenu) return;
    const isCondition = ref.indexOf('condition') > -1;
    this.curType = isCondition ? 'condition' : 'method';
    this.needDelete = isCondition;
    this.menuList = isCondition ? this.conditionList : this.methodList;
    // eslint-disable-next-line prefer-destructuring
    this.curSelectTarget = this.$refs[ref];
    this.curIndex = index;
    this.curValueIndex = valueIndex;
    this.showSelectMenu = true;
  }

  handelMenuSelect({ id }) {
    const row = this.localValueRenderList[this.curIndex];
    row[this.curType][this.curType] = id;
    this.emitLocalChange();
  }

  handleMenuHidden() {
    this.curSelectTarget = null;
    this.menuList = [];
    this.showSelectMenu = false;
  }

  handleMenuDelete() {
    this.localValue.splice(this.curValueIndex, 1);
    this.emitLocalChange();
  }

  render() {
    return (
      <div class={['threshold-select-wrap', { 'is-readonly': this.readonly }]}>
        <span
          class='desc-text'
          style='margin-right: 8px;'
        >
          {this.label}
        </span>
        {this.localValueRenderList.map((item, index) => {
          if (item.condition) {
            return (
              <span
                style={`display: ${!index && 'none;'}`}
                key={`condition-${index}`}
                class='condition active'
                ref={`condition-${index}`}
                onClick={() => this.handleShowSelect(`condition-${index}`, index, item.index)}
              >
                {this.conditionNameDisplsy(item.condition.condition)}
              </span>
            );
          }
          if (item.method) {
            return (
              <span
                key={`method-${index}`}
                ref={`method-${index}`}
                class={['method', { active: this.isActive(index, 'method') }]}
                onClick={() => this.handleShowSelect(`method-${index}`, index)}
              >
                {this.methodNameDisplsy(item.method.method)}
              </span>
            );
          }
          if (item.value) {
            return (
              <span key={`value-${index}`}>
                <bk-input
                  class={[
                    'num-input',
                    {
                      'has-unit': this.unit,
                      'has-unit-larger': this.unit.length > 2
                    }
                  ]}
                  behavior='simplicity'
                  readonly={this.readonly}
                  onInput={this.emitLocalChange}
                  // style="width: 78px"
                  v-model={item.value.value}
                  type='number'
                >
                  <template slot='append'>
                    <div class='right-unit'>{this.unit}</div>
                  </template>
                </bk-input>
              </span>
            );
          }
        })}
        {!this.readonly && (
          <span
            class='add-btn icon-monitor icon-mc-add'
            onClick={this.handleAdd}
          ></span>
        )}
        {this.isChinese ? (
          <span
            class='desc-text'
            style='margin-left: 8px;'
          >
            时触发告警
          </span>
        ) : undefined}
        <SelectMenu
          show={this.showSelectMenu}
          target={this.curSelectTarget}
          list={this.menuList}
          min-width={60}
          need-delete={this.needDelete}
          {...{
            on: {
              'on-delete': this.handleMenuDelete,
              'on-select': this.handelMenuSelect,
              'on-hidden': this.handleMenuHidden
            }
          }}
        ></SelectMenu>
      </div>
    );
  }
}
