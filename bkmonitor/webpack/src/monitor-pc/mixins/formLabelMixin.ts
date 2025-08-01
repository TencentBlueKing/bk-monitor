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

interface IFormLabelConfig {
  el?: HTMLElement;
  labelClass?: string;
  safePadding?: number;
}

@Component
export default class formLabelMixin extends Vue {
  public maxFormLabelWidth = 120;

  public initFormLabelWidth(config: IFormLabelConfig = {}) {
    const { el = this.$el, safePadding = 0, labelClass = '.item-label' } = config;
    if (!el || this.$i18n.locale === 'zhCN') return;
    let max = 0;
    let maxTextLabelNode = null;
    const $labelEleList = el.querySelectorAll<HTMLElement>(labelClass);
    $labelEleList.forEach(item => {
      const text = item.innerText;
      if (text.length > max) {
        maxTextLabelNode = item;
      }
      max = Math.max(max, text.length);
    });
    if (!maxTextLabelNode) return;

    const cloneNode = maxTextLabelNode.cloneNode(true);
    const newNode = document.body.appendChild(cloneNode) as HTMLElement;
    newNode.style.cssText = 'display: inline-block; font-size: 14px; visibility: hidden;';
    let { width } = newNode.getBoundingClientRect();
    document.body.removeChild(newNode);

    if (width >= this.maxFormLabelWidth) {
      width = this.maxFormLabelWidth;
    }
    width = Math.ceil(width + safePadding);

    this.setFormLabelWidth($labelEleList, width);
    return width;
  }

  public setFormLabelWidth($labelEleList: NodeListOf<HTMLElement>, width) {
    $labelEleList.forEach(item => {
      item.style.width = `${width}px`;
      item.style.flexBasis = `${width}px`;
    });
  }
}
