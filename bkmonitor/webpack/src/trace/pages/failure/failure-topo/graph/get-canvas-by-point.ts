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

/**
 * @file combo → 画布坐标映射纯函数
 * @description 供 failure-topo 行为与 resource-graph 行为共用，无 Vue / composable 依赖。
 */

import type { CanvasByPointResult } from '../types/g6';
import type { Graph, ICombo } from '@antv/g6';

/**
 * 将 combo 的包围盒转换为画布坐标系下的左上 / 右下点
 * @param combo G6 combo item
 * @param graph 当前 Graph 实例
 * @returns CanvasByPointResult — combo 包围盒左上/右下在画布坐标系下的点
 */
export function getComboCanvasBounds(combo: ICombo, graph: Graph): CanvasByPointResult {
  const comboBBox = combo.getBBox();
  return {
    topLeft: graph.getCanvasByPoint(comboBBox.x, comboBBox.y),
    bottomRight: graph.getCanvasByPoint(comboBBox.x + comboBBox.width, comboBBox.y + comboBBox.height),
  };
}
