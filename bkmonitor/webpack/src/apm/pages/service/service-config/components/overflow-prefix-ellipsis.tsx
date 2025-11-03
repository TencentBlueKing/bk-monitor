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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './overflow-prefix-ellipsis.scss';

interface OverflowPrefixEllipsisProps {
  text: string;
}

@Component
export default class OverflowPrefixEllipsis extends tsc<OverflowPrefixEllipsisProps> {
  @Prop({ default: '' }) text: string;

  @Ref('text') textRef: HTMLSpanElement;

  isOverflow = false;

  @Watch('text')
  onTextChange() {
    this.$nextTick(() => {
      this.adjustText();
    });
  }

  adjustText() {
    const containerWidth = (this.$el as HTMLDivElement).offsetWidth; // 获取容器宽度
    const textWidth = this.textRef.offsetWidth; // 获取文本实际宽度
    // 如果文本超出容器宽度
    if (textWidth > containerWidth) {
      let visibleText = this.text;
      this.isOverflow = true;

      // 从文本的末尾开始截断
      while (this.textRef.offsetWidth > containerWidth) {
        visibleText = visibleText.slice(1); // 删除第一个字符
        this.textRef.innerText = `...${visibleText}`; // 在前面添加省略号
      }
    }
  }

  mounted() {
    this.adjustText();
  }

  render() {
    return (
      <div class='overflow-prefix-ellipsis'>
        <span
          ref='text'
          class='overflow-prefix-ellipsis-text'
          v-bk-tooltips={{ content: this.text, disabled: !this.isOverflow, placements: ['top'] }}
        >
          {this.text}
        </span>
      </div>
    );
  }
}
