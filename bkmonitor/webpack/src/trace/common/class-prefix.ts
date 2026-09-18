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

import { defaultRootConfig } from 'bkui-vue/lib/config-provider';

/**
 * bkui-vue 的运行时类名前缀（不含连字符）。
 *
 * 组件包构建时会把源码与 CSS 里的 `bk-` 类名整体改写到该前缀下，与宿主自带的 `.bk-*` 隔离；
 * bkui-vue 组件的类名是运行时拼出来的，改不到，因此需要在这里同步告诉它。
 *
 * **必须与 `scripts/build.vue3.components.ts` 里的 `CLASS_PREFIX` 保持一致。**
 * 只有组件包的入口链路会引用本模块，trace 主站不引用，仍用 bkui-vue 默认的 `bk` 前缀。
 */
export const RUNTIME_CLASS_PREFIX = 'bkmv3';

/**
 * 把 bkui-vue 的默认前缀改成 RUNTIME_CLASS_PREFIX，需在任何组件渲染前调用。
 * 组件被挂在宿主自己的 app 下时走不到 provideGlobalConfig，所以必须改默认配置；
 * 两个发布入口（vue3 / vue2）都要调用一次。
 */
export function applyRuntimeClassPrefix(): void {
  defaultRootConfig.prefix = RUNTIME_CLASS_PREFIX;
}
