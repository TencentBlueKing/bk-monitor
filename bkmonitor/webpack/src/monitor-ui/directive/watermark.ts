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
import type { VueConstructor } from 'vue';

interface WatermarkOptions {
  font: string; // canvas font
  text: string; // 文本
  textColor: string; // 文本颜色
}

export default class WatermarkDirective {
  public static install(Vue: VueConstructor): void {
    Vue.directive('watermark', {
      bind(el: HTMLElement, binding: { value: Partial<WatermarkOptions> }): void {
        if (!binding.value) return;
        // 默认值
        const defaults: WatermarkOptions = {
          text: '',
          font: '14px Arial',
          textColor: '#f1f1f1',
        };
        const options: WatermarkOptions = { ...defaults, ...binding.value };
        const canvas: HTMLCanvasElement = document.createElement('canvas');
        const ctx: CanvasRenderingContext2D | null = canvas.getContext('2d');
        canvas.style.display = 'none';
        ctx.globalAlpha = 0.5;
        if (ctx) {
          const textWidth: number = ctx.measureText(options.text).width;
          const offsetX: number = Math.ceil(textWidth * 3);
          canvas.width = offsetX;
          canvas.height = offsetX;

          ctx.rotate(-Math.PI / 6);
          ctx.font = options.font;
          ctx.fillStyle = options.textColor;
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';

          ctx.fillText(options.text, 0, 120 / 2 + 5);
        }
        el.style.backgroundImage = `url(${canvas.toDataURL('image/png')})`;
      },
    });
  }
}
