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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './custom-time-range.scss';

interface IProps {
  value: string[];
  allowCrossDay?: boolean;
}
interface IEvents {
  onChange?: string[];
}

@Component
export default class CustomTimeRange extends tsc<IProps, IEvents> {
  @Prop({ default: () => ['00:00', '23:59'], type: Array }) value: string[];
  @Prop({ default: true, type: Boolean }) allowCrossDay: boolean;
  @Ref('timepicker') timepickerRef: any;

  /* 时间段 */
  localValue = ['00:00', '23:59'];
  /* 是否展开 */
  isActive = false;

  created() {
    this.localValue = this.value;
  }

  /* 点击右边按钮 */
  handleClick() {
    if (this.isActive) return;
    this.timepickerRef.$el.querySelector('.bk-date-picker-editor').click();
  }

  handleOpen(state) {
    this.isActive = state;
  }

  @Emit('change')
  handleChange(value: string[]) {
    return value;
  }

  render() {
    return (
      <div class='custom-time-range-component'>
        <bk-time-picker
          v-model={this.localValue}
          type={'timerange'}
          placeholder={this.$t('选择')}
          format={'HH:mm'}
          transfer={true}
          ref='timepicker'
          allowCrossDay={this.allowCrossDay}
          on-open-change={this.handleOpen}
          on-change={this.handleChange}
        ></bk-time-picker>
        <span
          class={['time-btn', { active: this.isActive }]}
          onClick={this.handleClick}
        >
          <span class='icon-monitor icon-mc-time-shift time-icon'></span>
        </span>
      </div>
    );
  }
}
