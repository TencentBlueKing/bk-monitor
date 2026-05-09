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
/**
 * trace-explore-apm-entry.ts —— Vue 3 Trace 检索子应用入口
 *
 * 本模块作为 Vue 3 Trace 检索（TraceExploreApm → TraceExplore）的独立构建入口，供 Vue 2 宿主应用
 * （TraceExploreContainer）通过 dynamic import 加载并挂载。
 *
 * 设计背景：
 *   宿主应用基于 Vue 2，而 Trace 检索基于 Vue 3 开发。两者运行时完全隔离，
 *   因此需要一套"桥接"机制在两端传递数据和事件。
 *
 * 桥接机制概述：
 *   1. Props（Vue 2 → Vue 3）：
 *      - 宿主调用 mount(el, { props: {...} }) 传入初始属性
 *      - 内部用 reactive() 包装后通过 app.provide() 注入整棵 Vue 3 组件树
 *      - 宿主后续调用 handle.update({ key: newValue }) 即可推送变更，
 *        Vue 3 侧因 reactive 代理会自动触发响应式更新
 *
 *   2. Events（Vue 3 → Vue 2）：
 *      - 宿主通过 mount(el, { onEvent: (event, ...args) => {...} }) 注册回调
 *      - 内部将回调包装为 bridgeEmit 函数，通过 app.provide() 注入
 *      - Vue 3 子组件 inject(BRIDGE_EMIT_KEY) 后调用即可向宿主抛出事件
 */
import { createApp, reactive } from 'vue';

import Api from 'monitor-api/api';
import { userDisplayNameConfigure } from 'monitor-pc/common/user-display-name';
import { Message, provideGlobalConfig } from 'bkui-vue';
import { defaultRootConfig } from 'bkui-vue/lib/config-provider';
import {
  BarChart,
  CustomChart,
  HeatmapChart,
  LineChart,
  MapChart,
  PieChart,
  ScatterChart,
  TreemapChart,
} from 'echarts/charts';
import {
  BrushComponent,
  DataZoomComponent,
  DataZoomInsideComponent,
  DataZoomSliderComponent,
  GeoComponent,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { createPinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';

import directives from '../../directive/index';
import i18n from '../../i18n/i18n';
import TraceExploreApm, { BRIDGE_EMIT_KEY, BRIDGE_PROPS_KEY } from './trace-explore-apm';

import '@blueking/tdesign-ui/vue3/index.css';

defaultRootConfig.prefix = 'apm-bk';

use([
  BarChart,
  PieChart,
  LineChart,
  TreemapChart,
  ScatterChart,
  MapChart,
  HeatmapChart,
  CustomChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  CanvasRenderer,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  GraphicComponent,
  GeoComponent,
  VisualMapComponent,
  BrushComponent,
  DataZoomComponent,
  DataZoomInsideComponent,
  DataZoomSliderComponent,
]);

export default TraceExploreApm;

/* ==================== 桥接类型定义 ==================== */

/** 从 Vue 2 宿主传入的属性字典，内部以 reactive() 包装保持响应式 */
export interface BridgeProps {
  [key: string]: unknown;
}

/** 向 Vue 2 宿主抛出事件的函数签名 */
export type BridgeEmit = (event: string, ...args: unknown[]) => void;

// export { BRIDGE_PROPS_KEY, BRIDGE_EMIT_KEY };

/** mount() 的可选配置项 */
export interface MountOptions {
  /** 传递给 Vue 3 子应用的初始属性，后续可通过 handle.update() 增量更新 */
  props?: BridgeProps;
  /** 事件回调：Vue 3 子组件调用 bridgeEmit(event, ...args) 时触发 */
  onEvent?: BridgeEmit;
}

/** mount() 返回的控制句柄 */
export interface MountHandle {
  /** 卸载 Vue 3 子应用（需在宿主组件 beforeDestroy 中调用以防止内存泄漏） */
  unmount: () => void;
  /** 增量更新桥接属性，会合并到已有的 reactive 对象上，自动触发 Vue 3 响应式更新 */
  update: (newProps: Partial<BridgeProps>) => void;
}

/* ==================== 挂载入口 ==================== */

/**
 * 将 Vue 3 Trace 检索子应用挂载到指定 DOM 节点。
 *
 * @param el       - 挂载目标，可以是 CSS 选择器字符串或 HTMLElement
 * @param options  - 桥接配置：初始属性 & 事件回调
 * @returns 冻结的 MountHandle，包含 unmount / update 方法
 */
export function mount(el: string | HTMLElement, options?: MountOptions): MountHandle {
  /** 注册 bk-user-display-name 自定义元素并同步 API 配置；与 trace 主站、APM 入口一致，避免 Vue 当作未解析组件。 */
  userDisplayNameConfigure();

  const bridgeProps = reactive<BridgeProps>({ ...options?.props });
  const bridgeEmit: BridgeEmit = (event, ...args) => options?.onEvent?.(event, ...args);

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { render: () => null } }],
  });

  const app = createApp(TraceExploreApm);
  app.config.compilerOptions = {
    ...app.config.compilerOptions,
    isCustomElement: tag => tag === 'bk-user-display-name',
  };

  provideGlobalConfig({ prefix: 'apm-bk' }, app);

  app.provide(BRIDGE_PROPS_KEY, bridgeProps);
  app.provide(BRIDGE_EMIT_KEY, bridgeEmit);

  app.use(i18n);
  app.use(createPinia());
  app.use(router);
  app.use(directives);
  app.config.globalProperties.$api = Api;
  app.config.globalProperties.$Message = Message;

  app.mount(el);

  return Object.freeze({
    unmount: () => app.unmount(),
    update: (newProps: Partial<BridgeProps>) => Object.assign(bridgeProps, newProps),
  });
}
