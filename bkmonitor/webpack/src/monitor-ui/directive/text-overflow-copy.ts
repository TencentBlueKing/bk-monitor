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
import { VueConstructor } from 'vue';
import { DirectiveBinding } from 'vue/types/options';

import { copyText } from '../../monitor-common/utils/utils';

export default class TextOverflowCopyDirective {
  public static install(Vue: VueConstructor) {
    Vue.directive('textOverflowCopy', {
      componentUpdated(el: HTMLDivElement, binding: DirectiveBinding) {
        const eleWidth = el.clientWidth;
        const contentWidth = el.scrollWidth;
        if (contentWidth > eleWidth) {
          el.classList.add(binding.value);
          const copyBtn = document.createElement('span');
          copyBtn.className = 'icon-monitor icon-mc-copy';
          copyBtn.style.position = 'absolute';
          copyBtn.style.right = '0';
          copyBtn.style.top = '50%';
          copyBtn.style.transform = 'translateY(-50%)';
          copyBtn.style.cursor = 'pointer';
          el.addEventListener('click', () => {
            copyText(el.innerText, msg => {
              Vue.prototype.$bkMessage({
                message: msg,
                theme: 'error'
              });
              return;
            });
            Vue.prototype.$bkMessage({
              message: window.i18n.tc('复制成功'),
              theme: 'success'
            });
          });
          el.appendChild(copyBtn);
        }
      }
    });
  }
}
