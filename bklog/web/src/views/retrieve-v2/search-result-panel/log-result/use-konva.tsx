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
import Konva from 'konva';

import { WordListItem } from '../../../../hooks/use-text-segmentation';
export default ({ onSegmentClick }) => {
  const konvaInstance: {
    backgroundStage: Konva.Stage | null;
    backgroundLayer: Konva.Layer | null;
    frontStage: Konva.Stage | null;
    frontActionLayer: Konva.Layer | null;
  } = {
    backgroundStage: null,
    backgroundLayer: null,
    frontStage: null,
    frontActionLayer: null,
  };

  let fontFamily;
  const fontSize = 12;
  const lineHeight = 20 / 12;
  let tempText;
  let boxWidth = 0;
  let boxHeight = 0;

  let wordList: WordListItem[];
  let hoverItem;

  const containerBounds = { x: 0, y: 0, width: 0, height: 0 };

  const getTempText = () => {
    if (!tempText) {
      tempText = new Konva.Text({
        x: 0,
        y: 0,
        fontSize,
        fontFamily,
        lineHeight,
        fill: '#000000',
      });
    }
    return tempText;
  };

  const appendColorText = (word: WordListItem) => {
    const fillColor = word.isMark ? 'rgb(255, 255, 0)' : 'rgb(255, 255, 255)';
    const rect = new Konva.Rect({
      x: word.left,
      y: word.top + (fontSize * lineHeight - fontSize) / 2,
      width: word.width,
      height: fontSize,
      fill: fillColor,
    });

    const text = new Konva.Text({
      fontSize,
      lineHeight,
      fontFamily,
      x: word.left,
      y: word.top + 1,
      text: word.text,
      fill: '#3a84ff',
    });

    konvaInstance.frontActionLayer.add(rect);
    konvaInstance.frontActionLayer.add(text);
  };

  let isMouseDown = false;

  const updateContainerBounds = (parentNode: HTMLElement) => {
    const textContainer = parentNode.querySelector('.static-text');
    const { x, y, width, height } = textContainer.getBoundingClientRect();
    Object.assign(containerBounds, { x, y, width, height });
  };

  const handleTextBoxClick = evt => {
    const pointer = getPointerByMouseEvent(evt);
    const word = wordList.find(item => {
      const { left, top, width } = item;
      const bottom = top + 20;
      const right = left + width;
      const { x, y } = pointer;
      return left <= x && top <= y && bottom >= y && right >= x;
    });

    if (word?.isCursorText && word?.text) {
      onSegmentClick?.(evt, word?.text);
    }
  };

  const getPointerByMouseEvent = (e: MouseEvent) => {
    const { x, y } = e;
    return { x: x - containerBounds.x, y: y - containerBounds.y };
  };

  const handleTextBoxMousemove = evt => {
    if (isMouseDown) {
      return;
    }

    const pointer = getPointerByMouseEvent(evt);
    const word = wordList.find(item => {
      const { left, top, width } = item;
      const bottom = top + 20;
      const right = left + width;
      const { x, y } = pointer;
      return left <= x && top <= y && bottom >= y && right >= x;
    });

    if (word?.isCursorText && hoverItem !== word) {
      hoverItem = word;
      konvaInstance.frontActionLayer.destroyChildren();
      if (word.split?.length) {
        word.split.forEach(item => {
          appendColorText(item);
        });

        return;
      }

      appendColorText(word);
    }
  };

  const handleTextBoxMouseleave = () => {
    konvaInstance.frontActionLayer.destroyChildren();
  };

  const initKonvaInstance = (
    backgroundContainer: HTMLDivElement,
    frontContainer: HTMLDivElement,
    width: number,
    height: number,
    family: string,
  ) => {
    fontFamily = family;
    boxWidth = width;
    konvaInstance.backgroundStage = new Konva.Stage({
      container: backgroundContainer,
      width,
      height,
    });

    konvaInstance.frontStage = new Konva.Stage({
      container: frontContainer,
      width,
      height,
    });

    konvaInstance.backgroundLayer = new Konva.Layer({ id: 'backgroundLayer' });
    konvaInstance.backgroundStage.add(konvaInstance.backgroundLayer);

    konvaInstance.frontActionLayer = new Konva.Layer({ id: 'frontActionLayer' });
    konvaInstance.frontStage.add(konvaInstance.frontActionLayer);

    updateContainerBounds(frontContainer.parentElement);
  };

  const setRect = (width?: number, height?: number) => {
    if (width) {
      konvaInstance.backgroundStage.width(width);
      konvaInstance.frontStage.width(width);
    }

    if (height) {
      konvaInstance.backgroundStage.height(height);
      konvaInstance.frontStage.height(height);
    }

    updateContainerBounds(konvaInstance.backgroundStage.container().parentElement);
  };

  const getWrapText = (text: string, leftWidth: number) => {
    const box = getTempText();
    const chars = text.split('');
    const leftText = [];
    let width = 0;
    let bufferWidth = 0;
    while (width < leftWidth) {
      const char = chars.shift();
      box.text(char);
      bufferWidth = box.width();
      width += bufferWidth;
      if (width < leftWidth) {
        bufferWidth = 0;
        leftText.push(char);
      } else {
        chars.unshift(char);
      }
    }

    return [{ text: leftText.join(''), width: width - bufferWidth }, { text: chars.join('') }];
  };

  const computeWordListPosition = (list: WordListItem[]) => {
    wordList = list;
    return new Promise<WordListItem[]>(resolve => {
      let left = 0;
      // 换行产生的偏移量
      let offsetWidth = 0;
      let preWidth = 0;
      wordList.forEach(item => {
        const box = getTempText();
        preWidth = left;
        box.text(item.text);
        const width = box.width();
        const line = Math.floor(left / boxWidth);

        Object.assign(item, {
          left: (left % boxWidth) + offsetWidth,
          top: line * fontSize * lineHeight,
          width,
          line,
        });

        left = left + width;
        const nextLine = Math.floor(left / boxWidth);

        // 分词在换行被截断
        if (nextLine > line) {
          const diffWidth = left - boxWidth;
          const [leftText, rightText] = getWrapText(item.text, width - diffWidth);
          offsetWidth = boxWidth - (preWidth % boxWidth) - leftText.width;

          item.split = [
            {
              text: leftText.text,
              isMark: item.isMark,
              isCursorText: item.isCursorText,
              left: item.left,
              top: item.top,
              width: leftText.width,
              line,
            },
            {
              text: rightText.text,
              isMark: item.isMark,
              isCursorText: item.isCursorText,
              left: 0,
              top: item.top + fontSize * lineHeight,
              width: width - leftText.width,
              line: nextLine,
            },
          ];
        }
      });

      resolve(wordList);
    });
  };

  const setHighlightWords = (words: WordListItem[]) => {
    words
      .filter(item => item.isMark)
      .forEach(item => {
        // computeWordPosition(item);
        // 创建一个背景矩形
        const rect = new Konva.Rect({
          x: item.left,
          y: item.top + (fontSize * lineHeight - fontSize) / 2,
          width: item.width,
          height: fontSize,
          fill: 'rgb(255, 255, 0)',
        });

        konvaInstance.backgroundLayer.add(rect);
      });
  };

  const handleTextBoxMouseup = () => {
    isMouseDown = false;
    document.removeEventListener('mouseup', handleTextBoxMouseup);
  };

  const handleTextBoxMousedown = () => {
    isMouseDown = true;
    document.addEventListener('mouseup', handleTextBoxMouseup);
  };

  const getLines = () => {
    const lines = boxHeight / 20;
    return lines;
  };

  const fireEvent = (type: string, e: MouseEvent) => {
    const events = {
      mousemove: handleTextBoxMousemove,
      mouseleave: handleTextBoxMouseleave,
      mousedown: handleTextBoxMousedown,
      click: handleTextBoxClick,
    };

    events[type]?.(e);
  };

  return {
    setRect,
    getLines,
    fireEvent,
    setHighlightWords,
    initKonvaInstance,
    computeWordListPosition,
  };
};
