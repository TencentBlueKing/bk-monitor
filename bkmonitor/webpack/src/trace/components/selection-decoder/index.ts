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

import { createDecodeContent, createMenuContent } from './utils/dom';
import { autoDecodeString, detectEncodingType } from './utils/formatter-utils';
import { isPointerDragSelect, isSelectionDecoderTrigger } from './utils/geometry';
import { copyToClipboard } from './utils/message';
import { hideSelectionDecoder, prepareDecoderPopover, showPopover } from './utils/popover';
import { type SelectionDecoderPlacement, type SelectionDecoderTarget, DEFAULT_PLACEMENT } from './utils/typing';

import './index.scss';

/**
 * 自动解码并用 tippy 弹出解码结果
 */
const showDecodeResult = (text: string) => {
  const decoded = autoDecodeString(text);
  showPopover(createDecodeContent(decoded, copyToClipboard, hideSelectionDecoder), {
    theme: 'light selection-decoder-popover selection-decoder-dialog',
  });
};

export type { SelectionDecoderPlacement, SelectionDecoderTarget };

export { hideSelectionDecoder, isPointerDragSelect, isSelectionDecoderTrigger };

/**
 * 展示选中文本的复制 / 自动解码 tippy 操作弹窗
 * @param text 外部传入的待处理字符串
 * @param target tippy 锚点，支持元素或鼠标事件；缺省时使用当前文本选区
 * @param placement 相对划选区域的弹出位置，默认正下方
 */
export const showSelectionDecoder = (
  text: string,
  target?: SelectionDecoderTarget,
  placement: SelectionDecoderPlacement = DEFAULT_PLACEMENT
) => {
  if (!prepareDecoderPopover(text, target, placement)) {
    return;
  }

  showPopover(
    createMenuContent(text, copyToClipboard, showDecodeResult, {
      canDecode: !!detectEncodingType(text),
    })
  );
};

/**
 * 跳过复制 / 自动解码菜单，直接弹出解码结果弹窗
 * @param text 待解码字符串，仅传该参数时在视口中央弹出
 * @param target tippy 锚点，支持元素或鼠标事件；缺省时居中展示
 * @param placement 相对锚点的弹出位置，默认正下方
 */
export const showSelectionDecodeResult = (
  text: string,
  target?: SelectionDecoderTarget,
  placement: SelectionDecoderPlacement = DEFAULT_PLACEMENT
) => {
  if (
    !prepareDecoderPopover(text, target, placement, {
      fallbackCenter: true,
    })
  ) {
    return;
  }

  showDecodeResult(text);
};
