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
import {
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  METHOD_MAP,
  type IFilterField,
  type IWhereItem,
} from './utils';
import ValueOptions from './value-options';

import './setting-kv-selector.scss';

interface IProps {
  field?: IFilterField;
  value?: IWhereItem;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onChange?: (value: IWhereItem) => void;
}

@Component
export default class SettingKvSelector extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) field: IFilterField;
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
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;

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

  get tagList() {
    return this.localValue;
  }

  get localValueSet() {
    return new Set(this.localValue);
  }

  get isHighLight() {
    return !!this.inputValue || this.showSelector || this.expand;
  }

  created() {
    this.methodMap = JSON.parse(JSON.stringify(METHOD_MAP));
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    if (this.value) {
      console.log(this.value);
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

  mounted() {
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

  @Watch('tagList')
  handleWatchTagList() {
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
      const targetEvent = {
        target: this.$el.querySelector('.component-main > .value-wrap'),
      };
      this.handleShowSelect(targetEvent as any);
      this.isFocus = true;
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
      distance: 15,
      zIndex: 998,
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
  }

  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.expand = false;
    this.inputValue = '';
    this.showSelector = false;
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
      this.localValue.push(this.inputValue);
      this.inputValue = '';
      this.handleChange();
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
  handleMethodChange(item: { value: string; alias: string }) {
    this.methodMap[item.value] = item.alias;
    this.localMethod = item.value;
    this.handleChange();
  }

  handleChange() {
    this.$emit('change', {
      ...this.value,
      key: this.field.name,
      method: this.localMethod,
      value: this.localValue,
    });
  }

  handleIsChecked(v: boolean) {
    this.isChecked = v;
  }

  render() {
    return (
      <div class={['resident-setting__setting-kv-selector-component', { active: this.isHighLight }]}>
        <div
          class={['component-main', { expand: this.expand }]}
          onMouseenter={this.handleMouseenter}
          onMouseleave={this.handleMouseleave}
        >
          <span class='key-wrap'>{this.value?.key}</span>
          <span class='method-wrap'>
            <bk-dropdown-menu
              positionFixed={true}
              trigger='click'
            >
              <span
                class='method-span'
                slot='dropdown-trigger'
              >
                {METHOD_MAP[this.localMethod]}
              </span>
              <ul
                class='method-list-wrap'
                slot='dropdown-content'
              >
                {this.field.supported_operations.map(item => (
                  <li
                    key={item.value}
                    class={['method-list-wrap-item', { active: item.value === this.localMethod }]}
                    onClick={() => this.handleMethodChange(item)}
                  >
                    {item.alias}
                  </li>
                ))}
              </ul>
            </bk-dropdown-menu>
          </span>
          <div
            style={{
              borderBottomWidth: this.tagList?.length ? '1px' : '0',
            }}
            class='value-wrap'
            onClick={this.handleClickValueWrap}
          >
            {this.tagList?.map((item, index) => [
              this.hideIndex === index && !this.expand ? (
                <span
                  key={'count'}
                  class='hide-count'
                >
                  <span
                    v-bk-tooltips={{
                      content: this.tagList.slice(index).join(','),
                      delay: 300,
                    }}
                  >{`+${this.tagList.length - index}`}</span>
                </span>
              ) : undefined,
              <span
                key={index}
                class='tag-item'
              >
                <span class='tag-text'>{item}</span>
                <span
                  class='icon-monitor icon-mc-close'
                  onClick={e => this.handleDeleteTag(e, index)}
                />
              </span>,
            ])}
            {(this.expand || !this.tagList.length) && (
              <AutoWidthInput
                height={22}
                isFocus={this.isFocus}
                placeholder={`${this.$t('请输入')} ${this.$t('或')} ${this.$t('选择')}`}
                value={this.inputValue}
                onBlur={this.handleBlur}
                onEnter={this.handleEnter}
                onInput={this.handleInput}
              />
            )}
            {this.isHover && this.tagList.length ? (
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
              checkedItem={this.field}
              getValueFn={this.getValueFn}
              isPopover={true}
              search={this.inputValue}
              selected={this.tagList}
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
