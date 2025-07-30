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
import { ref, shallowRef } from 'vue';
import type { Ref } from 'vue';

import dagre from '@dagrejs/dagre';
import { Position, useVueFlow } from '@vue-flow/core';
import { toJpeg as ElToJpg, toPng as ElToPng } from 'html-to-image';

import type { Options as HTMLToImageOptions } from 'html-to-image/es/types';

export type CaptureScreenshot = (el: HTMLElement, options?: UseScreenshotOptions) => Promise<string>;

export type Download = (fileName: string) => void;

export type ImageType = 'jpeg' | 'png';

export interface UseScreenshot {
  // returns the data url of the screenshot
  capture: CaptureScreenshot;
  dataUrl: Ref<string>;
  download: Download;
  error: Ref;
}

export interface UseScreenshotOptions extends HTMLToImageOptions {
  fetchRequestInit?: RequestInit;
  fileName?: string;
  shouldDownload?: boolean;
  type?: ImageType;
}

export function useLayout() {
  // @dagrejs/dagre 使用了window.toString 但是 因为 babel在 useBuiltIns = usage 时重写 window.toString方法导致报错
  // 这里需重新替换为真实的 window.toString 方法
  window.toString = window.__POWERED_BY_BK_WEWEB__ ? window.rawWindow.toString : window.toString;

  const { findNode } = useVueFlow();

  const graph = shallowRef(new dagre.graphlib.Graph());

  const previousDirection = ref('LR');

  function layout(nodes, edges, direction, ranksep?) {
    // we create a new graph instance, in case some nodes/edges were removed, otherwise dagre would act as if they were still there
    const dagreGraph = new dagre.graphlib.Graph();

    graph.value = dagreGraph;

    dagreGraph.setDefaultEdgeLabel(() => ({}));

    const isHorizontal = direction === 'LR';
    dagreGraph.setGraph({ rankdir: direction, ranksep: ranksep || 50, ranker: 'network-simplex' });

    previousDirection.value = direction;

    const nodeWHMap = new Map();

    let nodeMaxWidth = 0;

    for (const node of nodes) {
      // if you need width+height of nodes for your layout, you can use the dimensions property of the internal node (`GraphNode` type)
      const graphNode = findNode(node.id);

      const wh = {
        width: graphNode.dimensions.width || 150,
        height: graphNode.dimensions.height || 50,
      };

      if (nodeMaxWidth < wh.width) {
        nodeMaxWidth = wh.width;
      }

      dagreGraph.setNode(node.id, wh);
      nodeWHMap.set(node.id, wh);
    }

    for (const edge of edges) {
      dagreGraph.setEdge(edge.source, edge.target);
    }

    dagre.layout(dagreGraph);

    // 找出所有相互调用的情况
    const loopEdgeSet = new Set();
    edges.forEach((edge, edgeIndex) => {
      edges.forEach((edge_, edgeIndex_) => {
        if (edgeIndex !== edgeIndex_ && edge.source === edge_.target && edge.target === edge_.source) {
          loopEdgeSet.add(edge.source);
        }
      });
    });

    // set nodes with updated positions
    const result = nodes.map(node => {
      const nodeWithPosition = dagreGraph.node(node.id);
      return {
        ...node,
        targetPosition: isHorizontal ? Position.Left : Position.Top,
        sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
        position: { x: nodeWithPosition.x, y: nodeWithPosition.y },
      };
    });
    for (const node of result) {
      const w = nodeWHMap.get(node.id).width;
      if (w < nodeMaxWidth) {
        node.position.x += (nodeMaxWidth - w) / 2;
      }
      // 处理环状图 a -> b b -> a 的节点位置
      if (
        loopEdgeSet.has(node.id) &&
        edges.filter(e => e.target === node.id && !loopEdgeSet.has(e.source)).length === 0 &&
        w < nodeMaxWidth
      ) {
        node.position.x += 20;
      }
    }
    return result;
  }

  return { graph, layout, previousDirection };
}

export function useScreenshot(): UseScreenshot {
  const dataUrl = ref<string>('');
  const imgType = ref<ImageType>('png');
  const error = ref();

  async function capture(el: HTMLElement, options: UseScreenshotOptions = {}) {
    let data = null;

    const fileName = options.fileName ?? `vue-flow-screenshot-${Date.now()}`;

    switch (options.type) {
      case 'jpeg':
        data = await toJpeg(el, options);
        break;
      case 'png':
        data = await toPng(el, options);
        break;
      default:
        data = await toPng(el, options);
        break;
    }

    // immediately download the image if shouldDownload is true
    if (options.shouldDownload && fileName !== '') {
      download(fileName);
    }

    return data;
  }

  function toJpeg(el: HTMLElement, options: HTMLToImageOptions = { quality: 0.95 }) {
    error.value = null;

    return ElToJpg(el, options)
      .then(data => {
        dataUrl.value = data;
        imgType.value = 'jpeg';
        return data;
      })
      .catch(error => {
        error.value = error;
        throw new Error(error);
      });
  }

  function toPng(el: HTMLElement, options: HTMLToImageOptions = { quality: 0.95 }) {
    error.value = null;

    return ElToPng(el, options)
      .then(data => {
        dataUrl.value = data;
        imgType.value = 'png';
        return data;
      })
      .catch(error => {
        error.value = error;
        throw new Error(error);
      });
  }

  function download(fileName: string) {
    const link = document.createElement('a');
    link.download = `${fileName}.${imgType.value}`;
    link.href = dataUrl.value;
    link.click();
  }

  return {
    capture,
    download,
    dataUrl,
    error,
  };
}
