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

import { ref, Ref } from 'vue';

interface AdaptivePaginationOptions {
  /** 需要减去的固定高度（页面中除表格内容以外的其他元素高度总和） */
  fixedHeight: number;
  /** 每行的固定高度，默认 43 */
  rowHeight?: number;
  /** 可选的分页大小列表，默认 [10, 20, 50, 100] */
  limitList?: number[];
}

interface AdaptivePaginationReturn {
  /** 计算出的分页大小 */
  limit: Ref<number>;
}

/**
 * 计算合适的分页大小
 */
function calcLimit(fixedHeight: number, rowHeight: number, limitList: number[]): number {
  // 获取浏览器高度
  const clientHeight = document.documentElement?.offsetHeight || 0;

  // 计算可以显示的行数
  const rows = Math.ceil((clientHeight - fixedHeight) / rowHeight);

  // 确保 limitList 有序（从小到大）
  const sortedLimitList = [...limitList].sort((a, b) => a - b);

  // 边界保护：确保 rows 至少为 1
  if (rows <= 0) {
    return sortedLimitList[0] || 10;
  }

  // 选择第一个大于等于 rows 的分页大小，如果都小于 rows 则选择最大值
  let targetLimit = sortedLimitList[sortedLimitList.length - 1] || 10;

  for (const item of sortedLimitList) {
    if (item >= rows) {
      targetLimit = item;
      break;
    }
  }

  return targetLimit;
}

/**
 * 自适应分页 hooks
 * 根据浏览器窗口高度自动计算合适的分页大小
 */
export default function useAdaptivePagination(options: AdaptivePaginationOptions): AdaptivePaginationReturn {
  const { fixedHeight, rowHeight = 43, limitList = [10, 20, 50, 100] } = options;

  // 分页大小 - 立即计算初始值
  const limit = ref(calcLimit(fixedHeight, rowHeight, limitList));

  return {
    limit,
  };
}
