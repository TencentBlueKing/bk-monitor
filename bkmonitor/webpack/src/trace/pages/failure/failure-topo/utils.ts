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

import type { IEntity, ITopoNode } from './types';

/** 根因节点样式 */
const rootNodeAttrs = {
  groupAttrs: {
    fill: 'rgba(197, 197, 197, 0.2)',
    stroke: '#979BA5',
  },
  rectAttrs: {
    stroke: '#3A3B3D',
    fill: '#F55555',
  },
  textAttrs: {
    fill: '#fff',
  },
  textNameAttrs: {
    fill: '#979BA5',
  },
};
/** 反馈根因节点 */
const feedbackRootAttrs = {
  groupAttrs: {
    fill: 'rgba(197, 197, 197, 0.2)',
    stroke: '#979BA5',
  },
  rectAttrs: {
    stroke: '#3A3B3D',
    fill: '#FF9C01',
  },
  textAttrs: {
    fill: '#fff',
  },
  textNameAttrs: {
    fill: '#979BA5',
  },
};
/** 告警未恢复 */
// const notRestoredAttrs = {
//   groupAttrs: {
//     fill: '#F55555',
//     stroke: '#F55555',
//   },
//   rectAttrs: {
//     stroke: '#3A3B3D',
//     fill: '#F55555',
//   },
//   textAttrs: {
//     fill: '#fff',
//   },
//   textNameAttrs: {
//     fill: '#F55555',
//   },
// };
/** 异常节点 */
const errorNodeAttrs = {
  groupAttrs: {
    fill: 'rgba(255, 102, 102, 0.4)',
    stroke: '#F55555',
  },
  rectAttrs: {
    stroke: '#F55555',
    fill: '#313238',
  },
  textAttrs: {
    fill: '#EAEBF0',
  },
  textNameAttrs: {
    fill: '#FF7575',
  },
};

/** 默认节点 */
const normalNodeAttrs = {
  groupAttrs: {
    fill: 'rgba(197, 197, 197, 0.2)',
    stroke: '#979BA5',
  },
  rectAttrs: {
    stroke: '#979BA5',
    fill: '#313238',
  },
  textAttrs: {
    fill: '#EAEBF0',
  },
  textNameAttrs: {
    fill: '#DCDEE5',
  },
};
/** 根据优先级返回 */
export const getNodeAttrs = (node: ITopoNode): typeof normalNodeAttrs => {
  // if (node.entity?.is_on_alert) {
  //   return { ...notRestoredAttrs };
  // }
  if (node.entity?.is_anomaly) {
    return { ...errorNodeAttrs };
  }
  if (node?.is_feedback_root) {
    return { ...feedbackRootAttrs };
  }
  if (node.entity?.is_root) {
    return { ...rootNodeAttrs };
  }
  return { ...normalNodeAttrs };
};

/**
 * 手动裁剪文本内容
 * @param {string} text - 原始文本
 * @param {number} maxWidth - 最大宽度
 * @param {number} fontSize - 字体大小
 * @param {string} fontFamily - 字体
 * @returns {string} - 裁剪后的文本
 */
export const truncateText = (text, maxWidth, fontSize, fontFamily) => {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  context.font = `${fontSize}px ${fontFamily}`;

  let width = context.measureText(text).width;
  if (width <= maxWidth) return text;

  let truncated = text;
  while (width > maxWidth) {
    truncated = truncated.slice(0, -1);
    width = context.measureText(truncated).width;
  }

  return truncated;
};

/** 获取apm类型节点 */
export const getApmServiceType = (entity: IEntity) => {
  if (entity.entity_type === 'APMService') {
    return entity.dimensions?.apm_service_category ?? 'Service';
  }
  return entity.entity_type || 'Service';
};

/**
 * 手动裁剪文本内容，支持换行，最多3行
 * @param {string} text - 原始文本
 * @param {number} maxWidth - 最大宽度
 * @returns {string} - 换行、裁剪后的文本
 * @returns {number} - 占用行数
 */
export const truncateTextWithWrap = (text: string, maxWidth: [string, number]) => {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  let result = '';
  let currentLine = '';
  let currentWidth = 0;
  let lineCount = 1; // 至少有一行
  const MAX_LINES = 3; // 最多三行

  for (const char of text) {
    const charWidth = context.measureText(char).width;

    // 情况1：当前行还能容纳字符
    if (currentWidth + charWidth <= maxWidth) {
      currentLine += char;
      currentWidth += charWidth;
      continue;
    }

    // 情况2：未达最大行数，换行
    if (lineCount < MAX_LINES) {
      result += `${currentLine}\n`;
      currentLine = char;
      currentWidth = charWidth;
      lineCount++;
      continue;
    }

    // 情况3：已达最大行数，处理截断
    const ellipsis = '...';
    const ellipsisWidth = context.measureText(ellipsis).width;
    let lastLine = currentLine;

    // 尝试追加当前字符（可能失败）
    if (currentWidth + charWidth + ellipsisWidth <= maxWidth) {
      lastLine += char;
      currentWidth += charWidth;
    }

    // 移除字符直到能放下省略号
    while (context.measureText(lastLine + ellipsis).width > maxWidth && lastLine.length > 0) {
      lastLine = lastLine.slice(0, -1);
    }

    return [result + lastLine + ellipsis, lineCount];
  }

  // 循环结束未触发截断的情况
  return [result + currentLine, lineCount];
};

export const getOffset = (root, lines) => {
  switch (lines) {
    case 1:
      return root ? 48 : 40;
    case 2:
      return root ? 56 : 48;
    case 3:
      return root ? 62 : 54;
  }
};
