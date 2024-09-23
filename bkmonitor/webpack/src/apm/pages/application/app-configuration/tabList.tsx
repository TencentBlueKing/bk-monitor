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

import './tabList.scss';

interface ITab {
  name: string;
  label: string;
}

interface IProps {
  tabList: ITab[];
  activeTab: string;
}
interface IEvent {
  onChange: (active: string) => void;
}
@Component
export default class TabList extends tsc<IProps, IEvent> {
  @Prop({ type: String }) activeTab: string;
  @Prop({ type: Array, default: () => [] }) tabList: ITab[];

  active = '';
  @Watch('activeTab', { immediate: true })
  handleChange(v) {
    this.active = v;
  }
  handleActiveChange(id: string) {
    this.active = id;
    this.$emit('change', id);
  }
  render() {
    return (
      <div class='tab-list-wrap'>
        <ul class='tab-list'>
          {this.tabList.map(item => {
            return (
              <li
                key={item.name}
                class={{ active: this.active === item.name }}
                onClick={this.handleActiveChange.bind(this, item.name)}
              >
                <span class='point' />
                <span class='tab-text'>{this.$t(item.label)}</span>
              </li>
            );
          })}
        </ul>
      </div>
    );
  }
}
