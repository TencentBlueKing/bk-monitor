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
import { statusList } from 'monitor-api/modules/report';
import { transformDataKey } from 'monitor-common/utils/utils';

import ListCollapse from './components/list-collapse.vue';
import { ITableColumnItem } from './types';

import './email-subscriptions-history.scss';

export interface IPagination {
  current: number;
  count: number;
  limit: number;
}
@Component
export default class EmailSubscriptionsHistory extends tsc<{}> {
  loading = false;
  /** 分页数据 */
  pagination: IPagination = {
    current: 1,
    count: 0,
    limit: 10
  };
  /** 展开发送列表 */
  activeList = ['1'];
  /** 当前页表格数据 */
  tableData = [];
  /** 全量数据 */
  allData = [];
  /** 表格列数据 */
  tableColumnsMap: ITableColumnItem[] = [
    { label: window.i18n.t('发送时间'), key: 'createTime' },
    { label: window.i18n.t('发送标题'), key: 'mailTitle' },
    { label: window.i18n.t('发送者'), key: 'username' },
    {
      label: window.i18n.t('接收者'),
      key: 'receivers',
      formatter: row => (row?.details?.receivers?.length ? row.receivers.join(', ') : '--')
    },
    { label: window.i18n.t('发送状态'), key: 'isSuccess' }
  ];

  created() {
    this.getSendList();
  }

  /** 前端分页 */
  changelistPage(page: number) {
    this.pagination.current = page;
    const { current, limit } = this.pagination;
    const start = (current - 1) * limit;
    const end = current * limit;
    this.tableData = this.allData.slice(start, end);
  }

  /** 获取全量的数据 */
  getSendList() {
    this.loading = true;
    statusList()
      .then(res => {
        this.allData = transformDataKey(res);
        this.pagination.count = res.length;
        this.changelistPage(1);
      })
      .finally(() => (this.loading = false));
  }

  /** 分页操作 */
  handlePageChange(page: number) {
    this.pagination.current = page;
    this.changelistPage(page);
  }
  /** 切换limit */
  handleLimitChange(limit: number) {
    this.pagination.limit = limit;
    this.changelistPage(1);
  }
  render() {
    return (
      <div class='email-subscriptions-history-wrap'>
        <ListCollapse
          class='collapse-wrap'
          title={this.$tc('已发送')}
          active-name={this.activeList}
          on-item-click={arr => (this.activeList = arr)}
        >
          <div
            slot='content'
            class='list-content'
          >
            <bk-table
              v-bkloading={{ isLoading: this.loading, zIndex: 1 }}
              style='margin-top: 15px'
              data={this.tableData}
              outer-border={true}
              header-border={false}
              pagination={this.pagination}
              on-page-change={this.handlePageChange}
              on-page-limit-change={this.handleLimitChange}
            >
              {this.tableColumnsMap.map((item, index) =>
                item.key === 'isSuccess' ? (
                  <bk-table-column
                    key={index}
                    label={this.$t('发送状态')}
                    prop='isSuccess'
                    scopedSlots={{
                      default: scope => (
                        <span class={scope.row.isSuccess ? 'is-success' : 'is-fail'}>
                          {scope.row.isSuccess ? this.$t('成功') : this.$t('失败')}
                        </span>
                      )
                    }}
                  ></bk-table-column>
                ) : (
                  <bk-table-column
                    key={index}
                    label={item.label}
                    prop={item.key}
                    formatter={item.formatter}
                  ></bk-table-column>
                )
              )}
            </bk-table>
          </div>
        </ListCollapse>
      </div>
    );
  }
}
