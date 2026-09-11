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
 * `@blueking/apm-vue3-for-vue2` 的入口，构建配置见 scripts/build.apm-vue3-for-vue2.ts。
 *
 * 面向 APM 的 Vue2 宿主：用 mount* 在指定节点挂载整块 Vue3 子应用，
 * 应用实例（router / pinia / i18n）由包内自行创建，宿主只需给一个挂载节点。
 * Vue3 工程请改用 `@blueking/monitor-vue3-components`（入口 components.ts），
 * 那边导出的是可直接渲染的组件。
 */
import { applyRuntimeClassPrefix } from './common/class-prefix';

import 'monitor-static/icons/monitor-icons.css';

applyRuntimeClassPrefix();

/** 告警中心：mountAlarmCenter 返回 { update, unmount } 句柄，宿主销毁时必须调用 unmount */
export { default as AlarmCenterApm, mount as mountAlarmCenter } from './pages/alarm-center/alarm-center-apm-entry';
export type { BridgeEmit, BridgeProps, MountHandle, MountOptions } from './pages/alarm-center/alarm-center-apm-entry';

/** Trace 检索：入参与句柄结构与告警中心一致 */
export { mount as mountTraceExplore, default as TraceExploreApm } from './pages/trace-explore/trace-explore-apm-entry';
