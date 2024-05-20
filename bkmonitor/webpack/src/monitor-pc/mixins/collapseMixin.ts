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
import { Component, Vue } from 'vue-property-decorator';

@Component
export default class collapseMixin extends Vue {
  public afterEnter(el) {
    el.classList.remove('collapse-transition');
    el.style.height = '';
    el.style.overflow = el.dataset.oldOverflow;
  }
  public afterLeave(el) {
    el.classList.remove('collapse-transition');
    el.style.height = '';
    el.style.overflow = el.dataset.oldOverflow;
  }

  public beforeEnter(el) {
    el.classList.add('collapse-transition');
    el.style.height = '0';
  }

  public beforeLeave(el) {
    el.dataset.oldOverflow = el.style.overflow;
    el.style.height = `${el.scrollHeight}px`;
    el.style.overflow = 'hidden';
  }

  public enter(el) {
    el.dataset.oldOverflow = el.style.overflow;
    if (el.scrollHeight !== 0) {
      el.style.height = `${el.scrollHeight}px`;
      setTimeout(() => {
        el.style.height = '';
      }, 300);
    } else {
      el.style.height = '';
    }
    el.style.overflow = 'hidden';
  }

  public leave(el) {
    if (el.scrollHeight !== 0) {
      el.classList.add('collapse-transition');
      el.style.height = 0;
    }
  }
}
