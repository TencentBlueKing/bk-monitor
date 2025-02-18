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

import { Component, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './dimension-filter-panel.scss';

interface DimensionFilterPanelEvents {
  onClose(): void;
}

@Component
export default class DimensionFilterPanel extends tsc<object, DimensionFilterPanelEvents> {
  list = [
    { name: '字符串', alias: '字符串', type: 'keyword' },
    { name: '文本', alias: '文本', type: 'text' },
    { name: '数字', alias: '数字', type: 'interger' },
    { name: '日期', alias: '日期', type: 'date' },
  ];

  typeIconMap = {
    keyword: 'icon-string',
    text: 'icon-text',
    interger: 'icon-number',
    date: 'icon-mc-time',
  };

  searchVal = '';

  @Emit('close')
  handleClose() {}

  render() {
    return (
      <div class='dimension-filter-panel-comp'>
        <div class='header'>
          <div class='title'>{this.$t('维度过滤')}</div>
          <i
            class='icon-monitor icon-back-left'
            onClick={this.handleClose}
          />
        </div>
        <div class='search-input'>
          <bk-input
            v-model={this.searchVal}
            placeholder={this.$t('搜索 维度字段')}
            right-icon='bk-icon icon-search'
          />
        </div>

        <div class='dimension-list'>
          {this.list.map(item => (
            <div
              key={item.name}
              class='dimension-item'
            >
              <span class={['icon-monitor', this.typeIconMap[item.type], 'type-icon']} />
              <span class='dimension-name'>{item.alias}</span>
              <span class='dimension-count'>10</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
}
