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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './custom-date-pick.scss';

interface IProps {
  value?: string; // 2022-03-11 00:00:00 此类格式
  readonlyTime?: boolean; // 是否可以选择时间
  readonly?: boolean; // 只读模式
}
interface IEvents {
  onChange?: string; // 格式和value一样
}

@Component
export default class CustomDatePick extends tsc<IProps, IEvents> {
  @Prop({ default: '', type: String }) value: string;
  @Prop({ default: true, type: Boolean }) readonlyTime: boolean;
  @Prop({ default: false, type: Boolean }) readonly: boolean;

  curDate = new Date(); // 绑定于选择的值
  curTime = '00:00'; // 时间点
  curDateValue = ''; // 头部输入框日期值

  created() {
    if (this.value) {
      const temp = this.value.split(' ');
      const date = temp[0];
      this.curTime = temp[1].slice(0, 5);
      this.curDate = new Date(date);
      this.curDateValue = date;
    } else {
      const newDate = new Date();
      this.curDateValue = this.getDateStr(newDate);
    }
  }

  dateFormat() {
    const dateStr = this.getDateStr(this.curDate);
    return `${dateStr} ${this.curTime}`;
  }

  getDateStr(date: Date) {
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${year}-${month < 10 ? `0${month}` : month}-${day < 10 ? `0${day}` : day}`;
  }

  handleDateChange(value) {
    this.curDateValue = this.getDateStr(this.curDate);
    this.handleChange(value);
  }

  handleInputChange(value: string) {
    const date = new Date(value);
    if (date.getTime()) {
      this.curDate = date;
      this.handleDateChange(`${value} ${this.curTime}`);
    } else {
      this.curDateValue = this.getDateStr(this.curDate);
    }
  }

  disabledDateFn(v) {
    const time = new Date(v).getTime();
    const curTime = new Date().getTime() - 24 * 60 * 60 * 1000;
    return time < curTime;
  }

  handleTimeChange(v: string) {
    const value = `${this.curDateValue} ${String(v).slice(0, 5)}`;
    this.handleChange(value);
  }

  @Emit('change')
  handleChange(value: string) {
    return value;
  }

  render() {
    return (
      <div class='custom-date-pick-component'>
        <bk-date-picker
          v-model={this.curDate}
          transfer={true}
          type={'date'}
          options={{
            disabledDate: this.disabledDateFn
          }}
          format={this.dateFormat()}
          clearable={false}
          readonly={this.readonly}
          onChange={this.handleDateChange}
        >
          <div
            slot='header'
            class='custom-date-pick-component-slot-header'
            onMousedown={(e: Event) => e.stopPropagation()}
          >
            <div class='left'>
              <bk-input
                v-model={this.curDateValue}
                onChange={this.handleInputChange}
              ></bk-input>
            </div>
            <div class='center'></div>
            <div class='right'>
              {this.readonlyTime ? (
                <bk-input
                  readonly={true}
                  v-model={this.curTime}
                ></bk-input>
              ) : (
                <bk-time-picker
                  v-model={this.curTime}
                  format={'HH:mm'}
                  transfer={false}
                  placement={'bottom-end'}
                  onChange={this.handleTimeChange}
                ></bk-time-picker>
              )}
            </div>
          </div>
        </bk-date-picker>
      </div>
    );
  }
}
