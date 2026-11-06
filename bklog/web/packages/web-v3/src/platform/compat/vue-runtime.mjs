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
import Vue, { getCurrentInstance } from '@vue/compat';
// Vue3 date-picker/icons use plain functional components. Interpreting them as
// Vue2 async factories invokes them without props and crashes the real picker.
Vue.configureCompat({
  COMPONENT_ASYNC: false,
  // 类组件仍走 Vue 2 行为；只消掉迁移期告警，不改运行时语义。
  GLOBAL_EXTEND: 'suppress-warning',
  GLOBAL_MOUNT: 'suppress-warning',
  GLOBAL_PROTOTYPE: 'suppress-warning',
  RENDER_FUNCTION: 'suppress-warning',
  OPTIONS_DATA_MERGE: 'suppress-warning',
  OPTIONS_BEFORE_DESTROY: 'suppress-warning',
  WATCH_ARRAY: 'suppress-warning',
  COMPONENT_V_MODEL: 'suppress-warning',
  ATTR_FALSE_VALUE: 'suppress-warning',
  ATTR_ENUMERATED_COERCION: 'suppress-warning',
  INSTANCE_ATTRS_CLASS_STYLE: 'suppress-warning',
});

// vue-class-component 7 在 data() 里 new 子类，并临时改写 prototype._init，
// 期望 Vue 2 构造函数调用 this._init()。compat 的 Vue() 会忽略 this，直接创建根应用，
// 随后 Object.keys(根实例) 触发 enumerating-keys，并在渲染过程中再挂一个应用。
function VueCtor(options) {
  const constructing = Boolean(new.target) || Boolean(this && this instanceof VueCtor);
  if (constructing && typeof this._init === 'function') {
    const init = this._init;
    // vue-class-component 收集 class 字段时会临时换成零参 _init，
    // 并在 Vue 3 实例上调用 hasOwnProperty。这里失败不能打断组件挂载，
    // 否则字段列表抛错会冻住同一轮父级更新，趋势图就停在 Loading。
    if (init.length === 0) {
      // 这段 _init 会执行 vm.hasOwnProperty。Vue 3 实例代理没有这个方法，
      // 调用会抛错；zone 会把它记成未捕获异常，并打断同一轮组件补丁。
      // 类字段在 super() 返回后写在哑实例上，collectDataFromConstructor 再抄走。
      const proxy = getCurrentInstance()?.proxy;
      if (!proxy || typeof proxy.hasOwnProperty !== 'function') {
        return this;
      }
      init.call(this);
      return this;
    }
    init.call(this, options);
    return this;
  }
  return Vue(options);
}
Object.setPrototypeOf(VueCtor, Vue);
VueCtor.prototype = Vue.prototype;

export * from '@vue/compat';
export default VueCtor;
export const set = Vue.set.bind(Vue);
export const del = Vue.delete.bind(Vue);
