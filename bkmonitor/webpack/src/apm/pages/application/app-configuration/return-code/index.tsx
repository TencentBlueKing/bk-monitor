/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import Redefine from './components/redefine';
import Remark from './components/remark';

import './index.scss';

interface ReturnCodeProps {
  appName: string;
}

@Component
export default class ReturnCode extends tsc<ReturnCodeProps> {
  @Prop({ default: '' }) appName: string;

  tabList = [
    {
      id: 'redefine',
      name: this.$t('返回码重定义'),
    },
    {
      id: 'remark',
      name: this.$t('返回码备注'),
    },
  ];
  activeTab = 'redefine';

  handleTabClick(id: string) {
    this.activeTab = id;
  }

  render() {
    return (
      <div class='return-code-page-main'>
        <div class='tab-list'>
          {this.tabList.map(item => {
            return (
              <div
                key={item.id}
                class={['tab-item', { 'is-active': this.activeTab === item.id }]}
                onClick={() => this.handleTabClick(item.id)}
              >
                <span class='tab-item-name'>{item.name}</span>
              </div>
            );
          })}
        </div>
        <div class='tab-content'>
          {this.activeTab === 'redefine' ? <Redefine appName={this.appName} /> : <Remark appName={this.appName} />}
        </div>
      </div>
    );
  }
}
