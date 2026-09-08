import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { EMPTY_TEXT } from '../constants';

import type { ILlmColumn, ISessionRow, ITokensCell, LlmRow } from '../typings';

import './llm-table.scss';

interface ILlmTableProps {
  columns: ILlmColumn[];
  data: LlmRow[];
  /** 展开区子表的列。传入后主表首列插入展开列，用于会话视角 */
  expandColumns?: ILlmColumn[];
  loading?: boolean;
  maxHeight?: number | string;
  scrollLoading?: boolean;
}

interface ILlmTableEvents {
  onScrollEnd: () => void;
  onSortChange: (payload: { order: string; prop: string }) => void;
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

  get hasExpand() {
    return !!this.expandColumns?.length;
  }

  handleScrollEnd() {
    this.$emit('scrollEnd');
  }

  handleSortChange(payload: { order: string; prop: string }) {
    this.$emit('sortChange', payload);
  }

  /** 单元格分发。取值字段与列 id 一致，值均已在数据转换阶段格式化完成 */
  renderCell(column: ILlmColumn, row: LlmRow) {
    const value = row[column.id];
    switch (column.cellType) {
      case 'link':
        // 本期只做展示，点击跳转后续接入
        return (
          <span
            class='llm-table-text llm-table-link'
            v-bk-overflow-tips
          >
            {value || EMPTY_TEXT}
          </span>
        );
      case 'countLink':
        return <span class='llm-table-link is-strong'>{value || EMPTY_TEXT}</span>;
      case 'tokens':
        return <span class='llm-table-text'>{(value as ITokensCell).totalText}</span>;
      case 'tokensBadge':
        return this.renderTokensBadge(value as ITokensCell);
      case 'status':
        // 接口暂未返回状态字段，统一占位；后端补齐后在此接入状态图标与文案映射
        return <span class='llm-table-text'>{(value as string) || EMPTY_TEXT}</span>;
      default:
        return (
          <span
            class='llm-table-text'
            v-bk-overflow-tips
          >
            {value || EMPTY_TEXT}
          </span>
        );
    }
  }

  /** Tokens 徽标：左侧为总量，右侧标签内分别是输入与输出 */
  renderTokensBadge(tokens: ITokensCell) {
    return (
      <div class='llm-table-tokens-badge'>
        <span class='tokens-total'>{tokens.totalText}</span>
        <span class='tokens-tag'>
          <i class='icon-monitor icon-arrow-right tokens-tag-icon' />
          <span class='tokens-tag-value'>{tokens.inputText}</span>
          <span class='tokens-tag-divider' />
          <i class='icon-monitor icon-arrow-left tokens-tag-icon is-output' />
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
        label={column.label}
        minWidth={column.minWidth}
        prop={column.sortField}
        scopedSlots={{ default: ({ row }) => this.renderCell(column, row as LlmRow) }}
        sortBy={localSort ? column.sortBy : undefined}
        sortable={sortable}
      />
    );
  }

  /** 展开区：会话下的多轮 Trace，数据取自 childs，无需二次请求 */
  renderExpandContent(row: ISessionRow) {
    return (
      <div class='llm-table-expand'>
        <bk-table
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
      <div class='llm-table'>
        <bk-table
          v-bkloading={{ isLoading: this.loading, zIndex: 10 }}
          data={this.data}
          max-height={this.maxHeight}
          outer-border={false}
          row-key='key'
          scroll-loading={{
            isLoading: this.scrollLoading,
            size: 'mini',
            theme: 'info',
            icon: 'circle-2-1',
            placement: 'right',
          }}
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
      </div>
    );
  }
}
