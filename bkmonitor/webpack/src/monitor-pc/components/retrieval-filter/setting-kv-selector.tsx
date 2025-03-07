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

import { Debounce } from 'monitor-common/utils';

import EmptyStatus from '../empty-status/empty-status';
import AutoWidthInput from './auto-width-input';
import {
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  METHOD_MAP,
  type IFilterField,
  type IWhereItem,
  ECondition,
  EMethod,
} from './utils';

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
  valueOptions: { id: string; name: string }[] = [];
  optionsLoading = false;
  resizeObserver = null;
  /* 隐藏了N个元素 */
  hideCount = 0;
  /* 是否展开所有元素 */
  expand = false;
  searchValue = '';
  popoverInstance = null;
  isHover = false;
  inputValue = '';
  isFocus = false;
  methodMap = {};

  get tagList() {
    return this.expand ? this.localValue : this.localValue.slice(0, this.localValue.length - this.hideCount);
  }

  get localValueSet() {
    return new Set(this.localValue);
  }

  created() {
    this.methodMap = JSON.parse(JSON.stringify(METHOD_MAP));
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    if (this.value) {
      const valueStr = this.value.value.join('____');
      const localValueStr = this.localValue.join('____');
      this.localMethod = this.value.method;
      if (valueStr !== localValueStr) {
        this.localValue = this.value.value;
      }
      if (this.value.method !== this.localMethod) {
        this.localMethod = this.value.method;
      }
    }
  }

  mounted() {
    const wrapEl = this.$el.querySelector('.component-main.hidden');
    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        // 获取元素的新宽度（content-box 尺寸）
        const width = entry.contentRect.width;
        this.setHideCount(width, wrapEl);
      }
    });
    this.resizeObserver.observe(wrapEl);
  }

  @Debounce(300)
  setHideCount(width: number, wrapEl: Element) {
    let hideCount = 0;
    const maxWidth = this.maxWidth - 68;
    if (width > maxWidth) {
      const elList = wrapEl.querySelector('.value-wrap');
      const wrapRect = wrapEl.getBoundingClientRect();
      let i = 0;
      for (const el of Array.from(elList.children)) {
        const elRect = el.getBoundingClientRect();
        const elLeft = elRect.left + elRect.width + 4 - wrapRect.left;
        if (elLeft > maxWidth) {
          hideCount = elList.children.length - i;
          break;
        }
        i += 1;
      }
    }
    this.hideCount = hideCount;
  }

  handleClickValueWrap(event) {
    event.stopPropagation();
    if (!this.expand) {
      this.expand = true;
      const targetEvent = {
        target: this.$el.querySelector('.component-main.show > .value-wrap'),
      };
      this.getValueData();
      this.handleShowSelect(targetEvent as any);
      this.isFocus = true;
    }
  }

  @Debounce(300)
  handleSearchChange() {
    this.getValueData();
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
  }

  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.expand = false;
    this.inputValue = '';
    this.searchValue = '';
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
    this.localValue.push(this.inputValue);
    this.inputValue = '';
    this.handleChange();
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
   * @description 获取可选项
   */
  async getValueData() {
    this.valueOptions = [];
    this.optionsLoading = true;
    if (this.field.name !== '*') {
      const data = await this.getValueFn({
        where: [
          {
            key: this.field.name,
            method: EMethod.eq,
            value: [this.searchValue],
            condition: ECondition.and,
          },
        ],
        fields: [this.field.name],
        limit: 5,
      });
      this.valueOptions = data.list;
      this.optionsLoading = false;
    }
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

  render() {
    return (
      <div class='resident-setting__setting-kv-selector-component'>
        <div
          class={['component-main show', { expand: this.expand }]}
          onMouseenter={this.handleMouseenter}
          onMouseleave={this.handleMouseleave}
        >
          <span class='key-wrap'>{this.value?.key}</span>
          <span class='method-wrap'>
            <bk-dropdown-menu trigger='click'>
              <span slot='dropdown-trigger'>{METHOD_MAP[this.localMethod]}</span>
              <ul
                class='method-list-wrap'
                slot='dropdown-content'
              >
                {this.field.supported_operations.map(item => (
                  <li
                    key={item.value}
                    class='method-list-wrap-item'
                    onClick={() => this.handleMethodChange(item)}
                  >
                    {item.alias}
                  </li>
                ))}
              </ul>
            </bk-dropdown-menu>
          </span>
          <div
            class='value-wrap'
            data-placeholder={this.inputValue || this.isFocus || this.tagList?.length ? '' : this.$tc('请选择')}
            onClick={this.handleClickValueWrap}
          >
            {this.tagList?.map((item, index) => (
              <span
                key={index}
                class='tag-item'
              >
                <span class='tag-text'>{item}</span>
                <span
                  class='icon-monitor icon-mc-close'
                  onClick={e => this.handleDeleteTag(e, index)}
                />
              </span>
            ))}
            {this.expand && (
              <AutoWidthInput
                height={22}
                // class='mb-5'
                isFocus={this.isFocus}
                value={this.inputValue}
                onBlur={this.handleBlur}
                onEnter={this.handleEnter}
                onInput={this.handleInput}
              />
            )}
            {!!this.hideCount && !this.expand && !!this.tagList.length && (
              <span class='tag-item hide-count'>{`+${this.hideCount}`}</span>
            )}
            {this.isHover ? (
              <div
                class='delete-btn'
                onClick={this.handleClear}
              >
                <span class='icon-monitor icon-mc-close-fill' />
              </div>
            ) : (
              <div class='expand-btn'>
                <span class='icon-monitor icon-arrow-down' />
              </div>
            )}
          </div>
        </div>
        <div class='component-main hidden'>
          <span class='key-wrap'>{this.value?.key}</span>
          <span class='method-wrap'>{METHOD_MAP[this.localMethod]}</span>
          <div class='value-wrap'>
            {this.localValue.map((item, index) => (
              <span
                key={index}
                class='tag-item'
              >
                <span class='tag-text'>{item}</span>
                <span class='icon-monitor icon-mc-close' />
              </span>
            ))}
          </div>
        </div>
        <div style='display: none;'>
          <div
            ref={'selector'}
            class='resident-setting__setting-kv-selector-component-pop'
          >
            <div class='search-wrap'>
              <bk-input
                v-model={this.searchValue}
                behavior='simplicity'
                left-icon='bk-icon icon-search'
                placeholder={this.$t('请输入关键字')}
                onChange={this.handleSearchChange}
              />
            </div>
            {this.optionsLoading ? (
              <div class='options-wrap'>
                {new Array(4).fill(null).map(index => {
                  return (
                    <div
                      key={index}
                      class='options-item skeleton-item'
                    >
                      <div class='skeleton-element h-16' />
                    </div>
                  );
                })}
              </div>
            ) : this.valueOptions.length ? (
              <div class='options-wrap'>
                {this.valueOptions.map((item, index) => (
                  <div
                    key={index}
                    class={['options-item', { checked: this.localValueSet.has(item.id) }]}
                    onClick={() => this.handleSelectOption(item)}
                  >
                    <span class='options-item-text'>{item.name}</span>
                    <span class='icon-monitor icon-mc-check-small' />
                  </div>
                ))}
              </div>
            ) : (
              <div class='options-wrap'>
                <EmptyStatus type={'empty'} />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
}
