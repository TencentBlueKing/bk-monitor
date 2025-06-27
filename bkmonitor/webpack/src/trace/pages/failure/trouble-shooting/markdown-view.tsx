/*
 * @Author: EmilyMei 447693773@qq.com
 * @Date: 2025-06-26 11:16:08
 * @LastEditors: EmilyMei 447693773@qq.com
 * @LastEditTime: 2025-06-26 11:50:45
 * @FilePath: /webpack/src/trace/pages/failure/trouble-shooting/markdown-view.tsx
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
 */
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
import { defineComponent, computed } from 'vue';

import MarkdownIt from 'markdown-it';

import './markdown-view.scss';

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
});

export default defineComponent({
  name: 'MarkdownView',
  props: {
    content: {
      type: String,
      default: '',
    },
  },
  setup(props, { emit }) {
    const htmlContent = computed(() => {
      return md.render(props.content);
    });
    return {
      htmlContent,
    };
  },

  render() {
    return (
      <div
        class='markdown-view-box'
        innerHTML={this.htmlContent}
      />
    );
  },
});
