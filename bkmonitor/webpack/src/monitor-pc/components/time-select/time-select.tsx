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

import './time-select.scss';

export interface ITimeListItem {
  name: string;
  id: string;
}
interface ITimeSelectProps {
  list: ITimeListItem[];
  value: string;
  tip?: string;
}
interface IITimeSelectEvent {
  onChange: string;
  onAddItem: ITimeListItem;
}
@Component
export default class TimeSelect extends tsc<ITimeSelectProps, IITimeSelectEvent> {
  // 选择时间列表
  @Prop({ required: true }) list: ITimeListItem[];
  // 值
  @Prop() value: string;
  @Prop({ default: '', type: String }) tip: string;
  // 自定义时间值
  customTimeVal = '';
  // 是否显示自定义编辑时间框
  showCustomTime = false;
  /**
   * @description: 自定义时间输入触发
   * @param {string} v 值
   * @param {any} e 事件event
   * @return {*}
   */
  handleKeyDown(v: string, e: any) {
    if (/enter/i.test(e.code) && /^([1-9][0-9]+)+(m|h|d|w|M|y)$/.test(this.customTimeVal)) {
      if (this.list.every(item => item.id !== this.customTimeVal)) {
        this.$emit('addItem', {
          id: this.customTimeVal,
          name: this.customTimeVal,
        });
      }
      this.$emit('change', this.customTimeVal);
      this.customTimeVal = '';
      this.showCustomTime = false;
      document.body.click();
    }
  }

  @Emit('change')
  /**
   * @description: 选择时间触发
   * @param {string} v 时间
   * @return {*}
   */
  handleChange(v: string) {
    this.customTimeVal = '';
    return v;
  }
  render() {
    return (
      <div class='time-select'>
        <bk-select
          clearable={false}
          value={this.value}
          onSelected={this.handleChange}
        >
          {this.list.map(item => (
            <bk-option
              id={item.id}
              key={item.id}
              name={item.name}
            >
              {item.name}
            </bk-option>
          ))}
          <div class='time-select-custom'>
            {this.showCustomTime ? (
              <span class='time-input-wrap'>
                <bk-input
                  v-model={this.customTimeVal}
                  size='small'
                  onKeydown={this.handleKeyDown}
                />
                <span
                  class='help-icon icon-monitor icon-mc-help-fill'
                  v-bk-tooltips={{
                    allowHTML: false,
                    content: this.tip || this.$t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年'),
                  }}
                />
              </span>
            ) : (
              <span
                class='custom-text'
                onClick={() => (this.showCustomTime = !this.showCustomTime)}
              >
                {this.$t('自定义')}
              </span>
            )}
          </div>
        </bk-select>
      </div>
    );
  }
}
