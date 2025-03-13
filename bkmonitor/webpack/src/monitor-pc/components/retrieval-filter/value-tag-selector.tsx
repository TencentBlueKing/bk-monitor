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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AutoWidthInput from './auto-width-input';
import { type IFilterField, type IGetValueFnParams, type IWhereValueOptionsItem, onClickOutside } from './utils';
import ValueOptions from './value-options';
import ValueTagInput from './value-tag-input';

import './value-tag-selector.scss';

export interface IValue {
  id: string;
  name: string; // 暂不显示 预留
}

interface IProps {
  value?: IValue[];
  checkedItem?: IFilterField;
  method?: string;
  isWildcard?: boolean;
  onChange?: (v: IValue[]) => void;
  onDropDownChange?: (v: boolean) => void;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
}

@Component
export default class ValueTagSelector extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) value: IValue[];
  @Prop({ type: Boolean, default: false }) scrollLoading: boolean;
  @Prop({ type: Object, default: () => null }) checkedItem: IFilterField;
  @Prop({ type: String, default: '' }) method: string;
  @Prop({ type: Boolean, default: false }) isWildcard: boolean;
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;

  /* tag列表 */
  localValue: IValue[] = [];
  /* 可选项 */
  localOptions: IValue[] = [];
  /* 是否显示下拉框 */
  isShowDropDown = false;
  /* 当前光标位置 */
  activeIndex = -1;
  /* 当前光标位置输入值 */
  inputValue = '';
  /* 输入框是否聚焦 */
  isFocus = false;
  /* 是否通过上下键悬停下拉选项 */
  isChecked = false;

  get hasCustomOption() {
    return !!this.inputValue;
  }

  mounted() {
    document.addEventListener('keydown', this.handleKeydownEvent);
    this.handleClick();
  }

  beforeDestroy() {
    document.removeEventListener('keydown', this.handleKeydownEvent);
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    this.localValue = JSON.parse(JSON.stringify(this.value));
  }

  @Watch('isShowDropDown')
  handleWatchIsShowDropDown() {
    this.$emit('dropDownChange', this.isShowDropDown);
  }

  /**
   * @description 下拉选项点击事件
   * @param item
   */
  handleCheck(item: IValue) {
    this.localValue.push(item);
    this.activeIndex += 1;
    this.handleChange();
  }

  /**
   * @description 点击输入框
   */
  handleClick() {
    if (!this.isShowDropDown) {
      this.handleShowShowDropDown(true);
    }
    this.activeIndex = this.localValue.length - 1;
    this.isFocus = true;
  }

  /**
   * @description 输入框输入事件
   * @param event
   */
  handleInput(value) {
    this.inputValue = value;
    if (!this.isShowDropDown) {
      this.handleShowShowDropDown(true);
    }
  }
  /**
   * @description 输入框失去焦点事件
   */
  handleBlur() {
    this.inputValue = '';
    this.isFocus = false;
    this.activeIndex = -1;
  }
  /**
   * @description 输入框enter事件
   */
  handleEnter() {
    if (!this.inputValue || this.isChecked) {
      return;
    }
    this.localValue.push({ id: this.inputValue, name: this.inputValue });
    this.activeIndex += 1;
    this.inputValue = '';
  }

  /**
   * @description 监听删除键
   */
  handleBackspace() {
    if (!this.inputValue) {
      if (this.activeIndex > 0) {
        this.activeIndex -= 1;
      }
      if (this.localValue.length > 1) {
        this.localValue.splice(this.activeIndex + 1, 1);
      } else {
        this.localValue = [];
        setTimeout(() => {
          this.handleClick();
        }, 300);
      }
    }
  }

  /**
   * @description 下拉展开与收起
   * @param v
   */
  handleShowShowDropDown(v: boolean) {
    this.isShowDropDown = v;
    if (this.isShowDropDown) {
      setTimeout(() => {
        onClickOutside(
          this.$el,
          () => {
            this.isShowDropDown = false;
          },
          { once: true }
        );
      }, 100);
    }
  }

  /**
   * @description 删除tag
   * @param index
   */
  handleDelete(index: number) {
    this.localValue.splice(index, 1);
    this.handleChange();
  }

  handleChange() {
    this.$emit('change', this.localValue);
  }
  handleTagUpdate(v: string, index: number) {
    this.localValue.splice(index, 1, { id: v, name: v });
  }

  handleKeydownEvent(event: KeyboardEvent) {
    switch (event.key) {
      case 'ArrowLeft': {
        event.preventDefault();
        if (this.activeIndex > 0) {
          this.activeIndex -= 1;
        }
        break;
      }
      case 'ArrowRight': {
        event.preventDefault();
        if (this.activeIndex < this.localValue.length - 1) {
          this.activeIndex += 1;
        }
        break;
      }
      case 'Enter': {
        event.preventDefault();
        break;
      }
    }
  }

  handleIsChecked(v: boolean) {
    this.isChecked = v;
  }

  render() {
    const inputRender = () => (
      <AutoWidthInput
        key={'input'}
        height={22}
        class='mb-4 mr-4'
        fontSize={12}
        isFocus={this.isFocus}
        value={this.inputValue}
        onBackspace={this.handleBackspace}
        onBlur={this.handleBlur}
        onEnter={this.handleEnter}
        onInput={this.handleInput}
      />
    );
    return (
      <div class='retrieval__value-tag-selector-component'>
        <div
          class={['value-tag-selector-component-wrap', { active: this.isShowDropDown || this.isFocus }]}
          onClick={this.handleClick}
        >
          {this.localValue.length
            ? this.localValue.map((item, index) => [
                <ValueTagInput
                  key={index}
                  class='value-tag-input'
                  value={item.id}
                  onChange={v => this.handleTagUpdate(v, index)}
                  onDelete={() => this.handleDelete(index)}
                />,
                this.activeIndex === index && inputRender(),
              ])
            : [
                inputRender(),
                !this.inputValue && (
                  <span
                    key={'no-data-placeholder'}
                    class='placeholder-span'
                  >{`${this.$t('请输入')} ${this.$t('或')} ${this.$t('选择')}`}</span>
                ),
              ]}
        </div>
        {this.isShowDropDown && (
          <ValueOptions
            checkedItem={this.checkedItem}
            getValueFn={this.getValueFn}
            isWildcard={this.isWildcard}
            method={this.method}
            search={this.inputValue}
            selected={this.localValue.map(item => item.id)}
            onIsChecked={this.handleIsChecked}
            onSelect={this.handleCheck}
          />
        )}
      </div>
    );
  }
}
