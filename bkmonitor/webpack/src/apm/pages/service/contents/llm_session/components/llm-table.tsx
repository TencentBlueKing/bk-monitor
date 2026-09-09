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

import { EMPTY_TEXT } from '../constants';

import type { ILlmColumn, ISessionRow, ITokensCell, LlmRow } from '../typings';

import './llm-table.scss';

interface ILlmTableEvents {
  onScrollEnd: () => void;
  onSortChange: (payload: { order: string; prop: string }) => void;
}

interface ILlmTableProps {
  columns: ILlmColumn[];
  data: LlmRow[];
  /** 表头升降序箭头的初始状态，仅在表格挂载时生效，用于还原回填的排序 */
  defaultSort?: { order: string; prop: string };
  /** 展开区子表的列。传入后主表首列插入展开列，用于会话视角 */
  expandColumns?: ILlmColumn[];
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
  @Prop({ type: Object }) defaultSort: { order: string; prop: string };
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
        label={column.label}
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
          scroll-loading={{
            isLoading: this.scrollLoading,
            size: 'mini',
            theme: 'info',
            icon: 'circle-2-1',
            placement: 'right',
          }}
          data={this.data}
          default-sort={this.defaultSort}
          max-height={this.maxHeight}
          outer-border={false}
          row-key='key'
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
