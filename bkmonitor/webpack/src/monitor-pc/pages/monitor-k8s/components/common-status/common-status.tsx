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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { ITableItemStatus } from '../../typings';

import './common-status.scss';

export type CommonStatusType = ITableItemStatus;

interface IProps {
  type: CommonStatusType;
  text?: string;
  tips?: string;
  icon?: string;
}

/**
 * 视图部分的状态小组件
 */
@Component
export default class CommonStatus extends tsc<IProps> {
  @Prop({ type: String }) type: CommonStatusType;
  @Prop({ type: String }) text: string;
  @Prop({ type: String }) tips: string;
  @Prop({ type: String }) icon: string;

  render() {
    return (
      <span
        class={['common-status-wrap']}
        v-bk-tooltips={{
          content: this.tips,
          delay: 300,
          theme: 'light',
          disabled: !this.tips,
          allowHTML: false
        }}
      >
        <span class={['common-status-icon', this.icon ? `${this.icon} status-icon` : `status-${this.type}`]}></span>
        {!!this.text && <span class='common-status-name'>{this.text}</span>}
      </span>
    );
  }
}
