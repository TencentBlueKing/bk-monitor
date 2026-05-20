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

/* eslint-disable no-unused-vars */
export interface IGrokItem {
  id: number;
  name: string;
  pattern: string;
  is_builtin: boolean;
  description: string | null;
  sample: string | null;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
  bk_biz_id: number;
}

// 调试状态枚举
export enum DebugStatus {
  NONE = 'none', // 未调试
  SUCCESS = 'success', // 调试成功
  CHANGED = 'changed', // 内容已变更，需重新调试
  FAILED = 'failed', // 调试失败
}

// GrokPopoverList 组件暴露的方法类型
export interface GrokPopoverListExpose {
  handleKeydown: (e: KeyboardEvent) => void;
  reset: () => void;
  fetchGrokList: (append?: boolean) => Promise<void>;
}
