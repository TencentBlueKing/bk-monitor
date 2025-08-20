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

import QueryTemplateTable from './components/query-template-table/query-template-table';

import type { QueryTemplateListItem } from './typings';

import './query-template.scss';

@Component
export default class MetricTemplate extends tsc<object> {
  current = 1;
  pageSize = 50;
  total = 100;
  sort = '-update_time';
  searchKeyword = '';
  tableLoading = false;
  tableData: QueryTemplateListItem[] = new Array(Math.floor(Math.random() * 100)).fill(1).map((v, i) => {
    if (i % 4 === 0) {
      return {
        id: i,
        name: `指标模板名称占位${i}${i}${i}${i}`,
        description: '1×1×1×1×……×1=1，不要事情找你，而要你找事情，很傻很天真，又猛又持久',
        create_user: '创建人',
        create_time: '2025-06-24 10:32:51+0800',
        update_user: '更新人',
        update_time: '2025-06-24 10:32:51+0800',
        relation_config_count: 8,
      };
    }
    return {
      id: i,
      name: `指标模板名称占位${i}${i}${i}${i}`,
      description: '1×1×1×1×……×1=1，不要事情找你，而要你找事情，很傻很天真，又猛又持久',
      create_user: '创建人',
      create_time: '2025-06-24 10:32:51+0800',
      update_user: '更新人',
      update_time: '2025-06-24 10:32:51+0800',
      relation_config_count: null,
    };
  });

  handleSortChange(sort: `-${string}` | string) {
    this.sort = sort;
  }

  handleCurrentPageChange(currentPage: number) {
    this.current = currentPage;
  }
  handlePageSizeChange(pageSize: number) {
    this.pageSize = pageSize;
  }

  handleSearchChange(keyword: string) {
    this.searchKeyword = keyword;
  }

  /**
   * @description 跳转至 新建查询模板 页面
   */
  jumpToCreatePage() {
    this.$router.push({
      name: 'query-template-create',
    });
  }

  render() {
    return (
      <div class='query-template'>
        <div class='query-template-header'>
          <div class='query-template-header-operations'>
            <bk-button
              icon='plus'
              theme='primary'
              title={this.$t('新建')}
              onClick={this.jumpToCreatePage}
            >
              {this.$t('新建')}
            </bk-button>
          </div>
          <div class='query-template-header-search'>
            <bk-input
              class='search-input'
              placeholder={this.$t('搜索 模板名称、模板说明、创建人、更新人')}
              right-icon='bk-icon icon-search'
              value={this.searchKeyword}
              onChange={this.handleSearchChange}
            />
          </div>
        </div>
        <div class='query-template-main'>
          <QueryTemplateTable
            current={this.current}
            loading={this.tableLoading}
            pageSize={this.pageSize}
            sort={this.sort}
            tableData={this.tableData}
            total={this.total}
            onCurrentPageChange={this.handleCurrentPageChange}
            onPageSizeChange={this.handlePageSizeChange}
            onSortChange={this.handleSortChange}
          />
        </div>
      </div>
    );
  }
}
