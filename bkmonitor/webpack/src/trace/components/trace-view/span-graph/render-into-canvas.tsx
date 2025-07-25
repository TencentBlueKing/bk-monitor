/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import type { TNil } from '../typings';

// exported for tests
export const BG_COLOR = '#fff';
export const ITEM_ALPHA = 0.8;
export const MIN_ITEM_HEIGHT = 2;
export const MAX_TOTAL_HEIGHT = 200;
export const MIN_ITEM_WIDTH = 10;
export const MIN_TOTAL_HEIGHT = 60;
export const MAX_ITEM_HEIGHT = 6;

export default function renderIntoCanvas(
  canvas: HTMLCanvasElement,
  items: { color: string; isVirtual: boolean; serviceName: string; valueOffset: number; valueWidth: number }[],
  totalValueWidth: number,

  getFillColor: (serviceName: string) => [number, number, number]
) {
  const fillCache: Map<string, string | TNil> = new Map();
  const cHeight = items.length < MIN_TOTAL_HEIGHT ? MIN_TOTAL_HEIGHT : Math.min(items.length, MAX_TOTAL_HEIGHT);
  const cWidth = window.innerWidth * 2;

  canvas.width = cWidth;

  canvas.height = cHeight;
  const itemHeight = Math.min(MAX_ITEM_HEIGHT, Math.max(MIN_ITEM_HEIGHT, cHeight / items.length));
  const itemYChange = cHeight / items.length;

  const ctx = canvas.getContext('2d', { alpha: false }) as CanvasRenderingContext2D;
  ctx.fillStyle = BG_COLOR;
  ctx.fillRect(0, 0, cWidth, cHeight);
  for (let i = 0; i < items.length; i++) {
    const { valueWidth, valueOffset, serviceName } = items[i];
    const x = (valueOffset / totalValueWidth) * cWidth;
    let width = (valueWidth / totalValueWidth) * cWidth;
    if (width < MIN_ITEM_WIDTH) {
      width = MIN_ITEM_WIDTH;
    }
    let fillStyle = fillCache.get(serviceName);
    if (!fillStyle) {
      const { color } = items[i];
      // fillStyle = `rgba(${getFillColor(serviceName)
      //   .concat(ITEM_ALPHA)
      //   .join()})`;
      /** 颜色由后端随机生成分配 */
      fillStyle = `${color}`;
      fillCache.set(serviceName, fillStyle);
    }

    if (items[i].isVirtual) {
      // 推断 span 纹理区分
      // const img = new Image(); // 创建Image对象
      // img.src = '';
      // img.onload = function () {
      //   const pattern = ctx.createPattern(img, 'repeat');
      //   ctx.fillStyle = pattern;
      //   ctx.fillRect(x, i * itemYChange, width, itemHeight);
      // };
      ctx.fillStyle = '#dddfe3';
      ctx.fillRect(x, i * itemYChange, width, itemHeight);
    } else {
      ctx.fillStyle = fillStyle;
      ctx.fillRect(x, i * itemYChange, width, itemHeight);
    }
  }
}
