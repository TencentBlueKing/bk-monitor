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

import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './consume-panel.scss';

@Component
export default class ConsumePanel extends tsc<object> {
  /** 筛选输入的关键字 */
  searchKeyword = '';
  /** 消费场景表格源数据 */
  tableData = [
    {
      name: '我是名称占位A',
      type: '仪表盘',
    },
    {
      name: '我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B',
      type: '仪表盘',
    },
    {
      name: '我是名称占位B',
      type: '告警策略',
    },
    {
      name: '我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B我是名称占位B',
      type: '告警策略',
    },
  ];
  /** 表格实际渲染的数据 */
  get tableViewData() {
    return this.tableData.filter(item => {
      const matchReg = new RegExp(`${this.searchKeyword}`.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&'), 'ig');
      return matchReg.test(item.name) || matchReg.test(item.type);
    });
  }

  /** 搜索输入框值改变时触发 */
  handleSearchChange(keyword: string) {
    this.searchKeyword = keyword;
  }

  /** 表格行点击跳转链接 */
  handleLinkTo() {
    console.log('点击跳转......，待补充');
  }
  render() {
    return (
      <div class='consume-panel'>
        <bk-alert
          class='consume-alert-tip'
          type='info'
        >
          <div
            slot='title'
            class='alert-tip-content'
          >
            <span class='tip-description'>
              {this.$t('仪表盘 Panel 级别的定位，需要一定的时间同步，如有需要请点击')}
            </span>
            <span class='refresh-btn'>{this.$t('刷新')}</span>
          </div>
        </bk-alert>
        <bk-input
          class='consume-search-input'
          placeholder={this.$t('搜索 消费场景')}
          right-icon='bk-icon icon-search'
          value={this.searchKeyword}
          onChange={this.handleSearchChange}
        />
        <div class='consume-panel-table'>
          <bk-table
            data={this.tableViewData}
            size='small'
            border={false}
            height='100%'
            stripe={true}
            outer-border={false}
          >
            <bk-table-column
              label={this.$t('名称')}
              prop='name'
              resizable={false}
              formatter={row => {
                return (
                  <div class='link-col'>
                    <div onClick={this.handleLinkTo}>
                      <div
                        class='link-col-text'
                        v-bk-overflow-tips
                      >
                        <span>{row.name}</span>
                      </div>
                      <i class='icon-monitor icon-mc-goto' />
                    </div>
                  </div>
                );
              }}
            />
            <bk-table-column
              label={this.$t('类型')}
              prop='type'
              width='248'
              resizable={false}
            />
          </bk-table>
        </div>
      </div>
    );
  }
}
