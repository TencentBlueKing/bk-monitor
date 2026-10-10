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
import type { ILlmColumn } from '../typings';

// Trace 视角 Trace ID 默认 180px，超长单行省略；会话 ID 默认 160px。
const ID_WIDTH = 180;
const SESSION_ID_WIDTH = 160;
const USER_ID_WIDTH = 96;
const TOKENS_WIDTH = 200;
const STATUS_WIDTH = 80;
/** 展开区右侧 16px 内边距，父表状态列补上这段宽度，耗时 / Tokens / 状态才能与子表对齐 */
const SESSION_STATUS_WIDTH = STATUS_WIDTH + 16;
/** 展开子表左边距等于展开列宽，Trace ID 覆盖「会话 ID + 用户 ID」，与父表最近活动时间对齐 */
const SESSION_TRACE_ID_WIDTH = SESSION_ID_WIDTH + USER_ID_WIDTH;

/**
 * 列定义注册表。
 *
 * 三份列表共用同一批单元格实现（见 LlmTable.renderCell），新增或调整列只需改这里。
 * sortField 缺省的列表示接口暂未提供对应排序键，后端补齐后在此补上即可开启远程排序。
 */

/** 会话视角主表列，首列由表格额外插入的展开列承载折叠图标 */
export function getSessionColumns(): ILlmColumn[] {
  return [
    {
      id: 'sessionId',
      label: window.i18n.tc('会话 ID'),
      cellType: 'text',
      className: 'is-no-padding-left',
      width: SESSION_ID_WIDTH,
    },
    { id: 'userId', label: window.i18n.tc('用户 ID'), cellType: 'text', width: USER_ID_WIDTH },
    { id: 'lastActiveText', label: window.i18n.tc('最近活动时间'), cellType: 'text', width: 190 },
    { id: 'ioSummary', label: window.i18n.tc('输入 / 输出摘要'), cellType: 'ioSummary', minWidth: 120 },
    { id: 'traceCountText', label: window.i18n.tc('Trace 数'), cellType: 'countLink', width: 100 },
    { id: 'elapsedText', label: window.i18n.tc('耗时'), cellType: 'duration', width: 100 },
    { id: 'tokens', label: 'Tokens', cellType: 'tokens', width: TOKENS_WIDTH },
    { id: 'status', label: window.i18n.tc('状态'), cellType: 'status', width: SESSION_STATUS_WIDTH },
  ];
}

/** 会话视角展开区的 Trace 子表列。数据来自 childs，排序为本地排序 */
export function getSessionTraceColumns(): ILlmColumn[] {
  return [
    { id: 'traceId', label: 'Trace ID', cellType: 'link', width: SESSION_TRACE_ID_WIDTH },
    {
      id: 'lastActiveText',
      label: window.i18n.tc('最近活动时间'),
      cellType: 'text',
      width: 190,
      sortBy: 'lastActiveValue',
    },
    { id: 'ioSummary', label: window.i18n.tc('输入 / 输出摘要'), cellType: 'ioSummary', minWidth: 120 },
    { id: 'elapsedText', label: window.i18n.tc('耗时'), cellType: 'duration', width: 100, sortBy: 'elapsedValue' },
    { id: 'tokens', label: 'Tokens', cellType: 'tokens', width: TOKENS_WIDTH, sortBy: 'tokensTotalValue' },
    { id: 'status', label: window.i18n.tc('状态'), cellType: 'status', width: STATUS_WIDTH },
  ];
}

/** Trace 视角主表列，Tokens 额外展示输入 / 输出徽标 */
export function getTraceColumns(): ILlmColumn[] {
  return [
    { id: 'traceId', label: 'Trace ID', cellType: 'link', width: ID_WIDTH },
    { id: 'sessionId', label: window.i18n.tc('会话 ID'), cellType: 'text', width: SESSION_ID_WIDTH },
    { id: 'userId', label: window.i18n.tc('用户 ID'), cellType: 'text', width: USER_ID_WIDTH },
    { id: 'lastActiveText', label: window.i18n.tc('最近活动时间'), cellType: 'text', width: 190 },
    { id: 'ioSummary', label: window.i18n.tc('输入 / 输出摘要'), cellType: 'ioSummary', minWidth: 120 },
    { id: 'elapsedText', label: window.i18n.tc('耗时'), cellType: 'duration', width: 100, sortField: 'elapsed_time' },
    { id: 'tokens', label: 'Tokens', cellType: 'tokensBadge', width: TOKENS_WIDTH },
    { id: 'status', label: window.i18n.tc('状态'), cellType: 'status', width: STATUS_WIDTH },
  ];
}
