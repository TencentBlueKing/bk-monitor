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
import i18n from '../../i18n/i18n';
import { createApp, reactive } from 'vue';

import { Message, provideGlobalConfig } from 'bkui-vue';
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
import Api from 'monitor-api/api';
import { userDisplayNameConfigure } from 'monitor-pc/common/user-display-name';
import { createPinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';

import { RUNTIME_CLASS_PREFIX } from '../../common/class-prefix';
import directives from '../../directive/index';
import TraceSliderApm, { BRIDGE_EMIT_KEY, BRIDGE_PROPS_KEY } from './trace-slider-apm';

import '@blueking/tdesign-ui/vue3/index.css';

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

export default TraceSliderApm;

export type BridgeEmit = (event: string, ...args: unknown[]) => void;

export interface BridgeProps {
  [key: string]: unknown;
}

export interface MountHandle {
  unmount: () => void;
  update: (newProps: Partial<BridgeProps>) => void;
}

export interface MountOptions {
  onEvent?: BridgeEmit;
  props?: BridgeProps;
}

/**
 * 将 Vue3 Trace 详情侧滑挂到指定节点。独立 Pinia，不污染宿主。
 */
export function mount(el: HTMLElement | string, options?: MountOptions): MountHandle {
  userDisplayNameConfigure();

  const bridgeProps = reactive<BridgeProps>({ ...options?.props });
  const bridgeEmit: BridgeEmit = (event, ...args) => options?.onEvent?.(event, ...args);

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { render: () => null } }],
  });

  const app = createApp(TraceSliderApm);
  app.config.compilerOptions = {
    ...app.config.compilerOptions,
    isCustomElement: tag => tag === 'bk-user-display-name',
  };

  provideGlobalConfig({ prefix: RUNTIME_CLASS_PREFIX }, app);

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
