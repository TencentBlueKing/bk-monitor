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

import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { IFunctionOptionsItem, IFunctionParam } from '../type/query-config';

import './function-creator-tag.scss';

interface IProps {
  value?: IFunctionOptionsItem;
  onChange?: (val) => void;
}

@Component
export default class FunctionCreatorTag extends tsc<IProps> {
  @Prop({ default: () => null, type: Object }) value: IFunctionOptionsItem;

  @Ref('menuList') menuListRef: HTMLElement;

  curFuncIndex = -1;
  curFuncParam = null;
  popoverInstance = null;
  params: IFunctionParam[] = [];

  created() {
    this.params = (this.value?.params || []).map(item => ({
      ...item,
      value: item?.value || item.default || '',
      edit: false,
    }));
  }

  // 选中函数参数时触发
  async handleClickParam(e: MouseEvent, index: number, refKey: string) {
    e.stopPropagation();
    this.curFuncIndex = -1;
    this.curFuncParam = this.params[index];
    this.params[index].edit = true;
    await this.$nextTick();
    await this.handlePopoverShow(this.$refs[refKey] as Element, () => {
      this.params[index].edit = false;
    });
    (this.$refs[refKey] as HTMLInputElement).focus();
  }
  handleParamValueChange(e: { target: { value: number | string } }, param) {
    const { value } = e.target;
    if (`${value}` === `${param.value}`) return;
    this.curFuncParam.value = typeof value === 'number' ? value : value.trim();
    this.handleValueChange();
  }

  handleValueChange() {
    this.$emit(
      'change',
      this.params.map(param => ({
        id: param.id,
        value: param.value,
      }))
    );
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

  handleDeleteSelect() {}
  handleSelectParamValue(v: number | string) {
    this.curFuncParam.value = v;
    this.destroyPopoverInstance();
    this.handleValueChange();
  }

  handleClickInput(e: MouseEvent, _index: number) {
    e.stopPropagation();
  }

  render() {
    return (
      <span class='template-function-creator-component-tag'>
        <span class={['is-hover', 'func-name']}>{this.value?.name}</span>
        {this.params?.length ? <span class='brackets'>&nbsp;(&nbsp;</span> : undefined}
        {this.params.map((param, pIndex) => (
          <span
            key={`item-${pIndex}}`}
            class='params-item'
          >
            <span
              style={{ display: !param.edit ? 'inline-block' : 'none' }}
              class={['params-text', 'is-hover']}
              on-click={e => this.handleClickParam(e, pIndex, `input-${pIndex}`)}
            >
              {param.value || `-${this.$t('空')}-`}
            </span>
            <input
              ref={`input-${pIndex}`}
              style={{ display: param.edit ? 'inline-block' : 'none' }}
              class={['params-input', { 'is-edit': param.edit }]}
              data-focus={param.edit}
              value={param.value}
              on-blur={evt => this.handleParamValueChange(evt, param)}
              onClick={e => this.handleClickInput(e, pIndex)}
            />
            {pIndex !== this.params.length - 1 && <span>,&nbsp;</span>}
          </span>
        ))}
        {this.params.length ? <span class='brackets'>&nbsp;)&nbsp;</span> : undefined}
        <div style='display: none'>
          <div
            ref='menuList'
            class='template-function-creator-component-tag-select-panel'
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
