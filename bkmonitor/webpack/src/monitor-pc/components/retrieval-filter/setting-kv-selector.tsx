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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AutoWidthInput from './auto-width-input';
import { type IWhereItem, getTitleAndSubtitle, METHOD_MAP, onClickOutside, OPPOSE_METHODS } from './utils';
import ValueOptions from './value-options';
import ValueTagInput from './value-tag-input';

import type { IFieldItem, TGetValueFn } from './value-selector-typing';

import './setting-kv-selector.scss';

interface IProps {
  fieldInfo?: IFieldItem;
  getValueFn?: TGetValueFn;
  maxWidth?: number;
  value?: IWhereItem;
  onChange?: (value: IWhereItem) => void;
}

@Component
export default class SettingKvSelector extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) fieldInfo: IFieldItem;
  @Prop({ type: Object, default: () => null }) value: IWhereItem;
  @Prop({ type: Number, default: 560 }) maxWidth: number;
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: TGetValueFn;

  @Ref('selector') selectorRef: HTMLDivElement;

  localValue: string[] = [];
  localMethod = '';
  /* 是否展开所有元素 */
  expand = false;
  popoverInstance = null;
  isHover = false;
  inputValue = '';
  isFocus = false;
  methodMap = {};
  showSelector = false;
  /* 是否通过上下键悬停下拉选项 */
  isChecked = false;
  hideIndex = -1;

  resizeObserver = null;
  optionsWidth = 0;

  keyWrapMinWidth = 0;

  clickOutsideFn = () => {};

  get localValueSet() {
    return new Set(this.localValue);
  }

  get isHighLight() {
    return !!this.inputValue || this.showSelector || this.expand;
  }

  get fieldAlias() {
    const { title } = getTitleAndSubtitle(this.fieldInfo?.alias || '');
    return title || this.value?.key || '';
  }

  created() {
    this.methodMap = JSON.parse(JSON.stringify(METHOD_MAP));
    for (const item of this.fieldInfo?.methods || []) {
      this.methodMap[item.id] = item.name;
    }
  }
  mounted() {
    this.keyWrapMinWidth = this.getTextWidth(this.fieldAlias);
    this.overviewCount();
    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { offsetWidth } = entry.target;
        this.optionsWidth = offsetWidth;
      }
    });
    const valueWrap = this.$el.querySelector('.component-main > .value-wrap') as any;
    this.resizeObserver.observe(valueWrap); // 开始监听
  }

  beforeDestroy() {
    this.clickOutsideFn?.();
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    if (this.value) {
      const valueStr = this.value.value.join('____');
      const localValueStr = this.localValue.join('____');
      this.localMethod = this.value.method;
      if (valueStr !== localValueStr) {
        this.localValue = this.value.value.slice();
      }
      if (this.value.method !== this.localMethod) {
        this.localMethod = this.value.method;
      }
    }
  }

  @Watch('localValue')
  handleWatchLocalValue() {
    this.overviewCount();
  }

  overviewCount() {
    let hasHide = false;
    this.$nextTick(() => {
      const valueWrap = this.$el.querySelector('.component-main > .value-wrap') as any;
      let i = -1;
      if (!valueWrap) {
        return;
      }
      for (const el of Array.from(valueWrap.children)) {
        if (el.className.includes('tag-item')) {
          i += 1;
          if ((el as any).offsetTop > 22) {
            hasHide = true;
            break;
          }
        }
      }
      if (hasHide && i > 1) {
        const preItem = valueWrap.children[i - 1] as any;
        if (preItem.offsetLeft + preItem.offsetWidth + 4 > valueWrap.offsetWidth - 68) {
          this.hideIndex = i - 1;
          return;
        }
      }
      this.hideIndex = hasHide ? i : -1;
    });
  }

  handleClickValueWrap(event) {
    event.stopPropagation();
    if (!this.expand) {
      this.expand = true;
      this.isFocus = true;
    }
    const targetEvent = {
      target: this.$el.querySelector('.component-main > .value-wrap'),
    };
    this.handleShowSelect(targetEvent as any);
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
      distance: 15,
      zIndex: 1002,
      animation: 'slide-toggle',
      followCursor: false,
      sticky: true,
      onHidden: () => {
        this.destroyPopoverInstance();
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show();
    this.showSelector = true;
    this.handleOnClickOutside();
  }

  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    // this.expand = false;
    this.showSelector = false;
  }

  handleOnClickOutside() {
    const el = document.querySelector('.resident-setting__setting-kv-selector-component-pop');
    this.clickOutsideFn = onClickOutside(
      [this.$el, el],
      () => {
        this.expand = false;
        this.inputValue = '';
        this.showSelector = false;
        this.destroyPopoverInstance();
      },
      { once: true }
    );
  }

  handleMouseenter() {
    this.isHover = true;
  }
  handleMouseleave() {
    this.isHover = false;
  }
  /**
   * @description 按下回车键
   */
  handleEnter() {
    if (!this.isChecked || !this.showSelector) {
      if (!this.localValue.includes(this.inputValue) && this.inputValue) {
        this.localValue.push(this.inputValue);
        this.handleChange();
      }
      this.inputValue = '';
    }
  }

  /**
   * @description 输入框输入
   * @param v
   */
  handleInput(v: string) {
    this.inputValue = v;
  }

  handleBlur() {
    this.isFocus = false;
  }

  /**
   * @description 清除
   * @param event
   */
  handleClear(event: MouseEvent) {
    event.stopPropagation();
    this.localValue = [];
    this.handleChange();
  }

  /**
   * @description 删除值
   * @param e
   * @param index
   */
  handleDeleteTag(e: MouseEvent, index: number) {
    e.stopPropagation();
    this.localValue.splice(index, 1);
    this.handleChange();
  }

  /**
   * @description 选择值
   * @param item
   */
  handleSelectOption(item: { id: string; name: string }) {
    if (this.localValueSet.has(item.id)) {
      const delIndex = this.localValue.findIndex(v => v === item.id);
      this.localValue.splice(delIndex, 1);
    } else {
      this.localValue.push(item.id);
    }
    this.handleChange();
  }

  /**
   * @description 切换method
   * @param item
   */
  handleMethodChange(item: { id: string; name: string }) {
    this.methodMap[item.id] = item.name;
    this.localMethod = item.id;
    this.handleChange();
  }

  handleChange() {
    this.$emit('change', {
      ...this.value,
      key: this.fieldInfo.field,
      method: this.localMethod,
      value: this.localValue,
    });
  }

  handleIsChecked(v: boolean) {
    this.isChecked = v;
  }

  handleValueUpdate(v: string, index: number) {
    if (v) {
      this.localValue.splice(index, 1, v);
    } else {
      this.localValue.splice(index, 1);
    }
    this.handleChange();
  }

  handleBackspaceNull() {
    if (!this.inputValue && this.localValue.length) {
      this.localValue.splice(this.localValue.length - 1, 1);
    }
  }

  getTextWidth(text: string) {
    const span = document.createElement('span');
    span.style.visibility = 'hidden';
    span.style.position = 'absolute';
    span.style.whiteSpace = 'nowrap';
    span.style.fontSize = '12px';
    document.body.appendChild(span);
    span.textContent = text;
    const width = span.offsetWidth;
    document.body.removeChild(span);
    return width;
  }

  render() {
    return (
      <div class={['resident-setting__setting-kv-selector-component', { active: this.isHighLight }]}>
        <div
          class={['component-main', { expand: this.expand }]}
          onMouseenter={this.handleMouseenter}
          onMouseleave={this.handleMouseleave}
        >
          <span
            style={{
              minWidth: `${this.keyWrapMinWidth < 120 ? this.keyWrapMinWidth : 120}px`,
            }}
            class='key-wrap'
            v-bk-tooltips={{
              content: this.value?.key,
              placement: 'top',
              duration: [300, 0],
            }}
          >
            {this.fieldAlias}
          </span>
          <span class='method-wrap'>
            <bk-dropdown-menu
              positionFixed={true}
              trigger='click'
            >
              <span
                class={['method-span', { 'red-text': OPPOSE_METHODS.includes(this.localMethod as any) }]}
                slot='dropdown-trigger'
              >
                {this.methodMap[this.localMethod] || this.localMethod}
              </span>
              <ul
                class='method-list-wrap'
                slot='dropdown-content'
              >
                {this.fieldInfo.methods.map(item => (
                  <li
                    key={item.id}
                    class={['method-list-wrap-item', { active: item.id === this.localMethod }]}
                    onClick={() => this.handleMethodChange(item)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            </bk-dropdown-menu>
          </span>
          <div
            style={{
              borderBottomWidth: this.localValue?.length ? '1px' : '0',
            }}
            class='value-wrap'
            onClick={this.handleClickValueWrap}
          >
            {this.localValue?.map((item, index) => [
              this.hideIndex === index && !this.expand ? (
                <span
                  key={'count'}
                  class='hide-count'
                  v-bk-tooltips={{
                    content: this.localValue.slice(index).join(','),
                    delay: 300,
                  }}
                >
                  <span>{`+${this.localValue.length - index}`}</span>
                </span>
              ) : undefined,
              // <span
              //   key={index}
              //   class='tag-item'
              // >
              //   <span class='tag-text'>{item}</span>
              //   <span
              //     class='icon-monitor icon-mc-close'
              //     onClick={e => this.handleDeleteTag(e, index)}
              //   />
              // </span>,
              <ValueTagInput
                key={index}
                class='tag-item'
                isOneRow={true}
                value={item}
                onChange={v => this.handleValueUpdate(v, index)}
                onDelete={e => this.handleDeleteTag(e, index)}
              />,
            ])}
            {(this.expand || !this.localValue.length) && (
              <AutoWidthInput
                height={22}
                isFocus={this.isFocus}
                placeholder={`${this.$t('请输入')} ${this.$t('或')} ${this.$t('选择')}`}
                value={this.inputValue}
                onBackspaceNull={this.handleBackspaceNull}
                onBlur={this.handleBlur}
                onEnter={this.handleEnter}
                onInput={this.handleInput}
              />
            )}
            {this.isHover && this.localValue.length ? (
              <div class='delete-btn'>
                <span
                  class='icon-monitor icon-mc-close-fill'
                  onClick={this.handleClear}
                />
              </div>
            ) : (
              <div class='expand-btn'>
                <span class='icon-monitor icon-arrow-down' />
              </div>
            )}
          </div>
        </div>
        <div style='display: none;'>
          <div
            ref={'selector'}
            class='resident-setting__setting-kv-selector-component-pop'
          >
            <ValueOptions
              width={this.optionsWidth}
              fieldInfo={this.fieldInfo}
              getValueFn={this.getValueFn}
              isPopover={true}
              noDataSimple={true}
              search={this.inputValue}
              selected={this.localValue}
              show={this.showSelector}
              onIsChecked={this.handleIsChecked}
              onSelect={this.handleSelectOption}
            />
          </div>
        </div>
      </div>
    );
  }
}
