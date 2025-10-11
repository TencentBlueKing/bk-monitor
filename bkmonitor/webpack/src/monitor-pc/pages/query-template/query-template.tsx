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

import { Component, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { commonPageSizeGet, commonPageSizeSet, Debounce, random } from 'monitor-common/utils';

import QueryTemplateSearch from './components/query-template-search/query-template-search';
import QueryTemplateTable from './components/query-template-table/query-template-table';
import { destroyQueryTemplateById, fetchQueryTemplateList } from './service/table';

import type { DeleteConfirmEvent } from './components/query-template-table/components/delete-confirm';
import type { QueryListRequestParams, QueryTemplateListItem } from './typings';

import './query-template.scss';

@Component
export default class MetricTemplate extends tsc<object> {
  /** 下发重新请求接口数据标志 */
  refreshKey = random(8);
  current = 1;
  pageSize = 50;
  total = 100;
  sort = '-update_time';
  searchKeyword: QueryListRequestParams['conditions'] = [];
  tableLoading = false;
  tableData: QueryTemplateListItem[] = [];
  /** 数据请求中止控制器 */
  abortController: AbortController = null;

  get requestParam() {
    const param = {
      refreshKey: this.refreshKey,
      page: this.current,
      page_size: this.pageSize,
      order_by: this.sort ? [this.sort] : [],
      conditions: this.searchKeyword,
    };

    delete param.refreshKey;
    return param as unknown as QueryListRequestParams;
  }

  created() {
    this.getRouterParams();
    this.pageSize = commonPageSizeGet();
  }
  mounted() {
    this.getQueryTemplateList();
  }
  beforeDestroy() {
    this.abortRequest();
  }

  @Debounce(200)
  @Watch('requestParam')
  async getQueryTemplateList() {
    this.abortRequest();
    this.tableLoading = true;
    this.abortController = new AbortController();
    const { total, templateList, isAborted } = await fetchQueryTemplateList(this.requestParam, {
      signal: this.abortController.signal,
    });
    if (isAborted) {
      return;
    }
    this.total = total;
    this.tableData = templateList;
    this.tableLoading = false;
  }

  /**
   * @description 中止数据请求
   */
  abortRequest() {
    if (!this.abortController) return;
    this.abortController.abort();
    this.abortController = null;
  }

  /**
   * @description 获取路由参数
   */
  getRouterParams() {
    const { sort, searchKeyword } = this.$route.query;
    try {
      this.sort = (sort as string) || '-update_time';
      this.searchKeyword = searchKeyword ? JSON.parse(searchKeyword as string) : [];
    } catch (error) {
      console.log('route query:', error);
    }
  }

  /**
   * @description 缓存条件参数知路由
   */
  setRouterParams(otherParams: Record<string, any> = {}) {
    const query = {
      ...this.$route.query,
      sort: this.sort,
      searchKeyword: JSON.stringify(this.searchKeyword),
      ...otherParams,
    };
    const targetRoute = this.$router.resolve({
      query,
    });
    /** 防止出现跳转当前地址导致报错 */
    if (targetRoute.resolved.fullPath !== this.$route.fullPath) {
      this.$router.replace({
        query,
      });
    }
  }

  /**
   * @description 删除查询模板
   * @param templateId 模板Id
   */
  deleteTemplateById(templateId: string, confirmEvent: DeleteConfirmEvent) {
    destroyQueryTemplateById(templateId)
      .then(() => {
        confirmEvent.successCallback();
        this.$bkMessage({
          message: this.$t('删除成功'),
          theme: 'success',
        });
        this.handleRefresh();
      })
      .catch(() => {
        confirmEvent.errorCallback();
        this.$bkMessage({
          message: this.$t('删除失败'),
          theme: 'error',
        });
      });
  }

  handleCurrentPageChange(currentPage: number) {
    this.current = currentPage;
  }

  /**
   * @description 刷新表格数据
   */
  handleRefresh() {
    this.refreshKey = random(8);
    this.handleCurrentPageChange(1);
  }

  handleSortChange(sort: `-${string}` | string) {
    if (sort === this.sort) return;
    this.sort = sort;
    this.handleCurrentPageChange(1);
    this.setRouterParams();
  }

  handlePageSizeChange(pageSize: number) {
    this.pageSize = pageSize;
    this.handleCurrentPageChange(1);
    commonPageSizeSet(this.pageSize);
  }

  handleSearchChange(keyword: QueryListRequestParams['conditions']) {
    this.searchKeyword = keyword;
    this.handleCurrentPageChange(1);
    this.setRouterParams();
  }

  /**
   * @description 将url中自动显示详情侧弹抽屉的参数配置清除
   */
  handleDisabledAutoShowSlider() {
    this.setRouterParams({ sliderShow: false, sliderActiveId: '' });
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
            <QueryTemplateSearch
              class='search-input'
              searchKeyword={this.searchKeyword}
              onChange={this.handleSearchChange}
            />
          </div>
        </div>
        <div class='query-template-main'>
          <QueryTemplateTable
            current={this.current}
            emptyType={this.searchKeyword?.length ? 'search-empty' : 'empty'}
            loading={this.tableLoading}
            pageSize={this.pageSize}
            sort={this.sort}
            tableData={this.tableData}
            total={this.total}
            onClearSearch={() => this.handleSearchChange([])}
            onCurrentPageChange={this.handleCurrentPageChange}
            onDeleteTemplate={this.deleteTemplateById}
            onDisabledAutoShowSlider={this.handleDisabledAutoShowSlider}
            onPageSizeChange={this.handlePageSizeChange}
            onSortChange={this.handleSortChange}
          />
        </div>
      </div>
    );
  }
}
