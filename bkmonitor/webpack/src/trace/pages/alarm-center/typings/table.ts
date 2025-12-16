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

import { type AlertAllActionEnum } from './constants';

import type { TableCol } from '@blueking/tdesign-ui';
import type { SlotReturnValue } from 'tdesign-vue-next';

/** 告警场景表格 行操作栏 可操作按钮项枚举类型 */
export type AlertRowOperationAction = Exclude<AlertAllActionEnum, AlertAllActionEnum.CANCEL>;

/** 告警场景表格 批量操作栏 可操作按钮项枚举类型 */
export type AlertSelectBatchAction = Exclude<AlertAllActionEnum, AlertAllActionEnum.MANUAL_HANDLING>;

// 表格列字段
export type TableColumnItem<T = any> = {
  /** 是否为默认列 */
  is_default?: boolean;
  /** 是否必须显示且不可编辑隐藏 */
  is_locked?: boolean;
} & TableCol<T>;

/** commonTable Empty 属性类型 */
export type TableEmpty = TableEmptyProps | TableRenderer;

export interface TableEmptyProps {
  emptyText: string;
  type: 'empty' | 'search-empty';
}

/** 表格分页属性类型 */
export interface TablePagination {
  /** 当前页码 */
  currentPage: number;
  /** 每页条数 */
  pageSize: number;
  /** 总数 */
  total: number;
}
/** 表格通用渲染函数类型 */
export type TableRenderer<T = undefined> = T extends undefined ? () => SlotReturnValue : (props?: T) => SlotReturnValue;
