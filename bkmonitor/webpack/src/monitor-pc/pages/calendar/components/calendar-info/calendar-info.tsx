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
import { Component, Emit, Model, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './calendar-info.scss';

export interface IProps {
  cancelText?: string;
  infoDesc?: string;
  infoTitle: string;
  okText?: string;
  value?: boolean;
  zIndex?: number;
}
interface IEvents {
  onCancel: void;
  onConfirm: void;
  onValueChange: boolean;
}
/**
 * 日历事项提醒弹窗
 */
@Component
export default class CalendarInfo extends tsc<IProps, IEvents> {
  @Model('valueChange', { type: Boolean, default: false }) value: boolean;
  @Prop({ type: String, default: '' }) infoTitle: string;
  @Prop({ type: String, default: '' }) infoDesc: string;
  @Prop({ type: String, default: '' }) okText: string;
  @Prop({ type: String, default: '' }) cancelText: string;
  @Prop({ type: Number }) zIndex: number;

  @Emit('confirm')
  handleConfirm() {}
  @Emit('cancel')
  handleCancel() {}
  @Emit('valueChange')
  handleValueChange(val: boolean) {
    return val;
  }

  render() {
    return (
      <bk-dialog
        {...{
          props: this.$props,
        }}
        width='450px'
        show-footer={false}
        value={this.value}
        onCancel={this.handleValueChange}
      >
        <div class='calendar-info-wrap'>
          <div class='calendar-info-icon'>
            <span class='calendar-info-icon-wrap'>
              <i class='icon-monitor icon-mind-fill' />
            </span>
          </div>
          <div class='calendar-info-title'>{this.infoTitle}</div>
          {(!!this.$slots.infoDesc || !!this.infoDesc) && (
            <div class='calendar-info-desc'>{this.$slots.infoDesc ? this.$slots.infoDesc : this.infoDesc}</div>
          )}
          <div class='calendar-info-btn-group'>
            {this.$slots.buttonGroup || [
              <bk-button
                theme='primary'
                onClick={this.handleConfirm}
              >
                {this.okText}
              </bk-button>,
              !!this.cancelText && <bk-button onClick={this.handleCancel}>{this.cancelText}</bk-button>,
            ]}
          </div>
        </div>
      </bk-dialog>
    );
  }
}
