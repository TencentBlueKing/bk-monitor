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

// Migration test runtime only: Vue2.7 libraries import these legacy named APIs.
import Vue from '@vue/compat';
// Vue3 date-picker/icons use plain functional components. Interpreting them as
// Vue2 async factories invokes them without props and crashes the real picker.
Vue.configureCompat({ COMPONENT_ASYNC: false });
// bk-magic table invokes a custom header with Vue2's render proxy as `this`.
// This bridge is restricted to the migration runtime; native Vue3 must replace
// the library's private-instance dependency when upgrading the table adapter.
Vue.mixin({
  beforeCreate() {
    Object.defineProperty(this.$.ctx, '_renderProxy', {
      configurable: true,
      get: () => this,
    });
  },
});
export * from '@vue/compat';
export default Vue;
export const set = Vue.set.bind(Vue);
export const del = Vue.delete.bind(Vue);
