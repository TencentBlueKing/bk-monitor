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
 * `@blueking/monitor-vue3-components` 的入口，构建配置见 scripts/build.vue3.components.ts。
 *
 * 面向 Vue3 工程：直接使用这里导出的组件、组合式函数与工具函数。
 * Vue2 宿主要嵌入整块能力（告警中心 / Trace 检索）请改用 `@blueking/apm-vue3-for-vue2`
 * （入口 apm-vue3-for-vue2.ts）；两个包构建选项共用，但各自独立发布，所以这里不含那两块页面代码。
 *
 * 注意这里**不引入** trace 主站的 global.scss 与 monitor-pc 的 reset.scss：
 * 二者含 `#app`、`.tippy-*`、标签重置等全站级规则，随包发布会污染宿主页面。
 */
import { applyRuntimeClassPrefix } from './common/class-prefix';
import PromqlEditor from './components/promql-editor/promql-editor';
import RetrievalFilter from './components/retrieval-filter/retrieval-filter';

applyRuntimeClassPrefix();

/**
 * 本包内联了 vue-i18n，宿主自己那份 vue-i18n 的注入 key 与包内不是同一个副本，
 * 因此使用组件前必须 `app.use(i18n)` 装上这里导出的实例，
 * 否则组件内的 `useI18n()` 会抛「Need to install with app.use」。
 */
export { default as i18n } from './i18n/i18n';

export * from './pages/trace-explore/components/explore-chart/index';

import 'monitor-static/icons/monitor-icons.css';

export { PromqlEditor, RetrievalFilter };
