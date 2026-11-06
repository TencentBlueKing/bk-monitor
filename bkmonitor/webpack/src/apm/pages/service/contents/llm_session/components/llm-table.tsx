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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from 'monitor-common/utils/utils';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';

import { EMPTY_TEXT } from '../constants';

import type { IIoSummaryCell, ILlmColumn, ISessionRow, ITokensCell, LlmRow, LlmStatus } from '../typings';

import './llm-table.scss';

interface ILlmTableEvents {
  onScrollEnd: () => void;
  onSortChange: (payload: { order: string; prop: string }) => void;
  onTraceIdClick: (traceId: string) => void;
}

interface ILlmTableProps {
  columns: ILlmColumn[];
  data: LlmRow[];
  /** 展开区子表的列。传入后主表首列插入展开列，用于会话视角 */
  expandColumns?: ILlmColumn[];
  loading?: boolean;
  maxHeight?: number | string;
  scrollLoading?: boolean;
}

/**
 * 配置驱动的 LLM 会话表格。
 *
 * 列由 ILlmColumn 元数据描述，单元格按 cellType 分发，会话视角与 Trace 视角复用同一套实现；
 * 展开区的子表也走同一个渲染入口，只是换一份列定义并改用本地排序。
 */
@Component
export default class LlmTable extends tsc<ILlmTableProps, ILlmTableEvents> {
  @Prop({ default: () => [], type: Array }) columns: ILlmColumn[];
  @Prop({ default: () => [], type: Array }) data: LlmRow[];
  @Prop({ type: Array }) expandColumns: ILlmColumn[];
  @Prop({ default: false, type: Boolean }) loading: boolean;
  @Prop({ default: false, type: Boolean }) scrollLoading: boolean;
  @Prop({ type: [Number, String] }) maxHeight: number | string;
  @Ref('table') tableRef: { $refs?: { bodyWrapper?: HTMLElement }; bodyWrapper?: HTMLElement };

  /** 手风琴：同时最多展开一行 */
  expandRowKeys: string[] = [];
  /** 已滚过展开区底部时取消吸顶；默认吸顶，避免展开瞬间 DOM 未就绪把 sticky 关掉 */
  isExpandStickyReleased = false;
  /** 主表的滚动容器，滚动的吸顶计算都基于它 */
  bodyScrollEl: HTMLElement | null = null;
  /** 监听展开区可见性，出入视口时触发吸顶状态重算 */
  expandStickyObserver: IntersectionObserver | null = null;
  /** 节流用 rAF 句柄：合并同一帧内的多次触发，避免高频 scroll/resize 反复布局计算 */
  expandStickyRaf = 0;

  get hasExpand() {
    return !!this.expandColumns?.length;
  }

  mounted() {
    this.bindExpandSticky();
    window.addEventListener('resize', this.scheduleExpandStickyUpdate);
  }

  beforeDestroy() {
    this.unbindExpandSticky();
    window.removeEventListener('resize', this.scheduleExpandStickyUpdate);
  }

  /**
   * 当 data / expandRowKeys / loading / maxHeight 任一变化时，在 DOM 更新后重新绑定吸顶逻辑。
   * 因为这些变化会导致表格重新渲染或尺寸变化，原有的 Observer 可能已失效。
   */
  @Watch('data')
  @Watch('expandRowKeys')
  @Watch('loading')
  @Watch('maxHeight')
  handleExpandStickyDepsChange() {
    this.$nextTick(() => this.bindExpandSticky());
  }

  /**
   * 获取主表 body 的滚动容器 DOM 节点。
   * 优先通过 $refs 取 bodyWrapper，降级回 DOM 查询（兼容不同 bk-table 版本）。
   * @returns 滚动容器元素，未找到时返回 null
   */
  getMainBodyWrapper() {
    return (
      this.tableRef?.bodyWrapper ||
      this.tableRef?.$refs?.bodyWrapper ||
      (this.$el?.querySelector(':scope > .bk-table > .bk-table-body-wrapper') as HTMLElement | null) ||
      null
    );
  }

  /**
   * 获取与吸顶计算相关的三个关键节点：
   * - scrollRoot: 主表滚动容器
   * - expandedRow: 被展开的行（吸顶目标）
   * - expandBox: 展开区域容器（用于判断是否滚过底部）
   */
  getExpandStickyNodes() {
    const scrollRoot = this.getMainBodyWrapper();
    const expandedRow = scrollRoot?.querySelector('table.bk-table-body tr.bk-table-row.expanded') as HTMLElement | null;
    const expandRow = expandedRow?.nextElementSibling as HTMLElement | null;
    const expandBox = (expandRow?.querySelector('.llm-table-expand') as HTMLElement | null) || expandRow;
    return { expandBox, expandedRow, scrollRoot };
  }

  /**
   * 绑定吸顶逻辑：
   * 1. 在滚动容器上注册 scroll 事件（再度监听前先移除旧的）
   * 2. 用 IntersectionObserver 监听展开区在滚动容器内的可见性变化
   * 3. 三种 threshold（0 / 0.01 / 1）覆盖入/出视口的边界情况
   * 4. 立即调用一次更新以确保初始状态正确
   */
  bindExpandSticky() {
    const scrollRoot = this.getMainBodyWrapper();
    if (this.bodyScrollEl !== scrollRoot) {
      this.bodyScrollEl?.removeEventListener('scroll', this.scheduleExpandStickyUpdate);
      this.bodyScrollEl = scrollRoot;
      this.bodyScrollEl?.addEventListener('scroll', this.scheduleExpandStickyUpdate, { passive: true });
    }
    this.expandStickyObserver?.disconnect();
    this.expandStickyObserver = null;
    const { expandBox } = this.getExpandStickyNodes();
    if (scrollRoot && expandBox) {
      this.expandStickyObserver = new IntersectionObserver(this.scheduleExpandStickyUpdate, {
        root: scrollRoot,
        threshold: [0, 0.01, 1],
      });
      this.expandStickyObserver.observe(expandBox);
    }
    this.scheduleExpandStickyUpdate();
  }

  /** 解绑吸顶：取消 rAF、断开 Observer、移除 scroll 监听，重置引用 */
  unbindExpandSticky() {
    if (this.expandStickyRaf) {
      cancelAnimationFrame(this.expandStickyRaf);
      this.expandStickyRaf = 0;
    }
    this.expandStickyObserver?.disconnect();
    this.expandStickyObserver = null;
    this.bodyScrollEl?.removeEventListener('scroll', this.scheduleExpandStickyUpdate);
    this.bodyScrollEl = null;
  }

  /**
   * 通过 requestAnimationFrame 节流频繁触发（scroll/resize/IntersectionObserver）
   * 同帧内的多次调用被合并为一次更新，避免布局抖动
   */
  scheduleExpandStickyUpdate = () => {
    if (this.expandStickyRaf) return;
    this.expandStickyRaf = requestAnimationFrame(() => {
      this.expandStickyRaf = 0;
      this.updateExpandSticky();
    });
  };

  /**
   * 展开区吸顶核心算法：
   * 当展开区底部滚过「吸顶行高度」时释放吸顶（sticky → relative），
   * 否则保持吸顶。这样展开区内部的子表 thead 能衔接到父表滚动位置，
   * 避免吸顶行遮挡展开区内容。
   * 判断条件：expandBox.bottom <= scrollRoot.top + rowHeight
   */
  updateExpandSticky() {
    if (!this.hasExpand || !this.expandRowKeys.length) {
      this.isExpandStickyReleased = false;
      return;
    }
    const { expandBox, expandedRow, scrollRoot } = this.getExpandStickyNodes();
    if (!expandBox || !expandedRow || !scrollRoot) return;
    const viewportTop = scrollRoot.getBoundingClientRect().top;
    const rowHeight = expandedRow.offsetHeight || 42;
    this.isExpandStickyReleased = expandBox.getBoundingClientRect().bottom <= viewportTop + rowHeight;
  }

  /**
   * 为当前展开行追加 CSS class：
   * 当该行处于「吸顶释放」状态时加 is-sticky-released，
   * 使 CSS 将 position:sticky 改为 position:relative，不遮挡展开区。
   * @returns 额外 class 字符串，无特殊情况返回空串
   */
  getRowClassName({ row }: { row: LlmRow }) {
    if (this.hasExpand && this.expandRowKeys[0] === row.key && this.isExpandStickyReleased) {
      return 'is-sticky-released';
    }
    return '';
  }

  handleScrollEnd() {
    this.$emit('scrollEnd');
  }

  handleSortChange(payload: { order: string; prop: string }) {
    this.$emit('sortChange', payload);
  }

  handleTraceIdClick(traceId: string) {
    if (!traceId) return;
    this.$emit('traceIdClick', traceId);
  }

  /** 会话视角：点击整行切换展开；已展开另一行时先收起，保证手风琴 */
  handleRowClick(row: LlmRow) {
    if (!this.hasExpand) return;
    this.setExpandedKey(this.expandRowKeys[0] === row.key ? undefined : row.key);
  }

  /** 展开图标走表格内部 toggle，再用受控 keys 收成单行展开 */
  handleExpandChange(row: LlmRow, expandedRows: LlmRow[]) {
    if (!this.hasExpand) return;
    const opened = expandedRows.some(item => item.key === row.key);
    this.setExpandedKey(opened ? row.key : undefined);
  }

  /**
   * 设置当前展开行 key（手风琴：最多展开一行）。
   * 切换行时重置 isExpandStickyReleased，让新展开区从吸顶状态开始。
   */
  setExpandedKey(key?: string) {
    this.expandRowKeys = key ? [key] : [];
    this.isExpandStickyReleased = false;
  }

  clipTooltipContent(value: string) {
    if (!value) return EMPTY_TEXT;
    if (value.length <= 200) return value;
    return `${value.substring(0, 200)}...`;
  }

  handleCopyIoText(event: Event, text: string) {
    event.preventDefault();
    event.stopPropagation();
    if (!text) return;
    copyText(text, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }

  /** 单元格分发。取值字段与列 id 一致，值均已在数据转换阶段格式化完成 */
  renderCell(column: ILlmColumn, row: LlmRow) {
    const value = row[column.id];
    switch (column.cellType) {
      case 'link': {
        return (
          <bk-button
            class='llm-table-id-link'
            theme='primary'
            text
            onClick={() => this.handleTraceIdClick(value as string)}
          >
            <span
              class='llm-table-text'
              v-bk-overflow-tips={{ content: value || EMPTY_TEXT }}
            >
              {value || EMPTY_TEXT}
            </span>
          </bk-button>
        );
      }
      case 'countLink':
        return (
          <span
            class='llm-table-link llm-table-text is-strong'
            v-bk-overflow-tips={{ content: value || EMPTY_TEXT }}
          >
            {value || EMPTY_TEXT}
          </span>
        );
      case 'duration':
        return <span class='llm-table-text'>{value || EMPTY_TEXT}</span>;
      case 'tokens':
      case 'tokensBadge':
        return this.renderTokensBadge(value as ITokensCell);
      case 'status':
        return this.renderStatus(value as '' | LlmStatus);
      case 'ioSummary':
        return this.renderIoSummary(value as IIoSummaryCell);
      default:
        return (
          <span
            class='llm-table-text'
            v-bk-overflow-tips={{ content: this.clipTooltipContent(value as string) }}
          >
            {value || EMPTY_TEXT}
          </span>
        );
    }
  }

  /** 输入 / 输出摘要：两侧各自缩略，中间箭头分隔；悬停弹出完整内容，超出 5 行滚动，可复制 */
  renderIoSummary(ioSummary: IIoSummaryCell) {
    const input = ioSummary?.input || EMPTY_TEXT;
    const output = ioSummary?.output || EMPTY_TEXT;
    return (
      <bk-popover
        width={597}
        class='llm-table-io-popover-trigger'
        tippy-options={{
          animateFill: false,
          animation: false,
          arrow: false,
          delay: [500, 0],
          hideOnClick: false,
          interactive: true,
        }}
        max-width={597}
        placement='top'
        theme='light padding-0 llm-table-io'
        transfer
      >
        <div class='llm-table-io-summary'>
          <span class='io-text'>{input}</span>
          <i class='icon-monitor icon-next-one io-arrow' />
          <span class='io-text'>{output}</span>
        </div>
        <div
          class='llm-table-io-popover'
          slot='content'
        >
          {this.renderIoPopoverSection(this.$t('输入') as string, input)}
          {this.renderIoPopoverSection(this.$t('输出') as string, output)}
        </div>
      </bk-popover>
    );
  }

  /** 弹层内的输入 / 输出分区：标题 + 最多 5 行正文 + 复制 */
  renderIoPopoverSection(title: string, content: string) {
    return (
      <div class='io-popover-section'>
        <div class='io-popover-title'>{title}</div>
        <div class='io-popover-box'>
          <div class='io-popover-text'>{content}</div>
          <i
            class='icon-monitor icon-mc-copy io-popover-copy'
            onClick={(event: Event) => this.handleCopyIoText(event, content)}
          />
        </div>
      </div>
    );
  }

  /** 状态：圆点 + 文案。success 成功 / error 失败，非法值回退占位 */
  renderStatus(status: '' | LlmStatus) {
    if (status !== 'success' && status !== 'error') {
      return <span class='llm-table-text'>{EMPTY_TEXT}</span>;
    }
    return (
      <span class='llm-table-status'>
        <span class={['llm-table-status-dot', `is-${status}`]} />
        <span>{status === 'success' ? this.$t('成功') : this.$t('失败')}</span>
      </span>
    );
  }

  /** Tokens 徽标：左侧为总量，右侧标签内分别是输入与输出 */
  renderTokensBadge(tokens: ITokensCell) {
    return (
      <div class='llm-table-tokens-badge'>
        <span class='tokens-total'>{tokens.totalText}</span>
        <span class='tokens-tag'>
          <i class='icon-monitor icon-mc-ai-input tokens-tag-icon' />
          <span class='tokens-tag-value'>{tokens.inputText}</span>
          <span class='tokens-tag-divider' />
          <i class='icon-monitor icon-mc-ai-output tokens-tag-icon is-output' />
          <span class='tokens-tag-value is-output'>{tokens.outputText}</span>
        </span>
      </div>
    );
  }

  /**
   * @param localSort 展开子表的数据已随主列表返回，排序在本地完成；主表走接口远程排序
   */
  renderColumn(column: ILlmColumn, localSort = false) {
    // 子表数据已在本地，交给 bk-table 内置排序；主表需要接口排序，用 custom 把排序事件抛给调用方
    const sortable = localSort ? !!column.sortBy : !!column.sortField && 'custom';
    return (
      <bk-table-column
        key={column.id}
        width={column.width}
        class-name={column.className}
        label={column.label}
        label-class-name={column.className}
        minWidth={column.minWidth}
        prop={column.sortField}
        scopedSlots={{ default: ({ row }) => this.renderCell(column, row as LlmRow) }}
        sortable={sortable}
        sortBy={localSort ? column.sortBy : undefined}
      />
    );
  }

  /** 展开区：会话下的多轮 Trace，数据取自 childs，无需二次请求 */
  renderExpandContent(row: ISessionRow) {
    return (
      <div class='llm-table-expand'>
        <bk-table
          class='llm-table-expand-table'
          data={row.children}
          outer-border={false}
          row-key='key'
        >
          {this.expandColumns.map(column => this.renderColumn(column, true))}
        </bk-table>
      </div>
    );
  }

  render() {
    return (
      // is-expand-sticky-released 类控制展开区子表 thead 的吸顶偏移量，
      // 展开区滚过吸顶行高度后释放，避免遮挡展开区内容
      <div class={['llm-table', { 'is-expandable': this.hasExpand, 'is-expand-sticky-released': this.isExpandStickyReleased }]}>
        {this.loading ? (
          <TableSkeleton
            class='llm-table-skeleton'
            type={2}
          />
        ) : (
          <bk-table
            ref='table'
            scroll-loading={{
              isLoading: this.scrollLoading,
              size: 'mini',
              theme: 'info',
              icon: 'circle-2-1',
              placement: 'right',
            }}
            data={this.data}
            expand-row-keys={this.expandRowKeys}
            max-height={this.maxHeight}
            outer-border={false}
            row-class-name={this.getRowClassName}
            row-key='key'
            on-expand-change={this.handleExpandChange}
            on-row-click={this.handleRowClick}
            on-scroll-end={this.handleScrollEnd}
            on-sort-change={this.handleSortChange}
          >
            {this.$slots.empty && <div slot='empty'>{this.$slots.empty}</div>}
            {this.hasExpand && (
              <bk-table-column
                key='__expand__'
                width={30}
                scopedSlots={{ default: ({ row }) => this.renderExpandContent(row as ISessionRow) }}
                type='expand'
              />
            )}
            {this.columns.map(column => this.renderColumn(column))}
          </bk-table>
        )}
      </div>
    );
  }
}
