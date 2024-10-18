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

import { Component, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './contrast-view.scss';
@Component({
  name: 'ContrastView',
  components: {},
})
export default class ContrastView extends tsc<object> {
  checkboxGroupValue = [];
  initDateTime = '';
  isShowPicker = false;
  pickerOptions = {
    disabledDate: this.setDisabledDate,
  };
  dateTime = [];
  typeList = [
    {
      label: this.$t('昨天'),
      value: 'yesterday',
    },
    {
      label: this.$t('上周'),
      value: 'week',
    },
  ];
  handleAdd() {
    if (!this.isDateAdd) {
      this.isShowPicker = !this.isShowPicker;
      this.initDateTime = '';
    }
  }
  @Emit('clear')
  handleClose(item) {
    this.dateTime = this.dateTime.filter(date => date !== item);
    return this.handleFormateDate();
  }
  /** 设置日历组件禁用时间 */
  setDisabledDate(date) {
    return date && date.valueOf() > Date.now();
  }
  get isChooseDateOrType() {
    return this.checkboxGroupValue.length === 1 && this.dateTime.length === 1;
  }
  get isDateAdd() {
    return this.checkboxGroupValue.length === 2 || this.dateTime.length === 2 || this.isChooseDateOrType;
  }

  disabledCheck(key) {
    if (this.dateTime.length === 2) {
      return true;
    }
    if (this.isChooseDateOrType) {
      return !this.checkboxGroupValue.includes(key);
    }
    return false;
  }

  handleFormateDate() {
    const dateArr = [];
    this.dateTime.map(item => dateArr.push({ label: item, value: item }));
    return dateArr;
  }

  @Emit('changeDate')
  changePicker(date) {
    this.isShowPicker = false;
    date && this.dateTime.push(date);
    return this.handleFormateDate();
  }
  @Emit('check')
  handleCheckboxChange() {
    const typeList = this.typeList.filter(item => this.checkboxGroupValue.includes(item.value));
    return typeList;
  }

  render() {
    return (
      <div class='contrast-view'>
        <bk-checkbox-group
          class='contrast-view-checkbox-group'
          v-model={this.checkboxGroupValue}
          onChange={this.handleCheckboxChange}
        >
          {this.typeList.map(item => (
            <bk-checkbox
              key={item.value}
              disabled={this.disabledCheck(item.value)}
              label={item.value}
            >
              {item.label}
            </bk-checkbox>
          ))}
        </bk-checkbox-group>
        <div class='contrast-custom'>
          <span>{this.$t('自定义日期')}</span>
          {this.dateTime.map(
            item =>
              !!item && (
                <bk-tag
                  key={item}
                  closable
                  onClose={() => this.handleClose(item)}
                >
                  {item}
                </bk-tag>
              )
          )}
          <span
            class={['contrast-custom-add', { disabled: this.isDateAdd }]}
            onClick={this.handleAdd}
          >
            <i class='icon-monitor icon-plus-line' />
          </span>
          {this.isShowPicker && (
            <bk-date-picker
              class='custom-date-picker'
              v-model={this.initDateTime}
              options={this.pickerOptions}
              onChange={this.changePicker}
            />
          )}
        </div>
      </div>
    );
  }
}
