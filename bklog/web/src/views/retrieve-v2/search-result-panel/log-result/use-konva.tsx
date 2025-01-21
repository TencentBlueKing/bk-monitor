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
  let tempText: Konva.Text;
  let boxWidth = 0;
  let boxHeight = 0;

  let wordList: WordListItem[];
  let hoverItem;
  let textContainer: HTMLDivElement;

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

  const updateContainerBounds = () => {
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

  const isSelectionCurrentNode = () => {
    const selection = window.getSelection();
    if (!selection?.isCollapsed) {
      const node = selection.focusNode.parentElement;
      return node === konvaInstance.frontStage.container().parentElement.querySelector('.static-text');
    }

    return false;
  };

  const handleTextBoxMousemove = evt => {
    // 如果有文本被选中此时跳过后续高亮逻辑

    if (isSelectionCurrentNode()) {
      konvaInstance.frontActionLayer.destroyChildren();
      return;
    }

    const pointer = getPointerByMouseEvent(evt);
    const validateWordRect = item => {
      const { left, top, width } = item;
      const bottom = top + 20;
      const right = left + width;
      const { x, y } = pointer;
      return left <= x && top <= y && bottom >= y && right >= x;
    };
    const word = wordList.find(item => {
      if (item.split?.length) {
        return item.split.some(child => validateWordRect(child));
      }

      return validateWordRect(item);
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
    textContainer = frontContainer.parentElement.querySelector('.static-text');

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

    updateContainerBounds();
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

    updateContainerBounds();
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

    return [
      { text: leftText.join(''), width: width > bufferWidth ? width - bufferWidth : 0 },
      { text: chars.join('') },
    ];
  };

  const resetWordWrapPositon = (
    textNode,
    itemList: WordListItem[],
    currentIndex: number,
    originLeft: number,
    updateLeft = true,
  ) => {
    const item = itemList[currentIndex];

    const getDiffWidth = (diffL, diffT, target: WordListItem) => {
      if (target.top < diffT) {
        return diffL + containerBounds.width - target.left;
      }

      return diffL - target.left;
    };

    if (item.split) {
      const [leftText, rightText] = item.split;
      const offsetXIndex = leftText?.text?.length ?? 0;
      const range = document.createRange();
      range.setStart(textNode, item.startIndex + offsetXIndex);
      range.setEnd(textNode, item.endIndex);

      const { x, y } = range.getBoundingClientRect();
      const top = Math.floor((y - containerBounds.y) / (lineHeight * fontSize)) * lineHeight * fontSize;
      const offsetLeft = x - containerBounds.x;

      if (offsetLeft > rightText.left || top > rightText.top) {
        const diffWidth = getDiffWidth(offsetLeft, top, rightText);
        rightText.left = offsetLeft;
        rightText.top = top;

        while (leftText.text.length > 0 && rightText.left > 0) {
          rightText.text = leftText.text.slice(-1) + rightText.text;
          leftText.text = leftText.text.slice(0, -1);

          const text = getTempText();
          text.text(rightText.text);
          const width = text.width();
          const diff = width - rightText.width;
          leftText.width = leftText.width - diff;
          rightText.left = rightText.left - diff;
          rightText.width = width;
        }

        if (updateLeft) {
          originLeft = originLeft + diffWidth;
        }

        if (leftText.text.length === 0) {
          item.left = rightText.left;
          item.top = rightText.top;
          item.line = rightText.line;
          item.split = undefined;
        }

        if (item.left > 0) {
          return resetWordWrapPositon(textNode, itemList, currentIndex - 1, originLeft, false);
        }
      }

      return originLeft;
    }

    const range = document.createRange();
    const offsetXIndex = item.text.length - 1;
    range.setStart(textNode, item.startIndex + offsetXIndex);
    range.setEnd(textNode, item.endIndex);

    const { x, y } = range.getBoundingClientRect();
    const top = Math.floor((y - containerBounds.y) / (lineHeight * fontSize));
    const offsetLeft = x - containerBounds.x;

    if (offsetLeft > item.left || top > item.top) {
      const diffWidth = getDiffWidth(offsetLeft, top, item);
      if (updateLeft) {
        originLeft = originLeft + diffWidth;
      }

      if (item.text.length > 1) {
        const rightText = item.text.slice(-1);
        const text = getTempText();
        text.text(rightText);
        const width = text.width();
        item.split = [
          {
            ...item,
            text: item.text.slice(0, -1),
            width: item.width - width,
            top: item.top,
          },
          {
            ...item,
            text: rightText,
            width,
            left: offsetLeft,
            top,
          },
        ];

        return resetWordWrapPositon(textNode, itemList, currentIndex, originLeft, false);
      }

      item.left = offsetLeft;
      item.top = top;
      return resetWordWrapPositon(textNode, itemList, currentIndex - 1, originLeft, true);
    }

    return originLeft;
  };

  const getRequestAnimationFrame = () => {
    if (window.requestIdleCallback) {
      return window.requestIdleCallback;
    }

    return window.requestAnimationFrame;
  };

  const computeWordListPosition = (list: WordListItem[]) => {
    wordList = list;
    return new Promise<WordListItem[]>(resolve => {
      getRequestAnimationFrame()(() => {
        let left = 0;
        // 换行产生的偏移量
        let offsetWidth = 0;
        wordList.forEach((item, index) => {
          const box = getTempText();
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
            const diffWidth = left % boxWidth;
            const [leftText, rightText] = getWrapText(item.text, width - diffWidth);
            rightText.width = item.width - leftText.width;
            left = boxWidth * nextLine + width - leftText.width;

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
            ].filter(item => item.width > 0);

            if (item.split.length === 1) {
              item.left = item.split[0].left;
              item.top = item.split[0].top;
              item.width = item.split[0].width;
              item.line = item.split[0].line;
              item.split = undefined;
            }

            left = resetWordWrapPositon(textContainer.firstChild, wordList, index, left, true);
          }
        });

        resolve(wordList);
      });
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

  const handleTextBoxMouseenter = () => {
    updateContainerBounds();
  };

  const getLines = () => {
    const lines = boxHeight / 20;
    return lines;
  };

  const events = {
    mouseenter: handleTextBoxMouseenter,
    mousemove: handleTextBoxMousemove,
    mouseleave: handleTextBoxMouseleave,
    click: handleTextBoxClick,
  };

  const fireEvent = (type: string, e: MouseEvent) => {
    requestAnimationFrame(() => {
      events[type]?.(e);
    });
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
