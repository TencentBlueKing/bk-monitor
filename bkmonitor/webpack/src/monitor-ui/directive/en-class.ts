import type { VueConstructor } from 'vue';

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
import { docCookies, LANGUAGE_COOKIE_KEY } from 'monitor-common/utils';

import type { DirectiveBinding } from 'vue/types/options';

export default class EnStyleDirective {
  public static install(Vue: VueConstructor) {
    Vue.directive('enClass', {
      bind(el: HTMLDivElement, binding: DirectiveBinding) {
        if (
          (typeof binding.value === 'string' && el?.classList.contains(binding.value)) ||
          docCookies.getItem(LANGUAGE_COOKIE_KEY) !== 'en'
        ) {
          return;
        }
        if (typeof binding.value === 'string') {
          binding.value && el.classList.add(binding.value);
          return;
        }
        let options: {
          class: string;
          styles: Record<string, string>;
        } = { class: '', styles: {} };
        options = { ...options, ...binding.value };
        options.class && el.classList.add(options.class);
        let cssText = '';
        if (typeof options.styles === 'string') {
          cssText += options.styles;
        } else
          Object.keys(options.styles).forEach(key => {
            cssText += `${key}: ${options.styles[key]};`;
          });
        el.style.cssText += cssText;
      },
    });
  }
}
