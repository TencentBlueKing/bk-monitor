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
/* eslint-disable no-param-reassign */
import Vue, { DirectiveBinding, VueConstructor } from 'vue';

import Skeleton, { ISkeletonCompData } from '../../monitor-pc/components/skeleton/skeleton-class';

const MonitorSkeleton = Vue.extend(Skeleton);
type SkeletonElement = Element & {
  instance: any;
  $vm: any;
  domInserted: boolean;
};
export default class SkeletonDirective {
  public static install(Vue: VueConstructor) {
    const toggleLoading = (el: SkeletonElement, options: any) => {
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
    Vue.directive('monitorSkeleton', {
      inserted(el: SkeletonElement, binding: DirectiveBinding<ISkeletonCompData>) {
        const data = Object.assign({}, binding.value);
        const instance = new MonitorSkeleton({
          data
        });
        // instance.options = data.options;
        (el as any).instance = instance;
        binding.value && toggleLoading(el, binding.value);
      },
      update(el: SkeletonElement, binding: DirectiveBinding<ISkeletonCompData>) {
        toggleLoading(el, binding.value);
      },
      unbind(el: SkeletonElement) {
        if (el.domInserted) {
          toggleLoading(el, { isLoading: false });
        }
        el.instance?.$destroy?.();
      }
    });
  }
}
