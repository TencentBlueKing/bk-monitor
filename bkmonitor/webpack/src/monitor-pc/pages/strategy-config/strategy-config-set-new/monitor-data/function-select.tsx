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

import { Component, Emit, InjectReactive, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import debounceDecorator from 'monitor-common/utils/debounce-decorator';
import { random } from 'monitor-common/utils/utils';

import FunctionMenu, { type IFunctionItem, type IFunctionParam } from './function-menu';

import './function-select.scss';

export interface IFunctionsValue {
  id: string;
  params: { id: string; value: any }[];
}
interface IFunctionProps {
  value?: IFunctionsValue[];
  placeholder?: string;
  readonly?: boolean;
  isExpSupport?: boolean;
  isMultiple?: boolean;
}
interface IEvent {
  onValueChange?: IFunctionsValue[];
}
@Component
export default class FunctionSelect extends tsc<IFunctionProps, IEvent> {
  @Model('valueChange', { default: () => [], type: Array }) readonly value!: any[];
  @Prop({ default: window.i18n.t('选择'), type: String }) readonly placeholder: string;
  @Prop({ default: false, type: Boolean }) readonly readonly: boolean;
  /** 只展示支持表达式的函数 */
  @Prop({ type: Boolean }) readonly isExpSupport: boolean;
  /** 是否支持多选 */
  @Prop({ type: Boolean, default: true }) readonly isMultiple: boolean;
  @Ref('menuList') menuListRef: HTMLDivElement;
  @InjectReactive('metricFunctions') metricFunctions;
  localValue: IFunctionItem[] = [];
  popoverInstance: any = {};
  curFuncIndex = -1;
  curFuncParam: IFunctionParam = null;

  beforeDestroy() {
    this.destroyPopoverInstance();
  }
  @Watch('metricFunctions', { immediate: true })
  handleFunctionListChange() {
    this.localValue = [];
    let hasInvalid = false;
    this.value?.length &&
      this.metricFunctions.forEach(item => {
        this.value.forEach(vItem => {
          const funcItem = item?.children?.find(set => set.id === vItem.id);
          if (funcItem) {
            this.localValue.push({
              ...funcItem,
              key: random(10),
              params:
                funcItem?.params?.map?.(param => {
                  const paramItem = vItem.params?.find(p => p.id === param.id);
                  return {
                    ...param,
                    value: paramItem?.value || param?.default || param?.shortlist[0],
                    edit: false,
                  };
                }) || [],
            });
          } else {
            hasInvalid = true;
          }
        });
      });
    hasInvalid && this.handleValueChange();
  }
  // 选择函数时触发 初始化函数列表
  handleFuncSelect(item: IFunctionItem) {
    this.localValue.push({
      ...item,
      key: random(10),
      params: item.params.map(param => ({ ...param, value: param?.default || param?.shortlist[0], edit: false })),
    });
    this.handleValueChange();
  }
  @Emit('valueChange')
  /**
   * @description: 函数变化时触发
   * @param {*}
   * @return {*}
   */
  handleValueChange() {
    return this.localValue.map(({ id, params }) => ({
      id,
      params: params?.map(({ id, value }) => ({ id, value })),
    }));
  }
  // 点击函数名称时触发
  handleClickFuncName(e: MouseEvent, index: number) {
    this.curFuncParam = null;
    this.curFuncIndex = index;
    this.handleDeleteSelect();
  }
  // 删除选中函数时触发
  handleDeleteSelect() {
    this.curFuncIndex > -1 && this.localValue.splice(this.curFuncIndex, 1);
    this.curFuncIndex = -1;
    this.destroyPopoverInstance();
    this.handleValueChange();
  }
  // 选中函数参数时触发
  async handleClickParam(e: MouseEvent, param: IFunctionParam, refKey: string) {
    this.curFuncIndex = -1;
    this.curFuncParam = param;
    param.edit = true;
    await this.$nextTick();
    await this.handlePopoverShow(this.$refs[refKey] as Element, () => {
      param.edit = false;
    });
    (this.$refs[refKey] as HTMLInputElement).focus();
  }
  // 选中函数参数列表值时触发
  handleSelectParamValue(v: number | string) {
    this.curFuncParam.value = v;
    this.destroyPopoverInstance();
    this.handleValueChange();
  }
  // 手动修改函数参数值时触发
  @debounceDecorator(100)
  handleParamValueChange(e: { target: { value: number | string } }, param) {
    const { value } = e.target;
    if (`${value}` === `${param.value}`) return;
    this.curFuncParam.value = typeof value === 'number' ? value : value.trim();
    this.handleValueChange();
  }
  // 显示参数或者函数列表
  async handlePopoverShow(target: EventTarget, onHide?: () => void) {
    this.destroyPopoverInstance();
    await this.$nextTick();
    this.popoverInstance = this.$bkPopover(target, {
      content: this.menuListRef,
      trigger: 'click',
      theme: 'light common-monitor',
      arrow: false,
      maxWidth: 444,
      hideOnClick: true,
      interactive: true,
      boundary: 'window',
      offset: -1,
      distance: 12,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        typeof onHide === 'function' && onHide();
      },
    });
    this.popoverInstance?.show?.(100);
  }
  // 清除popover实例
  destroyPopoverInstance() {
    this.popoverInstance?.hide?.(0);
    this.popoverInstance?.destroy?.();
    this.popoverInstance = {};
  }
  render() {
    return (
      <span
        class={[
          'function-select-wrap',
          {
            'is-readonly': this.readonly,
          },
        ]}
      >
        <span
          class='func-label'
          data-type='func'
        >
          {this.$t('函数')}
        </span>
        {this.localValue.map((item, index) => (
          <bk-tag
            key={item.key}
            ref={`target-${item.key}`}
            ext-cls='func-item'
            data-type='func'
          >
            <span class={['is-hover', 'func-name', { 'is-readonly': this.readonly }]}>{item.name}</span>
            {item?.params?.length ? <span class='brackets'>&nbsp;(&nbsp;</span> : undefined}
            {item?.params?.map((param, pIndex) => (
              <span
                key={`${item.key}-${pIndex}`}
                class='params-item'
              >
                <span
                  style={{ display: !param.edit ? 'inline-block' : 'none' }}
                  class={['params-text', 'is-hover', { 'is-readonly': this.readonly }]}
                  on-click={e => this.handleClickParam(e, param, `input-${item.key}-${pIndex}`)}
                >
                  {param.value || `-${this.$t('空')}-`}
                </span>
                <input
                  ref={`input-${item.key}-${pIndex}`}
                  style={{ display: param.edit ? 'inline-block' : 'none' }}
                  class={['params-input', { 'is-edit': param.edit }]}
                  data-focus={param.edit}
                  value={param.value}
                  on-blur={evt => this.handleParamValueChange(evt, param)}
                />
                {pIndex !== item.params.length - 1 && <span>,&nbsp;</span>}
              </span>
            ))}
            {item?.params?.length ? <span class='brackets'>&nbsp;)&nbsp;</span> : undefined}
            <i
              class='bk-icon icon-close-circle-shape clear-icon'
              onClick={(e: MouseEvent) => this.handleClickFuncName(e, index)}
            />
          </bk-tag>
        ))}
        <FunctionMenu
          class='init-add'
          isExpSupport={this.isExpSupport}
          list={this.metricFunctions}
          isMultiple={this.isMultiple}
          onFuncSelect={this.handleFuncSelect}
        >
          {!this.localValue?.length && <span class='init-add-input'>{this.placeholder}</span>}
        </FunctionMenu>
        <div style='display: none'>
          <div
            ref='menuList'
            class='select-panel'
          >
            <ul class='select-list'>
              {this.curFuncParam?.shortlist?.length > 0 &&
                this.curFuncParam.shortlist.map(val => (
                  <li
                    key={val}
                    class={['select-list-item', { 'item-active': String(val) === String(this.curFuncParam.value) }]}
                    on-click={() => this.handleSelectParamValue(val)}
                  >
                    {val || `-${this.$t('空')}-`}
                  </li>
                ))}
            </ul>
            {this.curFuncIndex > -1 && (
              <div
                class='select-btn del-btn'
                on-click={this.handleDeleteSelect}
              >
                <i class='icon-monitor icon-mc-alarm-closed btn-icon' />
                {this.$t('删除')}
              </div>
            )}
          </div>
        </div>
      </span>
    );
  }
}
