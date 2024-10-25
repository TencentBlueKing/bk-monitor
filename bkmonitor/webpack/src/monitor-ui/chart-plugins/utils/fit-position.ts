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
export interface ITipsPosition {
  left: number;
  top: number;
}
export function fitPosition(portions: ITipsPosition, width = 400, height = 200) {
  const { left, top } = portions;
  const { innerWidth, innerHeight } = window;

  // 计算新的位置
  let newLeft = left;
  let newTop = top;

  // 检查是否超出右边界
  if (newLeft + width > innerWidth) {
    newLeft = innerWidth - width;
  }

  // 检查是否超出下边界
  if (newTop + height > innerHeight) {
    newTop = innerHeight - height;
  }

  // 检查是否超出左边界
  if (newLeft < 0) {
    newLeft = 0;
  }

  // 检查是否超出上边界
  if (newTop < 0) {
    newTop = 0;
  }

  return { left: newLeft, top: newTop };
}
