/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import {
  Component,
  Prop,
  Watch,
  Emit,
  Model,
  Ref,
} from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './validator-input.scss';

interface IProps {
  value: string;
}

@Component
export default class LogFilter extends tsc<object> {
  @Model('change', { default: '', type: String }) value: IProps['value'];
  @Prop({ default: '', type: String }) placeholder: string;
  @Prop({ default: '', type: String }) activeType: string;
  @Prop({ default: 'text', type: String }) inputType: string;
  @Prop({ default: () => ({}), type: Object }) rowData: any;
  @Prop({ default: () => [], type: Array })
  originalFilterItemSelect: Array<any>;
  @Ref('input') readonly inputRef: any;
  @Ref('validateForm') readonly validateFormRef: any;

  isClick = false;
  formData = {
    inputValue: '',
  };

  rules = {
    inputValue: [
      {
        message: window.mainComponent.$t('必填项'),
        trigger: 'blur',
        validator: this.checkValidator,
      },
    ],
  };

  get isShowSelect() {
    return !!this.originalFilterItemSelect.length;
  }
  /** 当有下拉框的情况下 显示调试后行对应的值 */
  get selectedShowStr() {
    return this.originalFilterItemSelect.find(
      (item) => item.id === this.formData.inputValue
    )?.name;
  }
  /** 是否展示输入框  点击情况或者值为空的情况 */
  get isShowFormInput() {
    return this.isClick || !this.formData.inputValue;
  }

  @Watch('formData.inputValue')
  watchInputValue() {
    this.handleEmitModel();
  }

  @Watch('value', { immediate: true })
  watchPropsValue() {
    this.formData.inputValue = this.value;
  }

  @Emit('change')
  handleEmitModel() {
    return this.formData.inputValue;
  }

  validate() {
    return new Promise((reject) => {
      if (!this.validateFormRef) reject(true);
      this.validateFormRef.validate().then(
        () => reject(true),
        () => reject(false)
      );
    });
  }

  handleClickInput() {
    this.isClick = true;
    this.$nextTick(() => {
      this.inputRef.focus();
    });
  }

  blurInput() {
    this.isClick = false;
  }

  checkValidator() {
    const { fieldindex, word } = this.rowData;
    if (
      (!fieldindex && !word) ||
      (fieldindex && word) ||
      this.formData.inputValue ||
      this.activeType === 'match'
    )
      return true;
    return false;
  }

  render() {
    const inputTriggerSlot = (isSelect = false) => (
      <div
        class={{ 'input-trigger': true, 'none-border': this.isShowFormInput }}
        onClick={this.handleClickInput}
      >
        {this.isShowFormInput ? (
          formInput()
        ) : (
          <div class="input-box">
            <span class="input-value overflow-tips" v-bk-overflow-tips>
              {isSelect
                ? `${this.selectedShowStr || this.$t('第{n}行', { n: this.formData.inputValue })}`
                : this.$t('第{n}行', { n: this.formData.inputValue })}
            </span>
          </div>
        )}
      </div>
    );
    const formInput = () => (
      <bk-form
        form-type="inline"
        ref="validateForm"
        {...{
          props: {
            model: this.formData,
            rules: this.rules,
          },
        }}
      >
        <bk-form-item label="" property="inputValue">
          <bk-input
            clearable
            min={1}
            onBlur={this.blurInput}
            placeholder={this.placeholder ?? this.$t('请输入')}
            ref="input"
            show-clear-only-hover
            show-controls={false}
            type={this.inputType}
            v-model={this.formData.inputValue}
          />
        </bk-form-item>
      </bk-form>
    );
    return (
      <div class="bklog-log-filter form-input">
        {!this.isShowSelect ? (
          this.inputType !== 'number' ? (
            formInput()
          ) : (
            inputTriggerSlot()
          )
        ) : (
          <bk-select
            clearable={false}
            popover-width={320}
            scopedSlots={{
              trigger: () => inputTriggerSlot(true),
            }}
            searchable
            v-model={this.formData.inputValue}
          >
            {this.originalFilterItemSelect.map((option) => (
              <bk-option id={option.id} name={option.name}>
                <span
                  class="overflow-tips"
                  title={`${this.$t('第{n}行', { n: option.id })} ${option.value || ''}`}
                >{`${this.$t('第{n}行', { n: option.id })} ${option.value || ''}`}</span>
              </bk-option>
            ))}
          </bk-select>
        )}
      </div>
    );
  }
}
