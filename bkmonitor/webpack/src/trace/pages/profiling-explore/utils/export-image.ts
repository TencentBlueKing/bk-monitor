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
/** 导出倍率上限：位图按此倍率重新绘制，避免放大或打印时模糊。 */
const MAX_EXPORT_SCALE = 3;
/** 浏览器画布面积与单边上限（取移动端保守值），超出后位图为空白。 */
const MAX_CANVAS_AREA = 16_777_216;
const MAX_CANVAS_SIDE = 8192;

/** 按内容尺寸解析导出倍率，在提升清晰度的同时避开浏览器画布限制。 */
export function resolveExportScale(width: number, height: number): number {
  const areaScale = Math.sqrt(MAX_CANVAS_AREA / (width * height));
  const sideScale = MAX_CANVAS_SIDE / Math.max(width, height);
  return Math.min(MAX_EXPORT_SCALE, areaScale, sideScale);
}
