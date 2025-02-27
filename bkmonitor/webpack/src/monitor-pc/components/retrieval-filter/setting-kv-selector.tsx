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

import AutoWidthInput from './auto-width-input';
import { METHOD_MAP, type IFilterField, type IWhereItem } from './utils';

import './setting-kv-selector.scss';

interface IProps {
  field?: IFilterField;
  value?: IWhereItem;
}

@Component
export default class SettingKvSelector extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) field: IFilterField;
  @Prop({ type: Object, default: () => null }) value: IWhereItem;
  @Prop({ type: Number, default: 560 }) maxWidth: number;

  @Ref('selector') selectorRef: HTMLDivElement;

  localValue: string[] = [];
  localMethod = '';
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

  get tagList() {
    return this.expand ? this.localValue : this.localValue.slice(0, this.localValue.length - this.hideCount);
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
    }
  }

  mounted() {
    const wrapEl = this.$el.querySelector('.component-main.hidden');
    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        console.log('xxxx');
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
    const maxWidth = this.maxWidth + 68;
    if (width > maxWidth) {
      const elList = wrapEl.querySelector('.value-wrap');
      const wrapRect = wrapEl.getBoundingClientRect();
      let i = 0;
      for (const el of Array.from(elList.children)) {
        const elRect = el.getBoundingClientRect();
        const elLeft = elRect.left + elRect.width - wrapRect.left;
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
      this.handleShowSelect(targetEvent as any);
      this.isFocus = true;
    }
  }

  @Debounce(300)
  handleSearchChange() {
    //
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
          <span class='method-wrap'>{METHOD_MAP[this.localMethod]}</span>
          <div
            class='value-wrap'
            onClick={this.handleClickValueWrap}
          >
            {this.tagList.length
              ? this.tagList.map((item, index) => (
                  <span
                    key={index}
                    class='tag-item'
                  >
                    <span class='tag-text'>{item}</span>
                    <span class='icon-monitor icon-mc-close' />
                  </span>
                ))
              : !this.isFocus && <span class='placeholder-text'>{this.$t('请选择')}</span>}
            {this.expand && (
              <AutoWidthInput
                height={22}
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
          </div>
        </div>
      </div>
    );
  }
}
