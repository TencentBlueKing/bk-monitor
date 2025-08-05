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

import './select-wrap.scss';

interface IProps {
  active?: boolean;
  backgroundColor?: string;
  id?: string;
  minWidth?: number;
  onClick: (e: Event) => void;
}

@Component
export default class SelectWrap extends tsc<IProps> {
  @Prop({ default: false }) active: boolean;
  @Prop({ default: 127 }) minWidth: number;
  @Prop({ default: '#fff' }) backgroundColor: string;
  @Prop({ default: '' }) id: string;

  handleClick(e) {
    this.$emit('click', e);
  }

  render() {
    return (
      <div
        id={this.id}
        style={{ minWidth: `${this.minWidth}px`, backgroundColor: this.backgroundColor }}
        class='template-config-utils-select-wrap-component'
        onClick={e => this.handleClick(e)}
      >
        {this.$slots?.default || ''}
        <div class={['expand-wrap', { active: this.active }]}>
          <span class='icon-monitor icon-mc-arrow-down' />
        </div>
      </div>
    );
  }
}
