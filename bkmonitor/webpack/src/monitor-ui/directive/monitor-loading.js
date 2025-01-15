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

import Vue from 'vue';

import Loading from '../monitor-loading/monitor-loading.vue';

const MonitorLoading = Vue.extend(Loading);

const loadingDirective = {};
loadingDirective.install = Vue => {
  const toggleLoading = (el, options) => {
    if (!el.$vm) {
      el.$vm = el.instance.$mount();
      el.appendChild(el.$vm.$el);
    }
    if (options.isLoading) {
      Vue.nextTick(() => {
        el.$vm.visible = true;
      });
    } else {
      el.$vm.visible = false;
    }
    el.domInserted = true;
  };
  Vue.directive('monitorLoading', {
    inserted(el, binding) {
      const data = Object.assign({}, binding.value, { visible: false });
      const instance = new MonitorLoading({ data });
      el.instance = instance;
      binding.value && toggleLoading(el, binding.value);
    },

    update(el, binding) {
      toggleLoading(el, binding.value);
    },

    unbind(el) {
      if (el.domInserted) {
        el.mask?.parentNode?.removeChild?.(el.mask);
        toggleLoading(el, { isLoading: false });
      }
      el.instance?.$destroy?.();
    },
  });
};

export default loadingDirective;
