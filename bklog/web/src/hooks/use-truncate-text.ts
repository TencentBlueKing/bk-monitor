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
import { computed, ComputedRef } from 'vue';

type TextOption = {
  text: string;
  maxWidth: number;
  fontSize: number;
  font: string;
  showAll: boolean;
};
export default (options: ComputedRef<TextOption>) => {
  const getTextWidth = (text, font) => {
    // 创建一个离屏 canvas 元素
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    context.font = font;
    const metrics = context.measureText(text);
    return metrics.width;
  };

  const truncateTextWithCanvas = () => {
    const { text, maxWidth, font } = options.value;
    if (maxWidth <= 0) {
      return '';
    }

    if (typeof text !== 'string') {
      return text;
    }

    const ellipsText = '...more';
    const ellipsisWidth = getTextWidth(ellipsText, font);
    const avaliableWidth = maxWidth - ellipsisWidth - 18;

    let truncatedText = '';
    let currentWidth = 0;

    for (let char of text) {
      const charWidth = getTextWidth(char, font);

      if (currentWidth + charWidth > avaliableWidth) {
        break;
      }

      truncatedText += char;
      currentWidth += charWidth;
    }

    return truncatedText;
  };

  const truncatedText = computed(() => truncateTextWithCanvas());
  const showMore = computed(() => truncatedText.value.length < options.value.text.length && options.value.maxWidth > 0);

  return { truncatedText, showMore };
};
