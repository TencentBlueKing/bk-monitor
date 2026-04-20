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

import type { MergeResult } from '../types';

/**
 * @description 尝试合并两个有序数组，判断它们是否只存在首尾差异（中间重叠部分完全一致）
 * @param arr1 - 第一个有序数组（元素必须唯一且严格递增）
 * @param arr2 - 第二个有序数组（元素必须唯一且严格递增）
 * @returns 合并结果对象，包含合并后的数组及各自的首尾补齐数量；不可合并时返回 null
 */
export const mergeOverlappingArrays = (arr1: number[], arr2: number[]): MergeResult | null => {
  if (!arr1.length || !arr2.length) return null;
  // 两个数组必须存在交集才能合并，完全不重叠的数据不应合并到同一 xAxis
  const set1 = new Set(arr1);
  if (!arr2.some(v => set1.has(v))) return null;
  const merged = Array.from(new Set([...arr1, ...arr2])).sort((a, b) => a - b);
  const findOffset = (merged: number[], arr: number[]): number => {
    const idx = merged.indexOf(arr[0]);
    if (idx === -1) return -1;
    if (idx + arr.length > merged.length) return -1;
    for (let i = 0; i < arr.length; i++) {
      if (merged[idx + i] !== arr[i]) return -1;
    }
    return idx;
  };
  const offset1 = findOffset(merged, arr1);
  const offset2 = findOffset(merged, arr2);
  if (offset1 === -1 || offset2 === -1) return null;
  return {
    head1: offset1,
    head2: offset2,
    merged,
    tail1: merged.length - offset1 - arr1.length,
    tail2: merged.length - offset2 - arr2.length,
  };
};
