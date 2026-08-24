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

/** list_records 分页响应 */
export interface IRumRecordListResponse {
  list: IRumSpanRecord[];
}

/** 表格排序状态，与 tdesign SortInfo 对齐 */
export interface IRumSortInfo {
  descending: boolean | null;
  sortBy: string;
}
/**
 * list_records 返回的单条记录。
 *
 * 表格列由 view_config 的 display_fields 动态决定，且字段名带 `.`（如 `status.code`），
 * 所以这里只显式声明各 span 类型都会返回的固定字段，其余走索引签名。
 */
export interface IRumSpanRecord {
  [key: string]: unknown;
  'attributes.span_type'?: string;
  /** 耗时，单位由字段的 field_unit 决定（通常为 us） */
  elapsed_time?: number;
  /** 微秒级时间戳 */
  end_time?: number;
  span_id?: string;
  span_name?: string;
  /** 微秒级时间戳 */
  start_time?: number;
  'status.code'?: number;
  trace_id?: string;
}
