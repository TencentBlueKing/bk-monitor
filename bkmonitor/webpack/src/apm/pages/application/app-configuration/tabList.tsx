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

interface IEvent {
  onChange: (active: string) => void;
}

interface IProps {
  activeTab: string;
  tabList: ITab[];
}
interface ITab {
  disabledTips?: string;
  label: string;
  name: string;
  noDataTips?: string;
  status: 'disabled' | 'no_data' | 'normal';
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
  handleActiveChange(item: ITab) {
    // 暂时去掉
    if (!item.status || item.status === 'disabled') {
      return;
    }
    this.active = item.name;
    this.$emit('change', item.name);
  }

  tipContentFn(item) {
    if (item.status === 'no_data') {
      return item.noDataTips;
    }
    if (item.status === 'disabled') {
      return item.disabledTips;
    }
    return '';
  }

  render() {
    return (
      <div class='tab-list-wrap-app-config'>
        <ul class='tab-list'>
          {this.tabList.map(item => {
            return (
              <li
                key={item.name}
                class={[{ active: this.active === item.name }, `status-${item.status || 'disabled'}`]}
                v-bk-tooltips={{
                  content: this.tipContentFn(item),
                  disabled: !['no_data', 'disabled'].includes(item.status),
                }}
                onClick={() => this.handleActiveChange(item)}
              >
                <span class={['point']} />
                <span class='tab-text'>{this.$t(item.label)}</span>
              </li>
            );
          })}
        </ul>
      </div>
    );
  }
}
