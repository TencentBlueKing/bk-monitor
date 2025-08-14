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

interface ITabBtnGroupEvent {
  onChange: (id: string) => void;
}
interface ITabBtnGroupProps {
  activeKey: string;
  height?: number;
  list: ITabItem[];
  type?: string;
}

import type { ITabItem } from '../type';

import './tab-btn-group.scss';

@Component({
  name: 'TabBtnGroup',
  components: {},
})
export default class TabBtnGroup extends tsc<ITabBtnGroupProps, ITabBtnGroupEvent> {
  @Prop({ default: 'line', type: String }) type: string;
  @Prop({ default: 32, type: Number }) height: number;
  @Prop({ required: true, type: Array }) list: ITabItem[];
  @Prop({ required: true, type: String }) activeKey: string;
  typeStyle = {
    line: '',
    block: 'group-block',
    tab: 'group-tab',
  };
  get lineHeight() {
    return this.type === 'block' ? this.height - 4 : this.height;
  }
  get tabWidth() {
    return `${Number((100 / this.list.length).toFixed(2))}%`;
  }

  @Emit('change')
  handleClick(id: string) {
    return id;
  }

  render() {
    return (
      <div
        style={`height:${this.height}px; line-height: ${this.lineHeight}px;`}
        class={`tab-btn-group ${this.typeStyle[this.type]}`}
      >
        {(this.list || []).map(panel => (
          <div
            key={panel.id}
            style={{ width: this.tabWidth }}
            class={['tab-btn-group-item', { active: this.activeKey === panel.id }]}
            onClick={() => this.handleClick(panel.id)}
          >
            {panel.label}
            {panel?.icon && (
              <i
                class={`icon-monitor ${panel.icon} tab-row-icon`}
                onClick={() => panel?.handle?.()}
              />
            )}
          </div>
        ))}
      </div>
    );
  }
}
