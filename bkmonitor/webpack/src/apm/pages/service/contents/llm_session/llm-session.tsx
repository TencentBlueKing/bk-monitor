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
import { Component, Inject, InjectReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import axios, { type CancelTokenSource } from 'axios';
import { Debounce } from 'monitor-common/utils/utils';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import LlmTable from './components/llm-table';
import { PAGE_LIMIT } from './constants';
import { getSessionColumns, getSessionTraceColumns, getTraceColumns } from './utils/columns';
import { fetchLlmTraceList } from './utils/query';
import { fromTableSort, readRouteQuery, toRouteQuery, toTableSort } from './utils/route-query';
import { toSessionRow, toTraceRow } from './utils/transform';

import type { ILlmTraceItem, LlmRow, LlmViewMode } from './typings';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './llm-session.scss';

interface IViewModeItem {
  icon: string;
  id: LlmViewMode;
  name: string;
}

/**
 * APM 服务 - LLM 会话。
 *
 * 会话视角按会话字段折叠，主行可展开出该会话的多轮 Trace；Trace 视角平铺全部 Trace。
 * 两个视角查同一个 list_traces 接口，差异只有分组字段，因此请求与转换逻辑完全共享。
 */
@Component
export default class LlmSession extends tsc<object> {
  @InjectReactive('viewOptions') readonly viewOptions?: IViewOptions;
  @InjectReactive('timeRange') readonly timeRange?: TimeRangeType;
  @InjectReactive('timezone') readonly timezone?: string;
  @InjectReactive('refreshImmediate') readonly refreshImmediate?: string;
  /** CommonPage 汇总的各 tab 自定义路由参数，回填时从这里读 */
  @InjectReactive('customRouteQuery') readonly customRouteQuery?: Record<string, string>;
  /** 回写路由参数，CommonPage 内部合并后统一 replace，不会覆盖其他 tab 的参数 */
  @Inject('handleCustomRouteQueryChange') handleCustomRouteQueryChange?: (
    customRouteQuery: Record<string, number | string>
  ) => void;

  @Ref('tableWrap') tableWrapRef?: HTMLDivElement;

  viewMode: LlmViewMode = 'session';
  keyword = '';
  /** 远程排序参数：升序为字段名，降序加 - 前缀 */
  sort: string[] = [];

  rows: LlmRow[] = [];
  loading = false;
  scrollLoading = false;
  /** 上一页返回数不足一页，说明已无更多数据 */
  noMoreData = false;

  tableMaxHeight = 0;

  /** 请求序号，只接受最新一次请求的响应，避免快速切换视角时旧响应覆盖新数据 */
  requestSeq = 0;
  cancelTokenSource: CancelTokenSource | null = null;
  resizeObserver: null | ResizeObserver = null;

  viewModeList: IViewModeItem[] = [
    { id: 'session', name: `Session ${window.i18n.tc('视角')}`, icon: 'icon-Session' },
    { id: 'trace', name: `Trace ${window.i18n.tc('视角')}`, icon: 'icon-Tracing' },
  ];

  get appName() {
    return this.viewOptions?.filters?.app_name ?? '';
  }

  get serviceName() {
    return this.viewOptions?.filters?.service_name ?? '';
  }

  get isSessionMode() {
    return this.viewMode === 'session';
  }

  get columns() {
    return this.isSessionMode ? getSessionColumns() : getTraceColumns();
  }

  /** 只有会话视角需要展开区 */
  get expandColumns() {
    return this.isSessionMode ? getSessionTraceColumns() : undefined;
  }

  /** 表头升降序箭头的初始状态，让回填的排序在 UI 上可见 */
  get defaultSort() {
    return toTableSort(this.sort);
  }

  get searchPlaceholder() {
    return this.isSessionMode
      ? this.$tc('搜索 会话 ID、User ID')
      : this.$tc('搜索 Trace ID、User ID、会话 ID、输入输出摘要');
  }

  /** 请求依赖的上下文，聚合成单一 key 以避免多个 watch 造成重复请求 */
  get requestKey() {
    return [this.appName, this.serviceName, this.timeRange?.join('|'), this.timezone, this.refreshImmediate].join('__');
  }

  @Watch('requestKey')
  handleRequestKeyChange() {
    if (!this.appName) return;
    this.reload();
  }

  /**
   * 首次加载放在 created 而不是 immediate watch：immediate 的回调早于 created 执行，
   * 那时还来不及从路由回填查询条件，会先用默认条件多发一次请求。
   */
  created() {
    const { viewMode, keyword, sort } = readRouteQuery(this.customRouteQuery);
    this.viewMode = viewMode;
    this.keyword = keyword;
    this.sort = sort;
    if (this.appName) this.reload();
  }

  mounted() {
    this.observeTableHeight();
  }

  beforeDestroy() {
    this.resizeObserver?.disconnect();
    this.cancelTokenSource?.cancel?.();
  }

  /** 表格需要确定高度才能触发滚动到底事件，这里跟随容器尺寸变化更新 */
  observeTableHeight() {
    if (!this.tableWrapRef) return;
    this.resizeObserver = new ResizeObserver(entries => {
      this.tableMaxHeight = entries[0]?.contentRect?.height ?? 0;
    });
    this.resizeObserver.observe(this.tableWrapRef);
  }

  /**
   * 拉取一页数据
   * @returns 本次响应已过期时返回 null，调用方不应更新状态
   */
  async request(offset: number): Promise<ILlmTraceItem[] | null> {
    this.cancelTokenSource?.cancel?.();
    this.cancelTokenSource = axios.CancelToken.source();
    const seq = ++this.requestSeq;
    const items = await fetchLlmTraceList(
      {
        appName: this.appName,
        serviceName: this.serviceName,
        ...this.getTimestamps(),
        viewMode: this.viewMode,
        keyword: this.keyword,
        sort: this.sort,
        offset,
      },
      this.cancelTokenSource.token
    );
    if (seq !== this.requestSeq) return null;
    this.noMoreData = items.length < PAGE_LIMIT;
    return items;
  }

  getTimestamps() {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange ?? ['', '']);
    return { startTime, endTime };
  }

  toRows(items: ILlmTraceItem[]): LlmRow[] {
    return this.isSessionMode ? items.map(toSessionRow) : items.map(toTraceRow);
  }

  /** 条件变化后从头加载。会打断在途的滚动加载，因此一并复位其加载态 */
  async reload() {
    this.loading = true;
    this.scrollLoading = false;
    this.noMoreData = false;
    const items = await this.request(0);
    // 响应已过期说明有更新的请求在途，加载态交由后者收尾
    if (!items) return;
    this.rows = this.toRows(items);
    this.loading = false;
  }

  /** 滚动到底部加载下一页，offset 即已加载的分组数 */
  async handleScrollEnd() {
    if (this.loading || this.scrollLoading || this.noMoreData) return;
    this.scrollLoading = true;
    const items = await this.request(this.rows.length);
    if (!items) return;
    if (items.length) this.rows = [...this.rows, ...this.toRows(items)];
    this.scrollLoading = false;
  }

  /** 把当前查询条件同步到路由，刷新或分享链接时可原样还原 */
  syncRouteQuery() {
    this.handleCustomRouteQueryChange?.(
      toRouteQuery({ viewMode: this.viewMode, keyword: this.keyword, sort: this.sort })
    );
  }

  handleViewModeChange(mode: LlmViewMode) {
    if (this.viewMode === mode) return;
    this.viewMode = mode;
    // 两个视角的列与排序键不同，切换时重置排序
    this.sort = [];
    this.syncRouteQuery();
    this.reload();
  }

  @Debounce(300)
  handleKeywordChange() {
    this.syncRouteQuery();
    this.reload();
  }

  handleSortChange({ prop, order }: { order: string; prop: string }) {
    const sort = fromTableSort(prop, order);
    // default-sort 会在表格挂载后补发一次同值的排序事件，与当前条件一致时不必重复请求
    if (sort.join() === this.sort.join()) return;
    this.sort = sort;
    this.syncRouteQuery();
    this.reload();
  }

  handleClearSearch() {
    this.keyword = '';
    this.syncRouteQuery();
    this.reload();
  }

  renderViewModeTab() {
    return (
      <div class='llm-session-view-mode'>
        {this.viewModeList.map(item => (
          <div
            key={item.id}
            class={['view-mode-item', { 'is-active': this.viewMode === item.id }]}
            onClick={() => this.handleViewModeChange(item.id)}
          >
            <i class={['icon-monitor', item.icon]} />
            <span>{item.name}</span>
          </div>
        ))}
      </div>
    );
  }

  render() {
    return (
      <div class='llm-session'>
        <div class='llm-session-header'>
          {this.renderViewModeTab()}
          <bk-input
            class='llm-session-search'
            v-model={this.keyword}
            placeholder={this.searchPlaceholder}
            right-icon='bk-icon icon-search'
            clearable
            onChange={this.handleKeywordChange}
          />
        </div>
        <div
          ref='tableWrap'
          class='llm-session-table-wrap'
        >
          {this.loading ? (
            <TableSkeleton type={2} />
          ) : (
            <LlmTable
              columns={this.columns}
              data={this.rows}
              defaultSort={this.defaultSort}
              expandColumns={this.expandColumns}
              maxHeight={this.tableMaxHeight || undefined}
              scrollLoading={this.scrollLoading}
              onScrollEnd={this.handleScrollEnd}
              onSortChange={this.handleSortChange}
            >
              <EmptyStatus
                slot='empty'
                type={this.keyword ? 'search-empty' : 'empty'}
                onOperation={this.handleClearSearch}
              />
            </LlmTable>
          )}
        </div>
      </div>
    );
  }
}
