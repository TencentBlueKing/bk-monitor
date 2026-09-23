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
 * @file Composable 公共类型
 * @description Graph / Tooltip 访问器与 emit 类型，供各 use-topo-* 共用，避免重复定义
 */

import type { TopoRawDataCache } from './g6';
import type { ITopoData, ITopoNode } from './topo';
import type { Graph } from '@antv/g6';

/** G6 Tooltip 插件可调用面（注册后实例至少具备 hide） */
export interface G6TooltipInstance {
  hide: () => void;
}

/** Graph 实例访问器（通过 shallowRef.value 读取，未初始化时为 undefined） */
export interface GraphAccess {
  getGraph: () => Graph | undefined;
}

/** renderGraph 前向引用回调（interaction 早于 graph 创建时使用） */
export interface RenderGraphAccess {
  renderGraphCallback: (data?: ITopoData | TopoRawDataCache['complete'], renderComplete?: boolean) => void;
}

/** G6 Tooltip 插件实例访问器（只读；写入直接赋 g6TooltipRef.value） */
export interface TooltipAccess {
  getTooltip: () => G6TooltipInstance | undefined;
}

/** FailureTopo 组件 emits 事件类型（与 defineComponent emits 保持一致） */
export type TopoEmitEvent = 'changeSelectNode' | 'closeCollapse' | 'playing' | 'refresh' | 'toDetail' | 'toDetailTab';

/** emit 函数签名（按事件收窄参数） */
export type TopoEmitFn = {
  (event: 'changeSelectNode', nodeId: string): void;
  (event: 'closeCollapse', value?: boolean): void;
  (event: 'playing', playing: boolean, index?: number): void;
  (event: 'refresh'): void;
  (event: 'toDetail', node: ITopoNode): void;
  (event: 'toDetailTab', alertObj: unknown): void;
};
