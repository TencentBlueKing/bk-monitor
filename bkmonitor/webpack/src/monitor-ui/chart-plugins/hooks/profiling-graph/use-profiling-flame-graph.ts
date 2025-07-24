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

import { random, updateColorOpacity } from 'monitor-common/utils';

import { getSingleDiffColor } from '../../plugins/profiling-graph/flame-graph/utils';
import { parseProfileDataTypeValue, type ProfileDataUnit } from '../../plugins/profiling-graph/utils';
import { getSpanColorByName } from '../../typings/flame-graph';

import type { IFlameGraphDataItem, IProfilingGraphData } from './types';
const defaultHeight = 20;
const canvas = document.createElement('canvas');
const context = canvas.getContext('2d');
context.font = '12px sans-serif';
export function getMaxWidthText(text: string, width: number) {
  context.clearRect(0, 0, canvas.width, canvas.height);
  const charWidth = (text: string): number => context.measureText(text).width;
  let truncatedText = text;
  while (charWidth(truncatedText) > width && truncatedText.length > 0) {
    truncatedText = truncatedText.slice(0, -1);
  }
  return truncatedText;
}

export function recursionData(jsonData: IFlameGraphDataItem) {
  const rootValue = jsonData.value;
  function flattenTreeWithLevelBFS(data: IFlameGraphDataItem[]): any[] {
    const result: IProfilingGraphData[] = [];
    const queue: { node: IFlameGraphDataItem; level: number; start: number; end: number }[] = [];
    queue.push({ node: data[0], level: 0, start: 0, end: 0 });
    while (queue.length > 0) {
      const { node, level, start, end } = queue.shift();
      const { children, ...others } = node;
      const item = {
        ...others,
        level,
        start,
        end: level === 0 ? node.value : end,
        id: random(6),
      };
      result.push({
        ...item,
        // name: node.id,
        value: [
          level,
          start,
          level === 0 ? node.value : end,
          {
            ...item,
            proportion: `${((item.value / rootValue) * 100).toFixed(4).replace(/[0]+$/g, '').replace(/\.$/, '')}%`,
          },
        ],
      });
      if (node.children && node.children.length > 0) {
        let parentStart = start || 0; // 记录当前兄弟节点的 end 值
        for (const child of node.children) {
          queue.push({
            node: child,
            level: level + 1,
            start: parentStart,
            end: parentStart + child.value,
          });
          parentStart += child.value;
        }
      }
    }
    return result;
  }
  const list = flattenTreeWithLevelBFS(Array.isArray(jsonData) ? jsonData : [jsonData]);
  console.info(list);
  return list;
}

function renderItem(param, api, { data, unit, filterKeyword, textDirection = 'ltr', highlightNode }) {
  const level = api.value(0);
  const start = api.coord([api.value(1), level]);
  const end = api.coord([api.value(2), level]);
  const nodeItem: IFlameGraphDataItem = data[param.dataIndexInside]?.value?.[3];
  // const height: number = api.size([1, 1])[1];
  const width = Math.max(end[0] - start[0], 2);
  const isMinWidth = width < 4;
  // const y = defaultHeight <= height ? start[1] : defaultHeight * level + 2;
  const y = defaultHeight * level;
  const { value } = parseProfileDataTypeValue(nodeItem.value, unit);
  const color = nodeItem.diff_info ? getSingleDiffColor(nodeItem.diff_info) : getSpanColorByName(nodeItem.name);
  let rectColor = color;
  if (isMinWidth) {
    rectColor = '#ddd';
  } else if (filterKeyword) {
    rectColor = nodeItem.name.toLocaleLowerCase().includes(filterKeyword.toString().toLocaleLowerCase())
      ? color
      : '#aaa';
  } else if (+highlightNode?.level > level) {
    rectColor = '#aaa';
  }
  const name =
    textDirection === 'ltr'
      ? `${nodeItem.name} (${nodeItem.proportion}, ${value})`
      : `${nodeItem.name} (${nodeItem.proportion}, ${value})`.split('').reverse().join('');
  let text = '';
  if (!isMinWidth) {
    text = getMaxWidthText(name, width - 4);
    if (textDirection !== 'ltr') {
      text = text.split('').reverse().join('');
    }
  }
  return {
    type: 'rect',
    transition: [],
    animation: false,
    // z2: 10,
    shape: {
      x: start[0],
      y,
      width,
      height: defaultHeight,
      r: 0,
    },
    style: {
      fill: rectColor,
      stroke: '#fff',
      lineWidth: isMinWidth ? 0 : 0.5,
    },
    emphasisDisabled: true,
    emphasis: {
      style: {
        stroke: '#fff',
        fill: updateColorOpacity('#edeef3', 0.3),
      },
    },
    textConfig: {
      position: 'insideLeft',
      inside: true,
      outsideFill: 'transparent',
    },
    textContent: {
      type: 'text',
      // z2: 100,
      style: {
        textAlign: textDirection === 'ltr' ? 'left' : 'right',
        text,
        fill: '#63656e',
        width: width,
        overflow: 'truncate',
        ellipsis: '',
        truncateMinChar: 1,
      },
    },
  };
}
export function getGraphOptions(
  data: IProfilingGraphData[],
  {
    unit,
    filterKeyword,
    textDirection = 'ltr',
    highlightNode,
    isCompared = false,
  }: {
    unit: ProfileDataUnit;
    filterKeyword: string;
    textDirection: 'ltr' | 'rtl';
    highlightNode: IProfilingGraphData;
    isCompared: boolean;
  }
) {
  return {
    grid: {
      id: 'grid',
      show: false,
      left: 2,
      top: 2,
      bottom: 2,
      right: 2,
    },
    animation: false,
    tooltip: {
      padding: 0,
      backgroundColor: '#000',
      borderColor: '#000',
      appendToBody: false,
      trigger: 'item',
      axisPointer: {
        snap: false,
      },
      formatter: (params: any) => {
        const nodeItem: IFlameGraphDataItem = params.value?.[3];
        const { value, text } = parseProfileDataTypeValue(nodeItem.value, unit, true);
        const { name, diff_info, proportion } = nodeItem;
        let reference;
        let difference;
        let columnName = text;
        if (isCompared && diff_info) {
          const parseData = parseProfileDataTypeValue(diff_info.comparison, unit, true);
          reference = parseData.value;
          columnName = parseData.text;
          difference = diff_info.comparison === 0 || diff_info.mark === 'unchanged' ? 0 : diff_info.diff;
        }
        return `<div class="profiling-flame-graph-tips">
            <div class="funtion-name">${name}</div>
            <table class="tips-table">
              ${
                diff_info
                  ? `<thead>
                <th></th>
                <th>当前</th>
                <th>参照</th>
                <th>差异</th>
              </thead>`
                  : ''
              }
              <tbody>
                ${
                  !diff_info
                    ? `<tr>
                        <td>${window.i18n.t('占比')}</td>
                        <td>${proportion}</td>
                      </tr>
                      <tr>
                        <td>${columnName}</td>
                        <td>${value}</td>
                      </tr>`
                    : `<tr>
                      <td>${columnName}</td>
                      <td>${value}</td>
                      <td>${reference ?? '--'}</td>
                      <td>
                        ${
                          diff_info.mark === 'added'
                            ? `<span class='tips-added'>${diff_info.mark}</span>`
                            : `${(difference * 100).toFixed(2)}%`
                        }
                      </td>
                    </tr>`
                }
              </tbody>
            </table>
            <div class="tips-info">
              <span class="icon-monitor icon-mc-mouse tips-info-icon"></span>${window.i18n.t('鼠标右键有更多菜单')}
            </div>`;
      },
    },
    title: {
      show: false,
    },
    toolbox: false,
    hoverLayerThreshold: 1000 ** 5,
    xAxis: {
      show: false,
      max: data[0].value[2],
      position: 'top',
    },
    yAxis: {
      inverse: true,
      show: false,
      max: data.at(-1)?.level,
    },
    series: [
      {
        type: 'custom',
        renderItem: (api, params) =>
          renderItem(api, params, { data, unit, filterKeyword, textDirection, highlightNode }),
        encode: {
          x: [1, 2],
          y: 0,
        },
        data,
        animation: false,
      },
    ],
  };
}

/**
 *
 * @param base64Url
 * @param filename
 */
export function downloadBase64AsPng(base64Url: string, filename: string) {
  // 创建一个隐藏的<a>元素
  const link = document.createElement('a');

  // 将Base64 URL转换为Blob对象
  const byteString = atob(base64Url.split(',')[1]);
  const mimeString = base64Url.split(',')[0].split(':')[1].split(';')[0];

  const ab = new ArrayBuffer(byteString.length);
  const ia = new Uint8Array(ab);
  for (let i = 0; i < byteString.length; i++) {
    ia[i] = byteString.charCodeAt(i);
  }

  const blob = new Blob([ab], { type: mimeString });

  // 创建一个URL对象
  const url = URL.createObjectURL(blob);

  // 设置<a>的下载属性
  link.href = url;
  link.download = filename;

  // 触发点击事件下载文件
  document.body.appendChild(link); // 需要将元素添加到DOM中才能触发点击事件
  link.click();
  document.body.removeChild(link); // 下载完成后移除元素

  // 释放URL对象
  URL.revokeObjectURL(url);
}
