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
// bk-magic-vue 中未显式传 z-index 的 bk-dialog 每次显示按 2 递增（nextTickIndex(2)），此处对齐同一步长
const Z_INDEX_STEP = 2;

/**
 * 取一个严格高于当前所有已打开弹层的层级。
 * 适用于由全局逻辑兜底弹出、无法预知当前还有哪些弹层打开的弹窗（如 403 权限申请弹窗）。
 * @param minIndex 层级下限，用于兼容历史上被硬编码的固定层级，避免改动后层级反而变低
 */
export const getTopLayerZIndex = (minIndex = 0): number => {
  const nextZIndex = window.__bk_zIndex_manager?.nextZIndex?.() ?? 0;
  return Math.max(nextZIndex, minIndex) + Z_INDEX_STEP;
};
